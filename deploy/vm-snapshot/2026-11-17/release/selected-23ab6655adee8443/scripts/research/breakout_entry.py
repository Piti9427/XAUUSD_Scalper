"""Tick-grid entry geometry and fee-inclusive admission, research only."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
import math


@dataclass(frozen=True)
class EntryPlan:
    entry: float
    stop: float
    target: float
    admission_cap: float
    volume: float
    factor: float
    fee: float
    risk: float


def _level(price, grid, direction):
    units = Decimal(str(price)) / Decimal(str(grid))
    return float(
        units.to_integral_value(rounding=ROUND_FLOOR if direction == 1 else ROUND_CEILING)
        * Decimal(str(grid))
    )


def prepare_entry(row, bid, ask, broker, rules, costs, balance, peak, *, m5=False):
    """Return admitted geometry or first rejection reason; preserve operation order."""
    direction = int(row.direction)
    entry = float(ask if direction == 1 else bid) + direction * costs.slippage
    stop_atr = (
        rules.buy_stop_atr if direction == 1 and rules.buy_stop_atr is not None else rules.stop_atr
    )
    target_rr = (
        rules.buy_target_rr
        if direction == 1 and rules.buy_target_rr is not None
        else rules.target_rr
    )
    stop_mode = (
        rules.buy_stop_mode
        if direction == 1 and rules.buy_stop_mode is not None
        else rules.stop_mode
    )
    if direction == -1 and rules.sell_stop_mode is not None:
        stop_mode = rules.sell_stop_mode
    stop = _level(entry - direction * row.atr * stop_atr, broker["trade_tick_size"], direction)
    if stop_mode in ("structure", "trigger"):
        anchor = (
            (row.low if direction == 1 else row.high)
            if stop_mode == "trigger"
            else (row.stop_low if direction == 1 else row.stop_high)
        )
        if m5:
            # Bid candles -> Ask SELL stop, with decimal tick-grid geometry.
            anchor_price = Decimal(str(anchor))
            if direction == -1:
                anchor_price += Decimal(str(float(ask))) - Decimal(str(float(bid)))
            price = anchor_price - direction * Decimal(str(broker["trade_tick_size"]))
            stop = _level(float(price), broker["trade_tick_size"], direction)
        else:
            stop = _level(
                anchor - direction * broker["trade_tick_size"],
                broker["trade_tick_size"],
                direction,
            )
    if stop_mode == "boundary":
        stop = _level(
            row.entry_boundary - direction * 0.5 * row.atr, broker["trade_tick_size"], direction
        )
    executable = float(bid if direction == 1 else ask)
    if not math.isfinite(stop) or direction * (executable - stop) <= 0:
        return "invalid_stop"
    target_distance = abs(entry - stop) * target_rr if target_rr else row.atr * rules.target_atr
    target = _level(entry + direction * target_distance, broker["trade_tick_size"], direction)
    admission_cap = (
        rules.buy_risk_cap if direction == 1 and rules.buy_risk_cap is not None else rules.risk_cap
    )
    if rules.risk_mode == "drawdown_steps":
        drawdown = max(0.0, (peak - balance) / peak)
        if drawdown >= 0.15:
            admission_cap = min(admission_cap, 0.025)
        elif drawdown >= 0.10:
            admission_cap = min(admission_cap, 0.05)
    volume = 0.01
    sizing_mode = (
        rules.buy_sizing_mode
        if direction == 1 and rules.buy_sizing_mode is not None
        else rules.sizing_mode
    )
    if sizing_mode == "risk":
        per_lot = (abs(entry - stop) + costs.slippage) * broker[
            "trade_contract_size"
        ] + costs.commission_per_lot
        step = Decimal(str(broker["volume_step"]))
        available = min(balance * admission_cap / per_lot, broker["volume_max"])
        volume = float(
            (Decimal(str(available)) / step).to_integral_value(rounding=ROUND_FLOOR) * step
        )
        if volume < broker["volume_min"]:
            return "risk_cap"
    factor = broker["trade_contract_size"] * volume
    fee = costs.commission_per_lot * volume
    risk = (abs(entry - stop) + costs.slippage) * factor + fee
    if risk > balance * admission_cap:
        return "risk_cap"
    if balance - fee <= entry * factor / broker["leverage"]:
        return "margin"
    return EntryPlan(entry, stop, target, admission_cap, volume, factor, fee, risk)
