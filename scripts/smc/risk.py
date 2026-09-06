import math
from dataclasses import dataclass


@dataclass(frozen=True)
class LotResult:
    lot_size: float
    sl_distance: float
    risk_amount: float
    is_valid: bool
    reason: str


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
    max_risk_cap_pct: float = 0.015
) -> LotResult:
    """
    Calculates XAUUSD position sizing based on strict mathematical risk control.
    
    Formula:
        SL Distance = |Entry - SL Price| + Spread Buffer
        Raw Lot = (Balance * Risk Pct) / (SL Distance * Contract Size)
        Lot Size = floor(Raw Lot / Lot Step) * Lot Step

    Safety (ADR-020):
        If floored lot is less than min_lot, min_lot (0.01) is evaluated.
        If min_lot * SL Distance * Contract Size > Balance * max_risk_cap_pct (1.5%),
        the order is strictly REJECTED (is_valid=False) to prevent small-account blowup.
    """
    if balance <= 0:
        return LotResult(
            lot_size=0.0,
            sl_distance=0.0,
            risk_amount=0.0,
            is_valid=False,
            reason="Invalid account balance <= 0"
        )

    raw_dist = abs(entry_price - sl_price)
    if raw_dist <= 0:
        return LotResult(
            lot_size=0.0,
            sl_distance=0.0,
            risk_amount=0.0,
            is_valid=False,
            reason="Entry and SL prices are identical"
        )

    total_sl_dist = round(raw_dist + spread_buffer, 4)

    # ADR-019: Max SL Cap ($25.00 / 2500 points for Gold)
    if total_sl_dist > max_sl_cap:
        return LotResult(
            lot_size=0.0,
            sl_distance=total_sl_dist,
            risk_amount=0.0,
            is_valid=False,
            reason=f"SL distance exceeds max cap: {total_sl_dist:.2f} > {max_sl_cap:.2f}"
        )

    risk_amount = balance * risk_pct
    raw_lot = risk_amount / (total_sl_dist * contract_size)

    # Floor to lot step (0.01)
    floored_lot = math.floor(raw_lot / lot_step) * lot_step
    floored_lot = round(floored_lot, 2)

    # Clamp and enforce Strict Small-Account Risk Gate (ADR-020)
    if floored_lot < min_lot:
        min_lot_risk = round(min_lot * total_sl_dist * contract_size, 2)
        max_allowed_risk = round(balance * max_risk_cap_pct, 2)
        if min_lot_risk > max_allowed_risk:
            return LotResult(
                lot_size=0.0,
                sl_distance=total_sl_dist,
                risk_amount=min_lot_risk,
                is_valid=False,
                reason=f"Small-account protection: min lot {min_lot} risks ${min_lot_risk:.2f} ({(min_lot_risk/balance)*100:.2f}%), exceeding max risk cap of {max_risk_cap_pct*100:.1f}% (${max_allowed_risk:.2f})"
            )
        final_lot = min_lot
        risk_amount = min_lot_risk
    elif floored_lot > max_lot:
        final_lot = max_lot
    else:
        final_lot = floored_lot

    return LotResult(
        lot_size=final_lot,
        sl_distance=total_sl_dist,
        risk_amount=risk_amount,
        is_valid=True,
        reason="Valid lot size calculated"
    )
