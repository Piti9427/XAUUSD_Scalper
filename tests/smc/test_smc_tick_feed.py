import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.smc.tick_feed import annotate_bar_with_ticks, load_tick_frame, ticks_for_bar


class TickFeedTests(unittest.TestCase):
    def test_load_and_slice_ticks_for_bar(self):
        csv = (
            "time,bid,ask\n"
            "2026-03-02T08:15:00Z,2000.0,2000.2\n"
            "2026-03-02T08:15:10Z,2011.0,2011.2\n"
            "2026-03-02T08:15:20Z,1994.0,1994.2\n"
            "2026-03-02T08:20:00Z,2001.0,2001.2\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ticks.csv"
            path.write_text(csv)
            ticks = load_tick_frame(str(path))
        sliced = ticks_for_bar(
            ticks,
            bar_open=datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc),
            bar_close=datetime(2026, 3, 2, 8, 20, tzinfo=timezone.utc),
        )
        self.assertEqual(len(sliced), 3)
        bar = annotate_bar_with_ticks(
            {
                "time": datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc),
                "open": 2000.0,
                "high": 2011.0,
                "low": 1994.0,
                "close": 2002.0,
            },
            sliced,
            direction="BUY",
            sl_price=1995.0,
            tp_price=2010.0,
        )
        self.assertTrue(bar["has_tick_order"])
        self.assertEqual(bar["tick_first_exit"], "TP")

    def test_empty_ticks_clears_order_flag(self):
        bar = annotate_bar_with_ticks(
            {"time": datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc), "has_tick_order": True},
            [],
        )
        self.assertFalse(bar["has_tick_order"])


if __name__ == "__main__":
    unittest.main()
