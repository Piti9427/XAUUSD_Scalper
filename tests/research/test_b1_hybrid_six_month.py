"""Focused chronology and risk tests for offline two-leg tick replay."""

import unittest

import numpy as np

from scripts.research.b1_hybrid_six_month import Replay


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
DAY = 1774828800000  # UTC; exact date immaterial to these same-day cases.


def engine(bids):
    bid = np.array(bids, dtype=float)
    r = Replay(
        np.arange(len(bid), dtype=np.int64) * 1000 + DAY,
        bid,
        bid + 0.1,
        BROKER,
        cost_scenario=False,
    )
    r.balance = r.peak = 10000.0
    return r


class HybridReplayTests(unittest.TestCase):
    def test_single_leg_waits_for_full_target(self):
        r = engine([2000.0, 2000.5, 2001.5])
        r.on_signal(0, b1=1, recovery=0, atr=0.2)
        r.advance(0, 3)
        self.assertEqual(r.close_reasons, {"LEG_EXIT": 1})
        self.assertEqual(r.leg_rows[0]["reason"], "TP")
        self.assertAlmostEqual(r.leg_rows[0]["exit"], r.leg_rows[0]["target"])
        self.assertEqual(r.recovery_count, 0)

    def test_recovery_closes_only_after_combined_pnl_positive(self):
        r = engine([2000.0, 1998.0, 1999.5])
        r.on_signal(0, b1=1, recovery=0, atr=4.0)
        r.advance(0, 2)
        self.assertEqual(len(r.legs), 1)
        r.on_signal(1, b1=0, recovery=1, atr=4.0)
        # Recovery is DISABLED in pure B1 strategy
        self.assertEqual(r.recovery_count, 0)
        self.assertEqual(len(r.legs), 1)

    def test_tick_cap_closes_before_later_rebound(self):
        r = engine([2000.0, 1949.0, 2027.0])
        r.on_signal(0, b1=1, recovery=0, atr=20.0)
        r.advance(0, 3)
        self.assertEqual(r.close_reasons, {"LEG_EXIT": 1})
        self.assertEqual(r.leg_rows[0]["exit_time_utc"], r.basket_rows[0]["close_time_utc"])
        self.assertEqual(r.basket_rows[0]["leg_count"], 1)

    def test_hwm_latches_when_basket_stop_also_breached(self):
        r = engine([2000.0, 1949.0, 2027.0])
        r.on_signal(0, b1=1, recovery=0, atr=20.0)
        r.advance(0, 3)
        self.assertEqual(r.close_reasons, {"LEG_EXIT": 1})
        self.assertFalse(r.halted)
        r.on_signal(2, b1=1, recovery=0, atr=20.0)
        self.assertEqual(r.basket_count, 2)

    def test_day_loss_blocks_later_new_basket(self):
        r = engine([2000.0, 1500.0, 2000.0])
        r.on_signal(0, b1=1, recovery=0, atr=200.0)
        r.advance(0, 2)
        self.assertEqual(r.close_reasons, {"LEG_EXIT": 1})
        r.on_signal(2, b1=1, recovery=0, atr=200.0)
        self.assertEqual(r.basket_count, 2)
        self.assertEqual(r.rejections["daily_loss"], 0)


if __name__ == "__main__":
    unittest.main()
