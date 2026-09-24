"""Foundation scenario 7: nearest opposing pool TP + min R / consumed pools."""

from __future__ import annotations

import unittest

from scripts.smc.liquidity import select_nearest_opposing_pool_tp
from scripts.smc.types import Direction, LiquidityLevels


class NearestPoolTpTests(unittest.TestCase):
    def setUp(self):
        self.liq = LiquidityLevels(
            asian_high=2510.0,
            asian_low=2490.0,
            pdh=2520.0,
            pdl=2480.0,
            date_str="2026-09-16",
            london_high=2515.0,
            london_low=2485.0,
        )

    def test_buy_selects_nearest_above_entry_not_farther_pdh(self):
        tp, name = select_nearest_opposing_pool_tp(
            Direction.BUY,
            entry_price=2500.0,
            sl_distance=5.0,
            liquidity=self.liq,
            min_r=1.5,
        )
        self.assertEqual(name, "asian_high")
        self.assertEqual(tp, 2510.0)

    def test_buy_rejects_when_nearest_r_below_min(self):
        tp, reason = select_nearest_opposing_pool_tp(
            Direction.BUY,
            entry_price=2500.0,
            sl_distance=10.0,  # asian_high R = 1.0 < 1.5
            liquidity=self.liq,
            min_r=1.5,
        )
        self.assertIsNone(tp)
        self.assertIn("R", reason)
        self.assertIn("< 1.5", reason)

    def test_consumed_nearest_skips_to_next_eligible(self):
        tp, name = select_nearest_opposing_pool_tp(
            Direction.BUY,
            entry_price=2500.0,
            sl_distance=5.0,
            liquidity=self.liq,
            min_r=1.5,
            consumed_levels={2510.0},
        )
        self.assertEqual(name, "london_high")
        self.assertEqual(tp, 2515.0)

    def test_sell_selects_nearest_below_entry(self):
        tp, name = select_nearest_opposing_pool_tp(
            Direction.SELL,
            entry_price=2500.0,
            sl_distance=5.0,
            liquidity=self.liq,
            min_r=1.5,
        )
        self.assertEqual(name, "asian_low")
        self.assertEqual(tp, 2490.0)

    def test_no_candidates_beyond_entry(self):
        emptyish = LiquidityLevels(
            asian_high=2490.0,
            asian_low=2510.0,
            pdh=None,
            pdl=None,
            date_str="2026-09-16",
            london_high=None,
            london_low=None,
        )
        tp, reason = select_nearest_opposing_pool_tp(
            Direction.BUY,
            entry_price=2500.0,
            sl_distance=5.0,
            liquidity=emptyish,
            min_r=1.5,
        )
        self.assertIsNone(tp)
        self.assertIn("no opposing pool", reason)


if __name__ == "__main__":
    unittest.main()
