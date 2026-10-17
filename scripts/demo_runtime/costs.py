"""Account-bound Demo cost assumptions, independent of swap-free entitlement."""

from datetime import datetime, timedelta
import math


def validate_policy(raw, *, fingerprint: str, now: datetime):
    if not isinstance(raw, dict):
        return {}, "missing"
    try:
        reviewed = datetime.fromisoformat(raw["reviewed_utc"])
        commission = float(raw["commission_per_lot"])
        slippage = float(raw["slippage_allowance_price"])
        evidence = raw["account_evidence_sha256"]
        valid = (
            raw.get("version") == 1
            and raw.get("account_fingerprint") == fingerprint
            and raw.get("account_type") == "Standard Demo"
            and raw.get("commission_unit") == "USD_per_lot_round_trip"
            and raw.get("commission_from_symbol_info") is False
            and raw.get("slippage_basis") == "declared_assumption"
            and bool(str(raw.get("source") or "").strip())
            and bool(str(raw.get("commission_source") or "").strip())
            and isinstance(evidence, str)
            and len(evidence) == 64
            and all(c in "0123456789abcdef" for c in evidence)
            and reviewed.tzinfo is not None
            and reviewed.utcoffset() == timedelta(0)
            and timedelta(0) <= now - reviewed <= timedelta(hours=24)
            and math.isfinite(commission)
            and commission >= 0
            and math.isfinite(slippage)
            and slippage > 0
            and float(raw.get("spread_buffer", 0)) == 0
        )
        if valid:
            return dict(
                raw, commission_per_lot=commission, slippage_allowance_price=slippage
            ), "attested_demo_assumptions"
    except (KeyError, TypeError, ValueError, OverflowError):
        pass
    return {}, "invalid_or_stale"
