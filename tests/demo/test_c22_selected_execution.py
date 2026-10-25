"""Reviewed Demo admission and persistent broker protection use public cycles."""

from datetime import timedelta
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from copy import deepcopy

from scripts.c22_selected.execution import install_execution_review
from scripts.c22_selected.runner import SelectedDemoRunner
from scripts.c22_selected.strategy import CANDIDATE_ID, MAGIC, SNAPSHOT
from tests.demo.test_c22_selected_runner import SelectedBroker, selected_config
from tests.demo.test_demo_containment import policy_v2


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def review_fixture(runner, now):
    report = {
        "captured_utc": now.isoformat(), "status": "AWAITING_OPERATOR_REVIEW",
        "execution_authorized": False, "blockers": [], "snapshot": SNAPSHOT,
        "contract_id": CANDIDATE_ID, "magic": MAGIC,
        "account_fingerprint": runner.fingerprint,
        "cohort": {"release_hash": runner.release_hash,
                   "config_hash": runner.journal.audit_context["config_hash"]},
        "input_sha256": {"policy": canonical_hash(runner.policy),
                         "broker": "b" * 64, "parity": "c" * 64},
    }
    return {
        "version": 1, "scope": "SELECTED_DEMO_EXECUTION", "owner_authorized": True,
        "owner_instruction": "Synthetic explicit Demo execution authorization",
        "approved_utc": now.isoformat(), "readiness": report,
        "readiness_sha256": canonical_hash(report),
        "confirmations": {name: True for name in (
            "selected_feed_and_prospective_shadow_reviewed", "cost_tariff_swap_calendar_reviewed",
            "flat_single_sender_and_ledger_reviewed", "backup_restore_and_monitor_reviewed")},
    }


class SelectedExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.broker = SelectedBroker(1)
        for name in ("swap_mode", "swap_long", "swap_short", "swap_rollover3days"):
            setattr(self.broker.info, name, 0)
        self.cost = policy_v2(self.broker.now, self.broker.info)
        self.path = self.root / "review.json"

    def runner(self):
        result = SelectedDemoRunner(mt5=self.broker, expected_login=123,
            expected_server="Exness-Demo", journal_path=self.root / "execution.sqlite3",
            cost_policy=self.cost, config=selected_config(), execute=True)
        self.addCleanup(result.close)
        return result

    def publish(self, value):
        self.path.write_text(json.dumps(value))

    def test_exact_review_allows_real_lifecycle_and_revocation_preserves_be(self):
        runner = self.runner()
        self.publish(review_fixture(runner, self.broker.now))
        install_execution_review(runner, self.path, now=self.broker.now)
        result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "FILLED", result)
        self.assertEqual(self.broker.order_send.call_count, 1)
        self.path.unlink()
        runner.close()
        restarted = self.runner()
        install_execution_review(restarted, self.path, now=self.broker.now + timedelta(minutes=6))
        self.broker.tick.bid += 10
        self.broker.tick.ask += 10
        self.broker.next_bar()
        result = restarted.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "BE_MOVED", result)
        self.assertEqual(self.broker.order_send.call_count, 2)

    def test_unqualified_or_mismatched_review_never_grants_entry(self):
        runner = self.runner()
        original = review_fixture(runner, self.broker.now)
        for failure in ("candidate", "account", "cohort", "blocker", "owner", "confirmation", "stale"):
            with self.subTest(failure=failure):
                review = deepcopy(original)
                report = review["readiness"]
                if failure == "candidate":
                    report["contract_id"] = "1af968e9ac6a26ea"
                elif failure == "account":
                    report["account_fingerprint"] = "another-account"
                elif failure == "cohort":
                    report["cohort"]["release_hash"] = "f" * 64
                elif failure == "blocker":
                    report["blockers"] = ["fresh_broker_quote_missing"]
                elif failure == "owner":
                    review["owner_authorized"] = False
                elif failure == "confirmation":
                    review["confirmations"]["cost_tariff_swap_calendar_reviewed"] = False
                else:
                    report["captured_utc"] = (self.broker.now - timedelta(minutes=6)).isoformat()
                review["readiness_sha256"] = canonical_hash(report)
                self.publish(review)
                with self.assertRaisesRegex(ValueError, "selected_execution_review_invalid"):
                    install_execution_review(runner, self.path, now=self.broker.now)
                self.broker.order_send.assert_not_called()

    def test_removing_review_after_start_blocks_a_new_entry(self):
        runner = self.runner()
        self.publish(review_fixture(runner, self.broker.now))
        install_execution_review(runner, self.path, now=self.broker.now)
        self.path.unlink()
        result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertEqual(result["reason"], "selected_execution_review_invalid")
        self.broker.order_send.assert_not_called()
