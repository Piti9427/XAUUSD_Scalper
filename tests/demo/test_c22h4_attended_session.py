"""An attended console separates entry blocking from loss of protection."""

from datetime import datetime, timezone, timedelta
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[2] / "deploy/c22-demo/attended_session.py"
SPEC = importlib.util.spec_from_file_location("c22_attended", MODULE)
console = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(console)


class AttendedSessionTests(unittest.TestCase):
    def setUp(self):
        now = datetime(2026, 10, 24, tzinfo=timezone.utc)
        self.value = dict(
            captured_utc=now.isoformat(),
            active=False,
            safety_halt=None,
            units={"c22-demo-shadow.service": "active", "c22-demo-execution.service": "inactive"},
            last_result=dict(
                captured_utc=now.isoformat(),
                execute=False,
                status="BLOCKED",
                reason="quote_stale",
                position_protection="flat",
                critical=False,
            ),
        )

    def test_closed_market_is_entry_block_not_false_protection_alarm(self):
        self.assertEqual(console.classify(self.value), "ENTRY_BLOCKED:quote_stale")
        self.value["last_result"].update(status="WAIT", reason="no_signal")
        self.assertEqual(console.classify(self.value), "WAITING_FOR_STRATEGY")

    def test_stale_unknown_and_critical_state_need_attention(self):
        for change in (
            dict(
                captured_utc=(
                    datetime(2026, 10, 24, tzinfo=timezone.utc) - timedelta(seconds=16)
                ).isoformat()
            ),
            dict(position_protection="unknown"),
            dict(critical=True),
        ):
            with self.subTest(change=change):
                value = self.value | {"last_result": self.value["last_result"] | change}
                self.assertTrue(console.classify(value).startswith("ATTENTION"))

    def test_managed_position_and_safety_halt_do_not_hide_behind_heartbeat(self):
        self.value.update(active=True)
        self.value["last_result"].update(status="MANAGING", position_protection="confirmed")
        self.assertEqual(console.classify(self.value), "POSITION_MANAGED")
        self.value["safety_halt"] = "contract_violation"
        self.assertEqual(console.classify(self.value), "ATTENTION_SAFETY_HALT")

    def test_connection_loss_and_two_senders_alarm_without_mutation(self):
        self.value["units"]["c22-demo-execution.service"] = "active"
        self.assertEqual(console.classify(self.value), "ATTENTION_SERVICE_OWNERSHIP")
        with patch.object(console.subprocess, "run", side_effect=OSError("unreachable")) as run:
            self.assertEqual(console.main([]), 2)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][-1], "python3 -")
        self.assertNotIn("order_send", console.REMOTE_STATUS)
        self.assertNotIn("systemctl','stop", console.REMOTE_STATUS)
