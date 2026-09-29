"""One read-only MT5 cycle producing an append-only Pure B1 Shadow decision."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path

from scripts.pure_b1.broker_data import completed_m15_from_m1
from scripts.pure_b1.decision import decide
from scripts.smc.account_mode import verify_account_mode
from scripts.strategy import pure_b1_bars


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(account) -> str:
    return hashlib.sha256(f"{account.server}:{account.login}".encode()).hexdigest()[:16]


def _day_start(
    state_path: Path, *, now: datetime, fingerprint: str, equity: float, balance: float
) -> tuple[float | None, str]:
    day = now.date().isoformat()
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state.get("account_fingerprint") != fingerprint:
            raise ValueError("day-state account mismatch")
        if state.get("day_utc") == day:
            value = float(state["day_start_equity"])
            if math.isfinite(value) and value > 0:
                if not math.isclose(float(state["day_start_balance"]), balance, abs_tol=0.01):
                    return None, "balance_changed"
                return value, "captured_at_utc_boundary"
            raise ValueError("invalid day-start equity")
    # Equity cannot be reconstructed from later account snapshots. Missing boundary is unknown.
    if now.hour != 0 or now.minute != 0 or now.second != 0:
        return None, "day_start_unknown"
    state = {
        "day_utc": day,
        "day_start_equity": equity,
        "day_start_balance": balance,
        "account_fingerprint": fingerprint,
        "captured_utc": now.isoformat(),
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_suffix(state_path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, sort_keys=True) + "\n")
    temporary.replace(state_path)
    return equity, "captured_at_utc_boundary"


def _last_bar(log_path: Path) -> str | None:
    if not log_path.exists():
        return None
    with log_path.open(encoding="utf-8") as handle:
        last = deque(handle, maxlen=1)
    if not last:
        return None
    return json.loads(last[0]).get("bar_open_utc")


def _checked_policy(raw: dict | None, *, fingerprint: str, now: datetime) -> tuple[dict, str]:
    if not isinstance(raw, dict):
        return {}, "missing"
    try:
        reviewed = datetime.fromisoformat(str(raw["reviewed_utc"]).replace("Z", "+00:00"))
        commission = float(raw["commission_per_lot"])
        slippage = float(raw["slippage_allowance_price"])
        valid = (
            raw.get("version") == 1
            and raw.get("account_fingerprint") == fingerprint
            and raw.get("account_type") == "Standard Demo"
            and raw.get("swap_free_qualified") is True
            and raw.get("commission_unit") == "USD_per_lot_round_trip"
            and len(str(raw.get("account_evidence_sha256") or "")) == 64
            and all(c in "0123456789abcdef" for c in raw["account_evidence_sha256"])
            and bool(str(raw.get("source") or "").strip())
            and reviewed.tzinfo is not None
            and reviewed.utcoffset() == timedelta(0)
            and timedelta(0) <= now - reviewed <= timedelta(hours=24)
            and math.isfinite(commission)
            and commission >= 0
            and math.isfinite(slippage)
            and slippage > 0
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return {}, "invalid_or_stale"
    if not valid:
        return {}, "invalid_or_stale"
    return {
        "version": 1,
        "account_type": "Standard Demo",
        "commission_per_lot": commission,
        "commission_unit": "USD_per_lot_round_trip",
        "account_evidence_sha256": raw["account_evidence_sha256"],
        "slippage_allowance_price": slippage,
        "swap_free_qualified": True,
        "reviewed_utc": reviewed.isoformat(),
    }, "operator_attested_for_shadow"


def shadow_cycle(
    mt5,
    *,
    symbol: str,
    expected_login: int,
    expected_server: str,
    cost_policy: dict | None,
    now: datetime,
    log_path: Path,
    state_path: Path,
) -> dict:
    """Read market/account state, decide, and log; no MT5 mutation or alerts."""
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("Shadow clock must be timezone-aware UTC")
    account = mt5.account_info()
    if (
        account is None
        or int(account.login) != expected_login
        or str(account.server) != expected_server
        or int(account.trade_mode) != int(mt5.ACCOUNT_TRADE_MODE_DEMO)
        or str(account.currency) != "USD"
        or not verify_account_mode(account_info=account, require_hedging=True).ok
    ):
        raise ValueError("target Demo account identity/mode mismatch")
    if not all(
        math.isfinite(float(value)) and float(value) > 0
        for value in (account.balance, account.equity)
    ) or not math.isfinite(float(account.margin_free)):
        raise ValueError("invalid account capital snapshot")
    info = mt5.symbol_info(symbol)
    if info is None or str(info.name) != symbol or "XAUUSD" not in symbol:
        raise ValueError("target broker symbol mismatch")
    positions = mt5.positions_get(symbol=symbol)
    orders = mt5.orders_get(symbol=symbol)
    if positions is None or orders is None:
        raise ValueError("broker exposure unavailable")
    all_positions = mt5.positions_get()
    if all_positions is None:
        raise ValueError("account-wide exposure unavailable")
    tick = mt5.symbol_info_tick(symbol)
    if tick is None or not getattr(tick, "time_msc", 0):
        raise ValueError("broker quote unavailable")
    quote_time = datetime.fromtimestamp(int(tick.time_msc) / 1000, timezone.utc)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 60000)
    bars = completed_m15_from_m1(rates, now=now)
    if len(bars) < 1000:
        raise ValueError("M15 history warmup insufficient")
    full = pure_b1_bars(bars)
    tail_bars = min(1500, len(bars) // 2)
    tail = pure_b1_bars(bars.iloc[-tail_bars:])
    for field in ("rsi", "ema50", "atr", "hh30", "ll30"):
        if not math.isclose(
            float(full[field].iloc[-1]), float(tail[field].iloc[-1]), abs_tol=1e-8, rel_tol=0
        ):
            raise ValueError("M15 indicator warmup parity unproven")
    if int(full.direction.iloc[-1]) != int(tail.direction.iloc[-1]):
        raise ValueError("M15 signal warmup parity unproven")
    bar_open = bars.index[-1].to_pydatetime().isoformat()
    if _last_bar(log_path) == bar_open:
        return {
            "admit": False,
            "reason": "duplicate_bar",
            "bar_open_utc": bar_open,
            "order_api_called": False,
        }

    fingerprint = _fingerprint(account)
    policy, policy_status = _checked_policy(cost_policy, fingerprint=fingerprint, now=now)
    direction = int(full.direction.iloc[-1])
    entry = float(tick.ask if direction == 1 else tick.bid)
    margin = (
        mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY if direction == 1 else mt5.ORDER_TYPE_SELL,
            symbol,
            0.01,
            entry,
        )
        if direction
        else None
    )
    day_start, day_status = _day_start(
        state_path,
        now=now,
        fingerprint=fingerprint,
        equity=float(account.equity),
        balance=float(account.balance),
    )
    decision = decide(
        bars=bars,
        bid=float(tick.bid),
        ask=float(tick.ask),
        quote_time=quote_time,
        now=now,
        equity=float(account.equity),
        day_start_equity=day_start,
        contract_size=float(info.trade_contract_size),
        tick_size=float(info.trade_tick_size),
        min_lot=float(info.volume_min),
        max_lot=float(info.volume_max),
        lot_step=float(info.volume_step),
        commission_per_lot=policy.get("commission_per_lot"),
        cost_policy_source=policy_status if policy else "",
        slippage_allowance=policy.get("slippage_allowance_price"),
        margin_required=float(margin) if margin is not None else None,
        free_margin=float(account.margin_free),
        open_positions=len(positions),
        pending_orders=len(orders),
        broker_trade_mode=int(getattr(info, "trade_mode", -1)),
        broker_full_trade_mode=int(getattr(mt5, "SYMBOL_TRADE_MODE_FULL", 4)),
        stops_level=float(getattr(info, "trade_stops_level", float("nan"))),
        freeze_level=float(getattr(info, "trade_freeze_level", float("nan"))),
        point=float(getattr(info, "point", float("nan"))),
    )
    broker_stop_profit = None
    if direction and decision["stop"] is not None:
        broker_stop_profit = mt5.order_calc_profit(
            mt5.ORDER_TYPE_BUY if direction == 1 else mt5.ORDER_TYPE_SELL,
            symbol,
            0.01,
            decision["entry"],
            decision["stop"],
        )
        if broker_stop_profit is None or not math.isfinite(float(broker_stop_profit)):
            decision.update(admit=False, reason="broker_profit_unknown")
        elif float(broker_stop_profit) >= 0:
            decision.update(admit=False, reason="broker_profit_invalid")
        elif decision["risk_amount"] is not None:
            modeled_cost = 0.01 * (
                float(policy.get("slippage_allowance_price") or 0) * float(info.trade_contract_size)
                + float(policy.get("commission_per_lot") or 0)
            )
            broker_risk = -float(broker_stop_profit) + modeled_cost
            if broker_risk > float(account.equity) * 0.10:
                decision.update(admit=False, reason="broker_risk_cap")
            elif abs(broker_risk - float(decision["risk_amount"])) > 0.02:
                decision.update(admit=False, reason="broker_profit_mismatch")
    if direction and day_status == "balance_changed":
        decision.update(admit=False, reason="balance_changed")
    if direction and any(
        getattr(position, "symbol", symbol) != symbol for position in all_positions
    ):
        decision.update(admit=False, reason="foreign_exposure")
    record = {
        **decision,
        "schema": "pure-b1-shadow-v1",
        "bar_source": "complete 15/15 MT5 Bid M1 bars",
        "warmup_tail_bars": tail_bars,
        "captured_utc": now.isoformat(),
        "account_fingerprint": fingerprint,
        "symbol": symbol,
        "bid": float(tick.bid),
        "ask": float(tick.ask),
        "quote_utc": quote_time.isoformat(),
        "quote_age_seconds": (now - quote_time).total_seconds(),
        "spread_price": float(tick.ask) - float(tick.bid),
        "equity": float(account.equity),
        "day_start_equity": day_start,
        "day_start_status": day_status,
        "balance": float(account.balance),
        "positions": len(positions),
        "account_positions": len(all_positions),
        "pending_orders": len(orders),
        "margin_required": margin,
        "broker_stop_profit": broker_stop_profit,
        "broker_spec": {
            "trade_mode": int(getattr(info, "trade_mode", -1)),
            "stops_level": getattr(info, "trade_stops_level", None),
            "freeze_level": getattr(info, "trade_freeze_level", None),
            "point": getattr(info, "point", None),
            "contract_size": float(info.trade_contract_size),
            "tick_size": float(info.trade_tick_size),
            "volume_min": float(info.volume_min),
            "volume_max": float(info.volume_max),
            "volume_step": float(info.volume_step),
        },
        "indicators": {
            key: float(full[key].iloc[-1]) for key in ("rsi", "ema50", "atr", "hh30", "ll30")
        },
        "bar_data_sha256": hashlib.sha256(
            bars.to_csv(index_label="bar_open_utc").encode()
        ).hexdigest(),
        "contract_sha256": _sha256(Path("CORE_STRATEGY.md")),
        "cost_policy": policy,
        "cost_policy_validation": policy_status,
        "cost_policy_sha256": hashlib.sha256(
            json.dumps(cost_policy or {}, sort_keys=True).encode()
        ).hexdigest(),
        "strategy_sha256": _sha256(Path("scripts/strategy.py")),
        "risk_sha256": _sha256(Path("scripts/smc/risk.py")),
        "order_api_called": False,
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    return record
