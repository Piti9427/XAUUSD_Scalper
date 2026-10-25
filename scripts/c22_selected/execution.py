"""Operator-reviewed Demo entry permission; never obstruct an owned manager."""

from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

from scripts.c22_selected.runner import SelectedAdmission
from scripts.c22_selected.strategy import CANDIDATE_ID, MAGIC, SNAPSHOT
from scripts.demo_runtime.costs import validate_policy

CONFIRMATIONS = (
    "selected_feed_and_prospective_shadow_reviewed",
    "cost_tariff_swap_calendar_reviewed",
    "flat_single_sender_and_ledger_reviewed",
    "backup_restore_and_monitor_reviewed",
)


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

    def check(self, ctx, now, *, record=False):
        """A persisted exact approval permits restart, not unreviewed entries."""
        now = _utc(now)
        try:
            if self.path.stat().st_size > 1024 * 1024:
                raise ValueError("oversized review")
            raw = self.path.read_bytes()
            review = json.loads(raw)
            digest = hashlib.sha256(raw).hexdigest()
            report = review["readiness"]
            cohort = {"release_hash": ctx.release_hash,
                      "config_hash": ctx.journal.audit_context["config_hash"]}
            approved = _utc(review["approved_utc"])
            captured = _utc(report["captured_utc"])
            if not (
                review["version"] == 1 and review["scope"] == "SELECTED_DEMO_EXECUTION"
                and review["owner_authorized"] is True
                and isinstance(review["owner_instruction"], str) and review["owner_instruction"].strip()
                and all(review["confirmations"].get(name) is True for name in CONFIRMATIONS)
                and report["status"] == "AWAITING_OPERATOR_REVIEW" and report["blockers"] == []
                and report["execution_authorized"] is False and report["snapshot"] == SNAPSHOT
                and report["contract_id"] == CANDIDATE_ID and report["magic"] == MAGIC
                and report["account_fingerprint"] == ctx.fingerprint and report["cohort"] == cohort
                and review["readiness_sha256"] == canonical_hash(report)
                and captured <= approved <= now
            ):
                raise ValueError("binding mismatch")
            for name in ("policy", "broker", "parity"):
                value = report["input_sha256"][name]
                if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                    raise ValueError("input binding missing")
            if report["input_sha256"]["policy"] != canonical_hash(ctx.policy):
                raise ValueError("cost policy changed")
            cost, _ = validate_policy(ctx.policy, fingerprint=ctx.fingerprint, now=now, strategy="c22h4")
            if not cost or cost.get("version") != 2:
                raise ValueError("reviewed v2 costs required")
            resumed = ctx.journal.get("selected_execution_review_sha256") == digest
            if not resumed and (now - captured > timedelta(minutes=5) or now - approved > timedelta(minutes=5)):
                raise ValueError("initial readiness stale")
            if record and not resumed:
                ctx.journal.put("selected_execution_review_sha256", digest)
                ctx.journal.audit("EXECUTION_REVIEW_ACCEPTED", review_sha256=digest,
                                  readiness_sha256=review["readiness_sha256"])
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
            raise ValueError("selected_execution_review_invalid") from None


class ReviewedAdmission(SelectedAdmission):
    def __init__(self, context, review):
        super().__init__(context)
        self.review = review

    def admit(self, account, positions, orders, deals, info, tick, bars, now):
        self.review.check(self.context, now, record=True)
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
