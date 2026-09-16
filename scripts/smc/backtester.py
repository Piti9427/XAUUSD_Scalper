from dataclasses import dataclass, field, replace
from datetime import datetime, timezone, date
from typing import List, Dict, Any, Optional
import pandas as pd
from scripts.smc.types import (
    Direction,
    OrderIntentType,
    AccountState,
    Position,
    SetupSignal,
    LiquidityLevels,
)
from scripts.smc.liquidity import compute_liquidity_levels
from scripts.smc.detection import detect_smc_setup
from scripts.smc.orchestrator import StrategyOrchestrator


@dataclass
class BacktestSummary:
    initial_balance: float
    final_balance: float
    net_profit: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    be_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    avg_r: float
    trades_df: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())


class _RecordingOrchestrator(StrategyOrchestrator):
    """Capture the actual lifecycle evaluation, including fill-and-close bars."""

    evaluated_before = None
    evaluated_after = None

    def _evaluate_open_position(self, account, bar, bar_time):
        position = account.open_position
        self.evaluated_before = replace(position)
        intents = super()._evaluate_open_position(account, bar, bar_time)
        self.evaluated_after = replace(position)
        return intents


class SMCBacktester:
    """
    Offline Backtester for SMC Strategy v1.
    Walks historical M5 + H1 data bar-by-bar and simulates execution through the StrategyOrchestrator.
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        risk_pct: float = 0.005,
        spread_buffer: float = 0.30,
        max_sl_cap: float = 6.00,
        contract_size: float = 100.0,
        partial_tp_enabled: bool = False,
        partial_tp_r: float = 1.2,
        partial_tp_ratio: float = 0.5,
        be_trigger_r: float = 1.0,
        extended_killzones: bool = True,
        tp_r: float = 2.0,
        min_body_ratio: float = 0.50,
        max_sweep_pierce: float = 5.0,
        sweep_lookback: int = 20,
        max_sweep_to_mss_bars: int = 6,
        max_mss_to_fvg_bars: int = 3,
        require_choch: bool = False,
    ):
        self.initial_balance = initial_balance
        self.risk_pct = risk_pct
        self.spread_buffer = spread_buffer
        self.max_sl_cap = max_sl_cap
        self.contract_size = contract_size
        self.partial_tp_enabled = partial_tp_enabled
        self.partial_tp_r = partial_tp_r
        self.partial_tp_ratio = partial_tp_ratio
        self.be_trigger_r = be_trigger_r
        self.extended_killzones = extended_killzones
        self.tp_r = tp_r
        self.min_body_ratio = min_body_ratio
        self.max_sweep_pierce = max_sweep_pierce
        self.sweep_lookback = sweep_lookback
        self.max_sweep_to_mss_bars = max_sweep_to_mss_bars
        self.max_mss_to_fvg_bars = max_mss_to_fvg_bars
        self.require_choch = require_choch

    def run(self, df_m5: pd.DataFrame, df_h1: pd.DataFrame) -> BacktestSummary:
        m5 = df_m5.copy()
        if not pd.api.types.is_datetime64_any_dtype(m5["time"]):
            m5["time"] = pd.to_datetime(m5["time"], utc=True)
        elif m5["time"].dt.tz is None:
            m5["time"] = m5["time"].dt.tz_localize("UTC")
        else:
            m5["time"] = m5["time"].dt.tz_convert("UTC")

        m5 = m5.sort_values("time").reset_index(drop=True)

        h1 = df_h1.copy()
        if not pd.api.types.is_datetime64_any_dtype(h1["time"]):
            h1["time"] = pd.to_datetime(h1["time"], utc=True)
        elif h1["time"].dt.tz is None:
            h1["time"] = h1["time"].dt.tz_localize("UTC")
        else:
            h1["time"] = h1["time"].dt.tz_convert("UTC")

        h1 = h1.sort_values("time").reset_index(drop=True)

        # Performance Optimization: Precompute H1 EMA 200 once (O(N))
        h1["ema200"] = h1["close"].ewm(span=200, adjust=False).mean()
        h1_times = h1["time"].values

        # Performance Optimization: Precompute M5 5-bar fractals once (O(N))
        from scripts.smc.structure import find_fractals_5bar
        from scripts.smc.detection import is_in_session
        import numpy as np

        all_sh, all_sl = find_fractals_5bar(m5)

        m5_times = m5["time"].tolist()
        m5_opens = m5["open"].to_numpy(dtype=float)
        m5_highs = m5["high"].to_numpy(dtype=float)
        m5_lows = m5["low"].to_numpy(dtype=float)
        m5_closes = m5["close"].to_numpy(dtype=float)

        account = AccountState(
            balance=self.initial_balance,
            equity=self.initial_balance,
        )
        orchestrator = _RecordingOrchestrator(
            max_sl_cap=self.max_sl_cap,
            partial_tp_enabled=self.partial_tp_enabled,
            partial_tp_r=self.partial_tp_r,
            partial_tp_ratio=self.partial_tp_ratio,
            be_trigger_r=self.be_trigger_r,
            spread_buffer=self.spread_buffer,
            be_buffer=0.10,
        )

        trades: List[Dict[str, Any]] = []
        active_trade_log: Optional[Dict[str, Any]] = None
        liquidity_cache: Dict[str, Optional[LiquidityLevels]] = {}

        peak_equity = self.initial_balance
        max_drawdown = 0.0

        for i in range(15, len(m5)):
            bar_time: datetime = m5_times[i]
            current_bar = {
                "time": bar_time,
                "open": m5_opens[i],
                "high": m5_highs[i],
                "low": m5_lows[i],
                "close": m5_closes[i],
            }
            bar_date = bar_time.date()
            bar_date_str = bar_date.isoformat()

            # Cache liquidity levels per day
            if bar_date_str not in liquidity_cache:
                liquidity_cache[bar_date_str] = compute_liquidity_levels(m5, bar_date)
            current_liquidity = liquidity_cache[bar_date_str]

            # Fast binary search slice for H1 (O(log H) instead of O(H) linear scan)
            target_ts = (pd.Timestamp(bar_time) - pd.Timedelta(hours=1)).to_datetime64()
            h1_idx = int(np.searchsorted(h1_times, target_ts, side="right"))

            # Evaluate detection only if no active position and no pending order and in session
            setup_signal = None
            if account.open_position is None and account.pending_order is None:
                if is_in_session(bar_time, extended=self.extended_killzones):
                    sub_h1 = h1.iloc[:h1_idx]
                    sub_m5 = m5.iloc[: i + 1]
                    setup_signal = detect_smc_setup(
                        sub_h1,
                        sub_m5,
                        current_liquidity,
                        bar_time,
                        spread_buffer=self.spread_buffer,
                        max_sl_cap=self.max_sl_cap,
                        precomputed_swings=(all_sh[: i - 1] + [False, False],
                                            all_sl[: i - 1] + [False, False]),
                        extended_killzones=self.extended_killzones,
                        tp_r=self.tp_r,
                        min_body_ratio=self.min_body_ratio,
                        max_sweep_pierce=self.max_sweep_pierce,
                        sweep_lookback=self.sweep_lookback,
                        max_sweep_to_mss_bars=self.max_sweep_to_mss_bars,
                        max_mss_to_fvg_bars=self.max_mss_to_fvg_bars,
                        require_choch=self.require_choch,
                    )

            # Observe the same lifecycle used by the orchestrator; do not infer fills
            # solely from the position remaining open at the end of a candle.
            orchestrator.evaluated_before = None
            orchestrator.evaluated_after = None
            intents = orchestrator.on_bar(current_bar, account, setup_signal)
            before = orchestrator.evaluated_before
            after = orchestrator.evaluated_after
            if before is None:
                continue

            if active_trade_log is None:
                active_trade_log = {
                    "entry_time": before.open_time,
                    "direction": before.direction.value,
                    "entry_price": before.entry_price,
                    "sl_price": before.sl_price,
                    "tp_price": before.tp_price,
                    "lot_size": before.lot_size,
                    "initial_sl_dist": before.initial_sl_distance,
                    "partial_pnl": 0.0,
                }

            sign = 1 if before.direction == Direction.BUY else -1
            for intent in intents:
                if intent.intent_type == OrderIntentType.PARTIAL_CLOSE:
                    partial_cash = (before.initial_sl_distance * self.partial_tp_r
                                    * intent.lot_size * self.contract_size)
                    account.balance += partial_cash
                    active_trade_log["partial_pnl"] += partial_cash

            if account.open_position is None:
                ambiguous = any(
                    x.intent_type == OrderIntentType.CLOSE_MARKET and "AMBIGUOUS" in x.reason
                    for x in intents
                )
                rollover = any(
                    x.intent_type == OrderIntentType.CLOSE_MARKET and "AMBIGUOUS" not in x.reason
                    for x in intents
                )
                stop_hit = (float(current_bar["low"]) <= before.sl_price
                            if sign == 1 else float(current_bar["high"]) >= before.sl_price)
                if ambiguous:
                    # Do not invent SL or TP cash path; keep both touches visible.
                    exit_price, exit_reason = None, "AMBIGUOUS"
                    remaining_cash = 0.0
                    total_cash = None
                    pnl_r = None
                elif rollover:
                    exit_price, exit_reason = float(current_bar["close"]), "ROLLOVER_FLAT"
                    remaining_cash = sign * (exit_price - before.entry_price) * after.lot_size * self.contract_size
                    account.balance += remaining_cash
                    total_cash = remaining_cash + active_trade_log["partial_pnl"]
                    initial_risk = (active_trade_log["initial_sl_dist"]
                                    * active_trade_log["lot_size"] * self.contract_size)
                    pnl_r = round(total_cash / initial_risk, 4) if initial_risk else 0.0
                elif stop_hit:
                    exit_price = before.sl_price
                    exit_reason = "BE" if before.be_moved else "SL"
                    remaining_cash = sign * (exit_price - before.entry_price) * after.lot_size * self.contract_size
                    account.balance += remaining_cash
                    total_cash = remaining_cash + active_trade_log["partial_pnl"]
                    initial_risk = (active_trade_log["initial_sl_dist"]
                                    * active_trade_log["lot_size"] * self.contract_size)
                    pnl_r = round(total_cash / initial_risk, 4) if initial_risk else 0.0
                else:
                    exit_price, exit_reason = before.tp_price, "TP"
                    remaining_cash = sign * (exit_price - before.entry_price) * after.lot_size * self.contract_size
                    account.balance += remaining_cash
                    total_cash = remaining_cash + active_trade_log["partial_pnl"]
                    initial_risk = (active_trade_log["initial_sl_dist"]
                                    * active_trade_log["lot_size"] * self.contract_size)
                    pnl_r = round(total_cash / initial_risk, 4) if initial_risk else 0.0
                active_trade_log.update({
                    "exit_time": bar_time,
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "sl_touched": (
                        float(current_bar["low"]) <= before.sl_price
                        if sign == 1 else float(current_bar["high"]) >= before.sl_price
                    ),
                    "tp_touched": (
                        float(current_bar["high"]) >= before.tp_price
                        if sign == 1
                        else (float(current_bar["low"]) + self.spread_buffer) <= before.tp_price
                    ),
                    "pnl_dollar": None if total_cash is None else round(total_cash, 2),
                    "pnl_r": pnl_r,
                    "balance": round(account.balance, 2),
                })
                trades.append(active_trade_log)
                active_trade_log = None

            account.equity = account.balance
            peak_equity = max(peak_equity, account.balance)
            max_drawdown = max(max_drawdown, (peak_equity - account.balance) / peak_equity * 100.0)

        # Build Summary — AMBIGUOUS exits stay in the ledger but are excluded from expectancy.
        trades_df = pd.DataFrame(trades)
        total_trades = len(trades)
        scored = [t for t in trades if t.get("exit_reason") != "AMBIGUOUS" and t.get("pnl_r") is not None]
        winning_trades = len([t for t in scored if t["pnl_r"] > 0])
        losing_trades = len([t for t in scored if t["pnl_r"] < 0])
        be_trades = len([t for t in scored if t["pnl_r"] == 0])

        scored_n = len(scored)
        win_rate = (winning_trades / scored_n * 100.0) if scored_n > 0 else 0.0
        gross_profit = sum(t["pnl_dollar"] for t in scored if t["pnl_dollar"] is not None and t["pnl_dollar"] > 0)
        gross_loss = abs(sum(t["pnl_dollar"] for t in scored if t["pnl_dollar"] is not None and t["pnl_dollar"] < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 1.0)
        avg_r = (sum(t["pnl_r"] for t in scored) / scored_n) if scored_n > 0 else 0.0

        return BacktestSummary(
            initial_balance=self.initial_balance,
            final_balance=round(account.balance, 2),
            net_profit=round(account.balance - self.initial_balance, 2),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            be_trades=be_trades,
            win_rate=round(win_rate, 2),
            profit_factor=round(profit_factor, 2),
            max_drawdown_pct=round(max_drawdown, 2),
            avg_r=round(avg_r, 2),
            trades_df=trades_df,
        )


def format_backtest_summary(summary: BacktestSummary) -> str:
    """Formats BacktestSummary into a clean Markdown table."""
    return f"""
# SMC Trading System v1 — Backtest Results
| Metric | Value |
| :--- | :--- |
| **Initial Balance** | ${summary.initial_balance:,.2f} |
| **Final Balance** | ${summary.final_balance:,.2f} |
| **Net Profit** | ${summary.net_profit:,.2f} ({(summary.net_profit / summary.initial_balance * 100):.2f}%) |
| **Total Trades** | {summary.total_trades} |
| **Winning Trades** | {summary.winning_trades} |
| **Losing Trades** | {summary.losing_trades} |
| **Breakeven Trades** | {summary.be_trades} |
| **Win Rate** | {summary.win_rate:.2f}% |
| **Profit Factor** | {summary.profit_factor:.2f} |
| **Max Drawdown** | {summary.max_drawdown_pct:.2f}% |
| **Average R** | {summary.avg_r:.2f}R |
"""

