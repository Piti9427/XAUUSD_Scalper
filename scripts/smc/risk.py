import math
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LotResult:
    lot_size: float
    sl_distance: float
    risk_amount: float
    is_valid: bool
    reason: str


def check_fixed_lot_risk(
    *,
    equity: float,
    entry_price: float,
    sl_price: float,
    lot_size: float = 0.01,
    max_risk_cap_pct: float = 0.10,
    contract_size: float = 100.0,
    spread_buffer: float = 0.0,
    commission_per_lot: float | None = None,
    slippage_allowance: float | None = None,
    min_lot: float = 0.01,
    max_lot: float = 10.0,
    lot_step: float = 0.01,
    require_cost_model: bool = False,
) -> LotResult:
    """Admit one fixed-size B1 leg only when broker volume and equity cap allow it.

    Entry and SL should be broker-side prices. Use spread_buffer only when those
    prices do not already include spread. Live callers must require a cost model.
    """
    if require_cost_model and (commission_per_lot is None or slippage_allowance is None):
        return LotResult(0.0, 0.0, 0.0, False, "Missing commission or slippage cost model")
    commission = 0.0 if commission_per_lot is None else commission_per_lot
    slippage = 0.0 if slippage_allowance is None else slippage_allowance
    values = (
        equity,
        entry_price,
        sl_price,
        lot_size,
        max_risk_cap_pct,
        contract_size,
        spread_buffer,
        commission,
        slippage,
        min_lot,
        max_lot,
        lot_step,
    )
    if (
        not all(math.isfinite(v) for v in values)
        or min(
            equity,
            entry_price,
            sl_price,
            lot_size,
            max_risk_cap_pct,
            contract_size,
            min_lot,
            max_lot,
            lot_step,
        )
        <= 0
        or min(spread_buffer, commission, slippage) < 0
    ):
        return LotResult(0.0, 0.0, 0.0, False, "Invalid fixed-lot risk inputs")
    if lot_size != 0.01:
        return LotResult(0.0, 0.0, 0.0, False, "Pure B1 requires fixed 0.01 lot")
    distance = abs(entry_price - sl_price) + spread_buffer
    if distance <= 0:
        return LotResult(0.0, 0.0, 0.0, False, "Entry and SL prices are identical")
    if not min_lot <= lot_size <= max_lot or not math.isclose(
        (lot_size - min_lot) / lot_step,
        round((lot_size - min_lot) / lot_step),
        rel_tol=0.0,
        abs_tol=1e-8,
    ):
        return LotResult(0.0, distance, 0.0, False, "Fixed lot does not meet broker volume rules")
    risk = lot_size * ((distance + slippage) * contract_size + commission)
    budget = equity * max_risk_cap_pct
    if risk > budget:
        return LotResult(
            0.0,
            distance,
            round(risk, 2),
            False,
            f"Risk cap: fixed lot risks ${risk:.2f} > {max_risk_cap_pct * 100:.0f}% of equity (${budget:.2f})",
        )
    return LotResult(lot_size, distance, round(risk, 2), True, "Fixed lot within risk cap")


def calculate_lot_size(
    balance: float,
    entry_price: float,
    sl_price: float,
    risk_pct: float = 0.005,
    spread_buffer: float = 0.30,
    max_sl_cap: float = 25.00,
    min_lot: float = 0.01,
    max_lot: float = 10.0,
    contract_size: float = 100.0,
    lot_step: float = 0.01,
    max_risk_cap_pct: float = 0.10,
    equity: float | None = None,
    commission_per_lot: float | None = None,
    slippage_allowance: float | None = None,
    require_cost_model: bool = False,
) -> LotResult:
    """
    Calculates XAUUSD position sizing based on strict mathematical risk control.

    Formula:
        SL Distance = |Entry - SL Price| + Spread Buffer
        Raw Lot = (Balance * Risk Pct) / (SL Distance * Contract Size)
        Lot Size = floor(Raw Lot / Lot Step) * Lot Step

    Safety (ADR-020):
        If floored lot is less than min_lot, min_lot (0.01) is evaluated.
        If min_lot * SL Distance * Contract Size > Balance * risk_pct,
        the order is strictly REJECTED (is_valid=False) to prevent small-account blowup.

    Note:
        When entry/sl prices already include spread buffer (e.g. from TradingView alert),
        callers MUST pass spread_buffer=0.0 to avoid double-counting. The default 0.30 is for
        direct broker price feeds only.
    """
    capital = min(balance, equity) if equity is not None else balance
    if require_cost_model and (commission_per_lot is None or slippage_allowance is None):
        return LotResult(0.0, 0.0, 0.0, False, "Missing commission or slippage cost model")
    commission_per_lot = commission_per_lot or 0.0
    slippage_allowance = slippage_allowance or 0.0
    if (
        not all(
            math.isfinite(value)
            for value in (
                capital,
                entry_price,
                sl_price,
                risk_pct,
                spread_buffer,
                max_sl_cap,
                min_lot,
                max_lot,
                contract_size,
                lot_step,
                commission_per_lot,
                slippage_allowance,
                max_risk_cap_pct,
            )
        )
        or min(
            risk_pct,
            max_sl_cap,
            min_lot,
            max_lot,
            contract_size,
            lot_step,
            max_risk_cap_pct,
        )
        <= 0
        or min(spread_buffer, commission_per_lot, slippage_allowance) < 0
    ):
        return LotResult(0.0, 0.0, 0.0, False, "Invalid risk or broker cost inputs")
    if capital <= 0:
        return LotResult(
            lot_size=0.0,
            sl_distance=0.0,
            risk_amount=0.0,
            is_valid=False,
            reason="Invalid account balance <= 0",
        )

    raw_dist = abs(entry_price - sl_price)
    if raw_dist <= 0:
        return LotResult(
            lot_size=0.0,
            sl_distance=0.0,
            risk_amount=0.0,
            is_valid=False,
            reason="Entry and SL prices are identical",
        )

    total_sl_dist = round(raw_dist + spread_buffer, 4)

    # ADR-019: Max SL Cap ($25.00 / 2500 points for Gold)
    if total_sl_dist > max_sl_cap:
        return LotResult(
            lot_size=0.0,
            sl_distance=total_sl_dist,
            risk_amount=0.0,
            is_valid=False,
            reason=f"SL distance exceeds max cap: {total_sl_dist:.2f} > {max_sl_cap:.2f}",
        )

    # Legacy SMC sizing retains its existing cap and two-leg volume rules.
    # Pure B1 uses check_fixed_lot_risk above, not this sizing function.
    min_lot_sl_risk = total_sl_dist * contract_size * min_lot
    if capital > 0 and min_lot_sl_risk > capital * max_risk_cap_pct:
        return LotResult(
            lot_size=0.0,
            sl_distance=total_sl_dist,
            risk_amount=min_lot_sl_risk,
            is_valid=False,
            reason=f"Risk cap: min lot risks ${min_lot_sl_risk:.2f} > {max_risk_cap_pct * 100:.0f}% of ${capital:.2f} (${capital * max_risk_cap_pct:.2f})",
        )

    risk_budget = capital * risk_pct
    risk_per_lot = (total_sl_dist + slippage_allowance) * contract_size + commission_per_lot
    raw_lot = risk_budget / risk_per_lot

    # Floor to lot step (0.01)
    split_step = 2 * math.ceil((min_lot - 1e-12) / lot_step) * lot_step
    split_step = max(split_step, 2 * lot_step)
    floored_lot = math.floor((min(raw_lot, max_lot) + 1e-12) / split_step) * split_step
    lot_precision = max(0, -Decimal(str(lot_step)).as_tuple().exponent)
    floored_lot = round(floored_lot, lot_precision)

    # Both 50% legs must meet broker minimum and step.
    if floored_lot < min_lot:
        effective_cap_pct = min(risk_pct, max_risk_cap_pct)
        min_lot_risk = round(min_lot * risk_per_lot, 2)
        max_allowed_risk = round(capital * effective_cap_pct, 2)
        if min_lot_risk > max_allowed_risk:
            return LotResult(
                lot_size=0.0,
                sl_distance=total_sl_dist,
                risk_amount=min_lot_risk,
                is_valid=False,
                reason=f"Small-account protection: min lot {min_lot} risks ${min_lot_risk:.2f} ({(min_lot_risk / capital) * 100:.2f}%), exceeding configured risk of {effective_cap_pct * 100:.1f}% (${max_allowed_risk:.2f})",
            )
        return LotResult(
            0.0, total_sl_dist, 0.0, False, "Lot cannot split into two broker-valid legs"
        )
    else:
        final_lot = floored_lot

    risk_amount = round(final_lot * risk_per_lot, 2)
    # Risk Protection Invariant: never admit a lot that spends more than the
    # configured risk percentage after flooring/clamping.
    if risk_amount - risk_budget > 1e-6:
        return LotResult(
            lot_size=0.0,
            sl_distance=total_sl_dist,
            risk_amount=risk_amount,
            is_valid=False,
            reason=(
                f"Risk Protection Invariant: computed risk ${risk_amount:.2f} "
                f"exceeds budget ${risk_budget:.2f} ({risk_pct * 100:.2f}%)"
            ),
        )
    return LotResult(
        lot_size=final_lot,
        sl_distance=total_sl_dist,
        risk_amount=risk_amount,
        is_valid=True,
        reason="Valid lot size calculated",
    )


def frozen_initial_r(
    *,
    pnl_dollars: float,
    initial_sl_distance: float,
    filled_lot: float,
    contract_size: float = 100.0,
) -> float:
    """
    R multiple using the frozen entry→SL denominator at fill time.

    Never recompute R from later BE moves or partial-close residual volume.
    """
    initial_risk = float(initial_sl_distance) * float(filled_lot) * float(contract_size)
    if initial_risk <= 0:
        return 0.0
    return round(float(pnl_dollars) / initial_risk, 4)
