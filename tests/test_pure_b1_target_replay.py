"""Target replay must apply the same cost-inclusive cap as Pure B1 admission."""

import unittest

import numpy as np
import pandas as pd

from scripts.research.pure_b1_target_replay import replay_target


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


if __name__ == "__main__":
    unittest.main()
