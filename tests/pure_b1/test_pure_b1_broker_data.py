"""Broker M15 input must preserve Pure B1's completed UTC Bid-bar contract."""

from datetime import datetime, timezone
import unittest

import pandas as pd

from scripts.pure_b1.broker_data import completed_m15, completed_m15_from_m1, m1_gap_events


class PureB1BrokerDataTests(unittest.TestCase):
    def test_closed_bar_has_utc_index_and_forming_bar_is_excluded(self):
        opens = pd.date_range("2026-09-29 00:00", periods=62, freq="15min", tz="UTC")
        rates = [
            {
                "time": int(ts.timestamp()),
                "open": 3000.0,
                "high": 3001.0,
                "low": 2999.0,
                "close": 3000.0,
                "tick_volume": 10,
            }
            for ts in opens
        ]
        now = datetime(2026, 9, 29, 15, 16, tzinfo=timezone.utc)
        bars = completed_m15(rates, now=now)
        self.assertEqual(len(bars), 61)
        self.assertEqual(str(bars.index.tz), "UTC")
        self.assertEqual(bars.index[-1], pd.Timestamp("2026-09-29 15:00Z"))
        self.assertEqual(list(bars.columns), ["open", "high", "low", "close"])

    def test_duplicate_bar_is_rejected(self):
        ts = int(datetime(2026, 9, 29, tzinfo=timezone.utc).timestamp())
        rate = {"time": ts, "open": 3000, "high": 3001, "low": 2999, "close": 3000}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            completed_m15([rate, rate], now=datetime(2026, 9, 29, 0, 16, tzinfo=timezone.utc))

    def test_incomplete_m15_from_broker_m1_is_excluded_like_reference(self):
        opens = pd.date_range("2026-09-29 00:00", periods=30, freq="min", tz="UTC")
        rates = [
            {
                "time": int(ts.timestamp()),
                "open": 3000.0,
                "high": 3001.0,
                "low": 2999.0,
                "close": 3000.5,
            }
            for ts in opens
            if ts.minute != 17
        ]
        bars = completed_m15_from_m1(rates, now=datetime(2026, 9, 29, 0, 31, tzinfo=timezone.utc))
        self.assertEqual(list(bars.index), [pd.Timestamp("2026-09-29 00:00Z")])
        events = m1_gap_events(rates, now=datetime(2026, 9, 29, 0, 31, tzinfo=timezone.utc))
        gaps = [event for event in events if event["type"] == "incomplete_m1_interval"]
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["m1_count"], 14)
        self.assertFalse(gaps[0]["late_entry"])
        self.assertNotIn(gaps[0]["bar_open_utc"], {item.isoformat() for item in bars.index})

    def test_forming_m1_is_an_event_and_not_a_closed_bar(self):
        opens = pd.date_range("2026-09-29 00:00", periods=16, freq="min", tz="UTC")
        rates = [
            {
                "time": int(ts.timestamp()),
                "open": 3000.0,
                "high": 3001.0,
                "low": 2999.0,
                "close": 3000.5,
            }
            for ts in opens
        ]
        now = datetime(2026, 9, 29, 0, 15, 30, tzinfo=timezone.utc)
        bars = completed_m15_from_m1(rates, now=now)
        self.assertEqual(list(bars.index), [pd.Timestamp("2026-09-29 00:00Z")])
        forming = [
            event
            for event in m1_gap_events(rates, now=now)
            if event["type"] == "forming_bar_excluded"
        ]
        self.assertTrue(forming)
        self.assertFalse(any(event["late_entry"] for event in forming))


if __name__ == "__main__":
    unittest.main()
