"""Paired research contracts, causal H4 and swap/account-path regression seams."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np
import pandas as pd

from scripts.research.breakout_logic import Costs, Rules, replay
from scripts.research.rollover import SwapPolicy
from tests.research.test_breakout_logic import BROKER, START, END, sample


class SwapTests(unittest.TestCase):
    def test_swap_triple_day_and_weekend_gap(self):
        policy = SwapPolicy(-1000, 0, 0.001)
        start = pd.Timestamp("2026-04-01", tz="UTC")  # Wednesday
        end = start + pd.Timedelta(days=6)
        schedule = policy.schedule(start, end)
        stamps = pd.date_range(start, end, freq="D").as_unit("ms").asi8
        np.testing.assert_allclose(
            schedule.amount(stamps[0], stamps, 1, 1), [0, -3, -4, -5, -5, -5, -6]
        )
        np.testing.assert_allclose(
            schedule.amount(stamps[1], stamps[1:], 1, 1), [0, -1, -2, -2, -2, -3]
        )
        np.testing.assert_allclose(schedule.amount(stamps[0], stamps, -1, 1), 0)

    def test_default_replay_unchanged(self):
        # Execute actual starting-HEAD implementation, not a second call to new code.
        source = subprocess.check_output(
            [
                "git",
                "show",
                "ab4916c178ffb1ca926f74ae36742fd27af3c954:scripts/research/breakout_replay.py",
            ],
            text=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.py"
            path.write_text(source)
            spec = importlib.util.spec_from_file_location("scripts.research.legacy_control", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            frame, ticks = sample()
            for costs in (Costs(), Costs(extra_spread=0.2, slippage=0.1)):
                with self.subTest(costs=costs):
                    expected = module.replay(
                        frame, ticks, BROKER, Rules(), costs, start=START, end=END
                    )
                    actual = replay(frame, ticks, BROKER, Rules(), costs, start=START, end=END)
                    self.assertEqual(expected, actual)

    def test_swap_changes_next_risk_admission(self):
        frame, _ = sample()
        # BUY earns zero price PnL at overnight TP. Thursday midnight posts -3USD.
        frame.index = pd.DatetimeIndex(
            [
                START + pd.Timedelta(hours=23, minutes=30),
                START + pd.Timedelta(days=1),
                START + pd.Timedelta(days=1, minutes=15),
            ]
        )
        frame["direction"] = [1, 1, 0]
        frame["atr"] = [1, 7.96, 1]
        stamps = [
            START + pd.Timedelta(hours=23, minutes=45),
            START + pd.Timedelta(days=1),
            START + pd.Timedelta(days=1, minutes=15),
            START + pd.Timedelta(days=1, minutes=30),
        ]
        t = np.array([v.value // 10**6 for v in stamps])
        b = np.array([100.0, 103.2, 103.2, 103.2])
        ticks = (t, b, b + 0.2)
        end = START + pd.Timedelta(days=1, hours=1)
        before = replay(frame, ticks, BROKER, Rules(), Costs(), start=START, end=end)
        after = replay(
            frame,
            ticks,
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=end,
            swap_policy=SwapPolicy(-2000, 0, 0.001),
            capture_events=True,
        )
        self.assertEqual(before["trades"], 2)
        self.assertEqual(after["trades"], 1)
        self.assertAlmostEqual(after["swap_usd"], -6)
        self.assertAlmostEqual(after["net_before_swap_usd"], 3)
        self.assertAlmostEqual(after["final_balance"], 197)
        self.assertAlmostEqual(after["max_dd_pct"], 1.5)
        self.assertEqual(after["rejections"]["risk_cap"], 1)
        self.assertEqual(after["admission_events"][-1]["reason"], "risk_cap")
        self.assertFalse(after["admission_events"][-1]["position_open"])


class TuningTests(unittest.TestCase):
    def test_completion_requires_fresh_repeat_protocol(self):
        from scripts.research.reward156_tuning import run

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            with self.assertRaisesRegex(ValueError, "requires --repeat"):
                run(Path("config/reward156-tuning.json"), output, False)
            self.assertFalse(output.exists())

    def setUp(self):
        from scripts.research.reward156_tuning import (
            closed_h4_ema,
            prepare_contract,
            qualifies,
            blocking,
        )

        self.closed_h4_ema = closed_h4_ema
        self.prepare_contract = prepare_contract
        self.qualifies = qualifies
        self.blocking = blocking

    def bars(self, n=400):
        index = pd.date_range(START, periods=n, freq="15min")
        c = 100 + np.arange(n) * 0.01
        return pd.DataFrame(dict(open=c, high=c + 0.2, low=c - 0.2, close=c), index=index)

    def test_h4_closed_boundary_and_future_invariance(self):
        bars = self.bars(64)
        actual = self.closed_h4_ema(bars, 2)
        # First usable EMA after second complete bucket, at decision08:00 (07:45 open).
        self.assertTrue(pd.isna(actual.iloc[30]))
        self.assertAlmostEqual(
            actual.iloc[31], (bars.close.iloc[15] / 3 + bars.close.iloc[31] * 2 / 3)
        )
        future = bars.copy()
        future.loc[future.index >= START + pd.Timedelta(hours=8), "close"] *= 5
        pd.testing.assert_series_equal(actual.iloc[:32], self.closed_h4_ema(future, 2).iloc[:32])
        pd.testing.assert_series_equal(actual.iloc[:32], self.closed_h4_ema(bars.iloc[:32], 2))

    def test_h4_incomplete_bucket_and_warmup(self):
        bars = self.bars(64).drop(START + pd.Timedelta(minutes=15))
        actual = self.closed_h4_ema(bars, 2)
        self.assertTrue(pd.isna(actual.loc[START + pd.Timedelta(hours=7, minutes=45)]))
        self.assertTrue(pd.notna(actual.loc[START + pd.Timedelta(hours=11, minutes=45)]))
        self.assertTrue(self.closed_h4_ema(self.bars(150 * 16), 200).isna().all())
        incomplete = self.bars(64).drop(START + pd.Timedelta(hours=8, minutes=15))
        self.assertTrue(
            pd.isna(
                self.closed_h4_ema(incomplete, 2).loc[START + pd.Timedelta(hours=11, minutes=45)]
            )
        )

    def test_contracts_share_environment_but_keep_signals_and_exits(self):
        from scripts.strategy import trial30_bars, reward156_bars

        bars = self.bars()
        # Exercise actual BUY and SELL branches, not two all-zero signal arrays.
        close = 2000 + np.cumsum(np.random.default_rng(42).normal(size=len(bars)) * 2)
        bars[["open", "close"]] = np.column_stack([close, close])
        bars["high"] = close + 0.2
        bars["low"] = close - 0.2
        trial_directions = trial30_bars(bars).direction
        reward_directions = reward156_bars(bars).direction
        self.assertGreater(int((trial_directions == -1).sum()), 0)
        self.assertGreater(int((reward_directions == 1).sum()), 0)
        self.assertEqual(int((trial_directions == 1).sum()), 0)
        self.assertTrue((trial_directions != reward_directions).any())
        for strategy in ("trial30", "reward156"):
            with self.subTest(strategy=strategy):
                prepared, rules = self.prepare_contract(
                    bars,
                    dict(
                        name=strategy,
                        strategy=strategy,
                        macro_span=0,
                        buy_pause_drawdown=0.0 if strategy == "trial30" else 0.05,
                    ),
                )
                expected = (trial30_bars if strategy == "trial30" else reward156_bars)(bars)
                np.testing.assert_array_equal(prepared.direction, expected.direction)
                self.assertEqual(rules.risk_cap, 0.1)
                self.assertEqual(rules.daily_loss_limit, 0.2)
                self.assertEqual(rules.sizing_mode, "fixed")
                self.assertEqual(rules.stop_atr, 2.5)
                self.assertEqual(
                    rules.protect_mode, "break_even" if strategy == "trial30" else "off"
                )
                self.assertEqual(rules.protect_after_r, 1.0)
                self.assertEqual(rules.target_rr, 0 if strategy == "trial30" else 1.35)
        # Same synthetic market/cost inputs produce each contract's own exit target.
        frame, ticks = sample()
        ticks = (ticks[0], np.array([100, 110, 110]), np.array([100.2, 110.2, 110.2]))
        t30 = replay(
            frame,
            ticks,
            BROKER,
            Rules(target_atr=3, protect_mode="break_even", protect_after_r=1, daily_loss_limit=0.2),
            Costs(),
            start=START,
            end=END,
        )
        r156 = replay(
            frame,
            ticks,
            BROKER,
            Rules(target_rr=1.35, daily_loss_limit=0.2),
            Costs(),
            start=START,
            end=END,
        )
        self.assertAlmostEqual(t30["ledger"][0]["target"], 103.2)
        self.assertAlmostEqual(r156["ledger"][0]["target"], 103.575)

    def test_comparison_rejects_loss_and_missing_metrics(self):
        base = dict(
            net_usd=10,
            max_dd_pct=30,
            trades=60,
            buy_trades=0,
            sell_trades=60,
            win_rate=0.5,
            realized_rr=1.1,
            max_admitted_risk_pct=10,
            terminal_risk_blockage=False,
        )
        candidate = dict(
            base, net_usd=20, buy_trades=10, sell_trades=50, win_rate=0.6, realized_rr=1.2
        )
        self.assertTrue(self.qualifies(candidate, base, 60))
        for change in (
            dict(net_usd=-1),
            dict(realized_rr=None),
            dict(buy_trades=0),
            dict(max_dd_pct=35.01),
            dict(terminal_risk_blockage=True),
            dict(trades=59),
        ):
            self.assertFalse(self.qualifies(dict(candidate, **change), base, 60))

    def test_risk_blocked_days_require_all_signals_and_no_position(self):
        events = [
            dict(time_utc="2026-04-01T00:15:00+00:00", reason="risk_cap", position_open=False),
            dict(time_utc="2026-04-02T00:15:00+00:00", reason="risk_cap", position_open=False),
            dict(time_utc="2026-04-02T00:30:00+00:00", reason="buy_pause", position_open=False),
        ]
        result = self.blocking(events, [], START, START + pd.Timedelta(days=60))
        self.assertEqual(result["risk_blocked_days"], 1)
        self.assertFalse(result["terminal_risk_blockage"])
        held = [
            dict(
                entry_time_utc="2026-04-01T12:00:00+00:00",
                exit_time_utc="2026-04-01T13:00:00+00:00",
            )
        ]
        self.assertEqual(
            self.blocking(events, held, START, START + pd.Timedelta(days=60))["risk_blocked_days"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
