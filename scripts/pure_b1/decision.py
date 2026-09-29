"""Side-effect-free Pure B1 admission using the shared signal and risk functions."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import math

import pandas as pd

from scripts.smc.risk import check_fixed_lot_risk
from scripts.strategy import pure_b1_bars, pure_b1_levels


def _grid(price: float, tick_size: float, *, up: bool) -> float:
    units = Decimal(str(price)) / Decimal(str(tick_size))
    rounding = ROUND_CEILING if up else ROUND_FLOOR
    return float(units.to_integral_value(rounding=rounding) * Decimal(str(tick_size)))


def _utc(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)


def decide(
    *,
    bars: pd.DataFrame,
    bid: float,
    ask: float,
    quote_time: datetime,
    now: datetime,
    equity: float,
    day_start_equity: float | None,
    contract_size: float,
    tick_size: float,
    min_lot: float,
    max_lot: float,
    lot_step: float,
    commission_per_lot: float | None,
    cost_policy_source: str,
    slippage_allowance: float | None,
    margin_required: float | None,
    free_margin: float | None,
    open_positions: int,
    pending_orders: int,
    broker_trade_mode: int,
    broker_full_trade_mode: int,
    stops_level: float,
    freeze_level: float,
    point: float,
) -> dict:
    """Return one explainable decision; never access MT5 or submit an order."""
    result = {
        "admit": False,
        "reason": "invalid_input",
        "direction": 0,
        "entry": None,
        "stop": None,
        "target": None,
        "atr": None,
        "risk_amount": None,
        "bar_open_utc": None,
    }
    if bars.empty or not _utc(now) or not _utc(quote_time):
        return result
    calculated = pure_b1_bars(bars)
    row = calculated.iloc[-1]
    bar_open = calculated.index[-1].to_pydatetime()
    bar_close = bar_open + timedelta(minutes=15)
    result["bar_open_utc"] = bar_open.isoformat()
    result["direction"] = int(row.direction)
    if not bool(row.ready) or not result["direction"]:
        result["reason"] = "no_signal"
        return result
    result["atr"] = float(row.atr)
    if not all(math.isfinite(v) and v > 0 for v in (bid, ask, equity, contract_size, tick_size)):
        return result
    if ask < bid or quote_time > now or not bar_close <= quote_time:
        result["reason"] = "invalid_quote"
        return result
    if (now - quote_time).total_seconds() > 60 or (quote_time - bar_close).total_seconds() > 90:
        result["reason"] = "stale_quote"
        return result
    if open_positions < 0 or pending_orders < 0:
        result["reason"] = "broker_state_unknown"
        return result
    if open_positions or pending_orders:
        result["reason"] = "symbol_exposure"
        return result
    if broker_trade_mode != broker_full_trade_mode or broker_full_trade_mode < 0:
        result["reason"] = "market_unavailable"
        return result
    if day_start_equity is None or not math.isfinite(day_start_equity) or day_start_equity <= 0:
        result["reason"] = "day_start_unknown"
        return result
    if day_start_equity - equity >= 0.40 * day_start_equity:
        result["reason"] = "daily_loss_limit"
        return result
    if not cost_policy_source or commission_per_lot is None or slippage_allowance is None:
        result["reason"] = "cost_model_missing"
        return result
    if margin_required is None or free_margin is None:
        result["reason"] = "margin_unknown"
        return result
    if not all(
        math.isfinite(v) and v >= 0
        for v in (commission_per_lot, slippage_allowance, margin_required, free_margin)
    ):
        result["reason"] = "invalid_cost_or_margin"
        return result
    if margin_required > free_margin:
        result["reason"] = "insufficient_margin"
        return result

    direction = result["direction"]
    entry = ask if direction == 1 else bid
    stop, target = pure_b1_levels(entry, direction, float(row.atr))
    stop = _grid(stop, tick_size, up=direction == -1)
    target = _grid(target, tick_size, up=direction == -1)
    result.update(entry=entry, stop=stop, target=target)
    if not all(math.isfinite(v) and v >= 0 for v in (stops_level, freeze_level)) or not (
        math.isfinite(point) and point > 0
    ):
        result["reason"] = "broker_stops_unknown"
        return result
    required_distance = max(stops_level, freeze_level) * point
    reference_price = bid if direction == 1 else ask
    stop_distance = reference_price - stop if direction == 1 else stop - reference_price
    target_distance = target - reference_price if direction == 1 else reference_price - target
    if stop_distance <= required_distance or target_distance <= required_distance:
        result["reason"] = "broker_stops_invalid"
        return result
    risk = check_fixed_lot_risk(
        equity=equity,
        entry_price=entry,
        sl_price=stop,
        lot_size=0.01,
        max_risk_cap_pct=0.10,
        contract_size=contract_size,
        spread_buffer=0.0,
        commission_per_lot=commission_per_lot,
        slippage_allowance=slippage_allowance,
        min_lot=min_lot,
        max_lot=max_lot,
        lot_step=lot_step,
        require_cost_model=True,
    )
    result["risk_amount"] = risk.risk_amount
    result["admit"] = risk.is_valid
    result["reason"] = (
        "admit"
        if risk.is_valid
        else ("risk_cap" if risk.reason.startswith("Risk cap:") else "invalid_lot_or_risk")
    )
    return result
