"""Offline same-assumption renewal planning, deliberately absent from the sender.

This module performs no writes, SDK reads, approval creation or installation.
A caller must obtain/pin an owner-issued grant independently. Even a matching
candidate still requires generation/incident validation and an atomic installer;
``REVIEW_CANDIDATE`` never authorizes entry, installation or scheduler activation.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import math
from zoneinfo import ZoneInfo

from scripts.c22_selected.trial_costs import build_trial_policy
from scripts.demo_runtime.costs import validate_policy

CALENDAR_FORMULA = "REGULAR_POINTS_NY17_WED3_WEEKEND0_V1"
_LIMITS = {"policy_hours": 168, "prepare_hours": 72,
           "broker_fresh_seconds": 300, "official_fresh_seconds": 86400}
_SPEC_FIELDS = frozenset({"trade_contract_size", "trade_tick_size", "point", "volume_min",
                          "volume_max", "volume_step", "swap_mode", "swap_long", "swap_short",
                          "swap_rollover3days"})


def _utc(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("renewal_aware_utc_required")
    return stamp


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _hex(value, size):
    return isinstance(value, str) and len(value) == size and all(c in "0123456789abcdef" for c in value)


def economic_scope(policy):
    """Exact economic/schedule assumptions; excludes renewable dates and hashes.

    Only the existing regular-swap Demo builder is supported. This neither
    attests account entitlement nor changes the native actual-cost drift check.
    The whole stored economic spec is bound, including any additional fields.
    """
    fields = policy["evidence"]["spec"]["document"]["fields"]
    if not isinstance(fields, dict) or not _SPEC_FIELDS.issubset(fields):
        raise ValueError("renewal_economic_spec_missing")
    numbers = list(fields.values()) + [policy[key] for key in
                                      ("commission_per_lot", "slippage_allowance_price", "spread_buffer")]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in numbers):
        raise ValueError("renewal_economic_spec_invalid")
    if not (policy["version"] == 2
            and policy["account_type"] == "Standard Demo"
            and policy["status"] == "CONSERVATIVE_REGULAR_SWAP_DEMO_ASSUMPTIONS"
            and policy["swap_entitlement"] == "UNKNOWN"
            and policy["research_economic_qualification"] == "COST_INCONCLUSIVE"
            and policy["execution_authorized"] is False):
        raise ValueError("renewal_regular_demo_scope_required")
    calendar = policy["evidence"]["swap_calendar"]["document"]
    reviewed = _utc(policy["reviewed_utc"])
    conversion = float(fields["point"]) * float(fields["trade_contract_size"])
    expected_days = {}
    for offset in range(8):
        day = reviewed.date() + timedelta(days=offset)
        rollover = datetime.combine(day, time(17), tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        factor = 0 if day.weekday() >= 5 else 3 if day.weekday() == 2 else 1
        expected_days[day.isoformat()] = {
            "rollover_utc": rollover.isoformat(),
            "buy": float(fields["swap_long"]) * conversion * factor,
            "sell": float(fields["swap_short"]) * conversion * factor,
        }
    if calendar["days"] != expected_days or calendar["broker_holiday_exceptions_verified"] is not False:
        raise ValueError("renewal_calendar_formula_changed")
    result = {key: policy[key] for key in (
        "version", "account_type", "status", "commission_per_lot", "commission_unit",
        "commission_source", "commission_from_symbol_info", "slippage_allowance_price",
        "slippage_basis", "spread_buffer", "swap_entitlement", "research_economic_qualification",
        "execution_authorized",
    )}
    calendar = policy["evidence"]["swap_calendar"]["document"]
    result.update(spec=dict(fields), calendar_formula=CALENDAR_FORMULA,
                  tariff_source=policy["evidence"]["tariff"]["document"]["source"],
                  swap_source=calendar["source"], calendar_source=calendar["holiday_source"]["source"],
                  calendar_unit=calendar["unit"],
                  broker_holiday_exceptions_verified=calendar["broker_holiday_exceptions_verified"],
                  assumptions=list(calendar["assumptions"]))
    # Round-trip prevents callers mutating the policy through returned values.
    return json.loads(json.dumps(result, sort_keys=True, allow_nan=False))


@dataclass(frozen=True)
class RenewalState:
    """Snapshot supplied by the existing sender; unknown values never mean flat."""

    broker_positions: int
    broker_orders: int
    journal_active: bool
    journal_unknown: bool

    def known(self):
        return (type(self.broker_positions) is int and self.broker_positions >= 0
                and type(self.broker_orders) is int and self.broker_orders >= 0
                and type(self.journal_active) is bool and type(self.journal_unknown) is bool)

    def install_window(self):
        return (self.known() and self.broker_positions == self.broker_orders == 0
                and not self.journal_active and not self.journal_unknown)


@dataclass(frozen=True)
class RenewalPlan:
    action: str
    reason: str
    old_entries_eligible: bool
    retained_policy: object
    retained_context: object
    policy_expires_at: datetime | None
    prepare_at: datetime | None
    next_check_at: datetime
    candidate_policy: dict | None = None
    installation_authorized: bool = False
    owned_management: str = "CONTINUE_RECONCILIATION"


def _binding(current):
    policy = current["policy"]
    if not (_hex(current["source_sha256"], 64) and _hex(current["config_sha256"], 64)
            and _hex(policy["account_fingerprint"], 16)):
        raise ValueError("renewal_current_binding_invalid")
    return {
        "account_type": "Standard Demo", "account_fingerprint": policy["account_fingerprint"],
        "contract_id": "26b8bcd69e043653", "source_sha256": current["source_sha256"],
        "config_sha256": current["config_sha256"], "economics_sha256": _hash(economic_scope(policy)),
        "calendar_formula": CALENDAR_FORMULA,
    }


def _grant_error(grant, pin, binding, now):
    if not _hex(pin, 64) or _hash(grant) != pin:
        return "grant_pin_missing_or_mismatch"
    if not (isinstance(grant, dict) and type(grant.get("version")) is int and grant["version"] == 1
            and grant.get("scope") == "SELECTED_DEMO_SAME_ASSUMPTION_RENEWAL"
            and grant.get("owner_authorized") is True
            and isinstance(grant.get("owner_instruction"), str) and grant["owner_instruction"].strip()
            and type(grant.get("revoked")) is bool):
        return "grant_missing_or_malformed"
    if grant["revoked"]:
        return "grant_revoked"
    approved, expires = _utc(grant["approved_utc"]), _utc(grant["expires_utc"])
    if not approved <= now < expires:
        return "grant_expired_or_not_yet_valid"
    if grant.get("binding") != binding:
        return "grant_scope_mismatch"
    limits = grant.get("limits")
    if (limits != _LIMITS or not isinstance(limits, dict)
            or any(type(value) is not int for value in limits.values())):
        return "grant_limits_changed"
    return None


def plan_renewal(*, current, grant=None, trusted_grant_sha256=None, now, state,
                 enabled=False, old_entry_gates_pass=False, broker_bytes=None,
                 sources=None, preparation_failed=False):
    """Plan without switching the current policy/context or bypassing a gate.

    ``current`` contains ``policy``, source/config SHA256 and opaque ``context``.
    The context is retained by identity on every path: no journal reset, cutoff
    advancement, cost incident clearing or owned-manager replacement occurs.
    ``old_entry_gates_pass`` is an observation of *all* existing gates, including
    actual costs, source/review, quote, exposure and financial limits. This flag
    cannot authorize anything: the sender must perform its normal fresh checks.

    A supplied trusted pin is an independently installed grant binding, never a
    hash inferred here from a newly created grant. No current runtime calls this
    function. Successful evidence construction yields only a reviewable candidate.
    """
    now = _utc(now)
    if not isinstance(current, dict):
        current = {}
    policy, context = current.get("policy"), current.get("context")
    expires = prepare_at = None
    eligible = False
    current_integrity = False
    try:
        reviewed = _utc(policy["reviewed_utc"])
        expires = reviewed + timedelta(hours=168)
        prepare_at = expires - timedelta(hours=72)
        if reviewed > now:
            raise ValueError("renewal_current_review_future")
        structural, _ = validate_policy(policy, fingerprint=policy["account_fingerprint"],
                                         now=reviewed, strategy="c22h4")
        economic_scope(policy)
        current_integrity = bool(structural) and context is not None
        valid, _ = validate_policy(policy, fingerprint=policy["account_fingerprint"],
                                   now=now, strategy="c22h4")
        eligible = (current_integrity and bool(valid) and old_entry_gates_pass is True
                    and isinstance(state, RenewalState) and state.install_window())
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        pass

    def result(action, reason, *, candidate=None):
        next_check = prepare_at if action == "NOT_DUE" else now
        return RenewalPlan(action, reason, eligible, policy, context, expires, prepare_at,
                           next_check, candidate)

    if enabled is not True:
        return result("DISABLED", "renewal_disabled")
    if not current_integrity:
        return result("REVIEW_REQUIRED", "current_generation_invalid")
    try:
        binding = _binding(current)
        error = _grant_error(grant, trusted_grant_sha256, binding, now)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        error = "grant_or_scope_malformed"
    if error:
        return result("REVIEW_REQUIRED", error)
    if not isinstance(state, RenewalState) or not state.known():
        return result("DEFER", "broker_journal_state_unknown")
    if expires is None or prepare_at is None:
        return result("REVIEW_REQUIRED", "current_generation_time_invalid")
    if now < prepare_at:
        return result("NOT_DUE", "renewal_preparation_not_due")
    if preparation_failed is True:
        return result("DEFER", "preparation_failed_keep_current_generation")
    if broker_bytes is None and sources is None:
        return result("PREPARE", "fresh_evidence_required_trading_not_paused")
    try:
        candidate = build_trial_policy(broker_bytes, now=now, sources=sources)
        if candidate["account_fingerprint"] != binding["account_fingerprint"]:
            return result("REVIEW_REQUIRED", "candidate_account_mismatch")
        if _hash(economic_scope(candidate)) != binding["economics_sha256"]:
            return result("REVIEW_REQUIRED", "candidate_economics_changed")
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as error:
        code = str(error)
        if not (code.startswith("trial_cost_") and code.isidentifier()):
            code = "candidate_evidence_invalid"
        return result("DEFER", code)
    if not state.install_window():
        return result("DEFER", "flat_no_orders_no_active_no_unknown_required", candidate=candidate)
    return result("REVIEW_CANDIDATE", "generation_and_incident_review_required", candidate=candidate)
