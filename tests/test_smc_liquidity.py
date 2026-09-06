import unittest
from datetime import datetime, date, timezone
import pandas as pd
from scripts.smc.liquidity import compute_liquidity_levels
from scripts.smc.types import LiquidityLevels


class TestSMCLiquidityMapping(unittest.TestCase):
    def setUp(self):
        # Create synthetic M5 candles across 2 days: Day 1 (2026-03-01) and Day 2 (2026-03-02)
        # Day 1: 00:00 to 23:55 UTC (288 candles)
        # Day 2: 00:00 to 23:55 UTC (288 candles)
        records = []
        
        # Day 1
        d1 = date(2026, 3, 1)
        for i in range(288):
            hour = (i * 5) // 60
            minute = (i * 5) % 60
            ts = datetime(2026, 3, 1, hour, minute, tzinfo=timezone.utc)
            # Make Day 1 high = 2050.0 at 14:00, low = 2000.0 at 10:00
            high = 2050.0 if hour == 14 and minute == 0 else 2030.0
            low = 2000.0 if hour == 10 and minute == 0 else 2020.0
            records.append({
                "time": ts,
                "open": 2025.0,
                "high": high,
                "low": low,
                "close": 2025.0,
                "tick_volume": 100
            })
            
        # Day 2: Asian range 00:00 to 07:00 (hours 0 to 6)
        d2 = date(2026, 3, 2)
        for i in range(288):
            hour = (i * 5) // 60
            minute = (i * 5) % 60
            ts = datetime(2026, 3, 2, hour, minute, tzinfo=timezone.utc)
            # Asian range: high = 2040.0 at 03:00, low = 2010.0 at 05:00
            if hour < 7:
                high = 2040.0 if hour == 3 and minute == 0 else 2035.0
                low = 2010.0 if hour == 5 and minute == 0 else 2015.0
            else:
                high = 2060.0
                low = 2005.0
            records.append({
                "time": ts,
                "open": 2020.0,
                "high": high,
                "low": low,
                "close": 2020.0,
                "tick_volume": 100
            })
            
        self.df = pd.DataFrame(records)

    def test_compute_liquidity_levels_day2(self):
        target_date = date(2026, 3, 2)
        levels = compute_liquidity_levels(self.df, target_date)
        
        self.assertIsInstance(levels, LiquidityLevels)
        self.assertEqual(levels.asian_high, 2040.0)
        self.assertEqual(levels.asian_low, 2010.0)
        # Previous Day (Day 1) full range
        self.assertEqual(levels.pdh, 2050.0)
        self.assertEqual(levels.pdl, 2000.0)
        self.assertEqual(levels.date_str, "2026-03-02")

    def test_missing_data_returns_none(self):
        # Empty df
        empty_df = pd.DataFrame(columns=["time", "open", "high", "low", "close", "tick_volume"])
        levels = compute_liquidity_levels(empty_df, date(2026, 3, 2))
        self.assertIsNone(levels)


if __name__ == "__main__":
    unittest.main()
