"""Account-bound Demo cost assumptions, independent of swap-free entitlement."""

from datetime import datetime, timedelta
import math
import hashlib
import json


def validate_policy(raw, *, fingerprint: str, now: datetime, strategy="trial30", spec=None):
    if not isinstance(raw, dict):
        return {}, "missing"
    try:
        reviewed = datetime.fromisoformat(raw["reviewed_utc"])
        commission = float(raw["commission_per_lot"])
        slippage = float(raw["slippage_allowance_price"])
        evidence = raw["account_evidence_sha256"]
        valid = (
            (raw.get("version") == 1 or (raw.get("version") == 2 and strategy == "c22h4"))
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
            and timedelta(0)
            <= now - reviewed
            <= timedelta(hours=168 if raw.get("version") == 2 else 24)
            and math.isfinite(commission)
            and commission >= 0
            and math.isfinite(slippage)
            and slippage > 0
            and float(raw.get("spread_buffer", 0)) == 0
        )
        if valid and raw.get("version") == 2:
            valid = validate_evidence(raw, spec=spec)
        if valid:
            return dict(
                raw, commission_per_lot=commission, slippage_allowance_price=slippage
            ), "attested_demo_assumptions"
    except (KeyError, TypeError, ValueError, OverflowError):
        pass
    return {}, "invalid_or_stale"


def validate_evidence(raw, *, spec=None):
    """v2 binds explicit tariff, broker spec and dated USD swap schedule."""
    evidence = raw.get("evidence", {})
    try:
        docs = {}
        for name in ("tariff", "spec", "swap_calendar"):
            item = evidence[name]
            doc = item["document"]
            encoded = json.dumps(doc, sort_keys=True, allow_nan=False).encode()
            if hashlib.sha256(encoded).hexdigest() != item["sha256"] or not doc.get("source"):
                return False
            docs[name] = doc
        tariff = docs["tariff"]
        if (
            tariff["commission_per_lot"] != raw["commission_per_lot"]
            or tariff["unit"] != "USD_per_lot_round_trip"
        ):
            return False
        fields = docs["spec"]["fields"]
        required = {
            "trade_contract_size",
            "trade_tick_size",
            "volume_min",
            "volume_max",
            "volume_step",
            "swap_mode",
            "swap_long",
            "swap_short",
            "swap_rollover3days",
        }
        if not required.issubset(fields):
            return False
        if any(not math.isfinite(float(v)) for v in fields.values()):
            return False
        if spec is not None and any(
            getattr(spec, key, None) != value for key, value in fields.items()
        ):
            return False
        calendar = docs["swap_calendar"]
        if calendar["unit"] != "USD_per_lot" or not calendar["days"]:
            return False
        for day, row in calendar["days"].items():
            rollover = datetime.fromisoformat(row["rollover_utc"])
            if rollover.tzinfo is None or rollover.utcoffset() != timedelta(0):
                return False
            if rollover.date().isoformat() != day:
                return False
            if any(not math.isfinite(float(row[k])) for k in ("buy", "sell")):
                return False
        return True
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return False


def validate_observed_costs(cost, deals, *, magic, now):
    """Closed ledgers must match dated swap evidence; no zero fallback."""
    if cost["version"] != 2:
        return
    calendar = cost["evidence"]["swap_calendar"]["document"]["days"]
    if now.date().isoformat() not in calendar:
        raise ValueError("cost_swap_calendar_missing")
    reviewed = datetime.fromisoformat(cost["reviewed_utc"])
    ids = {
        int(d.position_id)
        for d in deals
        if int(d.entry) == 0 and int(d.type) in (0, 1) and int(d.magic) == magic
    }
    for ident in ids:
        ledger = [d for d in deals if int(d.position_id) == ident and int(d.type) in (0, 1)]
        exits = [d for d in ledger if int(d.entry) in (1, 3)]
        if not exits or max(int(d.time_msc) for d in exits) < reviewed.timestamp() * 1000:
            continue
        if abs(sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in ledger)) > 1e-8:
            continue
        opened = min((d for d in ledger if int(d.entry) == 0), key=lambda d: int(d.time_msc))
        entry = datetime.fromtimestamp(int(opened.time_msc) / 1000, now.tzinfo)
        exit_at = datetime.fromtimestamp(max(int(d.time_msc) for d in exits) / 1000, now.tzinfo)
        expected_swap = 0.0
        day = entry.replace(hour=0, minute=0, second=0, microsecond=0)
        while day.date() <= exit_at.date():
            row = calendar.get(day.date().isoformat())
            if row is None:
                raise ValueError("cost_swap_calendar_missing")
            rollover = datetime.fromisoformat(row["rollover_utc"])
            if entry < rollover <= exit_at:
                held = sum(
                    float(d.volume) * (1 if int(d.type) == 0 else -1)
                    for d in ledger
                    if int(d.time_msc) <= rollover.timestamp() * 1000
                )
                expected_swap += float(row["buy" if int(opened.type) == 0 else "sell"]) * abs(held)
            day += timedelta(days=1)
        observed_swap = sum(float(d.swap) for d in ledger)
        charges = sum(max(0.0, -float(d.commission)) + max(0.0, -float(d.fee)) for d in ledger)
        if (
            abs(observed_swap - expected_swap) > 0.02
            or charges
            > float(cost["commission_per_lot"])
            * sum(float(d.volume) for d in ledger if int(d.entry) == 0)
            + 0.00000001
        ):
            raise ValueError("cost_broker_deal_drift")
