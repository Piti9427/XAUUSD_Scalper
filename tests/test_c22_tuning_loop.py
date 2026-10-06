"""Diversified research parent selection and copy-on-write input seams."""

import tempfile
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from scripts.research.c22_frequency_policy import search_rank


class ParentSelectionTests(unittest.TestCase):
    def test_every_lane_prioritizes_risk_safe_candidate(self):
        from scripts.research.c22_tuning_search import LANES, exploration_rank

        controls = {v: {"net_usd": 280.0} for v in ("base-swap", "stress-swap")}
        safe = dict(
            net_usd=100.0,
            max_dd_pct=50.0,
            mean_entries=5.0,
            min_equity=100.0,
            bankrupt=False,
            terminal_risk_blockage=False,
            max_admitted_risk_pct=9.0,
            fixed_lot=True,
        )
        unsafe = safe | dict(
            net_usd=700.0, max_dd_pct=20.0, mean_entries=30.0, max_admitted_risk_pct=11.0
        )
        rows = {
            "safe": {v: dict(safe) for v in controls},
            "unsafe": {v: dict(unsafe) for v in controls},
        }
        for lane in LANES:
            with self.subTest(lane=lane):
                self.assertEqual(
                    min(rows, key=lambda i: exploration_rank(i, rows[i], controls, lane)), "safe"
                )

    def test_frequency_lane_expands_parent_rejected_by_original_rank(self):
        from scripts.research.c22_tuning_search import select_parents

        def pair(net, dd, frequency):
            row = dict(
                net_usd=net,
                max_dd_pct=dd,
                mean_entries=frequency,
                min_equity=100.0,
                bankrupt=False,
                terminal_risk_blockage=False,
                max_admitted_risk_pct=9.0,
                fixed_lot=True,
            )
            return {"base-swap": row, "stress-swap": dict(row)}

        controls = {"base-swap": {"net_usd": 280.0}, "stress-swap": {"net_usd": 280.0}}
        rows = {
            "quality_a": pair(700.0, 35.0, 5.3),
            "quality_b": pair(690.0, 35.0, 5.3),
            "quality_c": pair(680.0, 35.0, 5.3),
            "dense": pair(450.0, 56.0, 12.0),
        }
        original = sorted(rows, key=lambda i: search_rank(i, rows[i], controls))[:3]
        self.assertNotIn("dense", original)
        selected = select_parents(rows, set(), controls)
        self.assertIn("dense", [p["id"] for p in selected])
        self.assertEqual(len({p["id"] for p in selected}), 3)
        self.assertEqual([p["lane"] for p in selected], ["frequency", "balanced", "quality"])
        self.assertEqual(
            selected, select_parents(dict(reversed(list(rows.items()))), set(), controls)
        )

    def test_expanded_and_dead_candidates_do_not_displace_survivors(self):
        from scripts.research.c22_tuning_search import select_parents

        row = dict(
            net_usd=300.0,
            max_dd_pct=30.0,
            mean_entries=10.0,
            min_equity=100.0,
            bankrupt=False,
            terminal_risk_blockage=False,
            max_admitted_risk_pct=9.0,
            fixed_lot=True,
        )

        def pair(r):
            return {"base-swap": r, "stress-swap": dict(r)}

        rows = {
            "a": pair(row),
            "b": pair(row),
            "dead": pair(row | {"min_equity": 0.0, "bankrupt": True, "mean_entries": 100.0}),
        }
        controls = {v: {"net_usd": 280.0} for v in ("base-swap", "stress-swap")}
        selected = select_parents(rows, {"a"}, controls)
        self.assertEqual(selected[0]["id"], "b")
        self.assertNotIn("a", [p["id"] for p in selected])


class TapeCloneTests(unittest.TestCase):
    def test_resize_clone_preserves_prefix_and_original_bytes(self):
        from scripts.research.c22_tuning_data import clone_tape

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.npy"
            target = root / "target.npy"
            np.save(source, np.array([1.0, 2.0, 3.0, 4.0]))
            before = source.read_bytes()
            target_array = clone_tape(source, target, 6)
            target_array[3:] = [9.0, 10.0, 11.0]
            target_array.flush()
            del target_array
            np.testing.assert_array_equal(np.load(target), [1.0, 2.0, 3.0, 9.0, 10.0, 11.0])
            self.assertEqual(source.read_bytes(), before)
            with self.assertRaises(ValueError):
                clone_tape(source, source, 6)


class CapacityTests(unittest.TestCase):
    def test_low_disk_blocks_before_acquisition_with_no_winner(self):
        import json
        from scripts.research.c22_tuning_loop import REPO, run

        with tempfile.TemporaryDirectory(dir=REPO / "runs") as directory:
            output = Path(directory)
            with (
                patch(
                    "scripts.research.c22_tuning_loop.shutil.disk_usage",
                    return_value=SimpleNamespace(free=0),
                ),
                patch("scripts.research.c22_tuning_loop.prepare_input") as acquire,
            ):
                with self.assertRaisesRegex(ValueError, "insufficient disk"):
                    run(output)
                acquire.assert_not_called()
            blocked = json.loads((output / "BLOCKED.json").read_text())
            self.assertEqual(blocked["status"], "BLOCKED")
            self.assertIsNone(blocked["selected"])


class TuningResumeTests(unittest.TestCase):
    def test_real_diversified_cells_resume_and_freeze_lanes_without_relaxing_gates(self):
        import pandas as pd
        from scripts.research.c22_tuning_loop import tune
        from scripts.research.c22_frequency_adapter import baseline_config, config_id
        from scripts.research.c22_frequency_store import Store
        from scripts.research.c22_frequency_policy import qualify
        from tests.test_c22_frequency import bars
        from tests.test_breakout_logic import BROKER

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "input"
            (inputs / "tape").mkdir(parents=True)
            source = bars(3600)
            source.to_csv(inputs / "bars.csv", index_label="bar_open_utc")
            times = (source.index + pd.Timedelta(minutes=15)).as_unit("ms").asi8
            bid = source.close.to_numpy()
            for key, array in zip(("time", "bid", "ask"), (times, bid, bid + 0.2)):
                np.save(inputs / "tape" / f"{key}.npy", array)
            manifest = dict(
                broker=dict(
                    BROKER,
                    swap_mode=1,
                    swap_long=-1000.0,
                    swap_short=0.0,
                    point=0.001,
                    swap_rollover3days=3,
                ),
                requested_start_utc="2024-09-01T00:00:00+00:00",
                requested_end_utc="2024-11-01T00:00:00+00:00",
                actual_last_quote="2024-10-08T12:00:00+00:00",
                costs=dict(
                    base=dict(extra_spread=0.0, slippage=0.0, commission_per_lot=7.0),
                    stress=dict(extra_spread=0.2, slippage=0.1, commission_per_lot=7.0),
                ),
            )
            base = baseline_config()
            configs = [
                base | {"buy_ema": 0, "buy_protect_mode": "break_even"},
                base | {"macro_span": 0},
                base | {"sell_lookback": 24},
            ]
            seeds = [
                dict(id=config_id(c), config=c, lane=lane)
                for c, lane in zip(configs, ("frequency", "balanced", "quality"))
            ]
            excluded = {config_id(base), *(s["id"] for s in seeds)}
            store = Store(root / "search", {"test": "synthetic diversified"})
            result, spent = tune(store, manifest, inputs, seeds, excluded, 4, 1, 9, 5)
            self.assertEqual(result["status"], "PARTIAL")
            frozen = store.get("rounds/001.json")
            self.assertEqual(
                [p["lane"] for p in frozen["parents"]], ["frequency", "balanced", "quality"]
            )
            result, _ = tune(
                Store(root / "search", {"test": "synthetic diversified"}),
                manifest,
                inputs,
                seeds,
                excluded,
                4,
                1,
                None,
                5,
            )
            self.assertEqual(result["new_variants"], 4)
            self.assertTrue(set(result["new_ids"]).isdisjoint(excluded))
            self.assertTrue(
                all(
                    qualify(c["metrics"], result["controls"])["qualified"] == c["qualified"]
                    for c in result["candidates"].values()
                )
            )
            resumed = Store(root / "search", {"test": "synthetic diversified"})
            self.assertEqual(frozen, resumed.get("rounds/001.json"))
            again, spent = tune(resumed, manifest, inputs, seeds, excluded, 4, 1, 0, 5)
            self.assertEqual(again, result)
            self.assertEqual(spent, 0)
            for identity in result["repeated"]:
                for view in ("base-swap", "stress-swap"):
                    self.assertTrue(
                        resumed.get(f"repeats/{identity}-{view}.json")["full_result_match"]
                    )
                    self.assertIn(
                        "swap_policy", resumed.get(f"cells/{identity}-{view}.json")["result"]
                    )

    def test_loop_budget_and_views_cannot_be_relaxed(self):
        import json
        from scripts.research.c22_tuning_loop import validate_config

        config = json.loads(Path("config/c22-tuning-loop.json").read_text())
        validate_config(config)
        for delta in (
            {"new_variants_per_campaign": 299},
            {"max_campaigns": 4},
            {"risk_cap": 0.2},
            {"views": ["base-swap"]},
            {"swap_required": False},
            {"unknown": 1},
        ):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                validate_config(config | delta)
