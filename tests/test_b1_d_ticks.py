"""Deterministic account-risk/tick-side checks for B1/D historical replay."""

import unittest
import numpy as np
import pandas as pd
from scripts.research.b1_d_ticks import replay
from scripts.research.strategies import Spec


class TickReplayTests(unittest.TestCase):
    def run_case(self, balance=1000, direction=1, bid=None, ask=None, extra=0, risk_pct=0.005):
        when = pd.Timestamp("2026-09-01T00:15:00Z")
        times = np.array([when.value // 1_000_000, when.value // 1_000_000 + 1000])
        frame = pd.DataFrame({"atr": [1.0]}, index=[when - pd.Timedelta(minutes=15)])
        sig = pd.DataFrame({"direction": [direction]}, index=frame.index)
        spec = Spec("fixture", "donchian", sl=2, tp=2)
        broker = {
            "trade_contract_size": 100.0,
            "volume_step": 0.01,
            "volume_min": 0.01,
            "volume_max": 200.0,
            "trade_tick_size": 0.001,
            "point": 0.001,
            "swap_long": -567.4,
            "swap_short": 0.0,
            "swap_mode": 1,
            "swap_rollover3days": 3,
        }
        return replay(
            times,
            np.array(bid or [2000.0, 2005.0]),
            np.array(ask or [2000.2, 2005.2]),
            frame,
            sig,
            spec,
            broker,
            balance,
            extra,
            risk_pct=risk_pct,
        )

    def test_under_minimum_risk_rejects_instead_of_rounding_up(self):
        log, stats = self.run_case(balance=100)
        self.assertTrue(log.empty)
        self.assertEqual(stats["rejections"]["risk_below_min"], 1)
        self.assertEqual(stats["final_balance"], 100)

    def test_long_enters_ask_and_limit_target_has_no_positive_gap_improvement(self):
        log, stats = self.run_case()
        self.assertAlmostEqual(log.iloc[0].entry, 2000.2)
        self.assertAlmostEqual(log.iloc[0]["exit"], 2004.2)
        self.assertAlmostEqual(log.iloc[0].volume, 0.02)
        self.assertAlmostEqual(stats["final_balance"], 1008)
        self.assertLessEqual(log.iloc[0].risk_money, log.iloc[0].risk_budget)

    def test_short_stops_on_ask_even_when_bid_does_not_touch_stop(self):
        log, stats = self.run_case(direction=-1, bid=[2000.0, 2001.9], ask=[2000.2, 2002.1])
        self.assertEqual(log.iloc[0].reason, "SL")
        self.assertAlmostEqual(log.iloc[0]["exit"], 2002.1)
        self.assertLess(stats["final_balance"], 1000)

    def test_extra_cost_reservation_respects_risk_budget(self):
        log, _ = self.run_case(extra=0.1)
        self.assertLessEqual(
            log.iloc[0].risk_money + log.iloc[0].extra_cost_scenario, log.iloc[0].risk_budget
        )
        self.assertIsNotNone(log.iloc[0].entry_time.tzinfo)

    def test_explicit_risk_override_increases_admitted_volume_without_exceeding_cap(self):
        log, _ = self.run_case(risk_pct=0.01)
        self.assertAlmostEqual(log.iloc[0].risk_budget, 10.0)
        self.assertAlmostEqual(log.iloc[0].volume, 0.05)
        self.assertLessEqual(log.iloc[0].risk_money, 10.0)

    def test_invalid_risk_is_rejected(self):
        for risk in (0.0, -0.01, 1.0, float("nan")):
            with self.subTest(risk=risk), self.assertRaises(ValueError):
                self.run_case(risk_pct=risk)


if __name__ == "__main__":
    unittest.main()
