import unittest
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.research.native_frequency_replay import replay_case, monthly_metrics
from tests.research.test_smc_challenger_adapter import BROKER
from scripts.research.native_frequency_campaign import (
    select,
    require_fresh_output,
    verify_complete,
    write,
    digest,
    verify_repeats,
)
from scripts.research.native_frequency_replay import CASES, VIEWS


class ReplayTests(unittest.TestCase):
    def test_monthly_cash_books_upfront_fee_separately_from_exit(self):
        result = dict(
            start_utc="2025-01-01T00:00:00+00:00",
            end_exclusive_utc="2025-03-01T00:00:00+00:00",
            ledger=[
                dict(
                    entry_time_utc="2025-01-31T12:00:00+00:00",
                    exit_time_utc="2025-02-01T12:00:00+00:00",
                    commission_usd=0.4,
                    net=4.0,
                )
            ],
            net_usd=4.0,
            final_balance=204.0,
            max_dd_pct=1.0,
            trades=1,
            win_rate=1.0,
            profit_factor=4.0,
            swap_usd=-1.0,
            rejections={},
            bankrupt=False,
            max_admitted_risk_pct=2.0,
        )
        metrics = monthly_metrics(
            result,
            first_quote=pd.Timestamp("2025-01-01", tz="UTC"),
            last_quote=pd.Timestamp("2025-03-01", tz="UTC"),
        )
        self.assertEqual(metrics["full_months"], 2)
        self.assertAlmostEqual(metrics["months"][0]["cash"], -0.4)
        self.assertAlmostEqual(metrics["months"][1]["cash"], 4.4)
        self.assertAlmostEqual(metrics["median_month_net"], 2.0)
        self.assertEqual(metrics["months"][0]["winners"], 1)

    def test_one_profitable_view_cannot_be_selected(self):
        baseline = dict(
            net_usd=50.0,
            max_dd_pct=20.0,
            bankrupt=False,
            max_admitted_risk_pct=8.0,
            full_months=2,
            mean_entries=10.0,
            median_month_net=1.0,
            positive_month_ratio=0.5,
        )
        cells = {(name, view): dict(metrics=dict(baseline)) for name in CASES for view in VIEWS}
        cells[("pullback", "base-swap")]["metrics"].update(
            net_usd=60.0, mean_entries=20.0, median_month_net=2.0, positive_month_ratio=0.75
        )
        cells[("pullback", "cost-stress-swap")]["metrics"]["net_usd"] = -1.0
        result = select(cells)
        self.assertEqual(result["verdict"], "NO_IMPROVEMENT")
        self.assertIsNone(result["selected"])

    def test_native_geometry_fee_stress_and_swap_flow_through_complete_replay(self):
        start = pd.Timestamp("2025-01-01", tz="UTC")
        end = start + pd.Timedelta(days=1, minutes=2)
        frame = pd.DataFrame(
            dict(
                open=[100.0],
                high=[101.0],
                low=[99.0],
                close=[100.0],
                atr=[1.0],
                direction=[1],
                native_entry=[100.2],
                native_stop=[98.0],
                native_target=[104.6],
            ),
            index=pd.DatetimeIndex([start]),
        )
        times = np.array(
            [
                (start + pd.Timedelta(minutes=5)).value // 10**6,
                (start + pd.Timedelta(days=1, milliseconds=1)).value // 10**6,
            ]
        )
        result = replay_case(
            frame,
            (times, np.array([100.0, 104.6]), np.array([100.2, 104.8])),
            dict(BROKER, swap_long=-567.4),
            strategy="pullback",
            view="cost-stress-swap",
            start=start,
            end=end,
        )
        self.assertEqual(result["trades"], 1)
        trade = result["ledger"][0]
        self.assertAlmostEqual(trade["risk_usd"], 2.6)
        self.assertAlmostEqual(trade["commission_usd"], 0.4)
        self.assertAlmostEqual(trade["swap_usd"], -1.7022)
        self.assertAlmostEqual(result["net_usd"], 2.2978)
        self.assertAlmostEqual(result["final_balance"], 202.2978)
        metrics = monthly_metrics(result, first_quote=start, last_quote=end)
        self.assertFalse(metrics["bankrupt"])
        self.assertAlmostEqual(metrics["net_usd"], 2.2978)
        self.assertEqual(metrics["months"][0]["observed_scope"], "partial")
        self.assertFalse(metrics["months"][0]["requested_full"])

    def test_incomplete_output_cannot_be_resumed_as_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out / "detector-parity.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "fresh output"):
                require_fresh_output(out)

    def test_completed_output_rejects_artifact_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            binary = out / "native-detector"
            binary.write_bytes(b"original")
            write(out / "COMPLETE.json", dict(artifacts={"native-detector": digest(binary)}))
            verify_complete(out)
            binary.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "artifact drift"):
                verify_complete(out)

    def test_every_repeat_must_match_before_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out / "repeats").mkdir()
            cells = {(name, view): dict(case=name, view=view) for name in CASES for view in VIEWS}
            for (name, view), cell in cells.items():
                write(out / "repeats" / (name + "-" + view + ".json"), cell)
            self.assertEqual(verify_repeats(out, cells), 10)
            cells[("pullback", "base-swap")]["changed"] = True
            with self.assertRaisesRegex(ValueError, "repeat mismatch"):
                verify_repeats(out, cells)

    def test_missing_swap_metadata_blocks_economic_replay(self):
        start = pd.Timestamp("2025-01-01", tz="UTC")
        with self.assertRaisesRegex(ValueError, "swap"):
            replay_case(
                pd.DataFrame(),
                (),
                {"trade_contract_size": 100},
                strategy="pullback",
                view="base-swap",
                start=start,
                end=start + pd.Timedelta(days=1),
            )
