"""Causal offline diagnostics, through public feature and replay seams."""

import unittest
import numpy as np
import pandas as pd
from scripts.research.c22_context import features


class ContextTests(unittest.TestCase):
    def test_population_z_includes_signal_close_and_ignores_future(self):
        bars = pd.DataFrame(
            {k: np.arange(1.0, 22.0) for k in ("open", "high", "low", "close")},
            index=pd.date_range("2026-01-01", periods=21, freq="15min", tz="UTC"),
        )
        close = bars.index[19] + pd.Timedelta(minutes=15)
        result = features(bars, close, -1)
        self.assertAlmostEqual(result["sd"]["z"], 1.647508942095828)
        self.assertEqual(result, features(bars.iloc[:20], close, -1))
        self.assertEqual(result["sr"]["status"], "coverage_unavailable")
        self.assertEqual(result["sd"]["published_utc"], close.isoformat())


class ReplayContextTests(unittest.TestCase):
    def test_observation_preserves_complete_result_and_links_trade(self):
        from tests.research.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs
        from scripts.research.c22_context import annotate

        frame, ticks = sample()
        baseline = replay(
            frame, ticks, BROKER, Rules(), Costs(), start=START, end=END, capture_events=True
        )
        observed = replay(
            frame,
            ticks,
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=END,
            capture_events=True,
            capture_context=True,
        )
        context_events = observed.pop("context_events")
        observed.pop("context_dd_witnesses")
        self.assertEqual(baseline, observed)
        observed["context_events"] = context_events
        rows = annotate(frame, observed, run="test", scenario="base", start=START, end=END)
        self.assertEqual(rows[0]["ledger_id"], 0)
        self.assertEqual(rows[0]["entry"], baseline["ledger"][0]["entry"])
        self.assertEqual(context_events[0]["signal_close_utc"], "2026-04-01T00:15:00+00:00")


class PeriodContextTests(unittest.TestCase):
    def setUp(self):
        self.bars = pd.DataFrame(
            dict(open=[100.0] * 31, high=[110.0] * 31, low=[90.0] * 31, close=[100.0] * 31),
            index=pd.date_range("2026-01-01T12:00Z", periods=31, freq="1D"),
        )
        self.coverage = dict(
            provenance="fixture session/gap audit",
            days=list(self.bars.index.strftime("%Y-%m-%d")),
            weeks=["2026-01-19"],
        )

    def test_prior_periods_publish_before_signal_and_range_is_frozen(self):
        from scripts.research.c22_context import room

        stamp = pd.Timestamp("2026-01-27T12:15Z")
        result = features(self.bars, stamp, 1, self.coverage)
        self.assertEqual(result["daily"]["median_range"], 20.0)
        self.assertEqual(result["daily"]["anchor"], 100.0)
        self.assertEqual(result["sr"]["levels"], [110.0, 90.0, 110.0, 90.0])
        self.assertLess(pd.Timestamp(result["sr"]["published_utc"]), stamp)
        self.assertEqual(room(result["sr"], 1, 100.0, 95.0)["value"], 2.0)
        self.assertEqual(room(result["sr"], -1, 100.0, 102.5)["value"], 4.0)
        self.assertEqual(room(result["sr"], 1, 111.0, 106.0)["status"], "no_opposing_level")
        self.assertEqual(room(result["sr"], 1)["status"], "entry_geometry_unavailable")
        future = self.bars.copy()
        future.loc[future.index > stamp, ["high", "low", "close"]] = [10000.0, 1.0, 9999.0]
        self.assertEqual(result, features(future, stamp, 1, self.coverage))

    def test_immediately_preceding_week_required_and_partial_day_unavailable(self):
        coverage = dict(self.coverage, weeks=["2026-01-12"])
        result = features(self.bars, pd.Timestamp("2026-01-27T12:15Z"), 1, coverage)
        self.assertEqual(result["sr"]["status"], "coverage_unavailable")
        self.assertEqual(
            features(self.bars.iloc[:10], pd.Timestamp("2026-01-10T12:15Z"), 1, self.coverage)[
                "daily"
            ]["status"],
            "warmup",
        )

    def test_naive_nonfinite_and_zero_variance_are_explicit(self):
        with self.assertRaisesRegex(ValueError, "aware UTC"):
            features(self.bars.tz_localize(None), pd.Timestamp("2026-01-27T12:15Z"), 1)
        with self.assertRaisesRegex(ValueError, "aware UTC"):
            features(self.bars, pd.Timestamp("2026-01-27T12:15"), 1)
        stamp = pd.Timestamp("2026-01-27T12:15Z")
        self.assertEqual(features(self.bars, stamp, 1)["sd"]["status"], "zero_variance")
        self.bars.loc[self.bars.index[25], "close"] = np.nan
        self.assertEqual(features(self.bars, stamp, 1)["sd"]["status"], "nonfinite")


class EventContextTests(unittest.TestCase):
    def test_macro_rejection_unvisited_and_labels_are_separate(self):
        from tests.research.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs
        from scripts.research.c22_context import annotate, report
        import copy

        frame, ticks = sample()
        frame["raw_direction"] = [1, -1, 1]
        frame["direction"] = [1, 0, 1]
        # Last signal has no quote at or after completion.
        ticks = tuple(a[:2] for a in ticks)
        result = replay(
            frame, ticks, BROKER, Rules(), Costs(), start=START, end=END, capture_context=True
        )
        rows = annotate(frame, result, run="test", scenario="base", start=START, end=END)
        self.assertEqual(
            [r["admission_reason"] for r in rows], ["admitted", "macro_blocked", "unvisited"]
        )
        changed = copy.deepcopy(result)
        changed["ledger"][0]["net"] = 99999.0
        altered = annotate(frame, changed, run="test", scenario="base", start=START, end=END)
        self.assertEqual([r["features"] for r in rows], [r["features"] for r in altered])
        self.assertIsNone(rows[1]["outcome"])
        self.assertEqual(report(rows)["executed"], 1)

    def test_parity_for_both_sides_and_circuit_rejections(self):
        from tests.research.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs
        from scripts.research.c22_context import annotate

        for direction in (1, -1):
            for atr in (1.0, 20.0):
                with self.subTest(direction=direction, atr=atr):
                    frame, ticks = sample()
                    frame["direction"] = [direction, direction, 0]
                    frame["atr"] = atr
                    rules = Rules(
                        max_daily_losses=1,
                        daily_loss_limit=0.1,
                        protect_mode="break_even",
                        buy_protect_mode="off",
                        buy_stop_atr=1.5,
                        buy_target_rr=2.0,
                    )
                    baseline = replay(frame, ticks, BROKER, rules, Costs(), start=START, end=END)
                    result = replay(
                        frame,
                        ticks,
                        BROKER,
                        rules,
                        Costs(),
                        start=START,
                        end=END,
                        capture_context=True,
                    )
                    self.assertEqual(
                        baseline, {k: v for k, v in result.items() if not k.startswith("context_")}
                    )
                    rows = annotate(
                        frame, result, run="test", scenario="base", start=START, end=END
                    )
                    self.assertEqual(
                        sum(r["ledger_id"] is not None for r in rows), baseline["trades"]
                    )


class DrawdownWitnessTests(unittest.TestCase):
    def test_local_peak_trough_survives_compressed_equity_trace(self):
        from tests.research.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs
        from scripts.research.c22_context_campaign import reconcile

        frame, _ = sample()
        times = START.value // 10**6 + np.array([900000, 910000, 920000, 930000, 940000, 950000])
        frame["atr"] = 7.9
        bid = np.array([100.0, 99.0, 140.0, 120.0, 145.0, 144.0])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(target_atr=6.25),
            Costs(),
            start=START,
            end=END,
            capture_context=True,
        )
        witness = result["context_dd_witnesses"][-1]
        self.assertAlmostEqual(witness["peak"], 239.8)
        self.assertAlmostEqual(witness["trough"], 219.8)
        self.assertAlmostEqual(result["max_dd_pct"], 20.0 / 239.8 * 100)
        metrics = reconcile(result, BROKER, result["context_dd_witnesses"])
        self.assertEqual(metrics["max_dd_pct"], result["max_dd_pct"])


class ExecutableGeometryTests(unittest.TestCase):
    def test_cost_grid_changes_room_but_not_completed_bar_context(self):
        from tests.research.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs
        from scripts.research.c22_context import annotate

        frame, ticks = sample()
        prefix = pd.concat([frame.iloc[[0]]] * 25)
        prefix.index = pd.date_range(
            START - pd.Timedelta(days=25) + pd.Timedelta(hours=12), periods=25, freq="1D"
        )
        prefix["direction"] = 0
        prefix["high"], prefix["low"] = 105.0, 95.0
        source = pd.concat([prefix, frame])
        coverage = dict(
            provenance="fixture explicit full session coverage",
            days=list(prefix.index.strftime("%Y-%m-%d")),
            weeks=["2026-03-23"],
        )
        contexts = []
        for costs, grid in ((Costs(), 0.001), (Costs(slippage=0.1, extra_spread=0.2), 0.01)):
            broker = dict(BROKER, trade_tick_size=grid)
            result = replay(
                source, ticks, broker, Rules(), costs, start=START, end=END, capture_context=True
            )
            row = annotate(
                source, result, run="test", scenario="view", start=START, end=END, coverage=coverage
            )[0]
            self.assertAlmostEqual(
                row["features"]["room"]["value"],
                (105.0 - row["entry"]) / abs(row["entry"] - row["initial_stop"]),
            )
            contexts.append(row["features"])
        self.assertEqual(contexts[0]["sd"], contexts[1]["sd"])
        self.assertEqual(contexts[0]["daily"], contexts[1]["daily"])
        self.assertNotEqual(contexts[0]["room"]["value"], contexts[1]["room"]["value"])
