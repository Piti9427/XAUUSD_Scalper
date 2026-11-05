"""Persistent operational incidents; real observer SQLite, no financial writes."""

from datetime import timedelta
from contextlib import closing
import hashlib
import json
import sqlite3
import unittest

from tests.demo import test_c22_selected_watchdog as fixtures

NOW = fixtures.NOW


class WatchdogContinuityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SelectedWatchdogTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def sample(self, seconds, *, reason="duplicate_bar", status="WAIT", **fields):
        fixture = self.fixture
        now = NOW + timedelta(seconds=seconds)
        fixture.values["last_result"].update(
            captured_utc=now.isoformat(), reason=reason, status=status, **fields
        )
        fixture.write_journal()
        digest = hashlib.sha256(fixture.journal.read_bytes()).hexdigest()
        result = fixture.run_check(now=now)
        self.assertEqual(hashlib.sha256(fixture.journal.read_bytes()).hexdigest(), digest)
        return result

    def test_alternating_permission_failure_survives_healthy_samples_and_restart(self):
        rows = []
        for step in range(7):
            rows.append(
                self.sample(
                    step * 60,
                    reason="algo_permissions_required" if step % 2 == 0 else "duplicate_bar",
                    status="BLOCKED" if step % 2 == 0 else "WAIT",
                )
            )
        self.assertEqual(rows[1]["status"], "RECOVERING")
        self.assertEqual(rows[4]["status"], "DEGRADED")
        self.assertTrue(rows[4]["critical"])
        self.assertTrue(rows[5]["critical"])
        self.assertEqual(self.fixture.notify.call_count, 1)
        self.assertEqual(rows[6]["incident_since_utc"], NOW.isoformat())

    def test_recovery_requires_continuous_grace_and_emits_once_at_exact_boundary(self):
        self.fixture.unit = "failed"
        self.assertTrue(self.sample(0)["critical"])
        self.fixture.unit = "active"
        self.assertEqual(self.sample(60)["status"], "RECOVERING")
        self.assertEqual(self.sample(239)["status"], "RECOVERING")
        result = self.sample(240)
        self.assertEqual(result["status"], "HEALTHY")
        self.assertFalse(result["critical"])
        self.sample(241)
        self.assertEqual(self.fixture.notify.call_count, 2)
        self.assertEqual(self.fixture.notify.call_args.args[0]["kind"], "C22_WATCHDOG_RECOVERED")

    def test_changing_blockers_does_not_reset_incident_or_duplicate_alert(self):
        self.sample(0, reason="cost_policy_invalid_or_stale", status="BLOCKED")
        self.fixture.values["safety_halt"] = "untrusted-sensitive-halt"
        result = self.sample(120, reason="algo_permissions_required", status="BLOCKED")
        self.assertTrue(result["critical"])
        self.fixture.values["safety_halt"] = None
        result = self.sample(180, reason="algo_permissions_required", status="BLOCKED")
        self.assertEqual(result["incident_since_utc"], NOW.isoformat())
        self.assertEqual(self.fixture.notify.call_count, 1)
        self.assertNotIn("untrusted-sensitive-halt", json.dumps(result))

    def test_day_old_quote_is_explicitly_unverified_session_not_market_closed_proof(self):
        first = self.sample(0, reason="quote_stale", status="BLOCKED", quote_age_seconds=86400)
        self.assertEqual(first["status"], "DEGRADED")
        self.assertIn("market_data_wait_session_unverified", first["findings"])
        self.assertEqual(first["market_session"], "UNVERIFIED")
        after = self.sample(180, reason="quote_stale", status="BLOCKED", quote_age_seconds=86580)
        self.assertTrue(after["critical"])
        self.assertEqual(self.fixture.notify.call_count, 1)

    def test_missing_quote_age_wait_is_bounded_across_observer_restart(self):
        first = self.sample(0, reason="quote_stale", status="BLOCKED")
        self.assertEqual(first["status"], "WAITING_MARKET_DATA")
        self.assertEqual(self.sample(179, reason="quote_stale", status="BLOCKED")["findings"], [])
        exact = self.sample(180, reason="quote_stale", status="BLOCKED")
        self.assertIn("market_data_wait_session_unverified", exact["findings"])
        self.assertTrue(exact["critical"])
        self.assertEqual(self.fixture.notify.call_count, 1)

    def test_invalid_age_never_serializes_untrusted_values_or_claims_market_health(self):
        for value in (float("nan"), float("inf"), -1, True, "private-age-value"):
            with self.subTest(value=str(value)):
                result = self.sample(
                    0, reason="quote_stale", status="BLOCKED", quote_age_seconds=value
                )
                self.assertEqual(result["market_session"], "UNVERIFIED")
                self.assertNotIn("private-age-value", json.dumps(result, allow_nan=False))

    def test_disabled_delivery_still_records_durable_local_incident(self):
        self.fixture.unit = "failed"
        result = self.fixture.run_check(notify=None)
        self.assertEqual(result["delivery"], "disabled")
        self.assertEqual(result["pending_notifications"], 1)
        self.assertTrue(result["critical"])
        self.assertEqual(result["delivery_status"], "DELIVERY_DISABLED")
        self.fixture.notify.assert_not_called()

    def test_policy_due_is_visible_even_when_latest_cycle_fails_before_admission(self):
        self.fixture.values["last_result"]["execution_review"] = dict(
            status="VALID", policy_due="DUE_24H", policy_expires_utc="2026-10-27T12:00:00+00:00"
        )
        result = self.sample(0, reason="algo_permissions_required", status="BLOCKED")
        self.assertEqual(result["advisories"], ["cost_review_due_24h"])
        self.assertEqual(result["policy_expires_utc"], "2026-10-27T12:00:00+00:00")
        self.fixture.values["last_result"]["execution_review"]["status"] = "BLOCKED"
        self.fixture.values["last_result"]["execution_review"]["policy_due"] = "EXPIRED"
        result = self.sample(180)
        self.assertIn("entry_review_blocked", result["findings"])
        self.assertTrue(result["critical"])

    def test_malformed_review_due_and_status_cannot_crash_observer_or_leak_payload(self):
        self.fixture.values["last_result"]["execution_review"] = dict(status="VALID", policy_due=[])
        result = self.sample(0)
        self.assertEqual(result["advisories"], [])
        result = self.sample(1, status=["private-invalid-status"])
        self.assertIn("heartbeat_status_invalid", result["findings"])
        self.assertNotIn("private-invalid-status", json.dumps(result))

    def test_future_or_invalid_persisted_times_raise_local_incident_instead_of_waiting(self):
        self.sample(0, reason="algo_permissions_required", status="BLOCKED")
        with closing(sqlite3.connect(self.fixture.state)) as conn:
            conn.execute(
                "UPDATE state SET value=? WHERE key='incident'",
                (
                    json.dumps(
                        dict(
                            issues=["entry_blocked", "private-incident-value"],
                            first_seen_utc=(NOW + timedelta(days=1)).isoformat(),
                            announced=False,
                        )
                    ),
                ),
            )
            conn.commit()
        result = self.sample(600, reason="algo_permissions_required", status="BLOCKED")
        self.assertTrue(result["critical"])
        self.assertIn("watchdog_state_invalid", result["findings"])
        self.assertEqual(self.fixture.notify.call_count, 1)
        self.assertNotIn("private-incident-value", json.dumps(self.fixture.notify.call_args.args))
        self.assertNotIn("private-incident-value", json.dumps(result))

    def test_future_wait_and_invalid_recovery_clock_cannot_claim_healthy(self):
        self.sample(0)
        with closing(sqlite3.connect(self.fixture.state)) as conn:
            conn.execute(
                "UPDATE state SET value=? WHERE key='market_wait_since_utc'",
                (json.dumps((NOW + timedelta(days=1)).isoformat()),),
            )
            conn.commit()
        result = self.sample(1, reason="quote_stale", status="BLOCKED")
        self.assertIn("watchdog_state_invalid", result["findings"])
        self.assertTrue(result["critical"])
        with closing(sqlite3.connect(self.fixture.state)) as conn:
            value = json.loads(
                conn.execute("SELECT value FROM state WHERE key='incident'").fetchone()[0]
            )
            value["healthy_since_utc"] = "private-invalid-clock"
            conn.execute("UPDATE state SET value=? WHERE key='incident'", (json.dumps(value),))
            conn.commit()
        result = self.sample(2)
        self.assertEqual(result["status"], "DEGRADED")
        self.assertIn("watchdog_state_invalid", result["findings"])
        self.assertNotIn("private-invalid-clock", json.dumps(result))

    def test_invalid_protection_type_stays_unknown_without_crashing_observer(self):
        result = self.sample(0, position_protection=["private-invalid-protection"])
        self.assertEqual(result["position_protection"], "unknown")
        self.assertNotIn("private-invalid-protection", json.dumps(result))

    def test_recovery_before_incident_start_cannot_clear_an_announced_incident(self):
        self.fixture.unit = "failed"
        self.sample(0)
        self.fixture.unit = "active"
        with closing(sqlite3.connect(self.fixture.state)) as conn:
            value = json.loads(
                conn.execute("SELECT value FROM state WHERE key='incident'").fetchone()[0]
            )
            value["healthy_since_utc"] = (NOW - timedelta(hours=1)).isoformat()
            conn.execute("UPDATE state SET value=? WHERE key='incident'", (json.dumps(value),))
            conn.commit()
        result = self.sample(1)
        self.assertEqual(result["status"], "DEGRADED")
        self.assertTrue(result["critical"])
        self.assertIn("watchdog_state_invalid", result["findings"])
        self.assertEqual(self.fixture.notify.call_count, 1)


if __name__ == "__main__":
    unittest.main()
