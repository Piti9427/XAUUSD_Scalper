"""Broker bars, captured Bid ticks, and reference bars must expose mismatches."""

import unittest

import pandas as pd

from scripts.pure_b1.parity import compare_bars, compare_signals, ticks_to_m15


class PureB1ParityTests(unittest.TestCase):
    def test_tick_bid_ohlc_matches_reference_and_reports_one_changed_close(self):
        ticks = pd.DataFrame(
            {
                "time_msc": [
                    int(pd.Timestamp(f"2026-09-29 00:{minute:02d}:00Z").timestamp() * 1000)
                    for minute in (0, 2, 4, 14)
                ],
                "bid": [3000.0, 3001.0, 2999.0, 3000.5],
                "ask": [3000.2, 3001.2, 2999.2, 3000.7],
            }
        )
        tick_bars = ticks_to_m15(ticks)
        same_millisecond = pd.concat([ticks.iloc[:1], ticks.iloc[:1], ticks.iloc[1:]])
        self.assertEqual(ticks_to_m15(same_millisecond).iloc[0]["close"], 3000.5)
        reference = tick_bars.copy()
        result = compare_bars(tick_bars, reference, tolerance=0.001)
        self.assertEqual(result["overlap_bars"], 1)
        self.assertEqual(result["mismatch_bars"], 0)
        reference.iloc[0, reference.columns.get_loc("close")] += 0.02
        mismatch = compare_bars(tick_bars, reference, tolerance=0.001)
        self.assertEqual(mismatch["mismatch_bars"], 1)
        self.assertEqual(mismatch["mismatches"][0]["field"], "close")
        outer_reference = pd.concat(
            [
                tick_bars,
                tick_bars.set_axis(tick_bars.index + pd.Timedelta(minutes=30)),
            ]
        )
        missing = compare_bars(
            pd.concat(
                [
                    outer_reference.iloc[:1],
                    tick_bars.set_axis(tick_bars.index + pd.Timedelta(minutes=15)),
                    outer_reference.iloc[1:],
                ]
            ),
            outer_reference,
            tolerance=0.001,
        )
        self.assertEqual(missing["status"], "FAIL")
        self.assertEqual(missing["broker_only_bars"], 1)

    def test_signal_parity_fails_when_broker_has_one_extra_closed_bar(self):
        opens = pd.date_range("2026-01-01", periods=600, freq="15min", tz="UTC")
        close = [100.0 + i % 2 for i in range(len(opens))]
        broker = pd.DataFrame(
            {
                "open": close,
                "high": [price + 1 for price in close],
                "low": [price - 1 for price in close],
                "close": close,
            },
            index=opens,
        )
        reference = broker.drop(opens[300])
        result = compare_signals(broker, reference)
        self.assertEqual(result["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
