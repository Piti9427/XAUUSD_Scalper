"""Causal M15 challenger through its public frame/cache interface."""

import unittest
import numpy as np
import pandas as pd

from scripts.research.smc_challenger_signals import prepare_signals, SignalCache, liquidity_pools


def bars_fixture():
    index = pd.date_range("2026-01-01", "2026-02-05T07:00:00", freq="15min", tz="UTC")
    bars = pd.DataFrame(dict(open=100.0, high=120.0, low=93.0, close=100.0), index=index[:-1])
    # Confirm low95, high105, bearish BOS94 -> sweep92 -> protected CHoCH107.
    candles = [
        (100, 104, 98, 101),
        (101, 106, 99, 103),
        (103, 110, 100, 105),
        (105, 107, 100, 102),
        (102, 104, 98, 100),
        (100, 102, 97, 99),
        (99, 101, 95, 98),
        (98, 102, 96, 100),
        (100, 103, 97, 101),
        (101, 105, 98, 102),
        (102, 104, 98, 101),
        (101, 103, 97, 100),
        (100, 102, 96, 98),
        (98, 99, 93.5, 94),
        (94, 97, 92, 94),
        (94, 98, 93, 96),
        (96, 99, 95, 98),
        (98, 100, 97, 99),
        (99, 108, 99, 107),
        (107, 110, 104, 108),
        (108, 109, 102, 103),
    ]
    tail = pd.DataFrame(
        candles,
        columns=["open", "high", "low", "close"],
        index=pd.date_range("2026-02-05T07:00:00", periods=len(candles), freq="15min", tz="UTC"),
    )
    return pd.concat([bars, tail])


class SignalTests(unittest.TestCase):
    def test_pivot_publication_bos_not_entry_and_conflicting_sweep_rejects(self):
        bars = bars_fixture()
        frame = prepare_signals(bars)
        self.assertEqual(
            frame.loc["2026-02-05T09:00:00+00:00", "pivot_confirmed_utc"],
            "2026-02-05T09:15:00+00:00",
        )
        self.assertEqual(frame.loc["2026-02-05T10:15:00+00:00", "structure_event"], "BOS")
        self.assertEqual(frame.loc["2026-02-05T10:15:00+00:00", "direction"], 0)
        bars.iloc[-1] = [100, 121, 92, 100]
        frame = prepare_signals(bars)
        self.assertEqual(frame.signal_reason.iloc[-1], "conflicting_sweeps")
        self.assertEqual(frame.direction.iloc[-1], 0)

    def test_prefix_future_mutation_and_chunk_cache_match(self):
        bars = bars_fixture()
        full = prepare_signals(bars)
        for end in (len(bars) - 6, len(bars) - 3, len(bars) - 1):
            pd.testing.assert_frame_equal(full.iloc[:end], prepare_signals(bars.iloc[:end]))
        changed = bars.copy()
        changed.iloc[-1] = [200, 220, 180, 210]
        pd.testing.assert_frame_equal(full.iloc[:-1], prepare_signals(changed).iloc[:-1])
        cache = SignalCache()
        cache.append(bars.iloc[:-6])
        actual = cache.append(bars.iloc[-10:])
        pd.testing.assert_frame_equal(full, actual)
        corrupt = bars.iloc[-10:].copy()
        corrupt.iloc[0, 0] += 0.1
        with self.assertRaisesRegex(ValueError, "divergence"):
            cache.append(corrupt)

    def test_pools_publish_after_complete_session_missing_pool_stays_unavailable(self):
        bars = bars_fixture()
        pools = liquidity_pools(bars)
        self.assertTrue(np.isnan(pools.loc["2026-02-05T06:30:00+00:00", "asian_low"]))
        self.assertEqual(pools.loc["2026-02-05T06:45:00+00:00", "asian_low"], 93)
        broken = bars.drop(pd.Timestamp("2026-02-05T03:00:00", tz="UTC"))
        pools = liquidity_pools(broken)
        self.assertTrue(np.isnan(pools.asian_low.iloc[-1]))
        self.assertEqual(pools.pdl.iloc[-1], 93)
        broken = bars.drop(pd.Timestamp("2026-02-04T23:00:00", tz="UTC"))
        self.assertTrue(np.isnan(liquidity_pools(broken).pdl.iloc[-1]))

    def test_fvg_requires_third_close_and_displacement(self):
        bars = bars_fixture()
        bars.iloc[-3, bars.columns.get_loc("open")] = 106
        self.assertEqual(int(prepare_signals(bars).direction.abs().sum()), 0)
        bars = bars_fixture()
        bars.iloc[-2, bars.columns.get_loc("low")] = 99
        self.assertEqual(int(prepare_signals(bars).direction.abs().sum()), 0)
        bars = bars_fixture().drop(bars_fixture().index[-2])
        self.assertEqual(int(prepare_signals(bars).direction.abs().sum()), 0)

    def test_wick_invalidation_retest_expiry_and_no_revived_setup(self):
        bars = bars_fixture()
        bars.iloc[-1] = [94, 95, 90, 91]
        self.assertEqual(prepare_signals(bars).signal_reason.iloc[-1], "wick_invalidated")
        base = bars_fixture().iloc[:-1]
        tail = pd.DataFrame(
            [[108, 109, 105, 106]] * 4 + [[106, 107, 102, 103]],
            columns=base.columns,
            index=pd.date_range(base.index[-1] + pd.Timedelta(minutes=15), periods=5, freq="15min"),
        )
        frame = prepare_signals(pd.concat([base, tail]))
        self.assertEqual(frame.signal_reason.iloc[-1], "retest_expired")
        self.assertEqual(int(frame.direction.abs().sum()), 0)
        source = bars_fixture()
        repeat = pd.DataFrame(
            [[104, 105, 102, 103]] * 3,
            columns=source.columns,
            index=pd.date_range(
                source.index[-1] + pd.Timedelta(minutes=15), periods=3, freq="15min"
            ),
        )
        self.assertEqual(int(prepare_signals(pd.concat([source, repeat])).direction.abs().sum()), 1)

    def test_unwarmed_macro_blocks_candidate(self):
        bars = bars_fixture().loc["2026-02-05":]
        frame = prepare_signals(bars)
        self.assertEqual(frame.signal_reason.iloc[-1], "macro_unavailable")
        self.assertEqual(frame.direction.iloc[-1], 0)

    def test_sweep_protected_choch_fvg_later_retest_buy_and_sell(self):
        bars = bars_fixture()
        for side in (1, -1):
            source = bars.copy()
            if side == -1:
                source = pd.DataFrame(
                    dict(
                        open=200 - bars.open,
                        high=200 - bars.low,
                        low=200 - bars.high,
                        close=200 - bars.close,
                    ),
                    index=bars.index,
                )
            frame = prepare_signals(source)
            self.assertEqual(frame.direction.iloc[-1], side)
            self.assertEqual(int((frame.direction != 0).sum()), 1)
            self.assertEqual(frame.structure_event.iloc[-3], "CHOCH")
            self.assertEqual(frame.fvg_published.iloc[-2], True)
            self.assertEqual(frame.direction.iloc[-2], 0)
            self.assertAlmostEqual(
                frame.stop_low.iloc[-1] if side == 1 else frame.stop_high.iloc[-1],
                92 if side == 1 else 108,
            )

    def test_naive_and_invalid_ohlc_rejected(self):
        bars = bars_fixture()
        bars.index = bars.index.tz_localize(None)
        with self.assertRaises(ValueError):
            prepare_signals(bars)
        bars = bars_fixture()
        bars.iloc[-1, bars.columns.get_loc("high")] = 1
        with self.assertRaises(ValueError):
            prepare_signals(bars)


if __name__ == "__main__":
    unittest.main()
