import unittest
from datetime import datetime, timezone

from scripts.smc.clock_exit import OpenFill, plan_clock_time_exits, plan_clock_rollover_exits


class ClockExitTests(unittest.TestCase):
    def test_hold_under_max_emits_nothing(self):
        fills = [
            OpenFill(
                order_id="A",
                open_time=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
                direction="BUY",
            )
        ]
        plans = plan_clock_time_exits(
            fills,
            now=datetime(2026, 3, 2, 8, 5, tzinfo=timezone.utc),
            max_hold_bars=2,
            bar_minutes=5,
        )
        self.assertEqual(plans, [])

    def test_hold_past_max_emits_time_exit(self):
        fills = [
            OpenFill(
                order_id="A",
                open_time=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
                direction="SELL",
            )
        ]
        plans = plan_clock_time_exits(
            fills,
            now=datetime(2026, 3, 2, 8, 10, tzinfo=timezone.utc),
            max_hold_bars=2,
            bar_minutes=5,
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].order_id, "A")
        self.assertIn("TIME_EXIT", plans[0].reason)

    def test_rollover_cutoff_emits_close_for_open_fills(self):
        fills = [
            OpenFill(
                order_id="R1",
                open_time=datetime(2026, 3, 2, 18, 0, tzinfo=timezone.utc),
                direction="BUY",
            )
        ]
        before = plan_clock_rollover_exits(
            fills,
            now=datetime(2026, 3, 2, 20, 54, tzinfo=timezone.utc),
            rollover_hour_utc=20,
            rollover_minute_utc=55,
        )
        self.assertEqual(before, [])
        after = plan_clock_rollover_exits(
            fills,
            now=datetime(2026, 3, 2, 20, 55, tzinfo=timezone.utc),
            rollover_hour_utc=20,
            rollover_minute_utc=55,
        )
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0].order_id, "R1")
        self.assertIn("ROLLOVER", after[0].reason.upper())


if __name__ == "__main__":
    unittest.main()
