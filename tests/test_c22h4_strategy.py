"""Frozen candidate public decision/cache contract, no broker side effects."""

import unittest
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scripts.c22h4.strategy import BarCache, CONTRACT, decide, verify_sources


def bars(count=3216):
    close = 200 - np.arange(count) * 0.01
    close[-1] -= 3
    return pd.DataFrame(
        dict(open=close, high=close + 0.5, low=close - 0.5, close=close),
        index=pd.date_range("2026-08-01", periods=count, freq="15min", tz="UTC"),
    )


class CandidateTests(unittest.TestCase):
    def test_macro_needs_201_complete_h4(self):
        with self.assertRaisesRegex(ValueError, "macro_warmup_insufficient"):
            BarCache().append(bars(3200))
        cache = BarCache()
        cache.append(bars())
        self.assertTrue(np.isfinite(cache.row.macro_ema))

    def test_cache_rejects_changed_or_missing_overlap_and_reuses_row(self):
        cache = BarCache()
        source = bars()
        cache.append(source)
        old = cache.row
        cache.append(source.iloc[-100:])
        self.assertIs(cache.row, old)
        changed = source.iloc[-100:].copy()
        changed.iloc[0, 0] += 0.001
        with self.assertRaisesRegex(ValueError, "bar_cache_divergence"):
            cache.append(changed)
        with self.assertRaisesRegex(ValueError, "bar_cache_divergence"):
            cache.append(source.iloc[-100:].drop(source.index[-50]))

    def test_warmup_remains_blocked_on_duplicate_poll(self):
        cache = BarCache()
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, "macro_warmup_insufficient"):
                cache.append(bars(3200))

    def test_frozen_sources_reject_hash_contract_and_missing_source(self):
        config = json.loads(Path("config/c22h4-demo.json").read_text())
        verify_sources(config)
        with self.assertRaisesRegex(ValueError, "source_drift"):
            verify_sources(config | {"source_hashes": None})
        for changed in (
            config | {"contract_id": "other"},
            config | {"source_hashes": config["source_hashes"] | {"scripts/strategy.py": "0" * 64}},
        ):
            with self.assertRaisesRegex(ValueError, "source_drift"):
                verify_sources(changed)

    def test_signal_and_geometry_equal_research(self):
        from scripts.research.reward156_search import prepare_candidate
        from scripts.research.breakout_entry import prepare_entry
        from scripts.research.breakout_models import Costs

        source = bars()
        frame, rules = prepare_candidate(source, CONTRACT)
        cache = BarCache()
        cache.append(source)
        pd.testing.assert_series_equal(cache.frame.direction, frame.direction)
        self.assertEqual(int(cache.row.direction), -1)
        spec = dict(
            trade_tick_size=0.001,
            trade_contract_size=100,
            volume_min=0.01,
            volume_max=100,
            volume_step=0.01,
            leverage=2000,
        )
        costs = dict(slippage_allowance_price=0.1, commission_per_lot=0)
        actual = decide(cache, 164.85, 165.05, spec, costs, 200)
        self.assertEqual(
            actual,
            prepare_entry(
                frame.iloc[-1], 164.85, 165.05, spec, rules, Costs(slippage=0.1), 200, 200
            ),
        )
        self.assertAlmostEqual(actual.entry, 164.75)

    def test_buy_target_uses_rounded_stop_distance(self):
        from test_c22h4_demo import buy_bars

        cache = BarCache()
        cache.append(buy_bars())
        self.assertEqual(int(cache.row.direction), 1)
        plan = decide(
            cache,
            100.2,
            100.4,
            dict(trade_tick_size=0.01, trade_contract_size=100, leverage=2000),
            dict(slippage_allowance_price=0.1, commission_per_lot=0),
            200,
        )
        # ATR=1, adverse entry=100.5, SL=99, target=100.5+2*1.5.
        self.assertEqual((plan.entry, plan.stop, plan.target), (100.5, 99.0, 103.5))

    def test_append_preserves_full_indicator_prefix(self):
        from scripts.research.reward156_search import prepare_candidate

        source = bars(3232)
        cache = BarCache()
        cache.append(source.iloc[:3216])
        cache.append(source.iloc[-100:])
        expected, _ = prepare_candidate(source, CONTRACT)
        pd.testing.assert_series_equal(cache.frame.direction, expected.direction)
        pd.testing.assert_frame_equal(cache.bars, source)
