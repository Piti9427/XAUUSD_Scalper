"""Public risk-overlay replay with synthetic quote tapes and explicit swap.

These fixtures prove causal accounting/state behavior, not candidate profitability.
"""

from decimal import Decimal, ROUND_HALF_UP
import inspect
import unittest

import numpy as np
import pandas as pd

from scripts.research.breakout_models import Costs, Rules
from scripts.research.breakout_replay import replay as frozen_replay
from scripts.research.c22_risk_policy import RiskOverlay
from scripts.research.c22_risk_replay import replay
from scripts.research.rollover import SwapPolicy


BROKER = dict(
    trade_contract_size=100.0,
    trade_tick_size=0.001,
    leverage=1000.0,
    volume_min=0.01,
    volume_max=200.0,
    volume_step=0.01,
)
VALID_SWAP = SwapPolicy(long_points=-0.4, short_points=-0.4, point=1.0)


def frame_at(stamps, directions, *, atr=1.0):
    index = pd.to_datetime(stamps, utc=True, format="ISO8601")
    return pd.DataFrame(
        dict(
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            hh=100.0,
            ll=95.0,
            atr=atr,
            direction=directions,
        ),
        index=index,
    )


def tape_at(stamps, bids, *, spread=0.2):
    times = pd.to_datetime(stamps, utc=True, format="ISO8601").as_unit("ms").asi8
    bid = np.asarray(bids, dtype=float)
    return times, bid, bid + spread


def native_rules(**changes):
    values = dict(
        stop_atr=2.5,
        buy_stop_atr=2.5,
        buy_target_rr=3.0,
        target_rr=1.35,
        daily_loss_limit=0.1,
        risk_cap=0.1,
        max_daily_losses=2,
        cooldown_bars=2,
        protect_after_r=1.0,
        protect_mode="break_even",
        buy_protect_mode="break_even",
    )
    return Rules(**(values | changes))


def cent_variant(function):
    # This is the same declared accounting convention used by the retained
    # campaign, applied independently to each function's own immutable source.
    source = inspect.getsource(function)
    assert source.count("if net < 0:") == 1

    def cent_loss(net):
        return Decimal(str(float(net))).quantize(Decimal(".01"), rounding=ROUND_HALF_UP) < 0

    scope = dict(function.__globals__, _cent_loss=cent_loss)
    exec(
        compile(source.replace("if net < 0:", "if _cent_loss(net):"), "<test-cent-replay>", "exec"),
        scope,
    )
    return scope[function.__name__]


class RiskOverlayReplayTests(unittest.TestCase):
    def run_case(
        self, frame, ticks, *, overlay=None, rules=None, costs=None, swap=VALID_SWAP, engine=replay
    ):
        start = frame.index[0].normalize()
        end = pd.Timestamp(int(ticks[0][-1]), unit="ms", tz="UTC") + pd.Timedelta(seconds=1)
        keywords = dict(
            start=start, end=end, swap_policy=swap, capture_events=True, capture_context=True
        )
        if engine is not frozen_replay:
            keywords["overlay"] = overlay or RiskOverlay()
        return engine(frame, ticks, BROKER, rules or native_rules(), costs or Costs(), **keywords)

    def budget_fixture(self):
        frame = frame_at(
            ["2026-04-06T00:00Z", "2026-04-06T00:15Z", "2026-04-06T00:30Z", "2026-04-06T00:45Z"],
            [1, 0, 1, 0],
            atr=6.0,
        )
        ticks = tape_at(
            [
                "2026-04-06T00:15Z",
                "2026-04-06T00:15:01Z",
                "2026-04-06T00:30Z",
                "2026-04-06T00:45:02Z",
                "2026-04-06T01:00Z",
            ],
            [100.0, 82.2, 100.0, 100.0, 100.0],
        )
        return frame, ticks

    def be_fixture(self, direction=1, *, first_executable=None):
        frame = frame_at(
            [
                "2026-04-07T23:30Z",
                "2026-04-07T23:45Z",
                "2026-04-08T00:00Z",
                "2026-04-08T23:45Z",
                "2026-04-09T00:00Z",
            ],
            [direction, 0, 0, 0, 0],
        )
        bids = (
            [100.0, 103.5, 103.6, 103.6, 100.9]
            if direction == 1
            else [100.0, 96.5, 96.4, 96.4, 99.1]
        )
        if first_executable is not None:
            bids[1] = first_executable if direction == 1 else first_executable - 0.2
        ticks = tape_at(
            [
                "2026-04-07T23:45Z",
                "2026-04-08T00:00Z",
                "2026-04-08T00:15Z",
                "2026-04-09T00:00Z",
                "2026-04-09T00:15Z",
            ],
            bids,
        )
        return frame, ticks

    def test_overlay_off_matches_full_frozen_result_raw_and_cent(self):
        frame, ticks = self.budget_fixture()
        for costs in (Costs(), Costs(slippage=0.1, commission_per_lot=20.0)):
            for cent in (False, True):
                with self.subTest(costs=costs, cent=cent):
                    old = cent_variant(frozen_replay) if cent else frozen_replay
                    new = cent_variant(replay) if cent else replay
                    start = frame.index[0].normalize()
                    end = pd.Timestamp(int(ticks[0][-1]), unit="ms", tz="UTC") + pd.Timedelta(
                        seconds=1
                    )
                    kwargs = dict(
                        start=start,
                        end=end,
                        swap_policy=VALID_SWAP,
                        capture_events=True,
                        capture_context=True,
                    )
                    expected = old(frame, ticks, BROKER, native_rules(), costs, **kwargs)
                    actual = new(
                        frame, ticks, BROKER, native_rules(), costs, overlay=RiskOverlay(), **kwargs
                    )
                    self.assertEqual(actual, expected)
                    self.assertNotIn("overlay", actual)

    def test_daily_reserved_sl_blocks_a_second_trade_while_native_cap_still_passes(self):
        frame, ticks = self.budget_fixture()
        native = self.run_case(frame, ticks)
        guarded = self.run_case(frame, ticks, overlay=RiskOverlay(daily_budget=True))
        self.assertEqual(native["trades"], 2)
        self.assertEqual(guarded["trades"], 1)
        self.assertAlmostEqual(guarded["ledger"][0]["net"], -18.0)
        decisions = guarded["overlay"]["budget_decisions"]
        rejected = [row for row in decisions if "daily_budget" in row["reasons"]]
        self.assertEqual(len(rejected), 1)
        row = rejected[0]
        self.assertAlmostEqual(row["equity"], 182.0)
        self.assertLessEqual(row["risk"], row["equity"] * 0.1)
        self.assertLess(row["projected_equity"], row["daily_floor"])
        self.assertEqual(guarded["overlay"]["state"]["episodes"], 0)

    def test_dd_budget_uses_full_tick_floating_peak_not_only_closed_balances(self):
        frame = frame_at(
            ["2026-04-06T12:00Z", "2026-04-06T12:15Z", "2026-04-07T12:00Z"],
            [1, 0, 1],
            atr=[8.0, 8.0, 5.6],
        )
        ticks = tape_at(
            [
                "2026-04-06T12:15Z",
                "2026-04-06T12:15:01Z",
                "2026-04-06T12:15:02Z",
                "2026-04-06T12:30Z",
                "2026-04-07T12:15Z",
                "2026-04-07T12:30Z",
            ],
            [100.0, 150.2, 50.2, 100.0, 100.0, 100.0],
        )
        rules = native_rules(protect_mode="off", buy_protect_mode="off")
        native = self.run_case(frame, ticks, rules=rules)
        guarded = self.run_case(
            frame, ticks, rules=rules, overlay=RiskOverlay(drawdown_budget=True)
        )
        self.assertEqual(native["trades"], 2)
        self.assertEqual(guarded["trades"], 1)
        rejected = [
            d for d in guarded["overlay"]["budget_decisions"] if "drawdown_budget" in d["reasons"]
        ]
        self.assertEqual(len(rejected), 1)
        row = rejected[0]
        self.assertAlmostEqual(row["peak"], 250.0)
        self.assertAlmostEqual(row["equity"], 150.0)
        self.assertGreater(row["projected_equity"], 200.0 * 0.6)
        self.assertLess(row["projected_equity"], row["peak"] * 0.6)
        self.assertTrue(any(abs(p["equity_usd"] - 250.0) < 1e-9 for p in guarded["equity"]))

    def test_public_replay_pause_24h_keeps_peak_and_waits_for_fresh_budget_passing_signal(self):
        frame = frame_at(
            ["2026-04-06T12:00Z", "2026-04-07T12:00Z", "2026-04-07T18:00Z", "2026-04-08T12:00Z"],
            [1, 1, 1, 1],
            atr=[8.0, 5.6, 0.8, 0.8],
        )
        ticks = tape_at(
            [
                "2026-04-06T12:15Z",
                "2026-04-06T12:15:01Z",
                "2026-04-06T12:15:02Z",
                "2026-04-07T12:15Z",
                "2026-04-07T18:15Z",
                "2026-04-08T12:15Z",
                "2026-04-08T12:30Z",
            ],
            [100.0, 155.2, 65.2, 100.0, 100.0, 100.0, 100.0],
        )
        rules = native_rules(protect_mode="off", buy_protect_mode="off")
        result = self.run_case(
            frame, ticks, rules=rules, overlay=RiskOverlay(drawdown_budget=True, dd_pause_hours=24)
        )
        self.assertEqual(result["trades"], 2)
        self.assertEqual(result["ledger"][1]["entry_time_utc"], "2026-04-08T12:15:00+00:00")
        decisions = result["overlay"]["budget_decisions"]
        first_reject, during, resumed = decisions[1:]
        self.assertIn("drawdown_budget", first_reject["reasons"])
        self.assertIn("dd_pause", during["reasons"])
        self.assertEqual(
            first_reject["state_after"]["pause_started_ms"],
            during["state_after"]["pause_started_ms"],
        )
        self.assertTrue(resumed["allowed"])
        self.assertEqual(resumed["stamp_ms"] - first_reject["stamp_ms"], 86_400_000)
        self.assertAlmostEqual(resumed["peak"], 255.0)
        self.assertEqual(result["overlay"]["state"]["episodes"], 1)
        self.assertEqual(result["overlay"]["state"]["resumes"], 1)
        self.assertIsNone(result["overlay"]["state"]["pause_started_ms"])

    def test_net_be_covers_accrued_debit_once_and_later_rollover_can_still_lose(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                frame, ticks = self.be_fixture(direction)
                costs = Costs(commission_per_lot=20.0, slippage=0.1)
                native = self.run_case(frame, ticks, costs=costs)
                result = self.run_case(
                    frame, ticks, costs=costs, overlay=RiskOverlay(net_be_first=True)
                )
                trade = result["ledger"][0]
                adjustments = result["overlay"]["be_adjustments"]
                self.assertEqual(len(adjustments), 1)
                self.assertEqual(trade["stop_updates"], 1)
                self.assertTrue(trade["net_be_done"])
                event = adjustments[0]
                self.assertAlmostEqual(event["accrued_swap"], -0.4)
                first_net = (
                    direction * (event["new_stop"] - event["entry"]) * event["factor"]
                    - event["fee"]
                    - event["exit_slippage"] * event["factor"]
                    + event["accrued_swap"]
                )
                self.assertGreaterEqual(first_net, -1e-10)
                self.assertLess(first_net, BROKER["trade_tick_size"] * event["factor"] + 1e-10)
                self.assertGreaterEqual(event["native_activation_net"], event["native_trigger"])
                self.assertGreater(direction * (event["new_stop"] - event["old_stop"]), 0)
                self.assertEqual(trade["target"], native["ledger"][0]["target"])
                self.assertAlmostEqual(trade["swap_usd"], -1.6)
                self.assertLess(trade["net"], 0)

    def test_positive_swap_credit_is_signed_and_does_not_clamp_to_native_be(self):
        frame, ticks = self.be_fixture(1)
        result = self.run_case(
            frame,
            ticks,
            costs=Costs(commission_per_lot=20.0, slippage=0.1),
            swap=SwapPolicy(0.5, 0.5, 1.0),
            overlay=RiskOverlay(net_be_first=True),
        )
        event = result["overlay"]["be_adjustments"][0]
        self.assertAlmostEqual(event["accrued_swap"], 0.5)
        self.assertLess(event["new_stop"], event["entry"])
        self.assertGreater(event["new_stop"], event["old_stop"])
        self.assertEqual(result["ledger"][0]["stop_updates"], 1)

    def test_positive_swap_does_not_change_original_one_r_activation(self):
        frame, ticks = self.be_fixture(1, first_executable=101.0)
        # Keep every later executable quote below the native1R threshold.
        ticks = (ticks[0][:3], np.array([100.0, 101.0, 101.1]), np.array([100.2, 101.2, 101.3]))
        result = self.run_case(
            frame.iloc[:3],
            ticks,
            costs=Costs(commission_per_lot=20.0, slippage=0.1),
            swap=SwapPolicy(10.0, 10.0, 1.0),
            overlay=RiskOverlay(net_be_first=True),
        )
        self.assertEqual(result["ledger"][0]["stop_updates"], 0)
        self.assertEqual(result["overlay"]["be_adjustments"], [])
        self.assertGreater(result["ledger"][0]["swap_usd"], 0)

    def test_geometry_failure_retries_until_first_success_and_does_not_move_tp(self):
        frame, ticks = self.be_fixture(1)
        ticks = (ticks[0][:3], np.array([100.0, 103.5, 105.0]), np.array([100.2, 103.7, 105.2]))
        result = self.run_case(
            frame.iloc[:3],
            ticks,
            costs=Costs(commission_per_lot=20.0, slippage=0.1),
            swap=SwapPolicy(-4.0, -4.0, 1.0),
            overlay=RiskOverlay(net_be_first=True),
        )
        trade = result["ledger"][0]
        self.assertEqual(trade["stop_updates"], 1)
        event = result["overlay"]["be_adjustments"][0]
        self.assertEqual(event["activation_stamp_ms"], int(ticks[0][1]))
        self.assertEqual(event["stamp_ms"], int(ticks[0][2]))
        self.assertGreater(event["native_activation_net"], event["native_trigger"])
        self.assertAlmostEqual(event["new_stop"], 104.6, delta=0.0011)
        self.assertEqual(event["target"], trade["target"])

    def test_signed_credit_never_loosens_current_initial_stop(self):
        frame, ticks = self.be_fixture(1)
        result = self.run_case(
            frame,
            ticks,
            costs=Costs(commission_per_lot=20.0, slippage=0.1),
            swap=SwapPolicy(5.0, 5.0, 1.0),
            overlay=RiskOverlay(net_be_first=True),
        )
        trade = result["ledger"][0]
        self.assertEqual(trade["stop"], trade["initial_stop"])
        self.assertEqual(trade["stop_updates"], 0)
        self.assertEqual(result["overlay"]["be_adjustments"], [])

    def test_overlay_on_requires_actual_explicit_swap_policy(self):
        frame, ticks = self.budget_fixture()
        for overlay in (
            RiskOverlay(daily_budget=True),
            RiskOverlay(drawdown_budget=True),
            RiskOverlay(net_be_first=True),
        ):
            for bad_swap in (None, object()):
                with self.subTest(overlay=overlay, bad_swap=bad_swap):
                    with self.assertRaises(ValueError):
                        self.run_case(frame, ticks, overlay=overlay, swap=bad_swap)


if __name__ == "__main__":
    unittest.main()
