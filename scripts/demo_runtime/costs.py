"""Account-bound Demo cost assumptions, independent of swap-free entitlement."""

from datetime import datetime, timedelta
import math
import hashlib
import json


_SPEC_DIAGNOSTIC_FIELDS = frozenset({
    "trade_contract_size", "trade_tick_size", "point", "volume_min", "volume_max",
    "volume_step", "swap_mode", "swap_long", "swap_short", "swap_rollover3days",
})


class CostPolicyError(ValueError):
    """Keep the legacy refusal text while carrying safe explanatory facts."""

    def __init__(self, reason, diagnostics):
        super().__init__(reason)
        self.diagnostics = dict(diagnostics)


def _diagnose(diagnostics, stage, code, **facts):
    if isinstance(diagnostics, dict):
        diagnostics.clear()
        diagnostics.update(stage=stage, code=code, **facts)
    return False


def _safe_spec_number(value):
    if value is None:
        return {"state": "MISSING"}
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) else {"state": "NONFINITE"}
    return {"state": "INVALID"}


def validate_policy(raw, *, fingerprint: str, now: datetime, strategy="trial30", spec=None,
                    diagnostics=None):
    """Original financial predicate with optional, non-authorizing diagnostics."""
    if isinstance(diagnostics, dict):
        diagnostics.clear()
    if not isinstance(raw, dict):
        _diagnose(diagnostics, "cost.policy", "cost_policy_missing")
        return {}, "missing"

    def failed(code):
        return _diagnose(diagnostics, "cost.policy", code)

    try:
        reviewed = datetime.fromisoformat(raw["reviewed_utc"])
        commission = float(raw["commission_per_lot"])
        slippage = float(raw["slippage_allowance_price"])
        evidence = raw["account_evidence_sha256"]
        valid = (
            ((raw.get("version") == 1 or (raw.get("version") == 2 and strategy == "c22h4"))
             or failed("cost_policy_version_unsupported"))
            and (raw.get("account_fingerprint") == fingerprint
                 or failed("cost_policy_account_mismatch"))
            and (raw.get("account_type") == "Standard Demo"
                 or failed("cost_policy_account_type_invalid"))
            and (raw.get("commission_unit") == "USD_per_lot_round_trip"
                 or failed("cost_policy_commission_unit_invalid"))
            and (raw.get("commission_from_symbol_info") is False
                 or failed("cost_policy_commission_basis_invalid"))
            and (raw.get("slippage_basis") == "declared_assumption"
                 or failed("cost_policy_slippage_basis_invalid"))
            and (bool(str(raw.get("source") or "").strip())
                 or failed("cost_policy_source_missing"))
            and (bool(str(raw.get("commission_source") or "").strip())
                 or failed("cost_policy_commission_source_missing"))
            and (isinstance(evidence, str)
                 or failed("cost_policy_account_evidence_invalid"))
            and (len(evidence) == 64 or failed("cost_policy_account_evidence_invalid"))
            and (all(c in "0123456789abcdef" for c in evidence)
                 or failed("cost_policy_account_evidence_invalid"))
            and (reviewed.tzinfo is not None
                 or failed("cost_policy_review_timezone_invalid"))
            and (reviewed.utcoffset() == timedelta(0)
                 or failed("cost_policy_review_timezone_invalid"))
            and (timedelta(0) <= now - reviewed
                 <= timedelta(hours=168 if raw.get("version") == 2 else 24)
                 or failed("cost_policy_review_future" if now < reviewed
                           else "cost_policy_expired"))
            and (math.isfinite(commission) or failed("cost_policy_commission_invalid"))
            and (commission >= 0 or failed("cost_policy_commission_invalid"))
            and (math.isfinite(slippage) or failed("cost_policy_slippage_invalid"))
            and (slippage > 0 or failed("cost_policy_slippage_invalid"))
            and (float(raw.get("spread_buffer", 0)) == 0
                 or failed("cost_policy_spread_buffer_invalid"))
        )
        if valid and raw.get("version") == 2:
            valid = validate_evidence(raw, spec=spec, diagnostics=diagnostics)
        if valid:
            return dict(
                raw, commission_per_lot=commission, slippage_allowance_price=slippage
            ), "attested_demo_assumptions"
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        if not diagnostics:
            _diagnose(diagnostics, "cost.policy", "cost_policy_input_invalid",
                      exception_class=type(exc).__name__)
    return {}, "invalid_or_stale"


def validate_evidence(raw, *, spec=None, diagnostics=None):
    """v2 binds explicit tariff, broker spec and dated USD swap schedule."""
    if isinstance(diagnostics, dict):
        diagnostics.clear()
    evidence = raw.get("evidence", {})
    stage = "cost.evidence"
    try:
        docs = {}
        for name in ("tariff", "spec", "swap_calendar"):
            item = evidence[name]
            doc = item["document"]
            encoded = json.dumps(doc, sort_keys=True, allow_nan=False).encode()
            if hashlib.sha256(encoded).hexdigest() != item["sha256"]:
                return _diagnose(diagnostics, stage, "cost_evidence_hash_mismatch",
                                 document=name)
            if not doc.get("source"):
                return _diagnose(diagnostics, stage, "cost_evidence_source_missing",
                                 document=name)
            docs[name] = doc
        stage = "cost.tariff"
        tariff = docs["tariff"]
        if (
            tariff["commission_per_lot"] != raw["commission_per_lot"]
            or tariff["unit"] != "USD_per_lot_round_trip"
        ):
            return _diagnose(diagnostics, stage, "cost_tariff_contract_invalid")
        stage = "cost.spec"
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
            return _diagnose(diagnostics, stage, "cost_spec_required_fields_missing")
        if any(not math.isfinite(float(v)) for v in fields.values()):
            return _diagnose(diagnostics, stage, "cost_spec_stored_value_invalid")
        if spec is not None:
            for key, value in fields.items():
                try:
                    observed = getattr(spec, key, None)
                except Exception as exc:
                    detail = {}
                    _diagnose(detail, stage, "cost_spec_read_failed",
                              field=key if key in _SPEC_DIAGNOSTIC_FIELDS
                              else "UNRECOGNIZED_SPEC_FIELD",
                              exception_class=type(exc).__name__)
                    if isinstance(diagnostics, dict):
                        diagnostics.update(detail)
                    try:
                        exc.diagnostics = detail
                    except Exception:
                        pass
                    raise
                if observed != value:
                    facts = {"field": "UNRECOGNIZED_SPEC_FIELD"}
                    if key in _SPEC_DIAGNOSTIC_FIELDS:
                        facts = dict(field=key, expected=_safe_spec_number(value),
                                     observed=_safe_spec_number(observed))
                    return _diagnose(diagnostics, stage, "cost_spec_mismatch", **facts)
        stage = "cost.calendar"
        calendar = docs["swap_calendar"]
        if calendar["unit"] != "USD_per_lot" or not calendar["days"]:
            return _diagnose(diagnostics, stage, "cost_calendar_contract_invalid")
        for day, row in calendar["days"].items():
            rollover = datetime.fromisoformat(row["rollover_utc"])
            if rollover.tzinfo is None or rollover.utcoffset() != timedelta(0):
                return _diagnose(diagnostics, stage, "cost_calendar_rollover_invalid")
            if rollover.date().isoformat() != day:
                return _diagnose(diagnostics, stage, "cost_calendar_rollover_invalid")
            if any(not math.isfinite(float(row[k])) for k in ("buy", "sell")):
                return _diagnose(diagnostics, stage, "cost_calendar_value_invalid")
        return True
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
        if not diagnostics:
            _diagnose(diagnostics, stage, "cost_evidence_input_invalid",
                      exception_class=type(exc).__name__)
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
