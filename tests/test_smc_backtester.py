import unittest
from datetime import datetime, timezone, timedelta, date
import pandas as pd
from scripts.smc.backtester import SMCBacktester, BacktestSummary


class TestSMCBacktester(unittest.TestCase):
    def setUp(self):
        # Create minimal 2-day synthetic dataset with a clear winning trade
        # Day 1: 2026-03-01 (liquidity reference)
        # Day 2: 2026-03-02 (setup triggers in London and hits 2R TP)
        m5_records = []
        base_time = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
        
        # Day 1: Asian H=2030, L=2020. Day 1 H=2050, L=2000.
        for i in range(288):
            ts = base_time + timedelta(minutes=i*5)
            h = 2050.0 if i == 100 else 2030.0
            l = 2000.0 if i == 80 else 2020.0
            m5_records.append({"time": ts, "open": 2025.0, "high": h, "low": l, "close": 2025.0, "tick_volume": 100})
            
        # Day 2: Asian H=2040, L=2010 (hours 0-6)
        day2_base = datetime(2026, 3, 2, 0, 0, tzinfo=timezone.utc)
        for i in range(288):
            ts = day2_base + timedelta(minutes=i*5)
            hour = ts.hour
            minute = ts.minute
            
            if hour < 7:
                o = 2020.0
                h = 2040.0 if hour == 3 and minute == 0 else 2035.0
                l = 2010.0 if hour == 5 and minute == 0 else 2015.0
                c = 2020.0
            elif hour == 7 and minute < 50:
                o = 2011.5
                h = 2014.0 if minute == 25 else 2012.0
                l = 2011.0
                c = 2011.5
            elif hour == 7 and minute == 50:
                # Sweep Asian Low (2010.0) -> wick 2008.5, close 2011.0
                o = 2011.0
                h = 2011.5
                l = 2008.5
                c = 2011.0
            elif hour == 7 and minute == 55:
                o = 2011.0
                h = 2013.0
                l = 2010.8
                c = 2012.8
            elif hour == 8 and minute == 0:
                # MSS Displacement Candle: close 2016.0 > 2014.0
                o = 2012.8
                h = 2016.2
                l = 2012.7
                c = 2016.0
            elif hour == 8 and minute == 5:
                # FVG confirmation bar: low 2015.0 > 2013.0. FVG 2013-2015 -> 50% CE = 2014.0
                o = 2016.0
                h = 2018.0
                l = 2015.0
                c = 2017.5
            elif hour == 8 and minute == 10:
                # Price retraces to 2013.5 -> fills Limit order at 2014.0!
                o = 2017.5
                h = 2017.5
                l = 2013.5
                c = 2015.0
            elif hour == 8 and minute == 15:
                # Price rallies to 2030.0 -> hits TP (2025.60)
                o = 2015.0
                h = 2030.0
                l = 2014.5
                c = 2028.0
            else:
                o = 2022.0
                h = 2025.0
                l = 2020.0
                c = 2022.0
                
            m5_records.append({"time": ts, "open": o, "high": h, "low": l, "close": c, "tick_volume": 100})
            
        self.df_m5 = pd.DataFrame(m5_records)

        # H1 DataFrame (Bullish, 250 bars > EMA 200)
        h1_records = []
        for i in range(250):
            ts = datetime(2026, 2, 20, 0, 0, tzinfo=timezone.utc) + timedelta(hours=i)
            h1_records.append({
                "time": ts,
                "open": 2000.0 + i * 0.1,
                "high": 2005.0 + i * 0.1,
                "low": 1995.0 + i * 0.1,
                "close": 2002.0 + i * 0.1,
                "tick_volume": 1000
            })
        self.df_h1 = pd.DataFrame(h1_records)

    def test_backtest_execution_and_summary(self):
        backtester = SMCBacktester(initial_balance=10000.0)
        summary = backtester.run(self.df_m5, self.df_h1)
        
        self.assertIsInstance(summary, BacktestSummary)
        self.assertGreaterEqual(summary.total_trades, 1)
        self.assertEqual(summary.winning_trades, 1)
        self.assertEqual(summary.losing_trades, 0)
        self.assertGreater(summary.net_profit, 0.0)
        self.assertEqual(summary.win_rate, 100.0)


if __name__ == "__main__":
    unittest.main()
