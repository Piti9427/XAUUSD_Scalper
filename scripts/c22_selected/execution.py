"""Operator-reviewed Demo entry permission; never obstruct an owned manager."""

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3

from scripts.c22_selected.runner import SelectedAdmission
from scripts.c22_selected.strategy import CANDIDATE_ID, MAGIC, SNAPSHOT
from scripts.demo_runtime.costs import validate_policy

CONFIRMATIONS = (
    "selected_feed_and_prospective_shadow_reviewed",
    "cost_tariff_swap_calendar_reviewed",
    "flat_single_sender_and_ledger_reviewed",
    "backup_restore_and_monitor_reviewed",
)
TRIAL_CONFIRMATIONS = (
    "exact_demo_identity_and_flat_verified",
    "exact_strategy_sources_and_archive_agreement_reviewed",
    "regular_swap_assumptions_and_cost_drift_guard_reviewed",
    "single_sender_backup_restore_reviewed",
)
TRIAL_LIMITATIONS = {
    "COST_INCONCLUSIVE", "SWAP_ENTITLEMENT_UNKNOWN",
    "BROKER_FEED_PARITY_NOT_ESTABLISHED", "SHADOW_WAIT_WAIVED",
}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _utc(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("selected_execution_review_invalid")
    return value


class ExecutionReview:
    def __init__(self, path):
        self.path = Path(path)
        self.last_diagnostics = {}

    def check(self, ctx, now, *, record=False):
        """A persisted exact approval permits restart, not unreviewed entries."""
        return self._validate(ctx, now, record=record, persist=True)

    def inspect(self, ctx, now):
        """Observe review/cost binding only, without accepting an approval.

        VALID does not establish signal, calendar/ledger, market, exposure or
        risk readiness. This shares the admission validator but never records
        the implicit armed-trial acceptance performed by ``check``.
        """
        try:
            self._validate(ctx, now, record=False, persist=False)
        except ValueError:
            pass
        except sqlite3.Error:
            self.last_diagnostics.update(status="BLOCKED", code="review_inspection_unavailable")
        return dict(self.last_diagnostics)

    def _validate(self, ctx, now, *, record, persist):
        self.last_diagnostics = dict(
            status="BLOCKED", code="review_time_invalid", observational=True,
            coverage="review_and_policy_only", approval_accepted=None,
            policy_reviewed_utc=None, policy_expires_utc=None,
            policy_seconds_remaining=None, policy_due="UNKNOWN",
            approved_utc=None, arm_not_before_utc=None,
        )
        now = _utc(now)
        # Optional explanatory metadata cannot alter any admission predicate.
        try:
            reviewed = _utc(ctx.policy["reviewed_utc"])
            if type(ctx.policy.get("version")) is int and ctx.policy["version"] in (1, 2):
                expires = reviewed + timedelta(hours=168 if ctx.policy["version"] == 2 else 24)
                seconds = (expires - now).total_seconds()
                due = ("EXPIRED" if seconds < 0 else "DUE_6H" if seconds <= 6 * 3600
                       else "DUE_24H" if seconds <= 24 * 3600
                       else "DUE_72H" if seconds <= 72 * 3600 else "CURRENT")
                self.last_diagnostics.update(
                    policy_reviewed_utc=reviewed.isoformat(),
                    policy_expires_utc=expires.isoformat(),
                    policy_seconds_remaining=seconds,
                    policy_due="UNKNOWN" if reviewed > now else due,
                )
        except Exception:
            # This optional metadata never adds a prerequisite to the validator.
            pass
        code = "review_unreadable"
        try:
            if self.path.stat().st_size > 1024 * 1024:
                code = "review_oversized"
                raise ValueError("oversized review")
            raw = self.path.read_bytes()
            code = "review_malformed"
            review = json.loads(raw)
            digest = hashlib.sha256(raw).hexdigest()
            report = review["readiness"]
            cohort = {"release_hash": ctx.release_hash,
                      "config_hash": ctx.journal.audit_context["config_hash"]}
            approved = _utc(review["approved_utc"])
            captured = _utc(report["captured_utc"])
            armed = review["scope"] == "SELECTED_DEMO_ARMED_TRIAL"
            if armed:
                arm_not_before = _utc(review["arm_not_before_utc"])
                qualified = (
                    all(review["confirmations"].get(name) is True for name in TRIAL_CONFIRMATIONS)
                    and report["status"] == "ARMED_DEMO_TRIAL_WITH_LIMITATIONS"
                    and isinstance(report["limitations"], list)
                    and TRIAL_LIMITATIONS.issubset(report["limitations"])
                    and ctx.policy.get("status") == "CONSERVATIVE_REGULAR_SWAP_DEMO_ASSUMPTIONS"
                    and ctx.policy.get("swap_entitlement") == "UNKNOWN"
                    and ctx.policy.get("research_economic_qualification") == "COST_INCONCLUSIVE"
                    and ctx.policy.get("execution_authorized") is False
                )
            else:
                qualified = (
                    review["scope"] == "SELECTED_DEMO_EXECUTION"
                    and all(review["confirmations"].get(name) is True for name in CONFIRMATIONS)
                    and report["status"] == "AWAITING_OPERATOR_REVIEW" and report["blockers"] == []
                )
            code = "review_binding_mismatch"
            if not (
                type(review["version"]) is int and review["version"] == 1 and qualified
                and review["owner_authorized"] is True
                and isinstance(review["owner_instruction"], str) and review["owner_instruction"].strip()
                and report["execution_authorized"] is False and report["snapshot"] == SNAPSHOT
                and report["contract_id"] == CANDIDATE_ID and report["magic"] == MAGIC
                and report["account_fingerprint"] == ctx.fingerprint and report["cohort"] == cohort
                and review["readiness_sha256"] == canonical_hash(report)
                and captured <= approved <= now
            ):
                raise ValueError("binding mismatch")
            code = "review_input_binding_invalid"
            for name in ("policy", "broker", "parity"):
                value = report["input_sha256"][name]
                if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                    raise ValueError("input binding missing")
            code = "cost_policy_changed"
            if report["input_sha256"]["policy"] != canonical_hash(ctx.policy):
                raise ValueError("cost policy changed")
            code = "cost_policy_invalid"
            cost, _ = validate_policy(ctx.policy, fingerprint=ctx.fingerprint, now=now, strategy="c22h4")
            if not cost or cost.get("version") != 2:
                reviewed_value = self.last_diagnostics["policy_reviewed_utc"]
                if self.last_diagnostics["policy_due"] == "EXPIRED":
                    code = "cost_policy_expired"
                elif reviewed_value is not None and _utc(reviewed_value) > now:
                    code = "cost_policy_future"
                raise ValueError("reviewed v2 costs required")
            code = "review_acceptance_unavailable"
            resumed = ctx.journal.get("selected_execution_review_sha256") == digest
            self.last_diagnostics["approval_accepted"] = resumed
            if not resumed and (now - captured > timedelta(minutes=5) or now - approved > timedelta(minutes=5)):
                code = "review_initial_stale"
                raise ValueError("initial readiness stale")
            # An armed process may wait through a closed market before reaching
            # admission. Persist that exact acceptance now so its manager can
            # restart without pretending the Sunday market evidence was ready.
            if persist and (record or armed) and not resumed:
                ctx.journal.put("selected_execution_review_sha256", digest)
                ctx.journal.audit("EXECUTION_REVIEW_ACCEPTED", review_sha256=digest,
                                  readiness_sha256=review["readiness_sha256"])
                self.last_diagnostics["approval_accepted"] = True
            self.last_diagnostics.update(
                status="VALID", code="review_valid", approved_utc=approved.isoformat(),
                arm_not_before_utc=arm_not_before.isoformat() if armed else None,
            )
            return review
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError) as error:
            if code == "review_unreadable" and isinstance(error, FileNotFoundError):
                code = "review_missing"
            self.last_diagnostics["code"] = code
            raise ValueError("selected_execution_review_invalid") from None


class ReviewedAdmission(SelectedAdmission):
    def __init__(self, context, review):
        super().__init__(context)
        self.review = review

    def admit(self, account, positions, orders, deals, info, tick, bars, now):
        review = self.review.check(self.context, now, record=True)
        if review["scope"] == "SELECTED_DEMO_ARMED_TRIAL":
            not_before = _utc(review["arm_not_before_utc"])
            if now < not_before:
                raise ValueError("armed_trial_not_started")
            closed = _utc(bars.index[-1].to_pydatetime() + timedelta(minutes=15))
            if (
                closed <= _utc(review["approved_utc"]) or closed < not_before
                or not timedelta(0) <= now - closed <= timedelta(minutes=15)
            ):
                raise ValueError("armed_trial_new_closed_m15_required")
        return super().admit(account, positions, orders, deals, info, tick, bars, now)


def install_execution_review(runner, path, *, now):
    """Validate initial flat startup, then gate only admissions on every cycle.

    An owned active/UNKNOWN position still gets the shared reconciler on restart
    when the review was revoked, corrupted or expired. New entries remain blocked.
    """
    review = ExecutionReview(path)
    if runner.journal.get("active") is None:
        review.check(runner, now)
    runner._admission = ReviewedAdmission(runner, review)
