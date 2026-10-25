"""Armed Demo trial waits for prospective bars and retains broker lifecycle."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.c22_selected.execution import canonical_hash, install_execution_review
from scripts.c22_selected.runner import SelectedDemoRunner
from scripts.c22_selected.strategy import CANDIDATE_ID, MAGIC, SNAPSHOT
from tests.demo.test_c22_selected_runner import SelectedBroker, selected_config
from tests.demo.test_demo_containment import policy_v2


def monday_broker(direction):
    broker = SelectedBroker(direction)
    target = datetime(2026, 10, 26, 12, 0, 0, 500000, tzinfo=timezone.utc)
    shift = target - broker.now
    assert shift.total_seconds() % (4 * 3600) == 0
    milliseconds = int(shift.total_seconds() * 1000)
    broker.now += shift
    broker.tick.time_msc += milliseconds
    for rate in broker.rates:
        rate["time"] += milliseconds // 1000
    for deal in broker.deals:
        deal.time_msc += milliseconds
        deal.time = deal.time_msc // 1000
    for name, value in (("swap_mode", 1), ("swap_long", -490.8),
                        ("swap_short", 0), ("swap_rollover3days", 3)):
        setattr(broker.info, name, value)
    return broker


def armed_review(runner, now):
    approved = now - timedelta(seconds=60)
    report = {
        "captured_utc": approved.isoformat(), "status": "ARMED_DEMO_TRIAL_WITH_LIMITATIONS",
        "execution_authorized": False, "snapshot": SNAPSHOT,
        "contract_id": CANDIDATE_ID, "magic": MAGIC, "account_fingerprint": runner.fingerprint,
        "cohort": {"release_hash": runner.release_hash,
                   "config_hash": runner.journal.audit_context["config_hash"]},
        "input_sha256": {"policy": canonical_hash(runner.policy),
                         "broker": "b" * 64, "parity": "c" * 64},
        "limitations": ["COST_INCONCLUSIVE", "SWAP_ENTITLEMENT_UNKNOWN",
                        "BROKER_FEED_PARITY_NOT_ESTABLISHED", "SHADOW_WAIT_WAIVED"],
    }
    return {
        "version": 1, "scope": "SELECTED_DEMO_ARMED_TRIAL", "owner_authorized": True,
        "owner_instruction": "Synthetic owner authorization for actual Monday Demo trial",
        "approved_utc": approved.isoformat(), "arm_not_before_utc": "2026-10-25T17:00:00+00:00",
        "readiness": report, "readiness_sha256": canonical_hash(report),
        "confirmations": {name: True for name in (
            "exact_demo_identity_and_flat_verified",
            "exact_strategy_sources_and_archive_agreement_reviewed",
            "regular_swap_assumptions_and_cost_drift_guard_reviewed",
            "single_sender_backup_restore_reviewed",
        )},
    }


class ArmedTrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def runner(self, broker, *, name="execution"):
        costs = policy_v2(broker.now, broker.info) | {
            "status": "CONSERVATIVE_REGULAR_SWAP_DEMO_ASSUMPTIONS",
            "swap_entitlement": "UNKNOWN", "research_economic_qualification": "COST_INCONCLUSIVE",
            "execution_authorized": False,
        }
        runner = SelectedDemoRunner(mt5=broker, expected_login=123, expected_server="Exness-Demo",
            journal_path=self.root / (name + ".sqlite3"), cost_policy=costs,
            config=selected_config(), execute=True)
        self.addCleanup(runner.close)
        return runner

    def publish(self, review, *, name="review"):
        path = self.root / (name + ".json")
        path.write_text(json.dumps(review))
        return path

    def test_armed_trial_sends_both_sides_only_on_a_new_completed_bar(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                broker = monday_broker(direction)
                runner = self.runner(broker, name=str(direction))
                review = armed_review(runner, broker.now)
                path = self.publish(review, name=str(direction))
                install_execution_review(runner, path, now=broker.now)
                result = runner.cycle(now=broker.now)
                self.assertEqual(result["status"], "FILLED", result)
                self.assertTrue(result["execute"])
                self.assertEqual(broker.order_send.call_count, 1)
                self.assertEqual(broker.order_send.call_args.args[0]["type"], 0 if direction == 1 else 1)
                runner.close()

    def test_armed_start_waits_for_window_and_same_review_restarts_after_six_minutes(self):
        broker = monday_broker(1)
        runner = self.runner(broker)
        review = armed_review(runner, broker.now)
        review["arm_not_before_utc"] = (broker.now + timedelta(hours=1)).isoformat()
        path = self.publish(review)
        install_execution_review(runner, path, now=broker.now)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["reason"], "armed_trial_not_started", result)
        broker.order_send.assert_not_called()
        runner.close()
        broker.now += timedelta(minutes=6)
        broker.tick.time_msc += 6 * 60 * 1000
        restarted = self.runner(broker)
        # Reuse the actual policy bytes from first acceptance, not a timestamp
        # renewal created by the fixture's constructor.
        restarted.policy = runner.policy
        install_execution_review(restarted, path, now=broker.now)
        result = restarted.cycle(now=broker.now)
        self.assertEqual(result["reason"], "armed_trial_not_started", result)
        broker.order_send.assert_not_called()

    def test_historical_bootstrap_bar_cannot_be_the_first_trial_order(self):
        broker = monday_broker(1)
        runner = self.runner(broker)
        review = armed_review(runner, broker.now)
        review["approved_utc"] = (broker.now - timedelta(milliseconds=100)).isoformat()
        path = self.publish(review)
        install_execution_review(runner, path, now=broker.now)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["reason"], "armed_trial_new_closed_m15_required", result)
        broker.order_send.assert_not_called()

    def test_changed_account_cost_or_missing_limitations_never_grant_trial_entry(self):
        broker = monday_broker(1)
        runner = self.runner(broker)
        original = armed_review(runner, broker.now)
        for failure in ("account", "policy", "entitlement", "qualification", "limitations", "confirmation", "naive_start"):
            with self.subTest(failure=failure):
                review = deepcopy(original)
                policy = deepcopy(runner.policy)
                if failure == "account":
                    review["readiness"]["account_fingerprint"] = "different-account"
                elif failure == "policy":
                    review["readiness"]["input_sha256"]["policy"] = "d" * 64
                elif failure == "entitlement":
                    runner.policy["swap_entitlement"] = "QUALIFIED"
                    review["readiness"]["input_sha256"]["policy"] = canonical_hash(runner.policy)
                elif failure == "qualification":
                    runner.policy["research_economic_qualification"] = "PASS"
                    review["readiness"]["input_sha256"]["policy"] = canonical_hash(runner.policy)
                elif failure == "limitations":
                    review["readiness"]["limitations"].remove("BROKER_FEED_PARITY_NOT_ESTABLISHED")
                elif failure == "confirmation":
                    review["confirmations"]["regular_swap_assumptions_and_cost_drift_guard_reviewed"] = False
                else:
                    review["arm_not_before_utc"] = broker.now.replace(tzinfo=None).isoformat()
                review["readiness_sha256"] = canonical_hash(review["readiness"])
                path = self.publish(review)
                with self.assertRaisesRegex(ValueError, "selected_execution_review_invalid"):
                    install_execution_review(runner, path, now=broker.now)
                runner.policy = policy
                broker.order_send.assert_not_called()

    def test_revoked_trial_permission_does_not_stop_existing_buy_and_sell_be(self):
        for side in (1, -1):
            with self.subTest(side=side):
                broker = monday_broker(side)
                name = str(side)
                runner = self.runner(broker, name=name)
                path = self.publish(armed_review(runner, broker.now), name=name)
                install_execution_review(runner, path, now=broker.now)
                self.assertEqual(runner.cycle(now=broker.now)["status"], "FILLED")
                path.unlink()
                runner.close()
                restarted = self.runner(broker, name=name)
                install_execution_review(restarted, path, now=broker.now)
                broker.tick.bid += side * 10
                broker.tick.ask += side * 10
                broker.next_bar()
                result = restarted.cycle(now=broker.now)
                self.assertEqual(result["status"], "BE_MOVED", result)
                self.assertEqual(broker.order_send.call_count, 2)
                restarted.close()

    def test_revoked_trial_unknown_send_never_resubmits_after_restart(self):
        broker = monday_broker(1)
        broker.order_send.side_effect = lambda request: None
        runner = self.runner(broker)
        path = self.publish(armed_review(runner, broker.now))
        install_execution_review(runner, path, now=broker.now)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "UNKNOWN", result)
        path.unlink()
        runner.close()
        restarted = self.runner(broker)
        install_execution_review(restarted, path, now=broker.now)
        result = restarted.cycle(now=broker.now + timedelta(seconds=1))
        self.assertEqual(result["status"], "UNKNOWN", result)
        self.assertEqual(broker.order_send.call_count, 1)

    def test_trial_still_blocks_actual_negative_swap_discrepancy(self):
        broker = monday_broker(1)
        runner = self.runner(broker)
        prior_day = broker.now - timedelta(days=1)
        runner.policy["reviewed_utc"] = prior_day.isoformat()
        calendar = runner.policy["evidence"]["swap_calendar"]
        calendar["document"]["days"][prior_day.date().isoformat()] = {
            "rollover_utc": prior_day.replace(hour=21, minute=0, second=0, microsecond=0).isoformat(),
            "buy": 0.0, "sell": 0.0,
        }
        calendar["sha256"] = canonical_hash(calendar["document"])
        # Closed selected SELL has a negative swap although this fixture's
        # Sunday/no-rollover interval expects zero. Its cooldown already ended.
        broker.closed_loss(int((broker.now - timedelta(hours=13)).timestamp() * 1000), net=-0.1)
        path = self.publish(armed_review(runner, broker.now))
        install_execution_review(runner, path, now=broker.now)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertEqual(result["reason"], "cost_broker_deal_drift", result)
        broker.order_send.assert_not_called()

    def test_armed_permission_never_allows_a_real_account(self):
        broker = monday_broker(1)
        runner = self.runner(broker)
        path = self.publish(armed_review(runner, broker.now))
        install_execution_review(runner, path, now=broker.now)
        broker.account.trade_mode = 2
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertEqual(result["reason"], "demo_identity_required", result)
        broker.order_send.assert_not_called()

    def test_first_armed_acceptance_rejects_stale_evidence(self):
        broker = monday_broker(1)
        runner = self.runner(broker)
        review = armed_review(runner, broker.now)
        stamp = (broker.now - timedelta(minutes=6)).isoformat()
        review["approved_utc"] = stamp
        review["readiness"]["captured_utc"] = stamp
        review["readiness_sha256"] = canonical_hash(review["readiness"])
        with self.assertRaisesRegex(ValueError, "selected_execution_review_invalid"):
            install_execution_review(runner, self.publish(review), now=broker.now)
        broker.order_send.assert_not_called()

    def test_changed_raw_review_bytes_cannot_reuse_an_old_armed_acceptance(self):
        broker = monday_broker(1)
        runner = self.runner(broker)
        path = self.publish(armed_review(runner, broker.now))
        install_execution_review(runner, path, now=broker.now)
        original_policy = deepcopy(runner.policy)
        runner.close()
        path.write_text(path.read_text() + "\n")
        broker.now += timedelta(minutes=6)
        broker.tick.time_msc += 6 * 60 * 1000
        restarted = self.runner(broker)
        restarted.policy = original_policy
        with self.assertRaisesRegex(ValueError, "selected_execution_review_invalid"):
            install_execution_review(restarted, path, now=broker.now)
        broker.order_send.assert_not_called()
