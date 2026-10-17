"""Versioned Pure B1 cost policy. Unverified tariffs fail closed.

`symbol_info` does not provide the commission tariff before an order. A zero
commission is admissible only when the policy names a source other than
`symbol_info`. Slippage is a declared assumption and a stress input, not a
terminal-certified value. Swap-free status is current-policy only and is not
historical entitlement.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import math


ADMITTED_COMMISSION_UNIT = "USD_per_lot_round_trip"
RECOGNIZED_COMMISSION_UNITS = frozenset(
    {ADMITTED_COMMISSION_UNIT, "USD_per_lot_per_side"}
)
DECLARED_SLIPPAGE_PRICE = 0.10
DECLARED_SPREAD_STRESS_PRICE = 0.20


def validate_cost_policy(raw, *, fingerprint: str, now: datetime) -> tuple[dict, str]:
    """Return a shadow-admissible policy, or an empty policy and a fail-closed status."""
    if not isinstance(raw, dict):
        return {}, "missing"
    try:
        reviewed = datetime.fromisoformat(str(raw["reviewed_utc"]).replace("Z", "+00:00"))
        commission = float(raw["commission_per_lot"])
        slippage = float(raw["slippage_allowance_price"])
        spread_buffer = float(raw.get("spread_buffer", 0.0))
        evidence = str(raw.get("account_evidence_sha256") or "")
        valid = (
            raw.get("version") == 1
            and raw.get("account_fingerprint") == fingerprint
            and raw.get("account_type") == "Standard Demo"
            and raw.get("swap_free_qualified") is True
            and raw.get("swap_free_scope") == "current_policy_not_historical"
            and raw.get("commission_unit") == ADMITTED_COMMISSION_UNIT
            and raw.get("slippage_basis") == "declared_assumption"
            and raw.get("commission_from_symbol_info") is False
            and len(evidence) == 64
            and all(character in "0123456789abcdef" for character in evidence)
            and bool(str(raw.get("source") or "").strip())
            and bool(str(raw.get("commission_source") or "").strip())
            and reviewed.tzinfo is not None
            and reviewed.utcoffset() == timedelta(0)
            and timedelta(0) <= now - reviewed <= timedelta(hours=24)
            and math.isfinite(commission)
            and commission >= 0
            and math.isfinite(slippage)
            and slippage > 0
            and math.isfinite(spread_buffer)
            and spread_buffer == 0.0
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        return {}, "invalid_or_stale"
    if not valid:
        return {}, "invalid_or_stale"
    return {
        "version": 1,
        "account_type": "Standard Demo",
        "account_fingerprint": fingerprint,
        "source": str(raw["source"]),
        "reviewed_utc": reviewed.isoformat(),
        "commission_per_lot": commission,
        "commission_unit": ADMITTED_COMMISSION_UNIT,
        "commission_source": str(raw["commission_source"]),
        "commission_from_symbol_info": False,
        "account_evidence_sha256": evidence,
        "slippage_allowance_price": slippage,
        "slippage_basis": "declared_assumption",
        "spread_buffer": 0.0,
        "swap_free_qualified": True,
        "swap_free_scope": "current_policy_not_historical",
    }, "operator_attested_for_shadow"
