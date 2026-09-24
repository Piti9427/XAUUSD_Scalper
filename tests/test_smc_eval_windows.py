"""Tests for foundation development/holdout window labeling."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from scripts.smc.eval_windows import (
    assert_single_window_or_reason,
    label_foundation_window,
    samples_may_merge,
)


class EvalWindowsTests(unittest.TestCase):
    def test_development_vs_holdout_boundaries(self):
        mid_dev = label_foundation_window(date(2026, 1, 15))
        self.assertEqual(mid_dev.name, "development")
        self.assertTrue(mid_dev.ok_for_tuning)

        last_dev = label_foundation_window(date(2026, 5, 31))
        self.assertEqual(last_dev.name, "development")

        first_hold = label_foundation_window(date(2026, 6, 1))
        self.assertEqual(first_hold.name, "holdout")
        self.assertFalse(first_hold.ok_for_tuning)
        self.assertTrue(first_hold.ok_for_holdout_eval)

        last_hold = label_foundation_window(datetime(2026, 8, 31, 12, tzinfo=timezone.utc))
        self.assertEqual(last_hold.name, "holdout")

        after = label_foundation_window(date(2026, 9, 1))
        self.assertEqual(after.name, "out_of_range")

    def test_refuse_merge_dev_and_holdout(self):
        ok, reason = samples_may_merge(left_window="development", right_window="holdout")
        self.assertFalse(ok)
        self.assertIn("refuse_merge", reason)

        ok2, reason2 = samples_may_merge(left_window="holdout", right_window="holdout")
        self.assertTrue(ok2)
        self.assertEqual(reason2, "ok")

    def test_mixed_timestamps_blocked(self):
        window, reason = assert_single_window_or_reason([date(2026, 1, 1), date(2026, 7, 1)])
        self.assertIsNone(window)
        self.assertIn("refuse_merge", reason)

        window2, reason2 = assert_single_window_or_reason([date(2026, 7, 1), date(2026, 8, 1)])
        self.assertEqual(window2, "holdout")
        self.assertEqual(reason2, "ok")


if __name__ == "__main__":
    unittest.main()
