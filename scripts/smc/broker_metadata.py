"""Fail-closed broker sizing/margin metadata checks before new risk."""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional, Tuple


REQUIRED_SIZING_KEYS = (
    "balance",
    "equity",
    "min_lot",
    "max_lot",
    "lot_step",
    "contract_size",
    "margin_free",
)


def broker_metadata_allows_new_risk(
    snapshot: Optional[Mapping[str, Any]],
) -> Tuple[bool, str]:
    """
    Missing conversion/margin/sizing metadata must block new risk (foundation §4).

    Does not invent a minimum free-margin policy — only requires evidence present
    and self-consistent so lot sizing cannot run on unknown broker rules.
    """
    if snapshot is None:
        return False, "missing_broker_risk_snapshot"

    for key in REQUIRED_SIZING_KEYS:
        if key not in snapshot or snapshot[key] is None:
            return False, f"missing_{key}"
        try:
            value = float(snapshot[key])
        except (TypeError, ValueError):
            return False, f"invalid_{key}"
        if not math.isfinite(value):
            return False, f"invalid_{key}"

    balance = float(snapshot["balance"])
    equity = float(snapshot["equity"])
    min_lot = float(snapshot["min_lot"])
    max_lot = float(snapshot["max_lot"])
    lot_step = float(snapshot["lot_step"])
    contract_size = float(snapshot["contract_size"])
    margin_free = float(snapshot["margin_free"])

    if balance <= 0 or equity <= 0:
        return False, "non_positive_capital"
    if min_lot <= 0 or lot_step <= 0 or contract_size <= 0:
        return False, "invalid_lot_or_contract_metadata"
    if max_lot + 1e-12 < min_lot:
        return False, "max_lot_below_min_lot"
    if margin_free < 0:
        return False, "negative_margin_free"

    if "trade_allowed" in snapshot and snapshot["trade_allowed"] is not None:
        try:
            allowed = float(snapshot["trade_allowed"])
        except (TypeError, ValueError):
            return False, "invalid_trade_allowed"
        if allowed <= 0:
            return False, "trade_not_allowed"

    return True, "ok"
