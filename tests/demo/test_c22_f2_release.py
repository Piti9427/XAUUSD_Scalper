"""F2 (closed-H4 EMA200 distance >= 10 M15 ATR14) + F3 (max 1 net loss per UTC day) release seams."""

from dataclasses import asdict, fields
from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

import numpy as np
import pandas as pd

from scripts.c22_selected import strategy as S
from scripts.research.breakout_models import Rules
from scripts.research.breakout_signals import features
from scripts.research.reward156_tuning import closed_h4_ema
import tests.demo.test_c22_selected_runner as R
from tests.demo.test_c22_selected_strategy import signal_bars


def gate_frame(rows):
    frame = pd.DataFrame(rows, columns=["direction", "close", "macro_ema", "atr"],
                         index=pd.date_range("2026-01-05", periods=len(rows), freq="15min", tz="UTC"))
    frame["macro_blocked"] = False
    return frame


class F2ContractTests(unittest.TestCase):
    def test_contract_fields_and_new_rules_identity(self):
        self.assertEqual(S.CONTRACT["min_macro_distance_atr"], 10.0)
        self.assertIsInstance(S.CONTRACT["min_macro_distance_atr"], float)
        self.assertEqual(S.CONTRACT["max_daily_losses"], 1)
        self.assertEqual(S.SelectedStrategy.max_daily_losses, 1)
        self.assertEqual(S.CANDIDATE_ID, "7fe09f7246068bc9")
        # Everything else in the frozen 26b8 contract is unchanged.
        self.assertEqual((S.CONTRACT["risk_cap"], S.CONTRACT["daily_loss_limit"], S.CONTRACT["cooldown_bars"],
                          S.CONTRACT["stop_atr"], S.CONTRACT["buy_target_rr"], S.CONTRACT["sell_target"],
                          S.CONTRACT["macro_span"]), (0.1, 0.1, 2, 2.5, 3.0, "r1.35", 200))
        self.assertEqual((S.SelectedStrategy.risk_cap, S.SelectedStrategy.daily_loss_limit,
                          S.SelectedStrategy.cooldown_bars), (0.1, 0.1, 2))

    def test_f2_is_not_a_rules_field_so_geometry_is_unchanged(self):
        self.assertNotIn("min_macro_distance_atr", {f.name for f in fields(Rules)})
        cache = S.SelectedBarCache()
        cache.append(signal_bars(-1))
        rules = asdict(cache.rules)
        self.assertEqual(rules["max_daily_losses"], 1)
        self.assertEqual(S._rules_id(Rules(**{**rules, "max_daily_losses": 2})), "26b8bcd69e043653")

    def test_release_config_binds_new_contract(self):
        config = json.loads(S.CONFIG_PATH.read_text())
        S.verify_sources(config)
        self.assertEqual(config["contract_id"], S.CANDIDATE_ID)
        self.assertEqual(config["contract"]["min_macro_distance_atr"], 10.0)
        self.assertEqual(config["contract"]["max_daily_losses"], 1)
        drift = json.loads(json.dumps(config))
        drift["contract"]["min_macro_distance_atr"] = 8.0
        with self.assertRaisesRegex(ValueError, "source_drift"):
            S.verify_sources(drift)


class F2GateTests(unittest.TestCase):
    def test_boundary_and_both_sides(self):
        frame = gate_frame([
            (1, 1100.0, 1000.0, 10.0),     # BUY 10.0 ATR above -> allowed (research drops only < 10)
            (1, 1099.9, 1000.0, 10.0),     # BUY 9.99 ATR -> blocked
            (-1, 900.0, 1000.0, 10.0),     # SELL 10.0 ATR below -> allowed
            (-1, 900.1, 1000.0, 10.0),     # SELL 9.99 ATR -> blocked
            (-1, 700.0, 1000.0, 10.0),     # SELL 30 ATR -> allowed
            (0, 1500.0, 1000.0, 10.0),     # no candidate -> untouched
            (1, 1200.0, 1000.0, np.nan),   # unknown ATR -> fail closed
        ])
        S.apply_macro_distance_gate(frame, 10.0)
        self.assertEqual(frame.direction.tolist(), [1, 0, -1, 0, -1, 0, 0])
        self.assertEqual(frame.macro_distance_blocked.tolist(), [False, True, False, True, False, False, True])
        np.testing.assert_allclose(frame.macro_distance_atr.to_numpy()[:5], [10.0, 9.99, 10.0, 9.99, 30.0])
        self.assertTrue(np.isnan(frame.macro_distance_atr.iloc[5]))

    def test_distance_equals_abs_distance_for_macro_admitted_candidates(self):
        frame = gate_frame([(1, 1250.0, 1000.0, 20.0), (-1, 760.0, 1000.0, 20.0)])
        S.apply_macro_distance_gate(frame, 10.0)
        expected = (frame.close - frame.macro_ema).abs() / frame.atr
        np.testing.assert_allclose(frame.macro_distance_atr.to_numpy(), expected.to_numpy())

    def test_invalid_threshold_fails_closed(self):
        for bad in (0.0, -1.0, 10, float("nan")):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "selected_rules_drift"):
                S.apply_macro_distance_gate(gate_frame([(1, 1.0, 1.0, 1.0)]), bad)

    def test_wait_reason_priority(self):
        row = pd.Series(dict(macro_blocked=True, macro_distance_blocked=False))
        self.assertEqual(S.entry_wait_reason(row), "macro_gate")
        row = pd.Series(dict(macro_blocked=False, macro_distance_blocked=True))
        self.assertEqual(S.entry_wait_reason(row), "macro_distance_too_small")
        row = pd.Series(dict(macro_blocked=False, macro_distance_blocked=False))
        self.assertEqual(S.entry_wait_reason(row), "no_signal")

    def test_cache_distance_matches_research_h4dist_definition(self):
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                source = signal_bars(direction)
                cache = S.SelectedBarCache()
                cache.append(source)
                atr = features(source).atr          # M15 simple-mean TR(14), as research sig.atr
                macro = closed_h4_ema(source, 200)  # last complete H4 bar only, as research sig.macro
                h4dist = direction * (source.close.iloc[-1] - macro.iloc[-1]) / atr.iloc[-1]
                self.assertAlmostEqual(float(cache.row.macro_distance_atr), float(h4dist), places=10)
                self.assertEqual(int(cache.row.direction), direction if h4dist >= 10 else 0)

    def test_blocked_signal_returns_reason_from_decide(self):
        with mock.patch.dict(S.CONTRACT, {"min_macro_distance_atr": 1e9}):
            cache = S.SelectedBarCache()
            cache.append(signal_bars(-1))
        self.assertEqual(int(cache.row.direction), 0)
        self.assertEqual(int(cache.row.raw_direction), -1)
        self.assertTrue(bool(cache.row.macro_distance_blocked))
        self.assertEqual(S.decide(cache, 100.0, 100.2, {}, {}, 400.0), "macro_distance_too_small")


class F2RunnerTests(unittest.TestCase):
    runner = R.SelectedRunnerTests.runner

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "selected.sqlite3"

    def test_f2_block_is_a_normal_wait_and_never_sends(self):
        self.enterContext(mock.patch.dict(S.CONTRACT, {"min_macro_distance_atr": 1e9}))
        for side in (1, -1):
            with self.subTest(side=side):
                self.path = Path(self.temp.name) / f"f2-{side}.sqlite3"
                broker = R.SelectedBroker(side)
                runner = self.runner(broker, execute=True)
                result = runner.cycle(now=broker.now)
                self.assertEqual((result["status"], result["reason"]), ("WAIT", "macro_distance_too_small"), result)
                self.assertEqual(result["min_macro_distance_atr"], 1e9)
                self.assertLess(result["macro_distance_atr"], 1e9)  # observed distance is still journaled
                self.assertEqual(result["entry_availability"]["status"], "WAITING_SIGNAL")
                broker.order_send.assert_not_called()
                runner.close()

    def test_signal_beyond_threshold_still_admits(self):
        broker = R.SelectedBroker(-1)
        result = self.runner(broker).cycle(now=broker.now)
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)
        self.assertGreaterEqual(result["macro_distance_atr"], 10.0)

    def test_f2_never_touches_open_position_management(self):
        for side in (1, -1):
            with self.subTest(side=side):
                self.path = Path(self.temp.name) / f"be-{side}.sqlite3"
                broker = R.SelectedBroker(side)
                runner = self.runner(broker, execute=True)
                self.assertEqual(runner.cycle(now=broker.now)["status"], "FILLED")
                with mock.patch.dict(S.CONTRACT, {"min_macro_distance_atr": 1e9}):
                    broker.tick.bid += side * 10
                    broker.tick.ask += side * 10
                    self.assertEqual(runner.cycle(now=broker.now)["status"], "MANAGING")
                    broker.next_bar()
                    result = runner.cycle(now=broker.now)
                self.assertEqual(result["status"], "BE_MOVED", result)
                self.assertEqual(broker.order_send.call_count, 2)
                runner.close()

    def test_one_net_loss_today_blocks_new_entry(self):
        broker = R.SelectedBroker()
        broker.closed_loss(broker.tick.time_msc - 60 * 60 * 1000)
        result = self.runner(broker).cycle(now=broker.now)
        self.assertEqual((result["status"], result["reason"]), ("BLOCKED", "max_daily_losses"), result)
        self.assertEqual(result["entry_availability"]["known_blockers"][0]["resume_not_before_utc"],
                         (broker.now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat())
        broker.order_send.assert_not_called()

    def test_loss_on_previous_utc_day_does_not_count(self):
        broker = R.SelectedBroker()
        midnight = broker.now.replace(hour=0, minute=0, second=0, microsecond=0)
        broker.closed_loss(int((midnight - timedelta(minutes=1)).timestamp() * 1000))
        result = self.runner(broker).cycle(now=broker.now)
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)

    def test_net_win_today_does_not_count(self):
        broker = R.SelectedBroker()
        broker.closed_loss(broker.tick.time_msc - 60 * 60 * 1000, net=0.5)
        result = self.runner(broker).cycle(now=broker.now)
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)


if __name__ == "__main__":
    unittest.main()
