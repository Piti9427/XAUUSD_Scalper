"""Canonical tick accounting through SMC replay boundary, literal geometry."""

import unittest
import numpy as np
import pandas as pd

from scripts.research.breakout_models import Costs
from scripts.research.smc_challenger_adapter import replay_signals

START = pd.Timestamp("2026-04-01T00:00:00", tz="UTC")
END = START + pd.Timedelta(days=1)
BROKER = dict(
    trade_contract_size=100.0,
    trade_tick_size=0.001,
    leverage=1000.0,
    volume_min=0.01,
    volume_max=200.0,
    volume_step=0.01,
    point=0.001,
    swap_mode=1,
    swap_long=-1000.0,
    swap_short=0.0,
    swap_rollover3days=3,
)


def frame_fixture(side=-1):
    return pd.DataFrame(
        dict(
            open=[100.0],
            high=[101.0],
            low=[99.0],
            close=[100.0],
            atr=[1.0],
            hh=[101.0],
            ll=[99.0],
            direction=[side],
            stop_low=[98.0],
            stop_high=[101.0],
            setup_id=["fixture"],
        ),
        index=pd.DatetimeIndex([START]),
    )


class AdapterTests(unittest.TestCase):
    def test_cost_inclusive_cap_equality_and_one_cent_over_are_distinct(self):
        t = np.array([START.value // 10**6 + 900000])
        ticks = (t, np.array([100.0]), np.array([100.0]))
        broker = dict(BROKER, trade_tick_size=1.0)
        frame = frame_fixture(1)
        frame["stop_low"] = 81.0  # One tick below wick =80; literal20USD risk.
        allowed = replay_signals(frame, ticks, broker, Costs(), start=START, end=END)
        self.assertEqual(allowed["trades"], 1)
        self.assertEqual(allowed["ledger"][0]["risk_usd"], 20.0)
        denied = replay_signals(
            frame, ticks, broker, Costs(commission_per_lot=1.0), start=START, end=END
        )
        self.assertEqual(denied["trades"], 0)
        self.assertEqual(denied["rejections"]["risk_cap"], 1)

    def test_busy_margin_and_midday_unknown_baseline_remain_canonical(self):
        frame = frame_fixture(1)
        second = frame.copy()
        second.index += pd.Timedelta(minutes=15)
        second["setup_id"] = "second"
        frame = pd.concat([frame, second])
        t = np.array([START.value // 10**6 + 900000, START.value // 10**6 + 1800000])
        ticks = (t, np.array([100.0, 100.0]), np.array([100.2, 100.2]))
        busy = replay_signals(frame, ticks, BROKER, Costs(), start=START, end=END)
        self.assertEqual(busy["trades"], 1)
        self.assertEqual(busy["rejections"]["busy"], 1)
        margin = replay_signals(
            frame, ticks, dict(BROKER, leverage=0.1), Costs(), start=START, end=END
        )
        self.assertEqual(margin["rejections"]["margin"], 2)
        unknown = replay_signals(
            frame, ticks, BROKER, Costs(), start=START + pd.Timedelta(minutes=1), end=END
        )
        self.assertEqual(unknown["rejections"]["day_start_unknown"], 2)

    def test_sell_stop_uses_actual_ask_spread_and_adverse_grid(self):
        t = np.array(
            [
                (START + pd.Timedelta(minutes=15)).value // 10**6,
                (START + pd.Timedelta(minutes=16)).value // 10**6,
            ]
        )
        result = replay_signals(
            frame_fixture(),
            (t, np.array([100.0, 100.0]), np.array([100.2, 100.2])),
            BROKER,
            Costs(slippage=0.1),
            start=START,
            end=END,
        )
        self.assertEqual(result["trades"], 1)
        trade = result["ledger"][0]
        # Canonical float addition then adverse grid may widen by one extra tick.
        self.assertAlmostEqual(trade["initial_stop"], 101.202)
        self.assertAlmostEqual(trade["entry"], 99.9)
        self.assertAlmostEqual(trade["risk_usd"], 1.402)
        self.assertAlmostEqual(trade["target"], 97.297)
        self.assertIn("swap_policy", result)

    def test_swap_triple_midnight_changes_equity_and_no_global_replay_mutation(self):
        frame = frame_fixture(1)
        frame.index += pd.Timedelta(hours=23)
        t = np.array(
            [
                (START + pd.Timedelta(hours=23, minutes=15)).value // 10**6,
                (START + pd.Timedelta(days=1)).value // 10**6,
                (START + pd.Timedelta(days=1, minutes=1)).value // 10**6,
            ]
        )
        ticks = (t, np.full(3, 100.0), np.full(3, 100.2))
        result = replay_signals(
            frame, ticks, BROKER, Costs(slippage=0.1), start=START, end=END + pd.Timedelta(hours=1)
        )
        self.assertAlmostEqual(result["swap_usd"], -3.0)
        self.assertAlmostEqual(result["net_usd"], -3.4)
        self.assertAlmostEqual(result["final_balance"], 196.6)
        self.assertEqual(result["swap_debits"][0]["amount_usd"], -3.0)
        self.assertEqual(result["swap_debits"][0]["rollover_utc"], "2026-04-02T00:00:00+00:00")
        from scripts.research.breakout_replay import replay
        from scripts.research.breakout_signals import _entry_signals

        self.assertIs(replay.__globals__["_entry_signals"], _entry_signals)

    def test_missing_swap_or_invalid_tape_cannot_fall_back(self):
        ticks = (np.array([START.value // 10**6 + 900000]), np.array([100.0]), np.array([100.2]))
        for key in ("swap_short", "swap_mode", "swap_rollover3days", "point"):
            broker = dict(BROKER)
            broker.pop(key)
            with self.assertRaises(ValueError):
                replay_signals(frame_fixture(), ticks, broker, Costs(), start=START, end=END)
        with self.assertRaises(ValueError):
            replay_signals(
                frame_fixture(),
                (ticks[0], ticks[1], np.array([99.0])),
                BROKER,
                Costs(),
                start=START,
                end=END,
            )

    def test_no_quote_late_quote_fixed_volume_and_risk_rejections(self):
        closed = START.value // 10**6 + 900000
        no_quote = (np.array([closed - 1]), np.array([100.0]), np.array([100.2]))
        result = replay_signals(frame_fixture(), no_quote, BROKER, Costs(), start=START, end=END)
        self.assertEqual(result["no_quote_events"][0]["reason"], "no_quote")
        self.assertEqual(result["signal_count"], 1)
        late = (np.array([closed + 90001]), np.array([100.0]), np.array([100.2]))
        result = replay_signals(frame_fixture(), late, BROKER, Costs(), start=START, end=END)
        self.assertEqual(result["rejections"]["late_quote"], 1)
        ontime = (np.array([closed]), np.array([100.0]), np.array([100.2]))
        frame = frame_fixture(1)
        frame["stop_low"] = 70.0
        result = replay_signals(frame, ontime, BROKER, Costs(slippage=0.1), start=START, end=END)
        self.assertEqual(result["rejections"]["risk_cap"], 1)
        with self.assertRaises(ValueError):
            replay_signals(
                frame_fixture(), ontime, dict(BROKER, volume_min=0.1), Costs(), start=START, end=END
            )

    def test_prepared_replay_matches_canonical_for_unchanged_anchors(self):
        from scripts.research.breakout_replay import replay
        from scripts.research.rollover import SwapPolicy
        from scripts.research.smc_challenger_adapter import smc_rules, prepared_replay

        frame = frame_fixture(1)
        frame["stop_low"] = frame.low
        frame["stop_high"] = frame.high
        times = np.array([START.value // 10**6 + 900000, START.value // 10**6 + 1800000])
        ticks = (times, np.array([100.0, 99.0]), np.array([100.2, 99.2]))
        kwargs = dict(
            start=START,
            end=END,
            swap_policy=SwapPolicy.from_broker(BROKER),
            capture_events=True,
            capture_context=True,
        )
        expected = replay(frame, ticks, BROKER, smc_rules(), Costs(slippage=0.1), **kwargs)
        actual = prepared_replay(frame, ticks, BROKER, smc_rules(), Costs(slippage=0.1), **kwargs)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
