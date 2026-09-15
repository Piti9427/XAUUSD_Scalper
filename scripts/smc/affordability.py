"""Affordability diagnostics for Exness-style XAUUSD Demo accounts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AffordabilityReport:
    balance: float
    risk_pct: float
    risk_budget: float
    min_lot: float
    contract_size: float
    max_sl_distance_at_min_lot: float
    note: str


def build_affordability_report(
    *,
    balance: float,
    risk_pct: float = 0.005,
    min_lot: float = 0.01,
    contract_size: float = 100.0,
    spread_buffer: float = 0.30,
) -> AffordabilityReport:
    """
    Report how far Entry→SL can be at broker minimum lot without exceeding risk.

    Does not place orders. Missing live broker metadata must be disclosed by caller.
    """
    risk_budget = balance * risk_pct
    # risk = lot * sl_distance * contract_size  =>  sl = risk / (lot * contract)
    if min_lot <= 0 or contract_size <= 0:
        max_dist = 0.0
        note = "invalid_lot_or_contract"
    else:
        max_dist = risk_budget / (min_lot * contract_size)
        note = (
            f"At min lot {min_lot}, risk budget ${risk_budget:.2f} covers "
            f"~${max_dist:.2f} Entry-to-SL before buffer; buffer={spread_buffer:.2f}"
        )
    return AffordabilityReport(
        balance=balance,
        risk_pct=risk_pct,
        risk_budget=round(risk_budget, 4),
        min_lot=min_lot,
        contract_size=contract_size,
        max_sl_distance_at_min_lot=round(max_dist, 4),
        note=note,
    )
