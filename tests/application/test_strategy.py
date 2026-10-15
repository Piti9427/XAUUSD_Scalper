import sys
import types
import unittest

import pandas as pd


fake_ta = types.SimpleNamespace(
    ema=lambda series, length: series,
    rsi=lambda series, length: series,
    mfi=lambda high, low, close, volume, length: close,
    atr=lambda high, low, close, length: close,
)
sys.modules.setdefault("pandas_ta", fake_ta)

from scripts.strategy import XAUUSDSniperStrategy


def make_strategy():
    return XAUUSDSniperStrategy(
        {
            "strategy": {
                "ema_short": 20,
                "ema_long": 50,
                "rsi_period": 14,
                "tp_pips": 100,
                "sl_pips": 50,
                "max_spread": 30,
                "atr_multiplier_tp": 2.0,
                "atr_multiplier_sl": 1.5,
            }
        }
    )


def make_bars(hour=12):
    return pd.DataFrame(
        [
            {
                "time": f"2026-05-18 {hour}:00:00",
                "open": 2400,
                "high": 2401,
                "low": 2399,
                "close": 2400,
                "tick_volume": 1,
            },
            {
                "time": f"2026-05-18 {hour}:15:00",
                "open": 2400,
                "high": 2401,
                "low": 2399,
                "close": 2400,
                "tick_volume": 1,
            },
            {
                "time": f"2026-05-18 {hour}:30:00",
                "open": 2400,
                "high": 2401,
                "low": 2399,
                "close": 2400,
                "tick_volume": 1,
            },
            {
                "time": f"2026-05-18 {hour}:45:00",
                "open": 2400,
                "high": 2401,
                "low": 2399,
                "close": 2400,
                "tick_volume": 1,
            },
            {
                "time": f"2026-05-18 {hour}:59:00",
                "open": 2400,
                "high": 2401,
                "low": 2399,
                "close": 2400,
                "tick_volume": 1,
            },
        ]
    )


class StrategyTests(unittest.TestCase):
    def test_check_signals_returns_spread_unavailable(self):
        strategy = make_strategy()

        result = strategy.check_signals(make_bars(), make_bars(), make_bars(), current_spread=None)

        self.assertEqual(result, "SPREAD_UNAVAILABLE")

    def test_check_signals_returns_outside_session(self):
        strategy = make_strategy()

        result = strategy.check_signals(
            make_bars(hour=9), make_bars(), make_bars(), current_spread=1
        )

        self.assertEqual(result, "OUTSIDE_SESSION")

    def test_get_tp_sl_uses_atr_when_available(self):
        strategy = make_strategy()

        tp, sl = strategy.get_tp_sl(2400, "BUY", atr_value=4)

        self.assertEqual(tp, 2408)
        self.assertEqual(sl, 2394)

    def test_get_tp_sl_falls_back_to_fixed_pips(self):
        strategy = make_strategy()

        tp, sl = strategy.get_tp_sl(2400, "SELL")

        self.assertEqual(tp, 2390)
        self.assertEqual(sl, 2405)

    def test_check_signals_ema_trend_filter_blocks_counter_trend(self):
        strategy = make_strategy()
        # Create bars with bullish MSS signal
        bars = pd.DataFrame(
            [
                {
                    "time": "2026-05-18 12:00:00",
                    "open": 2400,
                    "high": 2401,
                    "low": 2399,
                    "close": 2400,
                },
                {
                    "time": "2026-05-18 12:15:00",
                    "open": 2400,
                    "high": 2401,
                    "low": 2399,
                    "close": 2400,
                },
                {
                    "time": "2026-05-18 12:30:00",
                    "open": 2400,
                    "high": 2405,
                    "low": 2395,
                    "close": 2400,
                },
                {
                    "time": "2026-05-18 12:45:00",
                    "open": 2404,
                    "high": 2407,
                    "low": 2398,
                    "close": 2406,
                },
                {
                    "time": "2026-05-18 13:00:00",
                    "open": 2406,
                    "high": 2407,
                    "low": 2405,
                    "close": 2406,
                },
            ]
        )
        bars["ema_long"] = 2410.0  # Price (2406) is below EMA 50 (2410) -> counter-trend

        result = strategy.check_signals(bars, bars, bars, current_spread=1.0)
        self.assertEqual(result, "EMA_FILTER_BLOCKED")

    def test_check_signals_ema_trend_filter_allows_aligned_trend(self):
        strategy = make_strategy()
        bars = pd.DataFrame(
            [
                {
                    "time": "2026-05-18 12:00:00",
                    "open": 2400,
                    "high": 2401,
                    "low": 2399,
                    "close": 2400,
                },
                {
                    "time": "2026-05-18 12:15:00",
                    "open": 2400,
                    "high": 2401,
                    "low": 2399,
                    "close": 2400,
                },
                {
                    "time": "2026-05-18 12:30:00",
                    "open": 2400,
                    "high": 2405,
                    "low": 2395,
                    "close": 2400,
                },
                {
                    "time": "2026-05-18 12:45:00",
                    "open": 2404,
                    "high": 2407,
                    "low": 2398,
                    "close": 2406,
                },
                {
                    "time": "2026-05-18 13:00:00",
                    "open": 2406,
                    "high": 2407,
                    "low": 2405,
                    "close": 2406,
                },
            ]
        )
        bars["ema_long"] = 2400.0  # Price (2406) is above EMA 50 (2400) -> aligned with trend

        result = strategy.check_signals(bars, bars, bars, current_spread=1.0)
        self.assertEqual(result, "BUY")

    def test_check_signals_ema_data_missing_fails_closed(self):
        strategy = make_strategy()
        bars = pd.DataFrame(
            [
                {
                    "time": "2026-05-18 12:00:00",
                    "open": 2400,
                    "high": 2401,
                    "low": 2399,
                    "close": 2400,
                },
                {
                    "time": "2026-05-18 12:15:00",
                    "open": 2400,
                    "high": 2401,
                    "low": 2399,
                    "close": 2400,
                },
                {
                    "time": "2026-05-18 12:30:00",
                    "open": 2400,
                    "high": 2405,
                    "low": 2395,
                    "close": 2400,
                },
                {
                    "time": "2026-05-18 12:45:00",
                    "open": 2404,
                    "high": 2407,
                    "low": 2398,
                    "close": 2406,
                },
                {
                    "time": "2026-05-18 13:00:00",
                    "open": 2406,
                    "high": 2407,
                    "low": 2405,
                    "close": 2406,
                },
            ]
        )
        # bars has no 'ema_long' column

        result = strategy.check_signals(bars, bars, bars, current_spread=1.0)
        self.assertEqual(result, "EMA_DATA_MISSING")


if __name__ == "__main__":
    unittest.main()
