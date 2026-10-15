"""Causal behavior for the separately declared RSI reversal research contract."""

import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from scripts.research.rsi_reversal import SPEC, rsi_reversal_signals


def frame(rsi, *, gap=False):
    index = pd.date_range("2025-01-01", periods=len(rsi), freq="15min", tz="UTC")
    if gap:
        index = index[1:].insert(0, index[0] - pd.Timedelta(minutes=30))
    return pd.DataFrame({"rsi": rsi, "atr": 1.0, "high": 101.0, "low": 99.0}, index=index)


class RsiReversalTests(unittest.TestCase):
    def test_contract_is_separate_from_frozen_registry_and_uses_common_exits(self):
        from scripts.research.strategies import registry

        self.assertNotIn(SPEC.name, {spec.name for spec in registry()})
        self.assertEqual((SPEC.timeframe, SPEC.sl, SPEC.tp, SPEC.entry), (15, 2, 2, "market"))

    def test_only_completed_cross_back_emits_signal(self):
        f = frame([50, 29, 30, 31, 45, 71, 70, 69, 50])
        signal = rsi_reversal_signals(f)
        self.assertEqual(signal.direction.tolist(), [0, 0, 0, 1, 0, 0, 0, -1, 0])
        self.assertTrue(np.isnan(signal.limit.to_numpy()).all())

    def test_missing_adjacent_bar_and_invalid_atr_reject_signal(self):
        f = frame([29, 31], gap=True)
        self.assertFalse(rsi_reversal_signals(f).direction.any())
        f = frame([29, 31])
        f.loc[f.index[1], "atr"] = np.nan
        self.assertFalse(rsi_reversal_signals(f).direction.any())

    def test_prefix_causality(self):
        f = frame([50, 29, 31, 50, 71, 69])
        assert_frame_equal(rsi_reversal_signals(f.iloc[:4]), rsi_reversal_signals(f).iloc[:4])


if __name__ == "__main__":
    unittest.main()
