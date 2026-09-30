"""Target replay must apply the same cost-inclusive cap as Pure B1 admission."""

import unittest

import numpy as np
import pandas as pd

from scripts.research.b1_hybrid_six_month import Replay
from scripts.research.pure_b1_target_replay import SCENARIOS, replay_target
from scripts.pure_b1.quote_time import FRESH_QUOTE


BROKER = {
    "trade_tick_size": 0.001,
    "trade_contract_size": 100.0,
    "leverage": 1000,
    "swap_long": 0.0,
    "swap_short": 0.0,
    "swap_mode": 1,
    "swap_rollover3days": 3,
    "point": 0.001,
    "volume_min": 0.01,
    "volume_max": 200.0,
    "volume_step": 0.01,
}


class PureB1TargetReplayTests(unittest.TestCase):
    def test_cost_inclusive_cap_rejects_fee_breaching_order(self):
        signal_open = pd.Timestamp("2026-04-13 06:15", tz="UTC")
        frame = pd.DataFrame(
            {"direction": [1], "atr": [7.6]}, index=pd.DatetimeIndex([signal_open])
        )
        first_tick = int((signal_open + pd.Timedelta(minutes=15)).value // 10**6)
        ticks = (
            np.array([first_tick, first_tick + 1000], dtype=np.int64),
            np.array([2600.0, 2600.0]),
            np.array([2600.1, 2600.1]),
        )
        with_cost, legs, _ = replay_target(frame, ticks, BROKER, cost_scenario=True)
        self.assertEqual(with_cost["basket_count"], 0)
        self.assertEqual(with_cost["cost_inclusive_risk_rejections"], 1)
        self.assertTrue(legs.empty)

        spread_only, _, _ = replay_target(frame, ticks, BROKER, cost_scenario=False)
        self.assertEqual(spread_only["basket_count"], 1)
        self.assertEqual(spread_only["cost_inclusive_risk_rejections"], 0)
        self.assertEqual(spread_only["scenario"], "archival_spread_only")
        self.assertFalse(spread_only["expected_standard_demo_result"])

    def test_fresh_quote_rule_rejects_a_tick_the_archival_window_accepts(self):
        signal_open = pd.Timestamp("2026-04-13 06:15", tz="UTC")
        frame = pd.DataFrame(
            {"direction": [1], "atr": [1.0]}, index=pd.DatetimeIndex([signal_open])
        )
        late = int((signal_open + pd.Timedelta(minutes=15, seconds=120)).value // 10**6)
        ticks = (
            np.array([late, late + 1000], dtype=np.int64),
            np.array([2600.0, 2600.0]),
            np.array([2600.1, 2600.1]),
        )
        archival, _, _ = replay_target(frame, ticks, BROKER, scenario="archival_spread_only")
        fresh, _, _ = replay_target(
            frame, ticks, BROKER, scenario="standard_no_commission_swap_free_current_policy"
        )
        self.assertEqual(archival["basket_count"], 1)
        self.assertEqual(fresh["basket_count"], 0)
        self.assertGreater(fresh["rejections"]["late_quote"], 0)
        self.assertEqual(fresh["quote_rule"], FRESH_QUOTE.name)
        self.assertFalse(fresh["expected_standard_demo_result"])

    def test_day_quota_cannot_block_labeled_replay_and_missing_day_start_does_not_reset(self):
        day = 1_774_828_800_000
        engine = Replay(
            np.array([day, day + 1000], dtype=np.int64),
            np.array([2000.0, 2000.0]),
            np.array([2000.1, 2000.1]),
            BROKER,
            cost_scenario=False,
            signal_day_start=False,
            day_quota_limit=None,
            boundary_day_start_only=True,
        )
        engine.balance = engine.peak = 10000.0
        engine.on_signal(0, 1, 0, 0.2)
        self.assertEqual(engine.rejections["day_start_unknown"], 1)
        self.assertEqual(engine.legs, [])
        self.assertNotIn(day // 86400000, engine.day_start)
        engine.day_start[day // 86400000] = 10000.0
        engine.day_quota[day // 86400000] = 99
        engine.on_signal(0, 1, 0, 0.2)
        self.assertEqual(engine.rejections["daily_quota"], 0)
        self.assertEqual(len(engine.legs), 1)

    def test_required_scenarios_do_not_claim_the_hypothetical_fee_result(self):
        hypothetical = SCENARIOS["archival_hypothetical_0_10r_current_spec_swap"]
        self.assertIn("0.10R", hypothetical["note"])
        self.assertFalse(hypothetical["expected_standard_demo_result"])
        for name in (
            "standard_no_commission_swap_free_current_policy",
            "non_swap_free",
            "slippage_spread_stress",
        ):
            spec = SCENARIOS[name]
            self.assertEqual(spec["quote_rule"], FRESH_QUOTE.name)
            self.assertIsNone(spec["day_quota_limit"])
            self.assertEqual(spec["spread_buffer"], 0.0)
            self.assertEqual(spec["hypothetical_fee_r"], 0.0)
            self.assertFalse(spec["expected_standard_demo_result"])
            self.assertEqual(spec["historical_swap_entitlement"], "missing")
            self.assertEqual(spec["broker_fills"], "missing")


if __name__ == "__main__":
    unittest.main()
