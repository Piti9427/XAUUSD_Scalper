"""Causal and contract tests for the one declared top-down research variant."""

import unittest

import numpy as np
import pandas as pd

from scripts.research.mtf_topdown import (
    BASE,
    NAME,
    SPEC,
    combine_entry_events,
    context_any_mask,
    donchian_direction,
    ema_direction,
    last_closed_state,
    m30_events_at_m15_close,
    weekly_bid_bars,
)


class TopdownResearchTests(unittest.TestCase):
    def test_contract_reuses_sourced_donchian_exit_without_parameter_grid(self):
        self.assertNotEqual(NAME, BASE.name)
        self.assertEqual((SPEC.lookback, SPEC.fast, SPEC.slow), (20, 20, 50))
        self.assertEqual((SPEC.sl, SPEC.tp, SPEC.timeframe, SPEC.entry), (2.0, 2.0, 15, "market"))

    def test_weekly_bar_requires_full_utc_monday_week(self):
        index = pd.date_range("2024-01-01", periods=7 * 24 * 60, freq="min", tz="UTC")
        m1 = pd.DataFrame(
            {
                "bid_open": 2000.0,
                "bid_high": 2001.0,
                "bid_low": 1999.0,
                "bid_close": 2000.0,
            },
            index=index,
        )
        week = weekly_bid_bars(m1)
        self.assertEqual(list(week.index), [pd.Timestamp("2024-01-01", tz="UTC")])
        self.assertEqual(float(week.iloc[0].close), 2000.0)
        self.assertTrue(weekly_bid_bars(m1.iloc[:-1]).empty)

    def test_weekly_state_is_unavailable_until_close_and_expires_if_missing(self):
        state = pd.Series([1], index=pd.DatetimeIndex(["2024-01-01"], tz="UTC"))
        times = pd.DatetimeIndex(
            [
                "2024-01-07 23:45",
                "2024-01-08 00:00",
                "2024-01-14 23:45",
                "2024-01-15 00:15",
            ],
            tz="UTC",
        )
        aligned = last_closed_state(state, pd.Timedelta(days=7), times)
        self.assertEqual(aligned.tolist(), [0, 1, 1, 0])

    def test_missing_weekly_history_stays_neutral(self):
        state = pd.Series(dtype=int, index=pd.DatetimeIndex([], tz="UTC"))
        times = pd.DatetimeIndex(["2024-01-08"], tz="UTC")
        self.assertEqual(last_closed_state(state, pd.Timedelta(days=7), times).tolist(), [0])

    def test_donchian_state_persists_until_opposite_break(self):
        index = pd.date_range("2024-01-01", periods=23, freq="h", tz="UTC")
        frame = pd.DataFrame(
            {"high": [101.0] * 23, "low": [99.0] * 23, "close": [100.0] * 23}, index=index
        )
        frame.loc[index[20], ["high", "close"]] = [103.0, 102.0]
        frame.loc[index[22], ["low", "close"]] = [97.0, 98.0]
        state = donchian_direction(frame)
        self.assertEqual(state.iloc[[19, 20, 21, 22]].tolist(), [0, 1, 1, -1])

    def test_ema_state_waits_for_50_completed_bars(self):
        index = pd.date_range("2024-01-01", periods=55, freq="D", tz="UTC")
        frame = pd.DataFrame({"close": [2000.0 + i for i in range(55)]}, index=index)
        result = ema_direction(frame)
        self.assertEqual(result.iloc[:49].tolist(), [0] * 49)
        self.assertEqual(result.iloc[49], 1)
        self.assertEqual(result.iloc[49], ema_direction(frame.iloc[:50]).iloc[-1])

    def test_context_any_requires_breakout_complete_w1_d1_and_matching_setup(self):
        direction = np.array([0, 1, -1, 1, 1, 1, -1])
        w1 = np.array([1, 1, 1, 0, 1, 1, 1])
        d1 = np.array([1, -1, -1, 1, 0, -1, -1])
        h4 = np.array([1, 1, -1, 1, 1, -1, -1])
        h1 = np.array([1, 1, -1, 1, 1, 1, -1])
        m30 = np.array([1, 1, -1, 1, 1, 1, -1])
        result = context_any_mask(direction, w1, d1, h4, h1, m30)
        self.assertEqual(result.tolist(), [False, True, True, False, False, False, True])

    def test_dual_entry_uses_only_m30_close_and_abstains_on_conflict(self):
        m30_frame = pd.DataFrame(index=pd.DatetimeIndex(["2025-01-01 10:00"], tz="UTC"))
        m30_events = pd.DataFrame({"direction": [1]}, index=m30_frame.index)
        m15_close = pd.DatetimeIndex(["2025-01-01 10:15", "2025-01-01 10:30"], tz="UTC")
        mapped = m30_events_at_m15_close(m30_frame, m30_events, m15_close)
        self.assertEqual(mapped.tolist(), [0, 1])
        self.assertEqual(combine_entry_events([0, 1, -1], [1, 1, 1]).tolist(), [1, 1, 0])


if __name__ == "__main__":
    unittest.main()
