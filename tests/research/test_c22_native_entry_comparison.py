import unittest

import numpy as np
import pandas as pd

from scripts.c22_selected.strategy import SelectedBarCache
from scripts.research.c22_native_entry_comparison import entry_profiles


class NativeEntryComparisonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(26)
        index = pd.date_range("2023-01-01", periods=16 * 450, freq="15min", tz="UTC")
        close = 1800 + np.cumsum(rng.normal(.04, .7, len(index)))
        opening = np.r_[close[0], close[:-1]]
        cls.bars = pd.DataFrame(dict(open=opening, close=close, high=np.maximum(opening, close) + .8,
                                     low=np.minimum(opening, close) - .8), index=index)

    def test_prefix_matches_native_and_filters_only_remove_native_signals(self):
        _, all_signals, _ = entry_profiles(self.bars)
        prefix = self.bars.iloc[:16 * 349 + 3]
        _, signals, _ = entry_profiles(prefix)
        pd.testing.assert_frame_equal(signals, all_signals.loc[prefix.index])
        self.assertFalse(signals.iloc[:201 * 16 - 1].any().any())
        cache = SelectedBarCache()
        cache.append(prefix)
        np.testing.assert_array_equal(signals.native.iloc[201 * 16 - 1:],
                                      cache.frame.direction.iloc[201 * 16 - 1:])
        for floor in (20, 25):
            filtered = signals[f"filter{floor}"]
            add = signals[f"add32_adx{floor}"]
            retained = filtered.ne(0)
            self.assertTrue(retained.any())
            np.testing.assert_array_equal(filtered[retained], signals.native[retained])
            np.testing.assert_array_equal(add[retained], filtered[retained])
            self.assertTrue((add.ne(0) & ~retained).any())

    def test_incomplete_h4_blocks_new_decisions_until_next_complete_h4(self):
        gap = self.bars.index[16 * 350]
        _, signals, _ = entry_profiles(self.bars.drop(gap))
        decisions = signals.index + pd.Timedelta(minutes=15)
        after_gap = (decisions >= gap + pd.Timedelta(hours=4)) & (decisions < gap + pd.Timedelta(hours=8))
        self.assertEqual(after_gap.sum(), 16)
        self.assertFalse(signals.loc[after_gap].any().any())
