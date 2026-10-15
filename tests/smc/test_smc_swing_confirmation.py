"""Story 17: swing confirmation times for 5-bar fractals."""

import unittest
from datetime import datetime, timezone, timedelta

from scripts.smc.structure import (
    pivot_confirmation_time,
    record_confirmed_pivots,
    available_confirmed_pivots,
)


class SwingConfirmationTimeTests(unittest.TestCase):
    def test_confirmation_is_second_right_hand_bar(self):
        base = datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc)
        times = [base + timedelta(minutes=5 * i) for i in range(10)]
        # Pivot at index 3 confirms when bar 5 closes.
        confirmed = pivot_confirmation_time(3, times)
        self.assertEqual(confirmed, times[5])

    def test_record_confirmed_pivots_includes_times(self):
        base = datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc)
        times = [base + timedelta(minutes=5 * i) for i in range(12)]
        flags = [False] * 12
        flags[4] = True
        prices = [100.0 + i for i in range(12)]
        # asof=10 → pivot 4 confirmed (4+2=6 < 10)
        rows = record_confirmed_pivots(flags, prices, asof_index=10, bar_times=times)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].index, 4)
        self.assertEqual(rows[0].confirmed_at_index, 6)
        self.assertEqual(rows[0].confirmed_at, times[6])
        # Not yet confirmed at asof=6 (need conf_i < asof)
        early = record_confirmed_pivots(flags, prices, asof_index=6, bar_times=times)
        self.assertEqual(early, [])

    def test_available_confirmed_pivots_matches_record_without_times(self):
        flags = [False, True, False, False, True, False, False, False]
        prices = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        self.assertEqual(
            available_confirmed_pivots(flags, prices, asof_index=7),
            [(1, 2.0), (4, 5.0)],
        )


if __name__ == "__main__":
    unittest.main()
