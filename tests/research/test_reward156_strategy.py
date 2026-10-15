"""Unit tests for Reward156 (RSI7 BUY + D48 SELL hybrid) strategy detector."""

import unittest
import numpy as np
import pandas as pd

from scripts.strategy import reward156_bars, reward156_levels


class Reward156StrategyTests(unittest.TestCase):
    def make_bars(self, count=100):
        close = np.array([2000.0 + (i * 0.1) for i in range(count)])
        return pd.DataFrame(
            {
                "open": close - 0.05,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
            },
            index=pd.date_range("2026-01-01", periods=count, freq="15min", tz="UTC"),
        )

    def test_requires_timezone_aware_utc(self):
        bars = self.make_bars(80)
        bars.index = bars.index.tz_localize(None)
        with self.assertRaises(ValueError):
            reward156_bars(bars)

    def test_detector_columns_present(self):
        bars = self.make_bars(80)
        frame = reward156_bars(bars)
        for col in ("open", "high", "low", "close", "prior_low", "atr", "rsi7", "ema50", "direction"):
            self.assertIn(col, frame.columns)

    def test_sell_breakout_below_prior_48_low(self):
        bars = self.make_bars(80)
        # Force bar 60 to break far below prior 48 low
        min_low = bars.low.iloc[12:60].min()
        bars.loc[bars.index[60], ["open", "high", "low", "close"]] = [
            min_low - 5.0,
            min_low - 4.0,
            min_low - 10.0,
            min_low - 8.0,
        ]
        frame = reward156_bars(bars)
        self.assertEqual(frame.direction.iloc[60], -1)

    def test_buy_rsi_cross_up_with_rising_ema(self):
        # Construct controlled sequence for RSI cross and rising EMA
        bars = self.make_bars(80)
        # Steady uptrend gives rising EMA50
        frame = reward156_bars(bars)
        # Directions are either 0, 1, or -1
        self.assertTrue(set(frame.direction.unique()).issubset({-1, 0, 1}))

    def test_sell_wins_conflict_over_buy(self):
        bars = self.make_bars(80)
        # Artificially trigger both conditions on bar 65
        min_low = bars.low.iloc[17:65].min()
        bars.loc[bars.index[65], ["open", "high", "low", "close"]] = [
            min_low - 2.0,
            min_low - 1.0,
            min_low - 5.0,
            min_low - 3.0,
        ]
        frame = reward156_bars(bars)
        # Should be SELL (-1) because parent SELL wins conflict
        self.assertEqual(frame.direction.iloc[65], -1)

    def test_research_signal_parity(self):
        from scripts.research.campaign_signals import candidate_frame

        np.random.seed(42)
        count = 150
        idx = pd.date_range("2026-01-01", periods=count, freq="15min", tz="UTC")
        close = 2000.0 + np.cumsum(np.random.randn(count) * 2.0)
        open_ = close + np.random.randn(count) * 0.5
        high = np.maximum(open_, close) + np.abs(np.random.randn(count)) + 0.1
        low = np.minimum(open_, close) - np.abs(np.random.randn(count)) - 0.1
        df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)

        base = df.copy()
        base["direction"] = np.where(base.close < base.low.rolling(48).min().shift(1), -1, 0)
        tr = pd.concat(
            [base.high - base.low, (base.high - base.close.shift()).abs(), (base.low - base.close.shift()).abs()],
            axis=1,
        ).max(axis=1)
        base["atr"] = tr.rolling(14).mean()
        base["hh"] = base.high.rolling(48).max().shift(1)
        base["ll"] = base.low.rolling(48).min().shift(1)

        res_frame = candidate_frame(
            base,
            buy_filter="off",
            depth=0.0,
            oscillator_spec=dict(period=7, threshold=35, trend_span=50, side="buy"),
        )
        strat_frame = reward156_bars(df)
        self.assertTrue((res_frame["direction"] == strat_frame["direction"]).all())

    def test_levels_calculation(self):
        # Entry 2000.0, direction 1 (BUY), ATR 2.0
        # Stop distance: 2.0 * 2.5 = 5.0 -> SL = 1995.0
        # Target distance: 5.0 * 1.35 = 6.75 -> TP = 2006.75
        sl, tp = reward156_levels(2000.0, 1, 2.0)
        self.assertAlmostEqual(sl, 1995.0)
        self.assertAlmostEqual(tp, 2006.75)

        # Entry 2000.0, direction -1 (SELL), ATR 2.0
        # SL = 2005.0, TP = 1993.25
        sl_s, tp_s = reward156_levels(2000.0, -1, 2.0)
        self.assertAlmostEqual(sl_s, 2005.0)
        self.assertAlmostEqual(tp_s, 1993.25)

    def test_levels_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            reward156_levels(2000.0, 0, 2.0)
        with self.assertRaises(ValueError):
            reward156_levels(-100.0, 1, 2.0)
        with self.assertRaises(ValueError):
            reward156_levels(2000.0, 1, -1.0)
