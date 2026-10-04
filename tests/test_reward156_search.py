"""Profit/survival policy and finite causal research search."""

import unittest

import numpy as np
import pandas as pd

from scripts.research.reward156_search import (
    cell_gates,
    config_id,
    seeds,
    variants,
    combinations,
    prepare_candidate,
)
from scripts.research.reward156_tuning import prepare_contract
from scripts.research.campaign_signals import candidate_frame
from tests import test_reward156_tuning as fixtures


class SearchTests(unittest.TestCase):
    def test_policy_boundaries_and_undefined_rr(self):
        m = dict(
            net_usd=50,
            max_dd_pct=45,
            trades=60,
            buy_trades=1,
            sell_trades=59,
            max_admitted_risk_pct=10,
            terminal_risk_blockage=False,
            final_balance=250,
            bankrupt=False,
            win_rate=None,
            realized_rr=None,
        )
        peers = [dict(net_usd=-10), dict(net_usd=49)]
        self.assertTrue(all(cell_gates(m, peers, "full").values()))
        for change in [
            dict(net_usd=49.99),
            dict(max_dd_pct=45.01),
            dict(trades=59),
            dict(trades=0),
            dict(final_balance=0),
            dict(buy_trades=0),
            dict(max_admitted_risk_pct=10.01),
            dict(terminal_risk_blockage=True),
            dict(bankrupt=True),
        ]:
            self.assertFalse(all(cell_gates(dict(m, **change), peers, "full").values()))
        self.assertFalse(all(cell_gates(m, [dict(net_usd=50)], "full").values()))
        half = dict(m, net_usd=-20, trades=10, buy_trades=0)
        self.assertTrue(all(cell_gates(half, peers, "first_half").values()))
        self.assertFalse(all(cell_gates(dict(half, net_usd=-20.01), peers, "first_half").values()))

    def test_finite_catalog_single_factor_and_dedup(self):
        for seed in seeds():
            candidates = variants(seed)
            self.assertLessEqual(len(candidates), 27)
            self.assertEqual(len({config_id(c) for c in candidates}), len(candidates))
            self.assertNotIn(config_id(seed), {config_id(c) for c in candidates})
            for c in candidates:
                keys = [k for k in seed if k not in ("name", "group", "parent")]
                self.assertEqual(sum(seed[k] != c[k] for k in keys), 1)
                self.assertEqual(c["risk_cap"], 0.1)
                self.assertEqual(c["buy_pause_drawdown"], 0)
            chosen = [
                next(c for c in candidates if c["group"] == g)
                for g in ("signal", "exit", "circuit")
            ]
            combined = combinations(seed, chosen)
            self.assertEqual(len(combined), 4)
            self.assertEqual(len({config_id(c) for c in combined}), 4)

    def test_frozen_default_and_archived_seed_parity(self):
        bars = fixtures.TuningTests().bars(4000)
        close = 2000 + np.cumsum(np.random.default_rng(42).normal(size=len(bars)) * 2)
        bars[["open", "close"]] = np.column_stack([close, close])
        bars["high"], bars["low"] = close + 0.2, close - 0.2
        seed = dict(seeds()[0], macro_span=0)
        actual, rules = prepare_candidate(bars, seed)
        expected, old_rules = prepare_contract(
            bars, dict(strategy="reward156", macro_span=0, buy_pause_drawdown=0)
        )
        pd.testing.assert_series_equal(actual.direction, expected.direction)
        self.assertGreater((actual.direction == 1).sum(), 0)
        self.assertGreater((actual.direction == -1).sum(), 0)
        self.assertEqual(rules.stop_atr, old_rules.stop_atr)
        warmed, _ = prepare_candidate(bars, seeds()[0])
        reference, _ = prepare_contract(
            bars, dict(strategy="reward156", macro_span=100, buy_pause_drawdown=0)
        )
        pd.testing.assert_series_equal(warmed.direction, reference.direction)
        self.assertGreater((warmed.direction != 0).sum(), 0)
        archived = seeds()[2]
        raw, _ = prepare_contract(
            bars, dict(strategy="reward156", macro_span=0, buy_pause_drawdown=0)
        )
        expected = candidate_frame(
            raw,
            "off",
            0,
            oscillator_spec=dict(
                period=14,
                threshold=25,
                trend_span=50,
                side="buy",
                parent_lookback=96,
                parent_trend_span=50,
            ),
        )
        actual, rules = prepare_candidate(bars, archived)
        pd.testing.assert_series_equal(actual.direction, expected.direction)
        pd.testing.assert_series_equal(actual.hh, expected.hh)
        self.assertEqual(rules.buy_stop_atr, 1.5)
        self.assertEqual(rules.buy_target_rr, 2)
        self.assertEqual(rules.protect_mode, "break_even")
        future = bars.copy()
        future.loc[future.index[600] :, ["open", "close", "high", "low"]] += 500
        later, _ = prepare_candidate(future, archived)
        pd.testing.assert_series_equal(actual.direction.iloc[:600], later.direction.iloc[:600])

    def test_cooldown_two_bars_is_supported(self):
        seed = seeds()[0]
        seed["cooldown_bars"] = 2
        _, rules = prepare_candidate(fixtures.TuningTests().bars(), seed)
        self.assertEqual(rules.cooldown_bars, 2)


if __name__ == "__main__":
    unittest.main()


class CampaignTests(unittest.TestCase):
    def test_checkpoint_integrity_repeat_and_corruption(self):
        from pathlib import Path
        import tempfile
        from scripts.research.reward156_campaign import Checkpoints

        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            cache = Checkpoints(output, "contract")
            calls = []

            def execute():
                calls.append(1)
                return {"ledger": [{"net": 3.0}], "equity": [200.0, 203.0]}

            cache.execute("cell", execute)
            self.assertEqual(len(calls), 1)
            cache.execute("cell", execute, repeat=True)
            self.assertEqual(len(calls), 2)
            cache.execute("cell", execute, repeat=True)
            self.assertEqual(len(calls), 2)
            (output / "cells/cell.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                cache.execute("cell", execute)

    def test_config_and_source_drift_rejected(self):
        from pathlib import Path
        import json
        import tempfile
        from scripts.research.reward156_campaign import CONFIG, freeze, validate_config

        config = json.loads(CONFIG.read_text())
        validate_config(config)
        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            digest = freeze(output, CONFIG, config)
            self.assertEqual(digest, freeze(output, CONFIG, config))
            config["volume"] = 0.02
            with self.assertRaisesRegex(ValueError, "pins changed"):
                validate_config(config)
            with self.assertRaisesRegex(ValueError, "resume source/config/input drift"):
                freeze(output, CONFIG, config)

    def test_deterministic_rank_and_holdout_requires_lock(self):
        from pathlib import Path
        import tempfile
        from scripts.research.reward156_search import rank
        from scripts.research.reward156_holdout import verify_lock

        a, b = seeds()[:2]
        rows = [
            dict(
                contract=c["name"],
                window="full",
                cost_view="swap",
                metrics=dict(net_usd=100, max_dd_pct=30),
                gates=dict(net=True),
            )
            for c in (a, b)
        ]
        ordered = sorted([a, b], key=lambda c: rank(c, rows))
        self.assertEqual(ordered, sorted([b, a], key=lambda c: rank(c, rows)))
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(FileNotFoundError):
                verify_lock(Path(root), a)


class ReviewRegressionTests(unittest.TestCase):
    def test_dedup_retains_all_per_seed_factor_choices(self):
        from scripts.research.reward156_search import variant_catalog

        chosen = seeds()[:2]
        new, refs = variant_catalog(chosen, seeds())
        self.assertEqual(len({config_id(c) for c in new}), len(new))
        for seed in chosen:
            expected = {config_id(c) for c in variants(seed)}
            self.assertEqual(expected, {config_id(c) for c in refs[config_id(seed)]})
        macro0 = [
            c for c in refs[config_id(chosen[1])] if c["group"] == "signal" and c["macro_span"] == 0
        ]
        self.assertEqual(len(macro0), 1)
        reused = next(c for c in refs[config_id(chosen[1])] if config_id(c) == config_id(chosen[0]))
        self.assertEqual(reused["name"], chosen[0]["name"])

    def test_interrupted_result_recomputed_and_lock_immutable(self):
        from pathlib import Path
        import tempfile
        from scripts.research.reward156_campaign import Checkpoints
        from scripts.research.reward156_holdout import verify_lock
        from scripts.research.reward156_tuning import atomic_json
        from scripts.research.tune_breakout_logic import sha256

        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            atomic_json(output / "cells/interrupted.json", {"unproved": True})
            cache = Checkpoints(output, "digest")
            self.assertEqual(cache.execute("interrupted", lambda: {"fresh": True}), {"fresh": True})
            winner = seeds()[0]
            atomic_json(output / "contract.json", {"behavior_sha256": "digest"})
            atomic_json(output / "discovery-results.json", {"selected": winner["name"]})
            atomic_json(
                output / "selection-lock.json",
                dict(
                    candidate=winner,
                    behavior_sha256="digest",
                    discovery_results_sha256=sha256(output / "discovery-results.json"),
                ),
            )
            atomic_json(output / "results.json", {"holdout": "PASSED"})
            self.assertEqual(verify_lock(output, winner)["candidate"], winner)
            atomic_json(output / "discovery-results.json", {"tampered": True})
            with self.assertRaisesRegex(ValueError, "lock mismatch"):
                verify_lock(output, winner)

    def test_cooldown_two_bars_rejects_then_admits_on_boundary(self):
        from scripts.research.breakout_logic import replay, Costs, Rules
        from tests.test_breakout_logic import sample, BROKER, START

        frame, _ = sample()
        frame = pd.concat([frame, frame.iloc[-1:]])
        frame.index = pd.date_range(START, periods=4, freq="15min")
        frame["direction"] = 1
        times = START.value // 10**6 + np.array(
            [900000, 900001, 1800000, 2700000, 3600000, 4500000]
        )
        bid = np.array([100.0, 96.0, 100.0, 100.0, 100.0, 100.0])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(cooldown_bars=2),
            Costs(),
            start=START,
            end=START + pd.Timedelta(minutes=80),
            capture_events=True,
        )
        self.assertEqual(result["rejections"]["cooldown"], 2)
        self.assertEqual(result["trades"], 2)
        self.assertEqual(result["admission_events"][-1]["reason"], "admitted")
        self.assertEqual(result["ledger"][1]["entry_time_utc"], "2026-04-01T01:00:00+00:00")


class SerializationTests(unittest.TestCase):
    def test_fresh_and_resumed_replay_matrix_serializes_native_boolean_gates(self):
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from scripts.research.reward156_campaign import Campaign, Checkpoints, CONTROLS
        from scripts.research.breakout_logic import Rules
        from scripts.research.reward156_tuning import atomic_json
        from tests.test_breakout_logic import sample, BROKER

        frame, ticks = sample()
        frame["macro_blocked"] = False
        frame["macro_unavailable"] = False
        broker = dict(
            BROKER, swap_mode=1, swap_long=-1000, swap_short=0, swap_rollover3days=3, point=0.001
        )
        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            campaign = Campaign.__new__(Campaign)
            campaign.output = output
            campaign.config = dict(
                datasets={
                    "A": dict(
                        start="2026-04-01", split="2026-04-01T00:30:00", end="2026-04-01T01:00:00"
                    )
                },
                costs={"base": {}},
            )
            campaign.datasets = {"A": (frame, ticks, broker)}
            campaign.checkpoints = Checkpoints(output, "digest")
            campaign.rows = {}
            with patch(
                "scripts.research.reward156_campaign.prepare_candidate",
                return_value=(frame, Rules()),
            ):
                for candidate in [*CONTROLS, seeds()[0]]:
                    campaign.cells(candidate)
                fresh = list(campaign.rows.values())
                atomic_json(output / "matrix.json", fresh)
                for row in fresh:
                    self.assertTrue(all(type(v) is bool for v in row.get("gates", {}).values()))
                campaign.rows = {}
                for candidate in [*CONTROLS, seeds()[0]]:
                    campaign.cells(candidate)
                atomic_json(output / "resumed.json", list(campaign.rows.values()))
            self.assertEqual(
                json.loads((output / "matrix.json").read_text()),
                json.loads((output / "resumed.json").read_text()),
            )


class SwapCircuitTests(unittest.TestCase):
    def test_break_even_swap_loss_counts_for_daily_circuit_before_next_admission(self):
        from scripts.research.breakout_logic import replay, Costs, Rules
        from scripts.research.rollover import SwapPolicy
        from tests.test_breakout_logic import sample, BROKER, START

        frame, _ = sample()
        frame = pd.concat([frame, frame.iloc[-1:], frame.iloc[-1:]])
        frame.index = pd.DatetimeIndex(
            [
                START + pd.Timedelta(hours=23, minutes=15),
                START + pd.Timedelta(hours=23, minutes=30),
                START + pd.Timedelta(days=1),
                START + pd.Timedelta(days=1, minutes=15),
                START + pd.Timedelta(days=2),
            ]
        )
        frame["direction"] = [1, 0, 1, 1, 1]
        stamps = [
            START + pd.Timedelta(hours=23, minutes=30),
            START + pd.Timedelta(hours=23, minutes=45),
            START + pd.Timedelta(days=1),
            START + pd.Timedelta(days=1, minutes=15),
            START + pd.Timedelta(days=1, minutes=30),
            START + pd.Timedelta(days=2, minutes=15),
        ]
        times = np.array([s.value // 10**6 for s in stamps])
        bid = np.array([100.0, 102.0, 100.2, 100.0, 100.0, 100.0])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(
                buy_stop_atr=1.5,
                buy_target_rr=2.0,
                buy_protect_mode="break_even",
                protect_after_r=1.0,
                max_daily_losses=1,
            ),
            Costs(),
            start=START,
            end=START + pd.Timedelta(days=2, minutes=30),
            swap_policy=SwapPolicy(-1000, 0, 0.001),
            capture_events=True,
        )
        first = result["ledger"][0]
        self.assertTrue(first["protection_active"])
        self.assertEqual(first["stop_updates"], 1)
        self.assertEqual(first["reason"], "SL")
        self.assertAlmostEqual(first["net_before_swap_usd"], 0)
        self.assertAlmostEqual(first["swap_usd"], -3)
        self.assertAlmostEqual(first["net"], -3)
        self.assertEqual(result["trades"], 2)
        self.assertEqual(result["rejections"]["daily_loss_count"], 2)
        self.assertEqual(result["admission_events"][-1]["reason"], "admitted")
