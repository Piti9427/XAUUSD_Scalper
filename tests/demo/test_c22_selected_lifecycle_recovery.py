"""Selected public cycles retain uncertain BE and reconcile read-only exits."""

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from scripts.c22_selected.execution import install_execution_review
from scripts.c22_selected.runner import SelectedDemoRunner
from tests.demo.test_c22_selected_armed_trial import armed_review, monday_broker
from tests.demo.test_c22_selected_runner import selected_config
from tests.demo.test_demo_containment import policy_v2


class SelectedLifecycleRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def runner(self, broker, name, *, policy=None, restart=False):
        costs = policy or (policy_v2(broker.now, broker.info) | {
            "status": "CONSERVATIVE_REGULAR_SWAP_DEMO_ASSUMPTIONS",
            "swap_entitlement": "UNKNOWN",
            "research_economic_qualification": "COST_INCONCLUSIVE",
            "execution_authorized": False,
        })
        runner = SelectedDemoRunner(
            mt5=broker, expected_login=123, expected_server="Exness-Demo",
            journal_path=self.root / name / "execution.sqlite3", cost_policy=costs,
            config=selected_config(), execute=True,
        )
        self.addCleanup(runner.close)
        review = self.root / (name + ".review.json")
        if not restart:
            review.write_text(json.dumps(armed_review(runner, broker.now)))
        install_execution_review(runner, review, now=broker.now)
        return runner

    def filled(self, direction, name):
        broker = monday_broker(direction)
        runner = self.runner(broker, name)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "FILLED", result)
        return broker, runner

    @staticmethod
    def close_at_broker(broker, direction):
        broker.now += timedelta(seconds=15)
        broker.tick.time_msc = int(broker.now.timestamp() * 1000)
        broker.send({
            "action": 1, "position": 777, "type": 1 if direction == 1 else 0,
            "volume": 0.01,
            "price": broker.tick.bid if direction == 1 else broker.tick.ask,
        })

    @staticmethod
    def events(runner):
        return [json.loads(row[0]) for row in runner.journal.conn.execute(
            "SELECT payload FROM events ORDER BY id"
        )]

    def test_be_placed_retains_pending_across_restart_until_broker_confirms_both_sides(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                name = f"placed-{direction}"
                broker, runner = self.filled(direction, name)
                broker.tick.bid += direction * 10
                broker.tick.ask += direction * 10
                broker.next_bar()
                broker.order_send.side_effect = lambda request: NS(retcode=10008)
                first = runner.cycle(now=broker.now)
                self.assertEqual(first["status"], "UNKNOWN", first)
                self.assertEqual(first["reason"], "awaiting_be_confirmation")
                pending = runner.journal.get("active")["be_pending"]
                self.assertEqual(broker.order_send.call_count, 2)
                self.assertEqual(runner.cycle(now=broker.now)["status"], "UNKNOWN")
                self.assertEqual(broker.order_send.call_count, 2)
                policy = deepcopy(runner.policy)
                runner.close()
                resumed = self.runner(broker, name, policy=policy, restart=True)
                self.assertEqual(resumed.cycle(now=broker.now)["status"], "UNKNOWN")
                self.assertEqual(broker.order_send.call_count, 2)
                broker.positions[0].sl = pending
                confirmed = resumed.cycle(now=broker.now)
                self.assertEqual(confirmed["status"], "BE_MOVED", confirmed)
                self.assertEqual(resumed.cycle(now=broker.now)["status"], "MANAGING")
                self.assertEqual(broker.order_send.call_count, 2)
                self.assertEqual([event["kind"] for event in self.events(resumed)],
                                 ["FILLED", "BE_MOVED"])
                resumed.close()

    def test_done_be_with_delayed_broker_observation_is_already_no_resend_control(self):
        broker, runner = self.filled(-1, "done-control")
        broker.tick.bid -= 10
        broker.tick.ask -= 10
        broker.next_bar()
        broker.order_send.side_effect = lambda request: NS(retcode=10009)
        first = runner.cycle(now=broker.now)
        self.assertEqual(first["status"], "UNKNOWN", first)
        self.assertIsNotNone(runner.journal.get("active").get("be_pending"))
        runner.cycle(now=broker.now)
        self.assertEqual(broker.order_send.call_count, 2)

    def test_stale_quote_does_not_delay_complete_broker_close_both_sides(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                broker, runner = self.filled(direction, f"stale-{direction}")
                self.close_at_broker(broker, direction)
                result = runner.cycle(now=broker.now + timedelta(minutes=2))
                self.assertEqual(result["status"], "CLOSED", result)
                self.assertEqual(result["net"], -1.0)
                self.assertTrue(result["day_start_valid"])
                self.assertEqual(result["day_start_day"], broker.now.date().isoformat())
                self.assertEqual(result["day_start_source"],
                                 "reconstructed_flat_midnight_from_reconciled_history")
                self.assertIsNone(runner.journal.get("active"))
                self.assertEqual(result["position_protection"], "flat")
                self.assertFalse(result["critical"])
                later = runner.cycle(now=broker.now + timedelta(minutes=6))
                self.assertEqual(later["reason"], "quote_stale")
                self.assertFalse(later["critical"])
                self.assertEqual([event["kind"] for event in self.events(runner)],
                                 ["FILLED", "CLOSED"])
                self.assertTrue(self.events(runner)[-1]["day_start_valid"])
                self.assertEqual(broker.order_send.call_count, 1)
                runner.close()

    def test_disabled_autotrading_does_not_delay_complete_broker_close_both_sides(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                broker, runner = self.filled(direction, f"disabled-{direction}")
                self.close_at_broker(broker, direction)
                broker.terminal_info = lambda: NS(
                    connected=True, trade_allowed=False, tradeapi_disabled=True,
                )
                result = runner.cycle(now=broker.now)
                self.assertEqual(result["status"], "CLOSED", result)
                self.assertIsNone(runner.journal.get("active"))
                self.assertEqual(result["observed_positions"], 0)
                self.assertFalse(result["critical"])
                self.assertEqual(runner.cycle(now=broker.now)["reason"],
                                 "algo_permissions_required")
                self.assertEqual(broker.order_send.call_count, 1)
                runner.close()

    def test_unavailable_symbol_spec_does_not_delay_proven_close(self):
        broker, runner = self.filled(1, "spec")
        self.close_at_broker(broker, 1)
        broker.symbol_info = lambda symbol: None
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "CLOSED", result)
        self.assertIsNone(runner.journal.get("active"))
        self.assertEqual(broker.order_send.call_count, 1)

    def test_held_midnight_close_labels_old_baseline_invalid_without_changing_its_value(self):
        broker, runner = self.filled(-1, "held-midnight")
        original_day = runner.journal.get("day")
        broker.now = (broker.now + timedelta(days=1)).replace(hour=0, minute=0, second=30)
        self.close_at_broker(broker, -1)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "CLOSED", result)
        self.assertEqual(result["day_start"], original_day["equity"])
        self.assertEqual(result["day_start_day"], original_day["day"])
        self.assertFalse(result["day_start_valid"])
        self.assertFalse(self.events(runner)[-1]["day_start_valid"])
        self.assertEqual(runner.journal.get("day"), original_day)
        self.assertEqual(broker.order_send.call_count, 1)

    def test_closure_labels_unproven_baseline_source_or_account_invalid(self):
        for failure in ("source", "account_fingerprint"):
            with self.subTest(failure=failure):
                broker, runner = self.filled(1, "baseline-" + failure)
                baseline = runner.journal.get("day")
                baseline[failure] = "unproven-fixture"
                runner.journal.put("day", baseline)
                self.close_at_broker(broker, 1)
                result = runner.cycle(now=broker.now)
                self.assertEqual(result["status"], "CLOSED", result)
                self.assertEqual(result["day_start"], 200)
                self.assertEqual(result["day_start_day"], broker.now.date().isoformat())
                self.assertFalse(result["day_start_valid"])
                self.assertFalse(self.events(runner)[-1]["day_start_valid"])
                self.assertEqual(broker.order_send.call_count, 1)
                runner.close()

    def test_incomplete_history_never_clears_active_or_sends_again(self):
        broker, runner = self.filled(-1, "history")
        self.close_at_broker(broker, -1)
        full_count = len(broker.deals)
        broker.history_deals_get = lambda *args, **kwargs: tuple(broker.deals[:-1])
        broker.history_deals_total = lambda *args: full_count
        result = runner.cycle(now=broker.now + timedelta(minutes=2))
        self.assertEqual(result["reason"], "history_unknown", result)
        self.assertIsNotNone(runner.journal.get("active"))
        self.assertEqual([event["kind"] for event in self.events(runner)], ["FILLED"])
        self.assertEqual(broker.order_send.call_count, 1)

    def test_unknown_exposure_never_infers_flat_from_complete_exit_history(self):
        broker, runner = self.filled(1, "exposure")
        self.close_at_broker(broker, 1)
        broker.positions_get = lambda **kwargs: None
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["reason"], "exposure_unknown", result)
        self.assertIsNotNone(runner.journal.get("active"))
        self.assertEqual([event["kind"] for event in self.events(runner)], ["FILLED"])
        self.assertEqual(broker.order_send.call_count, 1)

    def test_unknown_intent_resolves_complete_exit_after_restart_without_resending(self):
        broker = monday_broker(-1)
        name = "unknown-closed"
        runner = self.runner(broker, name)
        broker.order_send.side_effect = lambda request: None
        self.assertEqual(runner.cycle(now=broker.now)["status"], "UNKNOWN")
        request = runner.journal.get("active")["request"]
        self.assertNotIn("position_id", runner.journal.get("active"))
        # Broker later reveals that the uncertain intent filled and fully closed.
        broker.send(request)
        self.close_at_broker(broker, -1)
        policy = deepcopy(runner.policy)
        runner.close()
        broker.terminal_info = lambda: NS(
            connected=True, trade_allowed=False, tradeapi_disabled=True,
        )
        resumed = self.runner(broker, name, policy=policy, restart=True)
        result = resumed.cycle(now=broker.now + timedelta(minutes=2))
        self.assertEqual(result["status"], "CLOSED", result)
        self.assertIsNone(resumed.journal.get("active"))
        self.assertEqual(result["net"], -1.0)
        self.assertEqual([event["kind"] for event in self.events(resumed)], ["CLOSED"])
        self.assertEqual(broker.order_send.call_count, 1)

    def test_missing_owned_opening_never_infers_close_from_an_empty_account(self):
        broker, runner = self.filled(1, "opening")
        self.close_at_broker(broker, 1)
        broker.deals = [deal for deal in broker.deals if int(deal.entry) != 0 or int(deal.type) == 2]
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "UNKNOWN", result)
        self.assertIsNotNone(runner.journal.get("active"))
        self.assertEqual([event["kind"] for event in self.events(runner)], ["FILLED"])
        self.assertEqual(broker.order_send.call_count, 1)

    def test_read_only_reconciliation_never_weakens_mutation_or_demo_identity_gates(self):
        for failure in ("permissions", "stale", "real_account"):
            with self.subTest(failure=failure):
                broker, runner = self.filled(1, "gate-" + failure)
                broker.tick.bid += 10
                broker.tick.ask += 10
                broker.next_bar()
                now = broker.now
                expected = "algo_permissions_required"
                if failure == "permissions":
                    broker.terminal_info = lambda: NS(
                        connected=True, trade_allowed=False, tradeapi_disabled=False,
                    )
                elif failure == "stale":
                    now += timedelta(minutes=2)
                    expected = "quote_stale"
                else:
                    broker.account.trade_mode = 2
                    expected = "demo_identity_required"
                result = runner.cycle(now=now)
                self.assertEqual(result["reason"], expected, result)
                self.assertIsNotNone(runner.journal.get("active"))
                self.assertEqual(broker.order_send.call_count, 1)
                runner.close()
