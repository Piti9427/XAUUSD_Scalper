"""Offline synthetic bundle through campaign, resume and manifest boundaries."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from tests.test_smc_challenger import bars_fixture
from tests.test_smc_challenger_adapter import BROKER
from scripts.research.c22_context_campaign import digest
from scripts.research.smc_challenger_signals import ROOT
from scripts.research.smc_challenger_campaign import campaign
from scripts.research.smc_challenger_campaign import native


def fixture_input(root):
    root.mkdir(parents=True)
    bars = bars_fixture()
    bars.to_csv(root / "bars.csv", index_label="bar_open_utc")
    (root / "tape").mkdir()
    closed = bars.index[-1] + pd.Timedelta(minutes=15)
    # BUY retest103, Thursday triple debit then next tick exits sample.
    times = np.array([closed.value // 10**6, (closed + pd.Timedelta(minutes=1)).value // 10**6])
    for key, array in zip(
        ("time", "bid", "ask"), (times, np.array([103.0, 104.0]), np.array([103.2, 104.2]))
    ):
        np.save(root / "tape" / (key + ".npy"), array)
    manifest = dict(
        schema="smc_input_v1",
        kind="synthetic_fixture",
        requested_start_utc="2026-02-05T00:00:00+00:00",
        requested_end_utc="2026-02-06T00:00:00+00:00",
        broker=BROKER,
        costs=dict(
            base=dict(extra_spread=0.0, slippage=0.1, commission_per_lot=0.0),
            stress=dict(extra_spread=0.2, slippage=0.1, commission_per_lot=0.0),
        ),
        cost_basis=dict(
            quote_source="synthetic_fixture",
            swap_source="synthetic_points_fixture",
            commission_source="declared_zero_fixture",
            slippage_basis="declared_assumption",
            commission_unit="USD_per_lot_round_trip",
        ),
        bar_basis="UTC_Bid_M1_15_of_15",
        calendar="conservative_utc_96_bars_v1",
        artifacts={str(p.relative_to(root)): digest(p) for p in root.rglob("*") if p.is_file()},
    )
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root


class CampaignTests(unittest.TestCase):
    def test_archived_parity_uses_archive_broker_not_custom_broker(self):
        from scripts.research.breakout_replay import replay
        from scripts.research.breakout_models import Costs
        from scripts.research.c22_frequency_adapter import baseline_config
        from scripts.research.reward156_search import prepare_candidate
        from scripts.research.rollover import SwapPolicy
        from scripts.research.c22_context_campaign import NAME

        (ROOT / "runs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "runs") as directory:
            base = Path(directory)
            source = fixture_input(base / "custom")
            manifest = json.loads((source / "manifest.json").read_text())
            manifest["kind"] = "historical_discovery"
            manifest["broker"]["swap_long"] = -500.0
            (source / "manifest.json").write_text(json.dumps(manifest))
            archived = base / "archive"
            (archived / "input/continuous-tape").mkdir(parents=True)
            (archived / "cells").mkdir()
            bars = bars_fixture()
            bars.to_csv(archived / "input/continuous-bars.csv", index_label="bar_open_utc")
            ticks = tuple(
                np.load(source / "tape" / (key + ".npy")) for key in ("time", "bid", "ask")
            )
            for key, array in zip(("time", "bid", "ask"), ticks):
                np.save(archived / "input/continuous-tape" / (key + ".npy"), array)
            frame, rules = prepare_candidate(
                bars, {k: v for k, v in baseline_config().items() if k != "buy_ema"}
            )
            original = dict(
                start=manifest["requested_start_utc"],
                end=manifest["requested_end_utc"],
                costs=manifest["costs"],
            )
            for view in ("base", "stress"):
                result = replay(
                    frame,
                    ticks,
                    BROKER,
                    rules,
                    Costs(**manifest["costs"][view]),
                    start=pd.Timestamp(original["start"]),
                    end=pd.Timestamp(original["end"]),
                    swap_policy=SwapPolicy.from_broker(BROKER),
                    capture_events=True,
                )
                (archived / "cells" / (view + "-swap-" + NAME + ".json")).write_text(
                    json.dumps(native(result))
                )
            # External archive attestation read boundary, not signal/replay/accounting.
            with patch(
                "scripts.research.smc_challenger_campaign.verify_baseline",
                return_value=(original, dict(broker=BROKER), {}),
            ):
                result = campaign(
                    base / "out", input_root=source, baseline=archived, workers=1, max_cells=0
                )
            self.assertTrue(result["baseline_parity"])
            self.assertEqual(result["status"], "PARTIAL")

    def test_evaluation_coverage_excludes_tape_prefix_and_reports_warmup(self):
        (ROOT / "runs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "runs") as directory:
            base = Path(directory)
            source = fixture_input(base / "input")
            for key, array in (
                ("time", np.array([pd.Timestamp("2026-02-04", tz="UTC").value // 10**6])),
                ("bid", np.array([100.0])),
                ("ask", np.array([100.2])),
            ):
                path = source / "tape" / (key + ".npy")
                np.save(path, np.r_[array, np.load(path)])
            manifest = json.loads((source / "manifest.json").read_text())
            for name in manifest["artifacts"]:
                manifest["artifacts"][name] = digest(source / name)
            (source / "manifest.json").write_text(json.dumps(manifest))
            result = campaign(base / "out", input_root=source, fixture=True, workers=1, max_cells=0)
            coverage = result["coverage"]
            self.assertEqual(coverage["input_ticks"], 3)
            self.assertEqual(coverage["evaluation_ticks"], 2)
            self.assertEqual(coverage["prefix_ticks"], 1)
            self.assertEqual(coverage["actual_first_quote"], "2026-02-05T12:15:00+00:00")
            self.assertEqual(coverage["h4_unavailable_evaluation_bars"], 0)

    def test_missing_commission_in_either_view_blocks_without_default(self):
        (ROOT / "runs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "runs") as directory:
            base = Path(directory)
            source = fixture_input(base / "input")
            original = json.loads((source / "manifest.json").read_text())
            for view in ("base", "stress"):
                manifest = json.loads(json.dumps(original))
                manifest["costs"][view].pop("commission_per_lot")
                (source / "manifest.json").write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, "cost schema"):
                    campaign(base / view, input_root=source, fixture=True, workers=1)

    def test_partial_resume_equals_fresh_and_artifact_drift_blocks_completion(self):
        (ROOT / "runs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "runs") as directory:
            base = Path(directory)
            source = fixture_input(base / "input")
            output = base / "campaign"
            partial = campaign(output, input_root=source, fixture=True, workers=1, max_cells=1)
            self.assertEqual(partial["status"], "PARTIAL")
            self.assertFalse((output / "COMPLETE.json").exists())
            resumed = campaign(output, input_root=source, fixture=True, workers=1)
            fresh = campaign(base / "fresh", input_root=source, fixture=True, workers=1)
            self.assertEqual(resumed["scorecard"], fresh["scorecard"])
            target = output / "cells/smc-base-current-spec-swap.json"
            target.write_text("{}")
            with self.assertRaisesRegex(ValueError, "drift"):
                campaign(output, input_root=source, fixture=True, workers=1)
            self.assertFalse((output / "COMPLETE.json").exists())

    def test_input_drift_missing_cost_sources_and_no_fixture_shortcut(self):
        (ROOT / "runs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "runs") as directory:
            base = Path(directory)
            source = fixture_input(base / "input")
            with self.assertRaisesRegex(ValueError, "kind"):
                campaign(base / "out", input_root=source, workers=1)
            manifest = json.loads((source / "manifest.json").read_text())
            manifest.pop("cost_basis")
            (source / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "cost sources"):
                campaign(base / "out", input_root=source, fixture=True, workers=1)
            source = fixture_input(base / "other")
            (source / "bars.csv").write_text("bad")
            with self.assertRaisesRegex(ValueError, "drift"):
                campaign(base / "out", input_root=source, fixture=True, workers=1)
        with self.assertRaisesRegex(ValueError, "runs"):
            campaign(ROOT / "docs/reviews/bad-output", fixture=True)

    def test_both_swap_views_comparator_repeat_and_resume(self):
        (ROOT / "runs").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "runs") as directory:
            base = Path(directory)
            source = fixture_input(base / "input")
            output = base / "campaign"
            actual = campaign(output, input_root=source, fixture=True, workers=1)
            self.assertEqual(actual["status"], "FIXTURE_COMPLETE")
            self.assertEqual(len(actual["scorecard"]), 4)
            self.assertTrue(actual["fresh_full_result_match"])
            self.assertEqual(actual["conclusion"], "DESCRIPTIVE_ONLY_NO_SELECTION")
            for row in actual["scorecard"]:
                self.assertIn("swap_usd", row)
            self.assertEqual(campaign(output, input_root=source, fixture=True, workers=1), actual)


if __name__ == "__main__":
    unittest.main()
