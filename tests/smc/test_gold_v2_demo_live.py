"""GOLD_V2_DEMO seams: bar clock, window slice, place-only, two-tier quotes."""

from __future__ import annotations

import unittest
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from scripts.smc.broker_rates import classify_bar_clock, drop_forming_bars
from scripts.smc.demo_live import admit_place_intents, two_tier_intents
from scripts.smc.eval_windows import label_foundation_window
from scripts.smc.gold_v2_demo import GOLD_V2_DEMO, slice_m5_window
from scripts.smc.types import Direction, OrderIntent, OrderIntentType
from scripts.ops.mt5_wine_smc_live import _foreign


class BrokerRatesTests(unittest.TestCase):
    def test_drop_forming_m5_bar(self):
        now = datetime(2026, 9, 21, 4, 52, tzinfo=timezone.utc)
        closed = now.replace(minute=45, second=0, microsecond=0)
        forming = now.replace(minute=50, second=0, microsecond=0)
        df = pd.DataFrame(
            {
                "time": [closed, forming],
                "open": [1.0, 2.0],
                "high": [1.0, 2.0],
                "low": [1.0, 2.0],
                "close": [1.0, 2.0],
            }
        )
        out = drop_forming_bars(df, now=now, bar_minutes=5)
        self.assertEqual(list(out["time"]), [closed])

    def test_bar_clock_rejects_hour_skew(self):
        bar_open = datetime(2026, 9, 21, 3, 45, tzinfo=timezone.utc)
        tick = datetime(2026, 9, 21, 4, 50, tzinfo=timezone.utc)
        code = classify_bar_clock(bar_open=bar_open, tick_time=tick, bar_minutes=5)
        self.assertEqual(code, "DATA_BAD_TIMEZONE")

    def test_bar_clock_ok_when_last_closed_matches_tick(self):
        tick = datetime(2026, 9, 21, 4, 52, tzinfo=timezone.utc)
        bar_open = datetime(2026, 9, 21, 4, 45, tzinfo=timezone.utc)
        code = classify_bar_clock(bar_open=bar_open, tick_time=tick, bar_minutes=5)
        self.assertEqual(code, "ok")


class BrokerStateTests(unittest.TestCase):
    def test_unknown_positions_fail_closed(self):
        class Broker:
            def positions_get(self, **_kwargs):
                return None

            def orders_get(self, **_kwargs):
                return ()

        with self.assertRaisesRegex(RuntimeError, "broker_position_or_order_state_unavailable"):
            _foreign(Broker(), "XAUUSDm")


class WindowSliceTests(unittest.TestCase):
    def test_slice_keeps_single_foundation_window(self):
        times = [
            datetime(2026, 5, 31, 12, tzinfo=timezone.utc),
            datetime(2026, 6, 1, 12, tzinfo=timezone.utc),
            datetime(2026, 9, 21, 12, tzinfo=timezone.utc),
        ]
        df = pd.DataFrame(
            {
                "time": times,
                "open": [1.0, 1.0, 1.0],
                "high": [1.0, 1.0, 1.0],
                "low": [1.0, 1.0, 1.0],
                "close": [1.0, 1.0, 1.0],
            }
        )
        hold = slice_m5_window(df, "holdout")
        self.assertEqual(len(hold), 1)
        self.assertEqual(label_foundation_window(hold["time"].iloc[0]).name, "holdout")


class RunBacktestCliTests(unittest.TestCase):
    def test_missing_m5_path_exits_nonzero(self):
        import subprocess
        import sys

        proc = subprocess.run(
            [
                sys.executable,
                "scripts/run_backtest.py",
                "--m5",
                "/tmp/missing_xauusdm_m5.csv",
                "--h1",
                "/tmp/missing_xauusdm_h1.csv",
            ],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not found", proc.stdout.lower() + proc.stderr.lower())


class PlaceOnlyTests(unittest.TestCase):
    def test_blocks_orchestrator_fill_side_intents(self):
        intents = [
            OrderIntent(intent_type=OrderIntentType.CLOSE_MARKET, reason="invented fill"),
        ]
        reason, kept = admit_place_intents(intents)
        self.assertTrue(reason.startswith("blocked_non_place"))
        self.assertEqual(kept, [])

    def test_keeps_place_limit(self):
        place = OrderIntent(
            intent_type=OrderIntentType.PLACE_LIMIT,
            direction=Direction.BUY,
            limit_price=4300.0,
            sl_price=4290.0,
            tp_price=4325.0,
            lot_size=0.01,
            order_id="setup1",
        )
        reason, kept = admit_place_intents([place])
        self.assertEqual(reason, "ok")
        self.assertEqual(len(kept), 1)


class TwoTierTests(unittest.TestCase):
    def test_skips_unsplitable_lot(self):
        intents = two_tier_intents(
            order_id="s1",
            lot_size=0.01,
            direction="BUY",
            entry=4300.0,
            sl=4290.0,
            bid=4320.0,
            ask=4320.3,
            already_scaled=False,
            min_split_lot=GOLD_V2_DEMO["min_split_lot"],
            partial_ratio=GOLD_V2_DEMO["partial_tp_ratio"],
            be_buffer=GOLD_V2_DEMO["be_buffer"],
        )
        self.assertEqual(intents, [])

    def test_emits_partial_and_be_at_one_r(self):
        intents = two_tier_intents(
            order_id="s1",
            lot_size=0.02,
            direction="BUY",
            entry=4300.0,
            sl=4290.0,
            bid=4310.0,
            ask=4310.3,
            already_scaled=False,
            min_split_lot=GOLD_V2_DEMO["min_split_lot"],
            partial_ratio=GOLD_V2_DEMO["partial_tp_ratio"],
            be_buffer=GOLD_V2_DEMO["be_buffer"],
        )
        types = [i.intent_type for i in intents]
        self.assertEqual(
            types,
            [OrderIntentType.PARTIAL_CLOSE, OrderIntentType.MOVE_SL_TO_BE],
        )
        self.assertEqual(intents[0].lot_size, 0.01)
        self.assertEqual(intents[1].sl_price, 4300.1)

    def test_no_be_when_partial_not_ready(self):
        intents = two_tier_intents(
            order_id="s1",
            lot_size=0.02,
            direction="BUY",
            entry=4300.0,
            sl=4290.0,
            bid=4301.0,
            ask=4301.3,
            already_scaled=False,
            min_split_lot=GOLD_V2_DEMO["min_split_lot"],
            partial_ratio=GOLD_V2_DEMO["partial_tp_ratio"],
            be_buffer=GOLD_V2_DEMO["be_buffer"],
        )
        self.assertEqual(intents, [])


if __name__ == "__main__":
    unittest.main()
