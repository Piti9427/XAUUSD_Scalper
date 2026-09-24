import unittest

from scripts.smc.liquidity import select_nearest_opposing_pool_tp
from scripts.smc.types import Direction, LiquidityLevels


class NearestOpposingPoolTpTests(unittest.TestCase):
    def setUp(self):
        self.liquidity = LiquidityLevels(
            asian_high=2050.0,
            asian_low=2000.0,
            pdh=2060.0,
            pdl=1990.0,
            date_str="2026-03-02",
            london_high=2055.0,
            london_low=2005.0,
        )

    def test_buy_selects_nearest_pool_above_entry(self):
        tp, reason = select_nearest_opposing_pool_tp(
            Direction.BUY,
            entry_price=2014.0,
            sl_distance=4.0,
            liquidity=self.liquidity,
            min_r=1.5,
        )
        self.assertEqual(tp, 2050.0)
        self.assertIn("asian_high", reason)

    def test_sell_selects_nearest_pool_below_entry(self):
        tp, reason = select_nearest_opposing_pool_tp(
            Direction.SELL,
            entry_price=2040.0,
            sl_distance=4.0,
            liquidity=self.liquidity,
            min_r=1.5,
        )
        self.assertEqual(tp, 2005.0)
        self.assertIn("london_low", reason)

    def test_rejects_when_nearest_r_below_minimum(self):
        tp, reason = select_nearest_opposing_pool_tp(
            Direction.BUY,
            entry_price=2048.0,
            sl_distance=4.0,
            liquidity=LiquidityLevels(
                asian_high=2050.0,
                asian_low=2000.0,
                pdh=2050.5,
                pdl=1990.0,
                date_str="2026-03-02",
            ),
            min_r=1.5,
        )
        self.assertIsNone(tp)
        self.assertIn("R", reason)

    def test_skips_consumed_pools(self):
        tp, reason = select_nearest_opposing_pool_tp(
            Direction.BUY,
            entry_price=2014.0,
            sl_distance=4.0,
            liquidity=self.liquidity,
            min_r=1.5,
            consumed_levels={2050.0},
        )
        self.assertEqual(tp, 2055.0)
        self.assertIn("london_high", reason)


if __name__ == "__main__":
    unittest.main()
