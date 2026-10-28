"""Availability explains captured gates without re-running financial admission."""

from datetime import datetime, timedelta, timezone
import json
from unittest.mock import Mock, patch
import unittest

from scripts.demo_runtime import status
from tests.demo import test_c22_identity_diagnostics as fixtures
from tests.demo import test_c22_selected_execution as executions
from scripts.c22_selected.execution import install_execution_review

NOW = datetime(2026, 10, 27, 4, 0, tzinfo=timezone.utc)


class EntryAvailabilityTests(unittest.TestCase):
    def view(self, *, result=None, values=None, review=None):
        return status.entry_availability(
            result=result or dict(status="WAIT", reason="duplicate_bar", execute=True),
            values=values or {}, now=NOW, review=review, cooldown_minutes=30)

    def test_blocked_quote_does_not_hide_expired_review_or_persisted_halt(self):
        result = self.view(result=dict(status="BLOCKED", reason="quote_stale", execute=True),
            values=dict(safety_halt="private-halt-detail"),
            review=dict(status="BLOCKED", code="cost_policy_expired", policy_due="EXPIRED"))
        self.assertEqual({r["code"] for r in result["known_blockers"]},
                         {"quote_stale", "cost_policy_expired", "safety_halt"})
        self.assertTrue(result["requires_operator"])
        self.assertEqual(result["coverage"], "KNOWN_BLOCKERS_ONLY")
        self.assertEqual(result["downstream_admission"], "NOT_PROVEN")
        self.assertNotIn("private-halt-detail", json.dumps(result))

    def test_same_blocker_retains_since_and_disappeared_reason_does_not_linger(self):
        prior = self.view(result=dict(status="BLOCKED", reason="quote_stale", execute=True))
        for item in prior["known_blockers"]:
            item["since_utc"] = (NOW - timedelta(minutes=5)).isoformat()
        result = self.view(result=dict(status="BLOCKED", reason="quote_stale", execute=True),
                           values=dict(last_result=dict(entry_availability=prior)))
        self.assertEqual(result["known_blockers"][0]["since_utc"],
                         (NOW - timedelta(minutes=5)).isoformat())
        healthy = self.view(values=dict(last_result=dict(entry_availability=prior)))
        self.assertEqual(healthy["known_blockers"], [])
        self.assertEqual(healthy["status"], "WAITING_SIGNAL")
        self.assertEqual(healthy["downstream_admission"], "NOT_PROVEN")

    def test_cooldown_and_daily_resume_expose_conditional_boundaries_without_reset(self):
        last_loss = NOW - timedelta(minutes=10)
        cooldown = self.view(result=dict(status="BLOCKED", reason="cooldown", execute=True),
            values=dict(selected_last_loss_ms=int(last_loss.timestamp() * 1000)),
            review=None)
        item = cooldown["known_blockers"][0]
        self.assertEqual(item["resume_not_before_utc"], (NOW + timedelta(minutes=20)).isoformat())
        self.assertEqual(item["resume_condition"], "fresh_signal_after_cooldown_and_all_entry_checks")
        daily = self.view(result=dict(status="BLOCKED", reason="max_daily_losses", execute=True))
        self.assertEqual(daily["known_blockers"][0]["resume_not_before_utc"],
                         "2026-10-28T00:00:00+00:00")

    def test_active_protection_and_native_admission_are_distinct(self):
        managing = self.view(result=dict(status="MANAGING", execute=True),
                             values=dict(active=dict(status="FILLED")))
        self.assertEqual(managing["status"], "MANAGING")
        self.assertIn("active_reconciliation", [x["code"] for x in managing["known_blockers"]])
        admitted = self.view(result=dict(status="SHADOW_ADMIT", execute=False))
        self.assertEqual(admitted["downstream_admission"], "PASSED_THIS_CYCLE")
        self.assertEqual(admitted["status"], "SHADOW_ONLY")
        self.assertIn("shadow_mode", [x["code"] for x in admitted["known_blockers"]])

    def test_untrusted_runtime_error_is_not_copied_into_operator_fields(self):
        result = self.view(result=dict(status="BLOCKED", reason="secret-server-url", execute=True))
        self.assertEqual(result["known_blockers"][0]["code"], "runtime_blocked")
        self.assertNotIn("secret-server-url", json.dumps(result))

    def test_prior_blocker_timestamp_is_validated_instead_of_reflecting_untrusted_state(self):
        for stamp in ("private-invalid-timestamp", (NOW + timedelta(days=1)).isoformat(),
                      "2026-10-27T04:00:00"):
            with self.subTest(stamp=stamp):
                previous = dict(entry_availability=dict(known_blockers=[dict(
                    code="quote_stale", since_utc=stamp)]))
                result = self.view(result=dict(status="BLOCKED", reason="quote_stale", execute=True),
                                   values=dict(last_result=previous))
                self.assertEqual(result["known_blockers"][0]["since_utc"], NOW.isoformat())
                self.assertNotIn("private-invalid-timestamp", json.dumps(result))

    def test_armed_time_and_new_bar_waits_have_bound_conditional_resume_without_operator(self):
        metadata = dict(status="VALID", approved_utc=NOW.isoformat(),
                        arm_not_before_utc=(NOW + timedelta(minutes=16)).isoformat())
        for reason, expected in (("armed_trial_not_started", NOW + timedelta(minutes=16)),
                                ("armed_trial_new_closed_m15_required", NOW + timedelta(minutes=30))):
            with self.subTest(reason=reason):
                result = self.view(result=dict(status="BLOCKED", reason=reason, execute=True),
                                   review=metadata)
                self.assertFalse(result["requires_operator"])
                self.assertEqual(result["known_blockers"][0]["resume_not_before_utc"], expected.isoformat())
                self.assertEqual(result["downstream_admission"], "NOT_PROVEN")

    def test_public_cycle_reports_flags_halt_and_unreached_checks_without_extra_sdk_reads(self):
        fixture = fixtures.IdentityDiagnosticsTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        sdk = fixtures.SelectedBroker()
        sdk.terminal_info = Mock(return_value=fixture.terminal(connected=False))
        sdk.account_info = Mock(wraps=sdk.account_info)
        runner = fixture.runner(sdk)
        runner.journal.put("safety_halt", "private-halt-detail")
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            result = runner.cycle(now=sdk.now)
        view = result["entry_availability"]
        self.assertEqual({x["code"] for x in view["known_blockers"]},
                         {"terminal_disconnected", "safety_halt"})
        self.assertEqual(sdk.account_info.call_count, 1)
        self.assertEqual(sdk.terminal_info.call_count, 1)
        self.assertEqual(runner.journal.get("last_result")["entry_availability"], view)
        self.assertEqual(runner.journal.get("safety_halt"), "private-halt-detail")
        sdk.order_send.assert_not_called()

    def test_upstream_connection_block_still_reports_actual_expired_review_without_acceptance(self):
        fixture = executions.SelectedExecutionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        runner = fixture.runner()
        fixture.publish(executions.review_fixture(runner, fixture.broker.now))
        install_execution_review(runner, fixture.path, now=fixture.broker.now)
        fixture.broker.terminal_info = Mock(return_value=fixtures.IdentityDiagnosticsTests.terminal(
            connected=False))
        result = runner.cycle(now=fixture.broker.now + timedelta(hours=168, microseconds=1))
        self.assertEqual(result["reason"], "algo_permissions_required")
        self.assertEqual(result["execution_review"]["code"], "cost_policy_expired")
        self.assertEqual({x["code"] for x in result["entry_availability"]["known_blockers"]},
                         {"terminal_disconnected", "cost_policy_expired"})
        self.assertIsNone(runner.journal.get("selected_execution_review_sha256"))
        fixture.broker.order_send.assert_not_called()

    def test_revoked_review_does_not_stop_owned_protection_or_repeat_entry(self):
        fixture = executions.SelectedExecutionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        runner = fixture.runner()
        fixture.publish(executions.review_fixture(runner, fixture.broker.now))
        install_execution_review(runner, fixture.path, now=fixture.broker.now)
        self.assertEqual(runner.cycle(now=fixture.broker.now)["status"], "FILLED")
        fixture.path.unlink()
        fixture.broker.tick.bid += 10
        fixture.broker.tick.ask += 10
        fixture.broker.next_bar()
        result = runner.cycle(now=fixture.broker.now)
        self.assertEqual(result["status"], "BE_MOVED", result)
        self.assertEqual(result["position_protection"], "confirmed")
        self.assertEqual(result["execution_review"]["code"], "review_missing")
        self.assertEqual(result["entry_availability"]["status"], "MANAGING")
        self.assertEqual(fixture.broker.order_send.call_count, 2)
        with patch.object(runner._admission.review, "inspect", side_effect=RuntimeError("secret")):
            managing = runner.cycle(now=fixture.broker.now + timedelta(seconds=1))
        self.assertEqual(managing["status"], "MANAGING")
        self.assertEqual(managing["execution_review"]["code"], "review_inspection_unavailable")
        self.assertNotIn("secret", json.dumps(managing))
        self.assertEqual(fixture.broker.order_send.call_count, 2)


if __name__ == "__main__":
    unittest.main()
