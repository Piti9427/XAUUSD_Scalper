"""Broker M15 input must preserve Pure B1's completed UTC Bid-bar contract."""

from datetime import datetime, timezone
import unittest

import pandas as pd

from scripts.pure_b1.broker_data import completed_m15, completed_m15_from_m1


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


if __name__ == "__main__":
    unittest.main()
