"""B2 slice 1: BUY intrabar break-even trigger, observe-only (no trading behaviour change)."""

from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.c22_selected.execution import install_execution_review
from scripts.c22_selected.runner import SelectedDemoRunner
from tests.demo.test_c22_selected_armed_trial import armed_review, monday_broker
from tests.demo.test_c22_selected_runner import selected_config
from tests.demo.test_demo_containment import policy_v2

OBSERVE = {"buy_intrabar_be": "observe"}


class SelectedIntrabarBeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def runner(self, broker, name, *, management=OBSERVE, restart=False, policy=None):
        costs = policy or (policy_v2(broker.now, broker.info) | {
            "status": "CONSERVATIVE_REGULAR_SWAP_DEMO_ASSUMPTIONS", "swap_entitlement": "UNKNOWN",
            "research_economic_qualification": "COST_INCONCLUSIVE", "execution_authorized": False})
        config = selected_config()
        if management is not None:
            config["management"] = dict(management)
        runner = SelectedDemoRunner(mt5=broker, expected_login=123, expected_server="Exness-Demo",
            journal_path=self.root / name / "execution.sqlite3", cost_policy=costs, config=config, execute=True)
        self.addCleanup(runner.close)
        review = self.root / (name + ".review.json")
        if not restart:
            review.write_text(json.dumps(armed_review(runner, broker.now)))
        install_execution_review(runner, review, now=broker.now)
        return runner

    def filled(self, direction, name, **kw):
        broker = monday_broker(direction)
        runner = self.runner(broker, name, **kw)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "FILLED", result)
        return broker, runner

    @staticmethod
    def intrabar(broker, direction, *, move=10, seconds=3, age_ms=400):
        broker.tick.bid += direction * move
        broker.tick.ask += direction * move
        broker.now += timedelta(seconds=seconds)
        broker.tick.time_msc = int(broker.now.timestamp() * 1000) - age_ms

    @staticmethod
    def kinds(runner):
        return [json.loads(r[0])["kind"] for r in runner.journal.conn.execute("SELECT payload FROM events ORDER BY id")]

    def test_buy_intrabar_profit_is_observed_without_any_order_change(self):
        broker, runner = self.filled(1, "buy-observe")
        sends = broker.order_send.call_count
        self.intrabar(broker, 1)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "MANAGING", result)
        self.assertEqual(broker.order_send.call_count, sends)
        active = runner.journal.get("active")
        self.assertFalse(active.get("protection_active"))
        self.assertEqual(active["intrabar_observed"]["source"], "intrabar")
        self.assertEqual(self.kinds(runner), ["FILLED", "BE_TRIGGER_INTRABAR_OBSERVED"])
        # Observed once per position; later fresh quotes add nothing.
        self.intrabar(broker, 1, move=1)
        runner.cycle(now=broker.now)
        self.assertEqual(self.kinds(runner).count("BE_TRIGGER_INTRABAR_OBSERVED"), 1)

    def test_bar_close_be_still_moves_buy_after_observation(self):
        broker, runner = self.filled(1, "buy-then-bar")
        self.intrabar(broker, 1)
        runner.cycle(now=broker.now)
        broker.next_bar()
        moved = runner.cycle(now=broker.now)
        self.assertIn(moved["status"], ("BE_MOVED", "UNKNOWN"), moved)
        self.assertIn("BE_TRIGGER_INTRABAR_OBSERVED", self.kinds(runner))

    def test_sell_is_never_evaluated_intrabar(self):
        broker, runner = self.filled(-1, "sell-observe")
        sends = broker.order_send.call_count
        calls = broker.order_calc_profit.call_count if hasattr(broker.order_calc_profit, "call_count") else None
        self.intrabar(broker, -1)
        runner.cycle(now=broker.now)
        self.assertEqual(broker.order_send.call_count, sends)
        self.assertNotIn("intrabar_observed", runner.journal.get("active"))
        self.assertEqual(self.kinds(runner), ["FILLED"])
        if calls is not None:
            self.assertEqual(broker.order_calc_profit.call_count, calls)

    def test_stale_intrabar_quote_is_skipped(self):
        broker, runner = self.filled(1, "buy-stale")
        self.intrabar(broker, 1, age_ms=6000)
        runner.cycle(now=broker.now)
        self.assertNotIn("intrabar_observed", runner.journal.get("active"))

    def test_below_one_r_is_not_observed(self):
        broker, runner = self.filled(1, "buy-small")
        self.intrabar(broker, 1, move=0.5)
        runner.cycle(now=broker.now)
        self.assertNotIn("intrabar_observed", runner.journal.get("active"))

    def test_management_off_is_identical_to_native(self):
        broker, runner = self.filled(1, "buy-off", management=None)
        self.intrabar(broker, 1)
        runner.cycle(now=broker.now)
        self.assertNotIn("intrabar_observed", runner.journal.get("active"))
        self.assertEqual(self.kinds(runner), ["FILLED"])

    def test_act_mode_is_rejected_under_native_contract(self):
        # Invalid management blocks new entries (source error) but never enables acting.
        broker = monday_broker(1)
        runner = self.runner(broker, "buy-act", management={"buy_intrabar_be": "act"})
        self.assertEqual(runner.strategy.source_error, "source_drift")
        self.assertIsNone(runner.strategy.intrabar_protect(1))
        for bad in ({"buy_intrabar_be": "observe", "extra": 1}, {"buy_intrabar_be": "on"}, "observe"):
            config = selected_config() | {"management": bad}
            with self.assertRaises(ValueError):
                from scripts.c22_selected.strategy import verify_sources
                verify_sources(config)

    def test_observation_survives_restart_without_duplicate(self):
        broker, runner = self.filled(1, "buy-restart")
        self.intrabar(broker, 1)
        runner.cycle(now=broker.now)
        policy = runner.policy
        runner.close()
        resumed = self.runner(broker, "buy-restart", restart=True, policy=policy)
        self.intrabar(broker, 1, move=1)
        resumed.cycle(now=broker.now)
        self.assertEqual(self.kinds(resumed).count("BE_TRIGGER_INTRABAR_OBSERVED"), 1)


if __name__ == "__main__":
    unittest.main()
