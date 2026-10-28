"""Reproduce the observed11/16 H4 mechanism without inventing live candles."""

import unittest

import pandas as pd

from scripts.c22_selected.strategy import SelectedBarCache
from scripts.demo_runtime.market_data import completed_m15_from_m1
from scripts.pure_b1.broker_data import m1_gap_events
from scripts.research.reward156_tuning import closed_h4_ema


BUCKET = pd.Timestamp("2026-10-26T20:00:00Z")
MIDNIGHT = pd.Timestamp("2026-10-27T00:00:00Z")
RECOVERY = pd.Timestamp("2026-10-27T04:00:00Z")


def minute_fixture(*, future_jump=False):
    """Synthetic minute path reproduces observed gap shape, not session proof."""
    rates = []
    for number, stamp in enumerate(pd.date_range(BUCKET, periods=12 * 60, freq="min")):
        if pd.Timestamp("2026-10-26T20:58:00Z") <= stamp < pd.Timestamp("2026-10-26T22:00:00Z"):
            continue
        price = 3004 + number / 1000
        if future_jump and stamp >= RECOVERY:
            price += 500
        rates.append(dict(time=int(stamp.timestamp()), open=price,
                          high=price + 0.05, low=price - 0.05, close=price + 0.01))
    return rates


def warmed_prefix(now, *, future_jump=False):
    index = pd.date_range(end=BUCKET - pd.Timedelta(minutes=15),
                          periods=205 * 16, freq="15min")
    close = pd.Series(3000 + pd.RangeIndex(len(index)).to_numpy() / 1000, index=index)
    history = pd.DataFrame(dict(open=close - 0.005, high=close + 0.02,
                                low=close - 0.02, close=close))
    recent = completed_m15_from_m1(minute_fixture(future_jump=future_jump),
                                   now=now.to_pydatetime())
    return pd.concat([history, recent])


class H4GapRootCauseTests(unittest.TestCase):
    def test_rollover_sized_gap_drops_partial_m15_without_claiming_scheduled_closure(self):
        observed = [row for row in minute_fixture() if row["time"] < MIDNIGHT.timestamp()]
        bars = completed_m15_from_m1(observed, now=MIDNIGHT.to_pydatetime())
        missing = pd.date_range(BUCKET, periods=16, freq="15min").difference(bars.index)
        expected = pd.date_range("2026-10-26T20:45:00Z", periods=5, freq="15min")
        pd.testing.assert_index_equal(missing, expected)
        self.assertEqual(len(bars), 11)
        self.assertEqual(int(bars.close.resample("4h").count().iloc[0]), 11)
        events = m1_gap_events(observed, now=MIDNIGHT.to_pydatetime())
        self.assertEqual(len(events), 5)
        self.assertEqual([event["m1_count"] for event in events], [13, 0, 0, 0, 0])
        self.assertEqual([event["bar_open_utc"] for event in events],
                         [stamp.isoformat() for stamp in expected])
        for event in events:
            self.assertEqual(event["type"], "incomplete_m1_interval")
            self.assertEqual(event["cause"], "missing_minutes")
            self.assertIs(event["late_entry"], False)
            self.assertEqual(set(event),
                             {"type", "bar_open_utc", "m1_count", "cause", "late_entry"})

    def test_partial_rollover_h4_blocks_until_exact_next_complete_h4_close(self):
        cache = SelectedBarCache()
        before_gap_publication = warmed_prefix(MIDNIGHT - pd.Timedelta(seconds=1))
        cache.append(before_gap_publication)
        previous_macro = float(cache.row.macro_ema)
        self.assertEqual(cache.complete_h4, 205)
        self.assertTrue(pd.notna(previous_macro))

        for now in (MIDNIGHT, RECOVERY - pd.Timedelta(seconds=1)):
            with self.subTest(now=now), self.assertRaisesRegex(
                    ValueError, "^macro_latest_h4_incomplete$"):
                cache.append(warmed_prefix(now))
            self.assertTrue(pd.isna(cache.row.macro_ema))
            self.assertEqual(cache.h4_status["prior_h4_open_utc"], BUCKET.isoformat())
            self.assertEqual(cache.h4_status["prior_h4_m15_count"], 11)
            self.assertEqual(cache.h4_status["next_h4_close_utc"], RECOVERY.isoformat())
            self.assertEqual(cache.complete_h4, 205)

        recovered = warmed_prefix(RECOVERY)
        cache.append(recovered)
        completed = recovered.close.resample("4h").agg(["last", "count"])
        expected_macro = completed.loc[completed["count"] == 16, "last"].ewm(
            span=200, adjust=False, min_periods=200).mean().iloc[-1]
        self.assertTrue(pd.notna(cache.row.macro_ema))
        self.assertAlmostEqual(float(cache.row.macro_ema), float(expected_macro), places=10)
        self.assertNotAlmostEqual(float(cache.row.macro_ema), previous_macro, places=8)
        self.assertEqual(cache.complete_h4, 206)
        self.assertEqual(cache.h4_status["prior_h4_open_utc"], MIDNIGHT.isoformat())
        self.assertEqual(cache.h4_status["prior_h4_m15_count"], 16)
        pd.testing.assert_index_equal(cache.bars.index, recovered.index)

    def test_future_complete_h4_does_not_backfill_unavailable_prior_decisions(self):
        before_recovery = warmed_prefix(RECOVERY - pd.Timedelta(seconds=1))
        earlier = closed_h4_ema(before_recovery, 200)
        invalid_decisions = before_recovery.index + pd.Timedelta(minutes=15) >= MIDNIGHT
        self.assertEqual(int(invalid_decisions.sum()), 16)
        pd.testing.assert_index_equal(
            before_recovery.index[invalid_decisions] + pd.Timedelta(minutes=15),
            pd.date_range(MIDNIGHT, periods=16, freq="15min"), check_names=False)
        self.assertTrue(earlier.loc[invalid_decisions].isna().all())
        self.assertTrue(pd.notna(earlier.loc[~invalid_decisions].iloc[-1]))

        future = warmed_prefix(RECOVERY + pd.Timedelta(hours=4), future_jump=True)
        later = closed_h4_ema(future, 200)
        pd.testing.assert_series_equal(later.loc[before_recovery.index], earlier,
                                       check_exact=True, check_freq=False)
        publication_bar = RECOVERY - pd.Timedelta(minutes=15)
        at_recovery = closed_h4_ema(warmed_prefix(RECOVERY), 200)
        self.assertTrue(pd.notna(later.loc[publication_bar]))
        self.assertEqual(float(later.loc[publication_bar]), float(at_recovery.loc[publication_bar]))
        self.assertGreater(float(later.iloc[-1]), float(later.loc[publication_bar]))


if __name__ == "__main__":
    unittest.main()
