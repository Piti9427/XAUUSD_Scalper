"""Independent operational observer: real SQLite and loopback HTTP, no MT5."""

from contextlib import closing, redirect_stdout
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
from unittest.mock import Mock, patch
import unittest

from scripts.demo_runtime.delivery import TelegramDelivery
from scripts.ops.c22_selected_watchdog import (
    SNAPSHOT,
    check_once,
    main,
    read_journal,
    service_state,
)

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
FINGERPRINT = "0123456789abcdef"


class SelectedWatchdogTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.journal = self.root / "financial.sqlite3"
        self.state = self.root / "watchdog.sqlite3"
        self.notify = Mock()
        self.unit = "active"
        self.values = dict(
            identity=FINGERPRINT,
            strategy_snapshot=SNAPSHOT,
            active=None,
            safety_halt=None,
            last_result=dict(
                snapshot=SNAPSHOT,
                captured_utc=NOW.isoformat(),
                execute=True,
                status="BLOCKED",
                reason="quote_stale",
                critical=False,
                position_protection="flat",
                observed_positions=0,
            ),
        )
        self.write_journal()

    def write_journal(self):
        with closing(sqlite3.connect(self.journal)) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            conn.executemany(
                "INSERT OR REPLACE INTO kv VALUES (?,?)",
                [(key, json.dumps(value)) for key, value in self.values.items()],
            )
            conn.commit()

    def run_check(self, now=NOW, **changes):
        options = dict(
            journal=self.journal,
            state=self.state,
            now=now,
            expected_fingerprint=FINGERPRINT,
            unit_reader=lambda: self.unit,
            notify=self.notify,
        )
        return check_once(**(options | changes))

    def test_flat_stale_quote_is_waiting_not_feed_health_or_alert_and_journal_unchanged(self):
        digest = hashlib.sha256(self.journal.read_bytes()).hexdigest()
        first = self.run_check()
        second = self.run_check(now=NOW + timedelta(seconds=1))
        self.assertEqual(first["status"], "WAITING_MARKET_DATA")
        self.assertEqual(second["status"], "WAITING_MARKET_DATA")
        self.assertFalse(first["critical"])
        self.notify.assert_not_called()
        self.assertEqual(hashlib.sha256(self.journal.read_bytes()).hexdigest(), digest)
        self.assertEqual(read_journal(self.journal), self.values)

    def test_failed_service_alert_deduplicates_across_restart_then_reports_recovery_once(self):
        self.unit = "failed"
        first = self.run_check()
        self.run_check(now=NOW + timedelta(seconds=60))
        self.assertEqual(first["delivery"], "delivered")
        self.assertEqual(first["findings"], ["service_failed"])
        self.assertEqual(self.notify.call_count, 1)
        event = self.notify.call_args.args[0]
        self.assertEqual(event["kind"], "C22_WATCHDOG_ALERT")
        self.unit = "active"
        for elapsed in (120, 299, 300, 301):
            now = NOW + timedelta(seconds=elapsed)
            self.values["last_result"].update(
                captured_utc=now.isoformat(), status="WAIT", reason="duplicate_bar"
            )
            self.write_journal()
            result = self.run_check(now=now)
            if elapsed < 300:
                self.assertEqual(result["status"], "RECOVERING")
                self.assertEqual(self.notify.call_count, 1)
        self.assertEqual(self.notify.call_count, 2)
        self.assertEqual(self.notify.call_args.args[0]["kind"], "C22_WATCHDOG_RECOVERED")

    def test_stale_sender_heartbeat_alerts_while_systemd_process_remains_active(self):
        result = self.run_check(now=NOW + timedelta(seconds=181))
        self.assertEqual(result["findings"], ["heartbeat_stale"])
        self.assertTrue(result["critical"])
        self.assertEqual(self.notify.call_count, 1)

    def test_unexpected_block_waits_for_persisted_grace_instead_of_alerting_transient(self):
        self.values["last_result"].update(reason="cost_policy_invalid_or_stale")
        self.write_journal()
        self.assertFalse(self.run_check()["critical"])
        self.run_check(now=NOW + timedelta(seconds=179))
        self.notify.assert_not_called()
        self.values["last_result"]["captured_utc"] = (NOW + timedelta(seconds=180)).isoformat()
        self.write_journal()
        result = self.run_check(now=NOW + timedelta(seconds=180))
        self.assertEqual(result["findings"], ["entry_blocked"])
        self.assertTrue(result["critical"])
        self.notify.assert_called_once()

    def test_unknown_position_alert_payload_never_includes_financial_or_secret_values(self):
        self.values["active"] = dict(ticket=777, price=999.0, token="private-secret")
        self.values["last_result"].update(
            status="UNKNOWN",
            critical=True,
            position_protection="unknown",
            observed_positions=1,
            balance=1234.56,
            reason="secret-user-password",
        )
        self.write_journal()
        result = self.run_check()
        self.assertIn("position_protection_critical", result["findings"])
        raw = json.dumps(self.notify.call_args.args[0])
        for private in (
            "777",
            "999",
            "1234.56",
            "private-secret",
            "secret-user-password",
            FINGERPRINT,
        ):
            self.assertNotIn(private, raw)
        self.assertEqual(
            set(json.loads(raw)),
            {"kind", "snapshot", "captured_utc", "findings", "service_state", "event_id"},
        )

    def test_failed_delivery_survives_process_restart_retries_same_event_id_with_backoff(self):
        self.unit = "failed"
        self.notify.side_effect = RuntimeError("secret-transport-url")
        first = self.run_check()
        first_event = self.notify.call_args.args[0]
        self.assertEqual(first["delivery"], "pending_retry")
        self.assertEqual(first["pending_notifications"], 1)
        self.assertNotIn("secret", json.dumps(first))
        self.notify.side_effect = None
        self.assertEqual(
            self.run_check(now=NOW + timedelta(seconds=10))["delivery"], "retry_deferred"
        )
        self.assertEqual(self.notify.call_count, 1)
        retried = self.run_check(now=NOW + timedelta(seconds=30))
        self.assertEqual(retried["delivery"], "delivered")
        self.assertEqual(retried["pending_notifications"], 0)
        self.assertEqual(self.notify.call_count, 2)
        self.assertEqual(self.notify.call_args.args[0], first_event)

    def test_missing_or_invalid_journal_reports_safe_operational_codes(self):
        self.journal.unlink()
        first = self.run_check()
        self.assertEqual(first["findings"], ["journal_unavailable"])
        self.assertFalse(self.journal.exists())
        self.run_check(now=NOW + timedelta(seconds=180))
        self.assertEqual(self.notify.call_count, 1)
        self.journal.write_text("private-key-is-not-a-database")
        result = self.run_check(now=NOW + timedelta(seconds=181))
        self.assertEqual(result["findings"], ["journal_unavailable"])
        self.assertNotIn("private-key", json.dumps(result))

    def test_wrong_snapshot_cannot_report_a_healthy_selected_manager(self):
        self.values["strategy_snapshot"] = "old-strategy"
        self.write_journal()
        result = self.run_check()
        self.assertIn("snapshot_mismatch", result["findings"])
        self.assertTrue(result["critical"])

    def test_shadow_mode_or_naive_heartbeat_cannot_claim_execution_health(self):
        self.values["last_result"].update(execute=False, captured_utc="2026-10-26T12:00:00")
        self.write_journal()
        result = self.run_check()
        self.assertEqual(result["findings"], ["execution_not_armed", "heartbeat_invalid"])
        self.assertTrue(result["critical"])

    def test_health_channel_receives_current_state_every_run_without_old_event_replay(self):
        health = Mock(side_effect=RuntimeError("unreachable"))
        self.unit = "failed"
        first = self.run_check(health_notify=health)
        self.assertEqual(first["health_delivery"], "pending_retry")
        self.unit = "active"
        health.side_effect = None
        recovered = self.run_check(now=NOW + timedelta(seconds=1), health_notify=health)
        self.assertEqual(recovered["health_delivery"], "delivered")
        self.assertEqual(health.call_count, 2)
        self.assertTrue(health.call_args.args[0]["result"]["critical"])
        self.assertEqual(health.call_args.args[0]["result"]["status"], "RECOVERING")

    def test_monitor_state_cannot_overwrite_financial_journal_or_change_bound_account(self):
        digest = hashlib.sha256(self.journal.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "must_not_be_financial_journal"):
            self.run_check(state=self.journal)
        self.assertEqual(hashlib.sha256(self.journal.read_bytes()).hexdigest(), digest)
        self.run_check()
        with self.assertRaisesRegex(ValueError, "state_binding_mismatch"):
            self.run_check(expected_fingerprint="fedcba9876543210")

    def test_state_hardlink_or_other_financial_database_is_rejected_before_any_write(self):
        digest = hashlib.sha256(self.journal.read_bytes()).hexdigest()
        os.link(self.journal, self.state)
        with self.assertRaisesRegex(ValueError, "must_not_be_financial_journal"):
            self.run_check()
        self.assertEqual(hashlib.sha256(self.journal.read_bytes()).hexdigest(), digest)
        self.state.unlink()
        self.state.write_bytes(self.journal.read_bytes())
        state_digest = hashlib.sha256(self.state.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "state_database_required"):
            self.run_check()
        self.assertEqual(hashlib.sha256(self.state.read_bytes()).hexdigest(), state_digest)
        self.assertEqual(hashlib.sha256(self.journal.read_bytes()).hexdigest(), digest)

    def test_cli_default_never_creates_delivery_and_notify_requires_explicit_channel(self):
        args = [
            "--journal",
            str(self.journal),
            "--state",
            str(self.state),
            "--expected-fingerprint",
            FINGERPRINT,
        ]
        with (
            patch(
                "scripts.ops.c22_selected_watchdog.check_once", return_value={"status": "HEALTHY"}
            ),
            patch("scripts.ops.c22_selected_watchdog.TelegramDelivery") as telegram,
            patch("scripts.ops.c22_selected_watchdog.HealthDelivery") as health,
            patch.dict("os.environ", {}, clear=True),
            redirect_stdout(StringIO()),
        ):
            self.assertEqual(main(args), 0)
            telegram.assert_not_called()
            health.assert_not_called()
            self.assertEqual(main(args + ["--notify"]), 2)
            telegram.assert_not_called()
            health.assert_not_called()

    def test_cli_accepts_health_only_channel_and_never_prints_its_private_url(self):
        args = [
            "--journal",
            str(self.journal),
            "--state",
            str(self.state),
            "--expected-fingerprint",
            FINGERPRINT,
            "--notify",
        ]
        output = StringIO()
        with (
            patch(
                "scripts.ops.c22_selected_watchdog.check_once", return_value={"status": "HEALTHY"}
            ) as check,
            patch("scripts.ops.c22_selected_watchdog.TelegramDelivery") as telegram,
            patch("scripts.ops.c22_selected_watchdog.HealthDelivery") as health,
            patch.dict(
                "os.environ", {"DEMO_HEALTHCHECK_URL": "https://private.example/secret"}, clear=True
            ),
            redirect_stdout(output),
        ):
            self.assertEqual(main(args), 0)
            telegram.assert_not_called()
            health.assert_called_once_with("https://private.example/secret")
            self.assertIs(check.call_args.kwargs["health_notify"], health.return_value)
        self.assertNotIn("secret", output.getvalue())

    def test_service_reader_timeout_is_bounded_and_does_not_expose_command_output(self):
        with patch(
            "scripts.ops.c22_selected_watchdog.subprocess.run",
            side_effect=subprocess.TimeoutExpired("secret-command", 3),
        ) as process:
            self.assertEqual(service_state(), "unknown")
            self.assertEqual(process.call_args.kwargs["timeout"], 3)

    def test_actual_bounded_telegram_client_retries_loopback_http_without_financial_mutation(self):
        received, mode = [], {"status": 503}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(mode["status"])
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.unit = "failed"
            digest = hashlib.sha256(self.journal.read_bytes()).hexdigest()
            url = f"http://127.0.0.1:{server.server_port}"
            first = self.run_check(notify=TelegramDelivery("fixture", "owner", base_url=url))
            self.assertEqual(first["delivery"], "pending_retry")
            mode["status"] = 200
            second = self.run_check(
                now=NOW + timedelta(seconds=60),
                notify=TelegramDelivery("fixture", "owner", base_url=url),
            )
            self.assertEqual(second["delivery"], "delivered")
            self.assertEqual(len(received), 2)
            self.assertEqual(
                json.loads(received[0]["text"])["event_id"],
                json.loads(received[1]["text"])["event_id"],
            )
            self.assertEqual(hashlib.sha256(self.journal.read_bytes()).hexdigest(), digest)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
