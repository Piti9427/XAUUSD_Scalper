"""Review diagnostics observe the real approval validator without granting entry."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import sqlite3
import unittest
from unittest.mock import Mock

from scripts.c22_selected.execution import ExecutionReview, canonical_hash
from scripts.demo_runtime.journal import Journal
from tests.demo.test_c22_selected_armed_trial import armed_review
from tests.demo.test_c22_selected_execution import review_fixture
from tests.demo.test_demo_containment import policy_v2
from tests.demo.test_trial30_demo import Broker


class ReviewDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        self.policy = policy_v2(self.now, Broker().info)
        self.policy.update(
            status="CONSERVATIVE_REGULAR_SWAP_DEMO_ASSUMPTIONS",
            swap_entitlement="UNKNOWN",
            research_economic_qualification="COST_INCONCLUSIVE",
            execution_authorized=False,
        )
        journal = Journal(self.root / "journal.sqlite3")
        self.addCleanup(journal.close)
        journal.audit_context = {"config_hash": "c" * 64}
        self.ctx = NS(
            journal=journal,
            policy=self.policy,
            fingerprint=self.policy["account_fingerprint"],
            release_hash="r" * 64,
        )
        self.path = self.root / "review.json"
        self.review = ExecutionReview(self.path)

    def publish(self, value):
        self.path.write_text(json.dumps(value))

    def state(self):
        return (
            self.ctx.journal.conn.execute("SELECT * FROM kv").fetchall(),
            self.ctx.journal.conn.execute("SELECT * FROM audit_events").fetchall(),
        )

    def test_missing_and_malformed_review_have_finite_causes_and_policy_due(self):
        for raw, code in (
            (None, "review_missing"),
            ("{sensitive-private-data", "review_malformed"),
            ("[]", "review_malformed"),
            ("{}", "review_malformed"),
        ):
            with self.subTest(code=code, raw=raw):
                if raw is not None:
                    self.path.write_text(raw)
                elif self.path.exists():
                    self.path.unlink()
                before = self.state()
                result = self.review.inspect(self.ctx, self.now)
                self.assertEqual((result["status"], result["code"]), ("BLOCKED", code))
                self.assertEqual(
                    result["policy_expires_utc"], (self.now + timedelta(hours=168)).isoformat()
                )
                self.assertTrue(result["observational"])
                self.assertEqual(self.state(), before)
                self.assertNotIn("sensitive-private-data", json.dumps(result))
                with self.assertRaisesRegex(ValueError, "^selected_execution_review_invalid$"):
                    self.review.check(self.ctx, self.now)
                self.assertEqual(self.review.last_diagnostics["code"], code)

    def test_armed_inspection_never_persists_acceptance_but_check_still_does(self):
        self.publish(armed_review(self.ctx, self.now))
        before = self.state()
        result = self.review.inspect(self.ctx, self.now)
        self.assertEqual((result["status"], result["code"]), ("VALID", "review_valid"))
        self.assertIs(result["approval_accepted"], False)
        self.assertEqual(self.state(), before)
        accepted = self.review.check(self.ctx, self.now)
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertEqual(self.ctx.journal.get("selected_execution_review_sha256"), digest)
        self.assertEqual(accepted["scope"], "SELECTED_DEMO_ARMED_TRIAL")
        after = self.state()
        self.assertIs(self.review.inspect(self.ctx, self.now)["approval_accepted"], True)
        self.assertEqual(self.state(), after)
        self.review.check(self.ctx, self.now, record=True)
        self.assertEqual(self.state(), after)

    def test_strict_inspection_and_unrecorded_check_cannot_enable_late_restart(self):
        expected = review_fixture(self.ctx, self.now)
        self.publish(expected)
        before = self.state()
        self.assertEqual(self.review.inspect(self.ctx, self.now)["status"], "VALID")
        self.assertEqual(self.review.check(self.ctx, self.now), expected)
        self.assertEqual(self.state(), before)
        later = self.review.inspect(self.ctx, self.now + timedelta(minutes=6))
        self.assertEqual(later["code"], "review_initial_stale")
        self.assertEqual(self.state(), before)
        self.review.check(self.ctx, self.now, record=True)
        recorded = self.state()
        self.assertEqual(
            self.review.inspect(self.ctx, self.now + timedelta(minutes=6))["status"], "VALID"
        )
        self.assertEqual(self.state(), recorded)

    def test_exact_expiry_preserves_gate_and_due_thresholds_without_renewal(self):
        self.publish(armed_review(self.ctx, self.now))
        self.review.check(self.ctx, self.now)
        expiry = self.now + timedelta(hours=168)
        before = self.state()
        frozen_policy = deepcopy(self.ctx.policy)
        for hours, due in (
            (73, "CURRENT"),
            (72, "DUE_72H"),
            (24, "DUE_24H"),
            (6, "DUE_6H"),
            (0, "DUE_6H"),
        ):
            with self.subTest(hours=hours):
                result = self.review.inspect(self.ctx, expiry - timedelta(hours=hours))
                self.assertEqual(result["status"], "VALID")
                self.assertEqual(result["policy_due"], due)
                self.assertEqual(result["policy_seconds_remaining"], hours * 3600)
        after_expiry = expiry + timedelta(microseconds=1)
        result = self.review.inspect(self.ctx, after_expiry)
        self.assertEqual(
            (result["status"], result["code"], result["policy_due"]),
            ("BLOCKED", "cost_policy_expired", "EXPIRED"),
        )
        with self.assertRaisesRegex(ValueError, "^selected_execution_review_invalid$"):
            self.review.check(self.ctx, after_expiry)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.ctx.policy, frozen_policy)

    def test_binding_policy_and_initial_failures_keep_original_denial(self):
        original = review_fixture(self.ctx, self.now)
        for case, code in (
            ("cohort", "review_binding_mismatch"),
            ("owner", "review_binding_mismatch"),
            ("digest", "review_binding_mismatch"),
            ("input", "review_input_binding_invalid"),
            ("policy", "cost_policy_changed"),
        ):
            with self.subTest(case=case):
                value = deepcopy(original)
                if case == "cohort":
                    value["readiness"]["cohort"]["release_hash"] = "x" * 64
                elif case == "owner":
                    value["owner_authorized"] = False
                elif case == "digest":
                    value["readiness_sha256"] = "wrong-sensitive-secret"
                elif case == "input":
                    value["readiness"]["input_sha256"]["broker"] = "secret-invalid"
                else:
                    value["readiness"]["input_sha256"]["policy"] = "a" * 64
                if case != "digest":
                    value["readiness_sha256"] = canonical_hash(value["readiness"])
                value["owner_instruction"] = "sensitive-owner-secret"
                self.publish(value)
                before = self.state()
                diagnostic = self.review.inspect(self.ctx, self.now)
                self.assertEqual(diagnostic["code"], code)
                with self.assertRaisesRegex(ValueError, "^selected_execution_review_invalid$"):
                    self.review.check(self.ctx, self.now, record=True)
                self.assertEqual(self.state(), before)
                self.assertNotIn("secret", json.dumps(diagnostic))

    def test_policy_future_invalid_and_diagnostic_reset_cannot_grant_approval(self):
        original = deepcopy(self.policy)
        for case, code in (("future", "cost_policy_future"), ("invalid", "cost_policy_invalid")):
            with self.subTest(case=case):
                self.ctx.policy = deepcopy(original)
                if case == "future":
                    self.ctx.policy["reviewed_utc"] = (self.now + timedelta(seconds=1)).isoformat()
                else:
                    self.ctx.policy["evidence"]["spec"]["sha256"] = "f" * 64
                self.publish(review_fixture(self.ctx, self.now))
                before = self.state()
                self.assertEqual(self.review.inspect(self.ctx, self.now)["code"], code)
                self.assertEqual(self.state(), before)
        self.ctx.policy = original
        self.publish(review_fixture(self.ctx, self.now))
        result = self.review.inspect(self.ctx, self.now)
        self.assertEqual(result["code"], "review_valid")
        self.assertEqual(result["policy_due"], "CURRENT")
        self.assertIsNone(self.ctx.journal.get("selected_execution_review_sha256"))

    def test_inspection_has_no_broker_read_and_never_uses_mutating_journal_methods(self):
        self.publish(armed_review(self.ctx, self.now))
        self.ctx.journal.put = Mock(side_effect=AssertionError("write forbidden"))
        self.ctx.journal.audit = Mock(side_effect=AssertionError("write forbidden"))
        self.ctx.broker = Mock(side_effect=AssertionError("broker forbidden"))
        self.assertEqual(self.review.inspect(self.ctx, self.now)["status"], "VALID")
        self.ctx.journal.put.assert_not_called()
        self.ctx.journal.audit.assert_not_called()
        self.ctx.broker.assert_not_called()
        result = self.review.inspect(self.ctx, "invalid-sensitive-time")
        self.assertEqual((result["status"], result["code"]), ("BLOCKED", "review_time_invalid"))
        self.assertNotIn("sensitive", json.dumps(result))

    def test_oversized_review_does_not_parse_or_expose_its_contents(self):
        self.path.write_text("private-payload" * (1024 * 1024 // 14 + 1))
        before = self.state()
        result = self.review.inspect(self.ctx, self.now)
        self.assertEqual(result["code"], "review_oversized")
        self.assertIsNone(result["approval_accepted"])
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(self.state(), before)

    def test_unavailable_acceptance_store_is_observational_failure_without_private_error(self):
        self.publish(armed_review(self.ctx, self.now))
        self.ctx.journal.get = Mock(side_effect=sqlite3.OperationalError("private-db-path"))
        result = self.review.inspect(self.ctx, self.now)
        self.assertEqual(
            (result["status"], result["code"]), ("BLOCKED", "review_inspection_unavailable")
        )
        self.assertIsNone(result["approval_accepted"])
        self.assertNotIn("private", json.dumps(result))

    def test_arm_and_approval_times_are_bound_canonical_and_reset_after_failure(self):
        value = armed_review(self.ctx, self.now)
        value["owner_instruction"] = "private-owner-instruction"
        value["arm_not_before_utc"] = "2026-10-26T13:00:00Z"
        self.publish(value)
        before = self.state()
        result = self.review.inspect(self.ctx, self.now)
        self.assertEqual(result["status"], "VALID")
        self.assertEqual(result["approved_utc"], value["approved_utc"])
        self.assertEqual(result["arm_not_before_utc"], "2026-10-26T13:00:00+00:00")
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(self.state(), before)

        value["readiness"]["cohort"]["release_hash"] = "wrong-cohort"
        value["readiness_sha256"] = canonical_hash(value["readiness"])
        self.publish(value)
        blocked = self.review.inspect(self.ctx, self.now)
        self.assertEqual(blocked["code"], "review_binding_mismatch")
        self.assertIsNone(blocked["approved_utc"])
        self.assertIsNone(blocked["arm_not_before_utc"])
        self.assertEqual(self.state(), before)
