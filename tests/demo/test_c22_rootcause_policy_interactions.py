"""Reproduce interacting Selected26b8 gates without broker or policy changes."""

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.c22_selected.execution import canonical_hash, install_execution_review
from scripts.c22_selected.runner import SelectedDemoRunner
from tests.demo.test_c22_selected_armed_trial import armed_review, monday_broker
from tests.demo.test_c22_selected_runner import selected_config
from tests.demo.test_demo_containment import policy_v2


class RootCausePolicyInteractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.journal = self.root / "execution.sqlite3"
        self.review = self.root / "execution-review.json"

    @staticmethod
    def costs(broker):
        return policy_v2(broker.now, broker.info) | {
            "status": "CONSERVATIVE_REGULAR_SWAP_DEMO_ASSUMPTIONS",
            "swap_entitlement": "UNKNOWN",
            "research_economic_qualification": "COST_INCONCLUSIVE",
            "execution_authorized": False,
        }

    def runner(self, broker, costs):
        runner = SelectedDemoRunner(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=self.journal,
            cost_policy=deepcopy(costs),
            config=selected_config(),
            execute=True,
        )
        self.addCleanup(runner.close)
        return runner

    def publish(self, runner, now):
        review = armed_review(runner, now)
        self.review.write_text(json.dumps(review))
        install_execution_review(runner, self.review, now=now)
        return review

    def test_accepted_review_exact_expiry_blocks_even_after_successful_restart(self):
        broker = monday_broker(-1)
        original_costs = self.costs(broker)
        first = self.runner(broker, original_costs)
        expected = self.publish(first, broker.now)
        receipt = first.journal.get("selected_execution_review_sha256")
        self.assertEqual(receipt, hashlib.sha256(self.review.read_bytes()).hexdigest())
        first.close()

        # Reuse the original policy and approval, without refreshing either date.
        restarted = self.runner(broker, original_costs)
        install_execution_review(restarted, self.review, now=broker.now + timedelta(minutes=6))
        expiry = datetime.fromisoformat(original_costs["reviewed_utc"]) + timedelta(hours=168)
        for offset in (-1, 0):
            with self.subTest(offset_microseconds=offset):
                actual = restarted._admission.review.check(
                    restarted, expiry + timedelta(microseconds=offset)
                )
                self.assertEqual(actual, expected)
        with self.assertRaisesRegex(ValueError, "^selected_execution_review_invalid$"):
            restarted._admission.review.check(restarted, expiry + timedelta(microseconds=1))

        self.assertEqual(restarted.policy, original_costs)
        self.assertEqual(restarted.journal.get("selected_execution_review_sha256"), receipt)
        accepted = restarted.journal.conn.execute(
            "SELECT count(*) FROM audit_events WHERE json_extract(payload,'$.kind')=?",
            ("EXECUTION_REVIEW_ACCEPTED",),
        ).fetchone()[0]
        self.assertEqual(accepted, 1)
        self.assertIsNone(restarted.journal.get("active"))
        broker.order_send.assert_not_called()

    def test_policy_calendar_missing_masks_daily_limit_until_policy_restored(self):
        broker = monday_broker(-1)
        broker.account.equity = 180.0
        costs = self.costs(broker)
        calendar = costs["evidence"]["swap_calendar"]
        today = broker.now.date().isoformat()
        today_row = calendar["document"]["days"].pop(today)
        yesterday = broker.now - timedelta(days=1)
        calendar["document"]["days"][yesterday.date().isoformat()] = today_row | {
            "rollover_utc": yesterday.replace(
                hour=21, minute=0, second=0, microsecond=0
            ).isoformat()
        }
        calendar["sha256"] = canonical_hash(calendar["document"])
        runner = self.runner(broker, costs)
        self.publish(runner, broker.now)

        missing = runner.cycle(now=broker.now)
        self.assertEqual(
            (missing["status"], missing["reason"]), ("BLOCKED", "cost_swap_calendar_missing")
        )
        baseline = runner.journal.get("day")
        self.assertEqual(baseline["equity"], 200.0)
        self.assertEqual(baseline["source"], "reconstructed_flat_midnight_from_reconciled_history")
        self.assertIsNone(runner.journal.get("last_bar"))
        broker.order_send.assert_not_called()

        # Supply a complete synthetic policy/review pair; do not bypass its hash.
        restored = deepcopy(runner.policy)
        calendar = restored["evidence"]["swap_calendar"]
        calendar["document"]["days"][today] = today_row
        calendar["sha256"] = canonical_hash(calendar["document"])
        runner.policy = restored
        self.publish(runner, broker.now)
        daily = runner.cycle(now=broker.now)

        self.assertEqual((daily["status"], daily["reason"]), ("BLOCKED", "daily_loss_limit"))
        self.assertEqual(runner.journal.get("day"), baseline)
        self.assertIsNotNone(runner.journal.get("last_bar"))
        self.assertIsNone(runner.journal.get("active"))
        broker.order_check.assert_not_called()
        broker.order_send.assert_not_called()

    def test_resolved_unknown_latched_halt_still_blocks_fresh_entry_after_restart(self):
        broker = monday_broker(-1)
        costs = self.costs(broker)
        runner = self.runner(broker, costs)
        self.publish(runner, broker.now)
        broker.order_send.side_effect = lambda request: None
        unknown = runner.cycle(now=broker.now)
        self.assertEqual(
            (unknown["status"], unknown["reason"]), ("UNKNOWN", "awaiting_broker_reconciliation")
        )
        self.assertEqual(runner.journal.get("safety_halt"), "position_identity_unresolved")
        request = deepcopy(runner.journal.get("active")["request"])
        initial_bar = runner.journal.get("last_bar")
        baseline = deepcopy(runner.journal.get("day"))
        self.assertEqual(broker.order_send.call_count, 1)

        # Delayed broker facts establish a fill and complete exit; no resend.
        broker.send(request)
        broker.now += timedelta(seconds=15)
        broker.tick.time_msc = int(broker.now.timestamp() * 1000)
        broker.send(dict(action=1, position=777, type=0, volume=0.01, price=broker.tick.ask))
        closed = runner.cycle(now=broker.now)
        self.assertEqual(closed["status"], "CLOSED")
        self.assertEqual(closed["net"], -1.0)
        self.assertIsNone(runner.journal.get("active"))
        self.assertEqual(runner.journal.get("safety_halt"), "position_identity_unresolved")
        self.assertEqual(broker.order_send.call_count, 1)
        events = [
            json.loads(row[0])["kind"]
            for row in runner.journal.conn.execute("SELECT payload FROM events")
        ]
        self.assertEqual(events, ["CLOSED"])
        runner.close()

        # Translate the complete bar tape by one H4 to preserve its real signal
        # geometry while providing a fresh post-cooldown entry after restart.
        broker.now = (broker.now + timedelta(hours=4)).replace(second=0, microsecond=500000)
        broker.tick.time_msc = int(broker.now.timestamp() * 1000) - 400
        for rate in broker.rates:
            rate["time"] += 4 * 3600
        restarted = self.runner(broker, costs)
        install_execution_review(restarted, self.review, now=broker.now)
        blocked = restarted.cycle(now=broker.now)

        self.assertEqual((blocked["status"], blocked["reason"]), ("BLOCKED", "safety_halt"))
        self.assertGreater(restarted.journal.get("last_signal_bar"), initial_bar)
        signal = restarted.journal.conn.execute(
            "SELECT payload FROM audit_events WHERE json_extract(payload,'$.kind')='SIGNAL' ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        self.assertEqual(json.loads(signal)["direction"], -1)
        self.assertEqual(restarted.journal.get("day"), baseline)
        self.assertEqual(broker.account.balance, 199.0)
        self.assertIsNone(restarted.journal.get("active"))
        self.assertFalse(broker.positions)
        self.assertEqual(broker.order_send.call_count, 1)


if __name__ == "__main__":
    unittest.main()
