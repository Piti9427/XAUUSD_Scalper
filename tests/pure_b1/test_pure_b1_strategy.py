"""Pure B1 target contract; independent of legacy SMC and wick rejection."""

import unittest

import numpy as np
import pandas as pd

from scripts.strategy import pure_b1_bars, pure_b1_direction, pure_b1_levels


class PureB1StrategyTests(unittest.TestCase):
    def bars(self, count=80):
        close = np.array([100.0 + (i % 2) for i in range(count)])
        return pd.DataFrame(
            {
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close,
            },
            index=pd.date_range("2026-01-01", periods=count, freq="15min", tz="UTC"),
        )

    def test_strict_donchian_rsi_and_ema_boundaries(self):
        cases = (
            (103, 102, 99, 50, 101, 1),
            (102, 102, 99, 50, 101, 0),
            (103, 102, 99, 30, 101, 0),
            (103, 102, 99, 70, 101, 0),
            (103, 102, 99, 50, 103, 0),
            (98, 102, 99, 50, 100, -1),
            (99, 102, 99, 50, 100, 0),
            (98, 102, 99, 30, 100, 0),
            (98, 102, 99, 70, 100, 0),
            (98, 102, 99, 50, 98, 0),
        )
        for close, high, low, rsi, ema, expected in cases:
            with self.subTest(close=close, rsi=rsi, ema=ema):
                self.assertEqual(pure_b1_direction(close, high, low, rsi, ema), expected)

    def test_previous_thirty_bars_exclude_current(self):
        bars = self.bars()
        bars.loc[bars.index[40], ["open", "high", "close"]] = [103.0, 103.0, 103.0]
        frame = pure_b1_bars(bars)
        self.assertEqual(frame.hh30.iloc[40], 102.0)
        self.assertEqual(frame.hh30.iloc[41], 103.0)

    def test_indicator_prefix_does_not_change_with_future_bars(self):
        bars = self.bars()
        prefix = pure_b1_bars(bars.iloc[:60])
        bars.loc[bars.index[60] :, ["open", "high", "low", "close"]] += 10
        pd.testing.assert_frame_equal(prefix, pure_b1_bars(bars).iloc[:60])

    def test_invalid_or_naive_bar_data_fails_closed(self):
        for kind in ("naive", "misaligned", "duplicate", "nan", "bad_ohlc"):
            bars = self.bars()
            if kind == "naive":
                bars.index = bars.index.tz_localize(None)
            elif kind == "misaligned":
                bars.index += pd.Timedelta(minutes=1)
            elif kind == "duplicate":
                bars.index = pd.DatetimeIndex([bars.index[0]] + list(bars.index[:-1]))
            elif kind == "nan":
                bars.iloc[5, 0] = np.nan
            else:
                bars.iloc[5, 1] = 50.0
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                pure_b1_bars(bars)

    def test_levels_use_625_and_25_atr(self):
        self.assertEqual(pure_b1_levels(2600, 1, 4), (2590, 2625))
        self.assertEqual(pure_b1_levels(2600, -1, 4), (2610, 2575))


if __name__ == "__main__":
    unittest.main()
