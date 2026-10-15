"""Focused causal and adverse-fill checks for reconstructed Relick variants."""

import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from scripts.research.relick_variants import (
    EMA_SPEC,
    GRID_HARD_STOP,
    ema_stoch_signals,
    grid_signals,
    simulate_grid,
)


class RelickVariantsTests(unittest.TestCase):
    def test_ema_stoch_uses_only_completed_prefix(self):
        rng = np.random.default_rng(11)
        close = 2000 + np.cumsum(rng.normal(0, 2, 120))
        frame = pd.DataFrame(
            {
                "open": close - 0.2,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "atr": 2.0,
            },
            index=pd.date_range("2025-01-01", periods=120, freq="15min", tz="UTC"),
        )
        short = frame.iloc[:90]
        assert_frame_equal(ema_stoch_signals(short), ema_stoch_signals(frame).iloc[:90])
        self.assertEqual((EMA_SPEC.sl, EMA_SPEC.tp), (2.0, 2.0))

    def test_rsi_zone_entry_rejects_gap_and_repeated_zone(self):
        frame = pd.DataFrame(
            {"rsi": [50, 29, 27, 60, 72], "atr": 1.0, "high": 101.0, "low": 99.0},
            index=pd.date_range("2025-01-01", periods=5, freq="15min", tz="UTC"),
        )
        self.assertEqual(grid_signals(frame).direction.tolist(), [0, 1, 0, 0, -1])
        gapped = frame.iloc[[0, 2, 3, 4]]
        self.assertEqual(grid_signals(gapped).direction.tolist(), [0, 0, 0, -1])

    def test_grid_same_minute_stop_beats_basket_target(self):
        timestamp = pd.Timestamp("2025-01-01T00:15:00Z")
        bid = pd.DataFrame(
            [[100.0, 110.0, 40.0, 100.0]],
            columns=["open", "high", "low", "close"],
            index=pd.DatetimeIndex([timestamp]),
        )
        m1 = bid.add_prefix("bid_").join((bid + 0.2).add_prefix("ask_"))
        signals = pd.DataFrame(
            {"direction": [1]}, index=pd.DatetimeIndex([timestamp - pd.Timedelta(minutes=15)])
        )
        trades, balance, dd = simulate_grid(m1, signals)
        self.assertEqual(trades.iloc[0].reason, "HARD_STOP")
        self.assertAlmostEqual(trades.iloc[0].net, -GRID_HARD_STOP)
        self.assertAlmostEqual(balance, 100 - GRID_HARD_STOP)
        self.assertGreaterEqual(dd, GRID_HARD_STOP)

    def test_grid_gap_can_exceed_hard_stop_and_halts_exhausted_account(self):
        timestamps = pd.date_range("2025-01-01T00:15:00Z", periods=2, freq="min")
        bid = pd.DataFrame(
            [[100.0, 100.0, 100.0, 100.0], [30.0, 30.0, 30.0, 30.0]],
            columns=["open", "high", "low", "close"],
            index=timestamps,
        )
        m1 = bid.add_prefix("bid_").join((bid + 0.2).add_prefix("ask_"))
        signals = pd.DataFrame(
            {"direction": [1]}, index=pd.DatetimeIndex([timestamps[0] - pd.Timedelta(minutes=15)])
        )
        trades, balance, _ = simulate_grid(m1, signals)
        self.assertEqual(trades.iloc[0].reason, "HARD_STOP_GAP")
        self.assertLess(trades.iloc[0].net, -GRID_HARD_STOP)
        self.assertEqual(len(simulate_grid(m1, signals, starting_balance=0)[0]), 0)
        self.assertEqual(len(simulate_grid(m1, signals, starting_balance=54)[0]), 0)


if __name__ == "__main__":
    unittest.main()
