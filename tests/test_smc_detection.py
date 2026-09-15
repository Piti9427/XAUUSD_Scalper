import unittest
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
from scripts.smc.structure import find_fractals_5bar, check_displacement, detect_fvg, check_sweep
from scripts.smc.detection import detect_smc_setup
from scripts.smc.types import Direction, SetupSignal, LiquidityLevels


class TestSMCStructure(unittest.TestCase):
    def test_fractal_5bar(self):
        # 5 bars: [10, 12, 15, 12, 10] -> bar index 2 is swing high
        highs = [10.0, 12.0, 15.0, 12.0, 10.0]
        lows = [8.0, 9.0, 11.0, 9.0, 8.0]
        df = pd.DataFrame({"high": highs, "low": lows})
        swing_highs, swing_lows = find_fractals_5bar(df)
        self.assertTrue(swing_highs[2])
        self.assertFalse(swing_highs[1])
        self.assertFalse(swing_highs[3])

    def test_displacement_ratio(self):
        # Range = 10, Body = 7 (70% >= 60%) -> True
        self.assertTrue(check_displacement(open_val=100.0, high_val=110.0, low_val=100.0, close_val=107.0))
        # Range = 10, Body = 5 (50% < 60%) -> False
        self.assertFalse(check_displacement(open_val=100.0, high_val=110.0, low_val=100.0, close_val=105.0))

    def test_fvg_detection(self):
        # Bullish FVG: candle 1 high = 100, candle 2 (disp) 99 to 110, candle 3 low = 101.5
        # Gap = 101.5 - 100.0 = 1.50 >= 0.50 -> True
        c_prev = {"high": 100.0, "low": 95.0}
        c_disp = {"open": 99.0, "high": 110.0, "low": 99.0, "close": 109.0}
        c_next = {"high": 112.0, "low": 101.5}
        is_fvg, gap_high, gap_low, ce_50 = detect_fvg(c_prev, c_disp, c_next, direction=Direction.BUY)
        self.assertTrue(is_fvg)
        self.assertEqual(gap_low, 100.0)
        self.assertEqual(gap_high, 101.5)
        self.assertEqual(ce_50, 100.75)

    def test_sweep_wick_only(self):
        # Asian Low = 2000.0
        # Candle dips to 1998.0 (2.0 pierce <= 5.0) and closes at 2001.0 (inside)
        candle = {"open": 2002.0, "high": 2003.0, "low": 1998.0, "close": 2001.0}
        is_sweep, wick = check_sweep(candle, level=2000.0, is_high_level=False, max_pierce=5.0)
        self.assertTrue(is_sweep)
        self.assertEqual(wick, 1998.0)

        # Expansion breakout: candle body closes below 2000.0 (e.g. close=1997.0)
        breakout_candle = {"open": 2002.0, "high": 2003.0, "low": 1996.0, "close": 1997.0}
        is_sweep, _ = check_sweep(breakout_candle, level=2000.0, is_high_level=False, max_pierce=5.0)
        self.assertFalse(is_sweep)


class TestSMCDetectionIntegration(unittest.TestCase):
    def setUp(self):
        self.liquidity = LiquidityLevels(
            asian_high=2040.0,
            asian_low=2010.0,
            pdh=2050.0,
            pdl=2000.0,
            date_str="2026-03-02"
        )
        
        # Build H1 candles: 250 bars all with Close > EMA 200 (Bullish bias)
        h1_records = []
        base_time = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
        for i in range(250):
            h1_records.append({
                "time": base_time + timedelta(hours=i),
                "open": 2000.0 + i * 0.1,
                "high": 2005.0 + i * 0.1,
                "low": 1995.0 + i * 0.1,
                "close": 2002.0 + i * 0.1,
                "tick_volume": 1000
            })
        self.df_h1 = pd.DataFrame(h1_records)

    def valid_setup_inputs(self, direction=Direction.BUY):
        # 1. London session: 08:00 UTC
        # 2. Sweep of Asian Low (2010.0): wick touches 2008.0 (pierce $2.00 <= $5.00), close 2011.0
        # 3. Previous M5 swing high at 2014.0 (5-bar fractal)
        # 4. MSS: 3 bars later, bar closes at 2016.0 (body close > 2014.0) with body >= 60%
        # 5. FVG formed: low[i+1] (2015.0) > high[i-1] (2013.0) -> gap $2.00 >= $0.50
        # 6. SL distance = |2014.0 - 2008.0| + 0.30 = $6.30? Wait, let's keep SL <= $6.00 cap:
        #    Entry at 50% FVG = (2013.0 + 2015.0)/2 = 2014.0. Sweep wick = 2010.0 - 1.5 = 2008.5.
        #    SL dist = 2014.0 - 2008.5 + 0.30 = 5.80 <= 6.00 cap!
        
        m5_records = []
        start_time = datetime(2026, 3, 2, 7, 0, tzinfo=timezone.utc)
        
        # 15 bars leading up: create swing high at bar 5 (07:25) = 2014.0
        for i in range(15):
            ts = start_time + timedelta(minutes=i*5)
            h = 2014.0 if i == 5 else (2012.0 if i in [4, 6] else 2010.5)
            l = 2009.5
            m5_records.append({"time": ts, "open": 2010.0, "high": h, "low": l, "close": 2010.5, "tick_volume": 100})
            
        # Bar 15 (08:15): Sweep Asian Low (2010.0) with wick to 2008.5, closes at 2011.0
        m5_records.append({
            "time": start_time + timedelta(minutes=15*5),
            "open": 2010.5, "high": 2011.5, "low": 2008.5, "close": 2011.0, "tick_volume": 150
        })
        
        # Bar 16 (08:20): Pre-displacement base
        m5_records.append({
            "time": start_time + timedelta(minutes=16*5),
            "open": 2011.0, "high": 2013.0, "low": 2010.8, "close": 2012.8, "tick_volume": 120
        })
        
        # Bar 17 (08:25 - London killzone): MSS Displacement Candle
        # Breaks swing high 2014.0 with close at 2016.0 (body = 3.0, range = 3.5 -> 85% > 60%)
        m5_records.append({
            "time": start_time + timedelta(minutes=17*5),
            "open": 2012.8, "high": 2016.2, "low": 2012.7, "close": 2016.0, "tick_volume": 300
        })
        
        # Bar 18 (08:30): Next candle confirming FVG
        # Low = 2015.0 > Bar 16 High (2013.0) -> FVG = 2013.0 to 2015.0 ($2.00)
        m5_records.append({
            "time": start_time + timedelta(minutes=18*5),
            "open": 2016.0, "high": 2018.0, "low": 2015.0, "close": 2017.5, "tick_volume": 200
        })
        
        df_m5 = pd.DataFrame(m5_records)
        eval_time = start_time + timedelta(minutes=18*5)
        
        if direction == Direction.SELL:
            def mirror(df):
                result = df.copy()
                for column in ("open", "close"):
                    result[column] = 4000.0 - df[column]
                result["high"] = 4000.0 - df["low"]
                result["low"] = 4000.0 - df["high"]
                return result

            liquidity = LiquidityLevels(
                asian_high=4000.0 - self.liquidity.asian_low,
                asian_low=4000.0 - self.liquidity.asian_high,
                pdh=4000.0 - self.liquidity.pdl,
                pdl=4000.0 - self.liquidity.pdh,
                date_str=self.liquidity.date_str,
            )
            return mirror(self.df_h1), mirror(df_m5), liquidity, eval_time
        return self.df_h1, df_m5, self.liquidity, eval_time

    def test_valid_bullish_setup_during_london(self):
        signal = detect_smc_setup(*self.valid_setup_inputs())
        self.assertIsNotNone(signal)
        self.assertEqual(signal.direction, Direction.BUY)
        self.assertEqual(signal.entry_price, 2014.0) # 50% of [2013.0, 2015.0]
        self.assertEqual(signal.sl_price, 2008.20) # 2008.5 - 0.30 buffer
        self.assertAlmostEqual(signal.sl_distance, 5.80, places=2)
        self.assertAlmostEqual(signal.tp_price, 2014.0 + (5.80 * 2.0), places=2) # 2R TP

    def test_broken_other_level_preserves_fresh_sweep(self):
        for direction in Direction:
            with self.subTest(direction=direction):
                h1, m5, liquidity, now = self.valid_setup_inputs(direction)
                baseline = detect_smc_setup(h1, m5, liquidity, now)
                self.assertIsNotNone(baseline)
                liquidity = (replace(liquidity, pdl=2020.0) if direction == Direction.BUY
                             else replace(liquidity, pdh=1980.0))
                signal = detect_smc_setup(h1, m5, liquidity, now)
                self.assertEqual(signal, baseline)

    def test_breakout_branches_and_boundary(self):
        for direction in Direction:
            for kind in ("body", "wick", "at_cap", "older"):
                with self.subTest(direction=direction, kind=kind):
                    h1, m5, liquidity, now = self.valid_setup_inputs(direction)
                    is_buy = direction == Direction.BUY
                    level = liquidity.asian_low if is_buy else liquidity.asian_high
                    extreme = "low" if is_buy else "high"
                    sign = -1 if is_buy else 1
                    index = 14 if kind == "older" else 16
                    pierce = 1.0 if kind in ("body", "older") else (8.0 if kind == "at_cap" else 8.1)
                    m5.loc[index, extreme] = level + sign * pierce
                    if kind in ("body", "older"):
                        m5.loc[index, "close"] = level + sign * 0.2
                    signal = detect_smc_setup(h1, m5, liquidity, now, max_sl_cap=25.0,
                                              max_sweep_pierce=8.0)
                    if kind in ("body", "wick"):
                        self.assertIsNone(signal)
                    else:
                        self.assertIsNotNone(signal)
                        self.assertEqual(signal.direction, direction)
                        self.assertEqual(signal.entry_price, 2014.0 if is_buy else 1986.0)
                        wick = level + sign * (8.0 if kind == "at_cap" else 1.5)
                        self.assertAlmostEqual(signal.sl_price, wick + sign * 0.3)

    def test_out_of_session_returns_none(self):
        # Evaluation at 11:00 UTC (between London and NY)
        df_m5 = pd.DataFrame([{
            "time": datetime(2026, 3, 2, 11, 0, tzinfo=timezone.utc),
            "open": 2010.0, "high": 2015.0, "low": 2005.0, "close": 2012.0, "tick_volume": 100
        }])
        signal = detect_smc_setup(
            self.df_h1, df_m5, self.liquidity,
            datetime(2026, 3, 2, 11, 0, tzinfo=timezone.utc)
        )
        self.assertIsNone(signal)

    def test_counter_trend_h1_returns_none(self):
        # Make recent H1 closes drop sharply below EMA 200
        h1_bearish = self.df_h1.copy()
        h1_bearish.loc[h1_bearish.index[-50:], "close"] = 1800.0
        
        start_time = datetime(2026, 3, 2, 7, 0, tzinfo=timezone.utc)
        m5_records = []
        for i in range(15):
            h = 2014.0 if i == 5 else 2012.0
            # Low is above Asian Low (2010.0) so these don't sweep
            m5_records.append({"time": start_time + timedelta(minutes=i*5), "open": 2012.0, "high": h, "low": 2011.0, "close": 2011.5, "tick_volume": 100})
        m5_records.append({"time": start_time + timedelta(minutes=75), "open": 2011.5, "high": 2011.8, "low": 2008.5, "close": 2011.0, "tick_volume": 150})
        m5_records.append({"time": start_time + timedelta(minutes=80), "open": 2011.0, "high": 2013.0, "low": 2010.8, "close": 2012.8, "tick_volume": 120})
        m5_records.append({"time": start_time + timedelta(minutes=85), "open": 2012.8, "high": 2016.2, "low": 2012.7, "close": 2016.0, "tick_volume": 300})
        m5_records.append({"time": start_time + timedelta(minutes=90), "open": 2016.0, "high": 2018.0, "low": 2015.0, "close": 2017.5, "tick_volume": 200})
        df_m5 = pd.DataFrame(m5_records)

        signal = detect_smc_setup(h1_bearish, df_m5, self.liquidity, start_time + timedelta(minutes=90))
        # Since H1 is bearish, BUY setup is rejected!
        self.assertIsNone(signal)

    def test_sweep_pierce_greater_than_5_returns_none(self):
        start_time = datetime(2026, 3, 2, 7, 0, tzinfo=timezone.utc)
        m5_records = []
        for i in range(15):
            h = 2014.0 if i == 5 else 2012.0
            # Low is above Asian Low (2010.0) so these don't sweep
            m5_records.append({"time": start_time + timedelta(minutes=i*5), "open": 2012.0, "high": h, "low": 2011.0, "close": 2011.5, "tick_volume": 100})
        # Low pierces to 2004.0 (Asian low 2010.0 - 2004.0 = 6.00 > 5.00 max pierce!)
        m5_records.append({"time": start_time + timedelta(minutes=75), "open": 2011.5, "high": 2011.8, "low": 2004.0, "close": 2011.0, "tick_volume": 150})
        m5_records.append({"time": start_time + timedelta(minutes=80), "open": 2011.0, "high": 2013.0, "low": 2010.8, "close": 2012.8, "tick_volume": 120})
        m5_records.append({"time": start_time + timedelta(minutes=85), "open": 2012.8, "high": 2016.2, "low": 2012.7, "close": 2016.0, "tick_volume": 300})
        m5_records.append({"time": start_time + timedelta(minutes=90), "open": 2016.0, "high": 2018.0, "low": 2015.0, "close": 2017.5, "tick_volume": 200})
        df_m5 = pd.DataFrame(m5_records)

        signal = detect_smc_setup(self.df_h1, df_m5, self.liquidity, start_time + timedelta(minutes=90))
        self.assertIsNone(signal)

    def test_expansion_breakout_invalidates_stale_sweep(self):
        # CONTEXT.md Expansion Breakout rule: a candle whose body closes through
        # the liquidity level, or whose wick pierces beyond $8.00, invalidates
        # sweep search immediately -- an older sweep before that breakout must
        # never be reused for a new setup.
        #
        # Sequence: bar15 sweeps Asian Low (2010.0) cleanly (stale, pre-breakout).
        # bar16 is a body-close breakout ($9.00 through the level).
        # bar17 is a wick-only dip that pierces $9.50 (> $8.00 fixed breakout cap).
        # bar18 is neutral. bar19 is the MSS displacement candle.
        # bar20 confirms the FVG.
        #
        # Without the breakout check, the backward sweep search skips past
        # bars 16-18 (none of them satisfy check_sweep) and finds bar15's
        # stale sweep, producing a signal whose SL is tainted by bar16's low.
        # With the fix, the search must stop at the first breakout bar and
        # return no setup, since no valid sweep exists after the breakout.
        start_time = datetime(2026, 3, 2, 7, 0, tzinfo=timezone.utc)
        m5_records = []
        for i in range(15):
            h = 2014.0 if i == 5 else (2012.0 if i in [4, 6] else 2010.5)
            m5_records.append({
                "time": start_time + timedelta(minutes=i * 5),
                "open": 2010.0, "high": h, "low": 2009.5, "close": 2010.5,
                "tick_volume": 100,
            })
        # bar15 (08:15): stale sweep of Asian Low, pierce $1.50, closes back inside
        m5_records.append({
            "time": start_time + timedelta(minutes=15 * 5),
            "open": 2010.5, "high": 2011.5, "low": 2008.5, "close": 2011.0,
            "tick_volume": 150,
        })
        # bar16 (08:20): body-close breakout, close $9.00 through Asian Low
        m5_records.append({
            "time": start_time + timedelta(minutes=16 * 5),
            "open": 2011.0, "high": 2011.2, "low": 2000.0, "close": 2001.0,
            "tick_volume": 400,
        })
        # bar17 (08:25): wick-only dip piercing $9.50 (> $8.00 fixed breakout cap)
        m5_records.append({
            "time": start_time + timedelta(minutes=17 * 5),
            "open": 2001.0, "high": 2012.0, "low": 2000.5, "close": 2011.5,
            "tick_volume": 150,
        })
        # bar18 (08:30): neutral bar, no sweep
        m5_records.append({
            "time": start_time + timedelta(minutes=18 * 5),
            "open": 2011.5, "high": 2013.0, "low": 2011.0, "close": 2012.5,
            "tick_volume": 120,
        })
        # bar19 (08:35): MSS displacement candle, closes above swing high 2014.0
        m5_records.append({
            "time": start_time + timedelta(minutes=19 * 5),
            "open": 2012.5, "high": 2016.2, "low": 2012.4, "close": 2016.0,
            "tick_volume": 300,
        })
        # bar20 (08:40): confirms FVG (low 2015.0 > bar18 high 2013.0)
        m5_records.append({
            "time": start_time + timedelta(minutes=20 * 5),
            "open": 2016.0, "high": 2018.0, "low": 2015.0, "close": 2017.5,
            "tick_volume": 200,
        })
        df_m5 = pd.DataFrame(m5_records)
        eval_time = start_time + timedelta(minutes=20 * 5)

        signal = detect_smc_setup(self.df_h1, df_m5, self.liquidity, eval_time, max_sl_cap=25.0)
        self.assertIsNone(
            signal,
            "Expansion breakout must invalidate the stale pre-breakout sweep; "
            f"got a setup with SL tainted by the breakout instead: {signal}",
        )

    def test_require_choch_rejects_mss_only_legacy_setup(self):
        h1, m5, liquidity, now = self.valid_setup_inputs()
        legacy = detect_smc_setup(h1, m5, liquidity, now)
        self.assertIsNotNone(legacy, "legacy MSS path must still find the fixture")
        foundation = detect_smc_setup(h1, m5, liquidity, now, require_choch=True)
        self.assertIsNone(
            foundation,
            "foundation BaselinePlay must reject fractal-MSS that is not protected-swing CHOCH",
        )

    def test_require_choch_accepts_protected_swing_reversal(self):
        # Mechanical §3.5: opposite pivot must sit BETWEEN broken swing and break.
        # Form low → bounce high → break that low (bearish, protected=high) → sweep → CHOCH.
        start = datetime(2026, 3, 2, 7, 0, tzinfo=timezone.utc)
        rows = []

        def bar(i, o, h, l, c):
            return {
                "time": start + timedelta(minutes=5 * i),
                "open": o, "high": h, "low": l, "close": c, "tick_volume": 100,
            }

        # 0-7: swing low at 3 = 2016 (confirm by bar 5); stay above asian 2010
        for i in range(8):
            l = 2016.0 if i == 3 else (2017.0 if i in (2, 4) else 2019.0)
            rows.append(bar(i, 2019.0, 2020.0, l, 2019.5))

        # 8-12: swing high at 9 = 2030 (between low and later break; confirm by bar 11)
        for i in range(8, 13):
            h = 2030.0 if i == 9 else (2028.0 if i in (8, 10) else 2024.0)
            rows.append(bar(i, 2023.0, h, 2021.0, 2023.5))

        # 13: bearish BOS — close below swing low 2016; opposite high 2030 is between
        rows.append(bar(13, 2022.0, 2022.5, 2013.5, 2014.5))

        # 14: recover above asian without expansion close-through
        rows.append(bar(14, 2014.5, 2018.0, 2014.0, 2017.5))

        # 15: Sweep asian 2010
        rows.append(bar(15, 2017.5, 2018.0, 2008.5, 2011.0))

        # 16: FVG left / pre-CHOCH
        rows.append(bar(16, 2011.0, 2020.0, 2010.8, 2019.0))

        # 17: CHOCH through protected 2030
        rows.append(bar(17, 2019.0, 2035.0, 2018.5, 2034.0))

        # 18: FVG right (low > bar16 high)
        rows.append(bar(18, 2034.0, 2036.0, 2021.0, 2035.0))

        df_m5 = pd.DataFrame(rows)
        eval_time = start + timedelta(minutes=5 * 18)
        signal = detect_smc_setup(
            self.df_h1, df_m5, self.liquidity, eval_time,
            max_sl_cap=25.0, require_choch=True, min_body_ratio=0.45,
            max_sweep_to_mss_bars=8, max_mss_to_fvg_bars=4,
            max_sweep_pierce=8.0,
        )
        self.assertIsNotNone(signal, "protected-swing CHOCH fixture must qualify")
        self.assertEqual(signal.direction, Direction.BUY)
        self.assertIn("CHOCH", signal.reason)


if __name__ == "__main__":
    unittest.main()
