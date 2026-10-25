"""Selected native Rules and causal price-decision seam, no broker calls."""

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from scripts.c22_selected.strategy import (
    CANDIDATE_ID, CONTRACT, MAGIC, ROOT, SNAPSHOT, SOURCE_PATHS,
    SelectedBarCache, SelectedStrategy, decide, verify_sources,
)
from scripts.research.c22_frequency_adapter import prepare
from tests.demo.test_c22h4_demo import buy_bars
from tests.demo.test_c22h4_strategy import bars


EXPECTED_RULES = {
    "failed_closes": 0, "reset_after_exit": False, "stagnant_bars": 0,
    "entry_mode": "immediate", "stop_mode": "atr", "protect_mode": "break_even",
    "entry_guard": "off", "buy_pause_drawdown": 0.0, "risk_mode": "static",
    "risk_cap": 0.1, "daily_loss_limit": 0.1, "target_atr": 3.0,
    "min_depth_atr": 0.0, "target_rr": 1.35, "cooldown_bars": 2,
    "session_mode": "all", "max_daily_losses": 2, "protect_after_r": 1.0,
    "stop_atr": 2.5, "buy_stop_atr": 2.5, "buy_target_rr": 3.0,
    "buy_protect_mode": "break_even", "sizing_mode": "fixed",
    "holding_mode": "legacy", "buy_stop_mode": None, "buy_risk_cap": None,
    "buy_sizing_mode": None, "sell_stop_mode": None,
}


def signal_bars(direction):
    """Fixed synthetic prefix ending in a known selected BUY or SELL signal."""
    return buy_bars().iloc[:-1].copy() if direction == 1 else bars()


def selected_config(root=ROOT):
    return {
        "snapshot": SNAPSHOT, "contract_id": CANDIDATE_ID,
        "contract": dict(CONTRACT), "symbol": "XAUUSDm", "volume": 0.01,
        "real_money": "PROHIBITED",
        "source_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCE_PATHS},
    }


class SelectedStrategyTests(unittest.TestCase):
    def test_cache_uses_complete_selected_native_rules(self):
        cache = SelectedBarCache()
        cache.append(bars())
        self.assertEqual(asdict(cache.rules), EXPECTED_RULES)
        self.assertEqual(CANDIDATE_ID, "26b8bcd69e043653")
        self.assertEqual(
            hashlib.sha256(json.dumps(asdict(cache.rules), sort_keys=True).encode()).hexdigest()[:16],
            "26b8bcd69e043653",
        )

    def test_both_signal_directions_match_frozen_research_seed(self):
        seed = {
            "strategy": "reward156", "formula": "archived", "buy_pause_drawdown": 0.0,
            "risk_cap": 0.1, "rsi_period": 7, "rsi_threshold": 30, "sell_lookback": 48,
            "sell_ema": 50, "macro_span": 200, "buy_stop_atr": 2.0, "buy_target_rr": 2.0,
            "buy_protect_mode": "break_even", "stop_atr": 2.5, "sell_target": "r1.35",
            "protect_mode": "break_even", "daily_loss_limit": 0.1, "max_daily_losses": 2,
            "cooldown_bars": 0, "entry_session": "all", "risk_mode": "static", "buy_ema": 50,
        }
        for direction in (-1, 1):
            with self.subTest(direction=direction):
                source = signal_bars(direction)
                frame, _ = prepare(source, seed)
                cache = SelectedBarCache()
                cache.append(source)
                pd.testing.assert_series_equal(cache.frame.direction, frame.direction)
                self.assertEqual(int(cache.row.direction), direction)

    def test_rounded_buy_sell_geometry_and_cost_inclusive_cap(self):
        spec = {
            "trade_tick_size": 0.001, "trade_contract_size": 100,
            "volume_min": 0.01, "volume_max": 100, "volume_step": 0.01, "leverage": 2000,
        }
        costs = {"slippage_allowance_price": 0.1, "commission_per_lot": 7.0}
        for direction, expected in ((1, (100.5, 97.999, 108.003)), (-1, (100.1, 102.601, 96.724))):
            with self.subTest(direction=direction):
                cache = SelectedBarCache()
                cache.append(signal_bars(direction))
                cache.row["atr"] = 1.0001
                plan = decide(cache, 100.2, 100.4, spec, costs, 200)
                for value, literal in zip((plan.entry, plan.stop, plan.target), expected):
                    self.assertAlmostEqual(value, literal)
                self.assertAlmostEqual(plan.risk, 2.671)
                self.assertEqual(decide(cache, 100.2, 100.4, spec, costs, 26.70), "risk_cap")
                self.assertNotIsInstance(decide(cache, 100.2, 100.4, spec, costs, 27), str)

    def test_cache_omissions_and_changed_overlap_never_rewrite_causal_prefix(self):
        source = signal_bars(-1)
        cache = SelectedBarCache()
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
        pd.testing.assert_frame_equal(cache.bars, source)

    def test_warmup_and_naive_input_fail_closed(self):
        cache = SelectedBarCache()
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, "macro_warmup_insufficient"):
                cache.append(bars(3200))
        naive = bars()
        naive.index = naive.index.tz_localize(None)
        with self.assertRaises(ValueError):
            SelectedBarCache().append(naive)

    def test_contract_sources_identity_and_all_risk_invariants_are_bound(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for name in SOURCE_PATHS:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# fixture source\n")
            config = selected_config(root)
            verify_sources(config, root=root)
            for change in (
                {"contract_id": "other"}, {"snapshot": "old-demo"}, {"volume": 0.02},
                {"real_money": "ALLOWED"}, {"contract": dict(CONTRACT, risk_cap=0.2)},
                {"contract": dict(CONTRACT, cooldown_bars=0)}, {"source_hashes": None},
            ):
                with self.subTest(change=change), self.assertRaisesRegex(ValueError, "source_drift"):
                    verify_sources(config | change, root=root)
            (root / SOURCE_PATHS[0]).write_text("# changed\n")
            with self.assertRaisesRegex(ValueError, "source_drift"):
                verify_sources(config, root=root)

    def test_source_drift_blocks_admission_frame_before_any_broker_call(self):
        strategy = SelectedStrategy({})
        with self.assertRaisesRegex(ValueError, "source_drift"):
            strategy.frame(signal_bars(-1), None, "XAUUSDm", None)
        self.assertTrue(strategy.protects(1))
        self.assertTrue(strategy.protects(-1))
        self.assertFalse(strategy.protects(0))
        self.assertEqual((strategy.magic, strategy.max_daily_losses, strategy.cooldown_bars), (MAGIC, 2, 2))

    def test_native_rules_mutation_cannot_change_live_geometry(self):
        cache = SelectedBarCache()
        cache.append(signal_bars(-1))
        cache.rules = replace(cache.rules, risk_cap=0.2)
        self.assertEqual(decide(cache, 100.2, 100.4, {}, {}, 200), "selected_rules_drift")

    def test_extending_prefix_does_not_change_prior_causal_signals(self):
        full = buy_bars()
        cache = SelectedBarCache()
        cache.append(full.iloc[:-8])
        earlier = cache.frame.copy()
        cache.append(full.iloc[-100:])
        pd.testing.assert_series_equal(cache.frame.loc[earlier.index, "direction"], earlier.direction)
        pd.testing.assert_series_equal(cache.frame.loc[earlier.index, "macro_ema"], earlier.macro_ema)
