"""Offline renewal contract: fixtures convey no runtime or owner authority."""

from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import unittest

from tests.demo.test_c22_selected_trial_costs import NOW, broker_fixture, sources_fixture
from scripts.c22_selected.trial_costs import build_trial_policy
from scripts.c22_selected.renewal import (
    CALENDAR_FORMULA, RenewalState, economic_scope, plan_renewal,
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def fixture():
    policy = build_trial_policy(json.dumps(broker_fixture()).encode(), now=NOW, sources=sources_fixture())
    current = {
        "policy": policy, "source_sha256": "a" * 64, "config_sha256": "b" * 64,
        "context": {"journal": object(), "cost_incidents": ["must-retain"], "loss_count": 2},
    }
    grant = {
        "version": 1, "scope": "SELECTED_DEMO_SAME_ASSUMPTION_RENEWAL",
        "owner_authorized": True, "owner_instruction": "Test-only fixture, never installed",
        "approved_utc": (NOW - timedelta(hours=1)).isoformat(),
        "expires_utc": (NOW + timedelta(days=30)).isoformat(), "revoked": False,
        "binding": {
            "account_type": "Standard Demo", "account_fingerprint": policy["account_fingerprint"],
            "contract_id": "26b8bcd69e043653", "source_sha256": current["source_sha256"],
            "config_sha256": current["config_sha256"], "economics_sha256": digest(economic_scope(policy)),
            "calendar_formula": CALENDAR_FORMULA,
        },
        "limits": {"policy_hours": 168, "prepare_hours": 72,
                   "broker_fresh_seconds": 300, "official_fresh_seconds": 86400},
    }
    return current, grant


def inputs(now):
    broker, sources = broker_fixture(), sources_fixture()
    broker["captured_utc"] = (now - timedelta(seconds=1)).isoformat()
    broker["history_end_utc"] = broker["captured_utc"]
    for source in sources.values():
        source["checked_utc"] = (now - timedelta(hours=1)).isoformat()
    return json.dumps(broker).encode(), sources


class RenewalContractTests(unittest.TestCase):
    def call(self, *, now=None, current=None, grant=None, state=None, **kwargs):
        default_current, default_grant = fixture()
        current = default_current if current is None else current
        grant = default_grant if grant is None else grant
        return plan_renewal(
            current=current, grant=grant, trusted_grant_sha256=digest(grant),
            now=now or NOW + timedelta(hours=96),
            state=state or RenewalState(0, 0, False, False),
            enabled=True, old_entry_gates_pass=True, **kwargs,
        )

    def test_disabled_or_unpinned_grant_never_manufactures_authority(self):
        current, grant = fixture()
        result = plan_renewal(current=current, grant=grant, now=NOW,
                              state=RenewalState(0, 0, False, False))
        self.assertEqual(result.action, "DISABLED")
        result = plan_renewal(current=current, grant=grant, now=NOW, enabled=True,
                              state=RenewalState(0, 0, False, False))
        self.assertEqual(result.reason, "grant_pin_missing_or_mismatch")
        self.assertFalse(result.installation_authorized)
        self.assertIs(result.retained_context, current["context"])

    def test_72_hour_boundary_prepares_without_cooldown(self):
        before = self.call(now=NOW + timedelta(hours=96) - timedelta(microseconds=1))
        due = self.call(now=NOW + timedelta(hours=96))
        self.assertEqual(before.action, "NOT_DUE")
        self.assertEqual(due.action, "PREPARE")
        self.assertTrue(before.old_entries_eligible)
        self.assertTrue(due.old_entries_eligible)
        self.assertEqual(due.prepare_at, NOW + timedelta(hours=96))
        self.assertEqual(due.policy_expires_at, NOW + timedelta(hours=168))

    def test_grant_expired_revoked_future_or_lifetime_widening_requires_review(self):
        for kind in ("expired", "revoked", "future", "lifetime", "prepare", "broker", "official"):
            with self.subTest(kind=kind):
                current, grant = fixture()
                if kind == "expired":
                    grant["expires_utc"] = (NOW + timedelta(hours=96)).isoformat()
                elif kind == "revoked":
                    grant["revoked"] = True
                elif kind == "future":
                    grant["approved_utc"] = (NOW + timedelta(hours=97)).isoformat()
                else:
                    field = {"lifetime": "policy_hours", "prepare": "prepare_hours",
                             "broker": "broker_fresh_seconds", "official": "official_fresh_seconds"}[kind]
                    grant["limits"][field] += 1
                result = self.call(current=current, grant=grant)
                self.assertEqual(result.action, "REVIEW_REQUIRED")
                self.assertTrue(result.old_entries_eligible)
                self.assertFalse(result.installation_authorized)

    def test_changed_account_sources_config_or_cost_scope_never_renews(self):
        for field in ("account_fingerprint", "source_sha256", "config_sha256", "economics_sha256",
                      "account_type", "contract_id", "calendar_formula"):
            with self.subTest(field=field):
                current, grant = fixture()
                grant["binding"][field] = "changed"
                result = self.call(current=current, grant=grant)
                self.assertEqual(result.reason, "grant_scope_mismatch")
                self.assertIs(result.retained_context, current["context"])

    def test_lower_swap_commission_slippage_or_spec_drift_requires_review(self):
        for kind in ("lower_swap", "higher_swap", "spec", "commission", "slippage"):
            with self.subTest(kind=kind):
                current, grant = fixture()
                raw, sources = inputs(NOW + timedelta(hours=96))
                broker = json.loads(raw)
                if kind in ("lower_swap", "higher_swap"):
                    broker["spec"]["swap_long"] += 1 if kind == "lower_swap" else -1
                elif kind == "spec":
                    broker["spec"]["volume_max"] += 1
                elif kind == "commission":
                    current["policy"]["commission_per_lot"] = 0.1
                else:
                    current["policy"]["slippage_allowance_price"] = 0.2
                result = self.call(current=current, grant=grant,
                                   broker_bytes=json.dumps(broker).encode(), sources=sources)
                self.assertEqual(result.action, "REVIEW_REQUIRED")
                self.assertIsNone(result.candidate_policy)

    def test_matching_fresh_candidate_is_reviewable_but_never_installed(self):
        current, grant = fixture()
        raw, sources = inputs(NOW + timedelta(hours=96))
        before = deepcopy(current["policy"])
        result = self.call(current=current, grant=grant, broker_bytes=raw, sources=sources)
        self.assertEqual(result.action, "REVIEW_CANDIDATE")
        self.assertEqual(result.reason, "generation_and_incident_review_required")
        self.assertFalse(result.installation_authorized)
        self.assertTrue(result.old_entries_eligible)
        self.assertIs(result.retained_context, current["context"])
        self.assertEqual(current["policy"], before)
        self.assertEqual(result.candidate_policy["reviewed_utc"], (NOW + timedelta(hours=96)).isoformat())
        self.assertFalse(result.candidate_policy["execution_authorized"])
        self.assertEqual(result.candidate_policy["swap_entitlement"], "UNKNOWN")
        self.assertEqual(result.candidate_policy["research_economic_qualification"], "COST_INCONCLUSIVE")
        self.assertEqual(grant["approved_utc"], (NOW - timedelta(hours=1)).isoformat())

    def test_held_order_active_unknown_defers_install_but_preparation_can_start(self):
        states = (RenewalState(1, 0, False, False), RenewalState(0, 1, False, False),
                  RenewalState(0, 0, True, False), RenewalState(0, 0, False, True))
        raw, sources = inputs(NOW + timedelta(hours=96))
        for state in states:
            with self.subTest(state=state):
                self.assertEqual(self.call(state=state).action, "PREPARE")
                result = self.call(state=state, broker_bytes=raw, sources=sources)
                self.assertEqual(result.action, "DEFER")
                self.assertFalse(result.old_entries_eligible)
                self.assertEqual(result.reason, "flat_no_orders_no_active_no_unknown_required")
                self.assertEqual(result.owned_management, "CONTINUE_RECONCILIATION")
                self.assertFalse(result.installation_authorized)

    def test_failed_preparation_retains_complete_old_context_and_trading_eligibility(self):
        current, grant = fixture()
        result = self.call(current=current, grant=grant, preparation_failed=True)
        self.assertEqual(result.reason, "preparation_failed_keep_current_generation")
        self.assertIs(result.retained_context, current["context"])
        self.assertIs(result.retained_policy, current["policy"])
        self.assertEqual(result.retained_context["cost_incidents"], ["must-retain"])
        self.assertEqual(result.retained_context["loss_count"], 2)
        self.assertTrue(result.old_entries_eligible)

    def test_expired_or_invalid_old_generation_never_gets_new_entry_eligibility(self):
        for kind in ("expired", "invalid", "other_gate"):
            with self.subTest(kind=kind):
                current, grant = fixture()
                now = NOW + timedelta(hours=168, microseconds=1) if kind == "expired" else NOW + timedelta(hours=96)
                if kind == "invalid":
                    current["policy"]["evidence"]["tariff"]["sha256"] = "0" * 64
                result = plan_renewal(
                    current=current, grant=grant, trusted_grant_sha256=digest(grant), now=now,
                    state=RenewalState(0, 0, False, False), enabled=True,
                    old_entry_gates_pass=kind != "other_gate", preparation_failed=True,
                )
                self.assertFalse(result.old_entries_eligible)
                self.assertEqual(result.owned_management, "CONTINUE_RECONCILIATION")
                self.assertIs(result.retained_context, current["context"])

    def test_freshness_limits_never_relabel_stale_or_future_evidence(self):
        for kind in ("broker_stale", "broker_future", "official_stale", "official_future"):
            with self.subTest(kind=kind):
                now = NOW + timedelta(hours=96)
                raw, sources = inputs(now)
                broker = json.loads(raw)
                if kind.startswith("broker"):
                    broker["captured_utc"] = (now - timedelta(minutes=5, microseconds=1)
                                              if kind.endswith("stale") else now + timedelta(seconds=1)).isoformat()
                else:
                    sources["tariff"]["checked_utc"] = (now - timedelta(hours=24, microseconds=1)
                                                         if kind.endswith("stale") else now + timedelta(seconds=1)).isoformat()
                result = self.call(broker_bytes=json.dumps(broker).encode(), sources=sources)
                self.assertEqual(result.action, "DEFER")
                self.assertIsNone(result.candidate_policy)
                self.assertTrue(result.old_entries_eligible)

    def test_naive_time_and_malformed_state_cannot_be_treated_as_flat(self):
        with self.assertRaisesRegex(ValueError, "aware_utc"):
            self.call(now=NOW.replace(tzinfo=None))
        for state in (RenewalState(None, 0, False, False), RenewalState(False, 0, False, False),
                      RenewalState(0, 0, None, False)):
            with self.subTest(state=state):
                result = self.call(state=state)
                self.assertEqual(result.reason, "broker_journal_state_unknown")
                self.assertFalse(result.installation_authorized)

    def test_tampered_current_generation_cannot_be_hidden_by_a_clean_candidate(self):
        for kind in ("evidence_hash", "calendar_formula", "future_review", "missing_context"):
            with self.subTest(kind=kind):
                current, grant = fixture()
                if kind == "evidence_hash":
                    current["policy"]["evidence"]["tariff"]["sha256"] = "0" * 64
                elif kind == "calendar_formula":
                    item = current["policy"]["evidence"]["swap_calendar"]
                    item["document"]["days"]["2026-10-29"]["buy"] = 0
                    item["sha256"] = digest(item["document"])
                elif kind == "future_review":
                    current["policy"]["reviewed_utc"] = (NOW + timedelta(days=10)).isoformat()
                else:
                    del current["context"]
                raw, sources = inputs(NOW + timedelta(hours=96))
                result = self.call(current=current, grant=grant, broker_bytes=raw, sources=sources)
                self.assertEqual(result.action, "REVIEW_REQUIRED")
                self.assertFalse(result.old_entries_eligible)
                self.assertIsNone(result.candidate_policy)

    def test_grant_needs_explicit_owner_fields_and_pinned_unchanged_document(self):
        for field, value in (("owner_authorized", False), ("owner_authorized", "true"),
                             ("owner_instruction", ""), ("revoked", None), ("version", True)):
            with self.subTest(field=field, value=value):
                current, grant = fixture()
                grant[field] = value
                result = self.call(current=current, grant=grant)
                self.assertEqual(result.action, "REVIEW_REQUIRED")
                self.assertTrue(result.old_entries_eligible)
                self.assertFalse(result.installation_authorized)

    def test_legacy_exact_168h_policy_boundary_and_no_serialized_approval_refresh(self):
        current, grant = fixture()
        approved = grant["approved_utc"]
        # A file/restart round trip cannot manufacture a new approval date.
        restored_grant = json.loads(json.dumps(grant))
        self.assertEqual(digest(restored_grant), digest(grant))
        at = self.call(current=current, grant=restored_grant, now=NOW + timedelta(hours=168))
        after = self.call(current=current, grant=restored_grant,
                          now=NOW + timedelta(hours=168, microseconds=1))
        self.assertTrue(at.old_entries_eligible)  # existing <=168h validator contract
        self.assertFalse(after.old_entries_eligible)
        self.assertEqual(restored_grant["approved_utc"], approved)
        self.assertIs(at.retained_policy, after.retained_policy)
        self.assertIs(at.retained_context, after.retained_context)

    def test_missing_current_document_is_specific_review_not_implicit_generation(self):
        for malformed in (None, [], {}, {"policy": None, "context": None}):
            with self.subTest(current=malformed):
                result = plan_renewal(current=malformed, now=NOW, enabled=True,
                                      state=RenewalState(0, 0, False, False))
                self.assertEqual(result.reason, "current_generation_invalid")
                self.assertFalse(result.old_entries_eligible)
                self.assertIsNone(result.candidate_policy)

    def test_grant_document_mutation_without_new_trusted_pin_is_rejected(self):
        current, grant = fixture()
        pin = digest(grant)
        grant["expires_utc"] = (NOW + timedelta(days=300)).isoformat()
        result = plan_renewal(current=current, grant=grant, trusted_grant_sha256=pin,
                             now=NOW + timedelta(hours=96), state=RenewalState(0, 0, False, False),
                             enabled=True, old_entry_gates_pass=True)
        self.assertEqual(result.reason, "grant_pin_missing_or_mismatch")
        self.assertTrue(result.old_entries_eligible)


if __name__ == "__main__":
    unittest.main()
