from dataclasses import dataclass, field
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
    ):
        self.initial_balance = initial_balance
        self.risk_pct = risk_pct
        self.spread_buffer = spread_buffer
        self.max_sl_cap = max_sl_cap
        self.contract_size = contract_size

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
        all_sh, all_sl = find_fractals_5bar(m5)

        account = AccountState(
            balance=self.initial_balance,
            equity=self.initial_balance,
        )
        orchestrator = StrategyOrchestrator()

        trades: List[Dict[str, Any]] = []
        active_trade_log: Optional[Dict[str, Any]] = None
        liquidity_cache: Dict[str, Optional[LiquidityLevels]] = {}

        peak_equity = self.initial_balance
        max_drawdown = 0.0

        for i in range(15, len(m5)):
            current_bar = m5.iloc[i].to_dict()
            bar_time: datetime = current_bar["time"]
            bar_date = bar_time.date()
            bar_date_str = bar_date.isoformat()

            # Cache liquidity levels per day
            if bar_date_str not in liquidity_cache:
                liquidity_cache[bar_date_str] = compute_liquidity_levels(m5, bar_date)
            current_liquidity = liquidity_cache[bar_date_str]

            # Fast binary search slice for H1 (O(log H) instead of O(H) linear scan)
            import numpy as np
            target_ts = pd.Timestamp(bar_time).to_datetime64()
            h1_idx = int(np.searchsorted(h1_times, target_ts, side="right"))
            sub_h1 = h1.iloc[:h1_idx]
            sub_m5 = m5.iloc[: i + 1]

            # Track whether position was open before on_bar
            had_position = account.open_position is not None
            prev_pos: Optional[Position] = None
            if had_position:
                # Copy position details
                p = account.open_position
                prev_pos = Position(
                    direction=p.direction,
                    entry_price=p.entry_price,
                    sl_price=p.sl_price,
                    tp_price=p.tp_price,
                    lot_size=p.lot_size,
                    open_time=p.open_time,
                    initial_sl_distance=p.initial_sl_distance,
                    be_moved=p.be_moved,
                )

            # Evaluate detection only if no active position and no pending order
            setup_signal = None
            if account.open_position is None and account.pending_order is None:
                setup_signal = detect_smc_setup(
                    sub_h1,
                    sub_m5,
                    current_liquidity,
                    bar_time,
                    spread_buffer=self.spread_buffer,
                    max_sl_cap=self.max_sl_cap,
                    precomputed_swings=(all_sh[: i + 1], all_sl[: i + 1]),
                )

            # Step orchestrator
            intents = orchestrator.on_bar(current_bar, account, setup_signal)

            # Check if a position was just opened
            if not had_position and account.open_position is not None:
                new_p = account.open_position
                active_trade_log = {
                    "entry_time": new_p.open_time,
                    "direction": new_p.direction.value,
                    "entry_price": new_p.entry_price,
                    "sl_price": new_p.sl_price,
                    "tp_price": new_p.tp_price,
                    "lot_size": new_p.lot_size,
                    "initial_sl_dist": new_p.initial_sl_distance,
                }

            # Check if position was closed during this bar
            if had_position and account.open_position is None and prev_pos is not None:
                exit_price = prev_pos.entry_price
                exit_reason = "CLOSED"
                pnl_r = 0.0

                if prev_pos.direction == Direction.BUY:
                    if float(current_bar["high"]) >= prev_pos.tp_price:
                        exit_price = prev_pos.tp_price
                        exit_reason = "TP"
                        pnl_r = 2.0
                    elif float(current_bar["low"]) <= prev_pos.sl_price:
                        exit_price = prev_pos.sl_price
                        if prev_pos.be_moved:
                            exit_reason = "BE"
                            pnl_r = 0.0
                        else:
                            exit_reason = "SL"
                            pnl_r = -1.0
                else:  # SELL
                    if float(current_bar["low"]) <= prev_pos.tp_price:
                        exit_price = prev_pos.tp_price
                        exit_reason = "TP"
                        pnl_r = 2.0
                    elif float(current_bar["high"]) >= prev_pos.sl_price:
                        exit_price = prev_pos.sl_price
                        if prev_pos.be_moved:
                            exit_reason = "BE"
                            pnl_r = 0.0
                        else:
                            exit_reason = "SL"
                            pnl_r = -1.0

                # Check rollover close
                for intent in intents:
                    if intent.intent_type == OrderIntentType.CLOSE_MARKET:
                        exit_price = float(current_bar["close"])
                        exit_reason = "ROLLOVER_FLAT"
                        if prev_pos.direction == Direction.BUY:
                            pnl_r = (exit_price - prev_pos.entry_price) / prev_pos.initial_sl_distance
                        else:
                            pnl_r = (prev_pos.entry_price - exit_price) / prev_pos.initial_sl_distance

                # Calculate PnL Dollar
                pnl_dollar = pnl_r * (account.balance * self.risk_pct)
                account.balance += pnl_dollar
                account.equity = account.balance

                if account.balance > peak_equity:
                    peak_equity = account.balance
                dd = (peak_equity - account.balance) / peak_equity * 100.0
                if dd > max_drawdown:
                    max_drawdown = dd

                if active_trade_log is not None:
                    active_trade_log.update({
                        "exit_time": bar_time,
                        "exit_price": exit_price,
                        "exit_reason": exit_reason,
                        "pnl_dollar": round(pnl_dollar, 2),
                        "pnl_r": round(pnl_r, 2),
                        "balance": round(account.balance, 2),
                    })
                    trades.append(active_trade_log)
                    active_trade_log = None

        # Build Summary
        trades_df = pd.DataFrame(trades)
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.get("pnl_r", 0) > 0])
        losing_trades = len([t for t in trades if t.get("pnl_r", 0) < 0])
        be_trades = len([t for t in trades if t.get("pnl_r", 0) == 0])

        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0
        gross_profit = sum(t["pnl_dollar"] for t in trades if t["pnl_dollar"] > 0)
        gross_loss = abs(sum(t["pnl_dollar"] for t in trades if t["pnl_dollar"] < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 1.0)
        avg_r = (sum(t["pnl_r"] for t in trades) / total_trades) if total_trades > 0 else 0.0

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

