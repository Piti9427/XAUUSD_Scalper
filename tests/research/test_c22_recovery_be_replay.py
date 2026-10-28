"""Public-seam synthetic regressions; no candidate profitability evaluation."""

import copy
import json
import unittest

import pandas as pd

from scripts.research.breakout_models import Costs
from scripts.research.c22_recovery_be_replay import replay
from scripts.research.c22_risk_replay import replay as previous_replay
from scripts.research.rollover import SwapPolicy
from tests.research.test_c22_risk_replay import (
    BROKER, VALID_SWAP, cent_variant, frame_at, native_rules, tape_at,
)


class RecoveryNetBeReplayTests(unittest.TestCase):
    def run_case(self, frame, ticks, *, enabled=True, costs=None, swap=VALID_SWAP,
                 engine=replay, rules=None):
        kwargs = dict(start=frame.index[0].normalize(),
                      end=pd.Timestamp(int(ticks[0][-1]), unit="ms", tz="UTC")
                      + pd.Timedelta(seconds=1), swap_policy=swap,
                      capture_events=True, capture_context=True)
        if engine is not previous_replay:
            kwargs["recovery_be"] = enabled
        return engine(frame, ticks, BROKER, rules or native_rules(), costs or Costs(), **kwargs)

    def recovery_fixture(self):
        frame = frame_at(["2026-04-06T12:00Z", "2026-04-07T23:30Z",
                          "2026-04-07T23:45Z", "2026-04-08T00:00Z",
                          "2026-04-09T12:00Z", "2026-04-09T12:15Z",
                          "2026-04-09T23:45Z"], [1, 1, 0, 0, 1, 0, 0])
        ticks = tape_at(["2026-04-06T12:15Z", "2026-04-06T12:15:01Z",
                         "2026-04-07T23:45Z", "2026-04-08T00:00Z",
                         "2026-04-08T00:15Z", "2026-04-09T12:15Z",
                         "2026-04-09T12:30Z", "2026-04-10T00:00Z"],
                        [100., 97., 100., 103.5, 108., 100., 104., 100.])
        return frame, ticks

    def recovering_be_fixture(self, direction=1, *, first_executable=None):
        frame = frame_at(["2026-04-06T12:00Z", "2026-04-07T23:30Z",
                          "2026-04-07T23:45Z", "2026-04-08T00:00Z",
                          "2026-04-08T23:45Z", "2026-04-09T00:00Z"],
                         [1, direction, 0, 0, 0, 0])
        bids = ([100., 97., 100., 103.5, 103.6, 103.6, 100.9] if direction == 1
                else [100., 97., 100., 96.5, 96.4, 96.4, 99.1])
        if first_executable is not None:
            bids[3] = first_executable if direction == 1 else first_executable - .2
        ticks = tape_at(["2026-04-06T12:15Z", "2026-04-06T12:15:01Z",
                         "2026-04-07T23:45Z", "2026-04-08T00:00Z",
                         "2026-04-08T00:15Z", "2026-04-09T00:00Z",
                         "2026-04-09T00:15Z"], bids)
        return frame, ticks

    def test_recovery_gate_is_frozen_before_entry_fee_and_peak_uses_closed_net(self):
        frame, ticks = self.recovery_fixture()
        result = self.run_case(frame, ticks)
        evidence = result["recovery_be"]
        decisions = evidence["entry_decisions"]
        self.assertEqual(result["trades"], 3)
        self.assertEqual([x["eligible"] for x in decisions], [False, True, False])
        self.assertEqual(decisions[0]["closing_peak"], 200.)
        self.assertAlmostEqual(decisions[1]["balance"], 196.8)
        self.assertEqual(decisions[1]["closing_peak"], 200.)
        self.assertAlmostEqual(decisions[2]["closing_peak"], 203.9)
        self.assertAlmostEqual(decisions[2]["balance"], 203.9)
        self.assertAlmostEqual(evidence["closing_peak"], 203.9)
        self.assertEqual(len(evidence["be_adjustments"]), 1)
        self.assertEqual(evidence["be_adjustments"][0]["entry_ms"],
                         result["ledger"][1]["entry_ms"])
        self.assertAlmostEqual(result["ledger"][1]["swap_usd"], -0.4)
        self.assertTrue(result["ledger"][1]["recovery_be_eligible"])
        self.assertFalse(result["ledger"][2]["recovery_be_eligible"])
        json.dumps(result, allow_nan=False)

    def test_entry_commission_cannot_create_a_recovery_gate_or_change_native_be(self):
        frame, ticks = self.recovering_be_fixture()
        # First position starts at the initial peak. Its fee creates a lower
        # posted balance, but eligibility was frozen before that fee.
        frame = frame.iloc[1:]
        ticks = tuple(part[2:] for part in ticks)
        costs = Costs(commission_per_lot=20., slippage=.1)
        result = self.run_case(frame, ticks, costs=costs)
        self.assertFalse(result["recovery_be"]["entry_decisions"][0]["eligible"])
        self.assertEqual(result["recovery_be"]["entry_decisions"][0]["balance"], 200.)
        self.assertEqual(result["recovery_be"]["be_adjustments"], [])
        stripped = copy.deepcopy(result)
        stripped.pop("recovery_be")
        for trade in stripped["ledger"]:
            trade.pop("recovery_be_eligible")
        native = self.run_case(frame, ticks, costs=costs, engine=previous_replay)
        self.assertEqual(stripped, native)

    def test_recovering_buy_and_sell_cover_debit_once_and_keep_later_swap_loss(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                frame, ticks = self.recovering_be_fixture(direction)
                costs = Costs(commission_per_lot=20., slippage=.1)
                result = self.run_case(frame, ticks, costs=costs)
                native = self.run_case(frame, ticks, costs=costs, engine=previous_replay)
                trade = result["ledger"][1]
                events = result["recovery_be"]["be_adjustments"]
                self.assertEqual(len(events), 1)
                self.assertEqual(trade["stop_updates"], 1)
                self.assertTrue(trade["net_be_done"])
                event = events[0]
                self.assertAlmostEqual(event["accrued_swap"], -.4)
                net_at_stop = (direction * (event["new_stop"] - event["entry"])
                               * event["factor"] - event["fee"]
                               - event["exit_slippage"] * event["factor"]
                               + event["accrued_swap"])
                self.assertGreaterEqual(net_at_stop, -1e-10)
                self.assertLess(net_at_stop, .0011)
                self.assertGreaterEqual(event["native_activation_net"], event["native_trigger"])
                self.assertGreater(direction * (event["new_stop"] - event["old_stop"]), 0)
                self.assertEqual(trade["target"], native["ledger"][1]["target"])
                self.assertAlmostEqual(trade["swap_usd"], -1.6)
                self.assertLess(trade["net"], 0)

    def test_recovering_geometry_failure_retries_until_first_success(self):
        frame, ticks = self.recovering_be_fixture()
        ticks = (ticks[0][:5], ticks[1][:5].copy(), ticks[2][:5].copy())
        ticks[1][4], ticks[2][4] = 105., 105.2
        result = self.run_case(frame.iloc[:4], ticks,
                               costs=Costs(commission_per_lot=20., slippage=.1),
                               swap=SwapPolicy(-4., -4., 1.))
        event = result["recovery_be"]["be_adjustments"][0]
        self.assertEqual(event["activation_stamp_ms"], int(ticks[0][3]))
        self.assertEqual(event["stamp_ms"], int(ticks[0][4]))
        self.assertAlmostEqual(event["new_stop"], 104.6, delta=.0011)
        self.assertEqual(result["ledger"][1]["stop_updates"], 1)

    def test_swap_credit_does_not_activate_before_native_one_r(self):
        frame, ticks = self.recovering_be_fixture(first_executable=101.)
        ticks = (ticks[0][:5], ticks[1][:5].copy(), ticks[2][:5].copy())
        ticks[1][4], ticks[2][4] = 101.1, 101.3
        result = self.run_case(frame.iloc[:4], ticks,
                               costs=Costs(commission_per_lot=20., slippage=.1),
                               swap=SwapPolicy(10., 10., 1.))
        self.assertEqual(result["recovery_be"]["be_adjustments"], [])
        self.assertEqual(result["ledger"][1]["stop_updates"], 0)

    def test_recovering_swap_credit_never_loosens_initial_stop(self):
        frame, ticks = self.recovering_be_fixture()
        result = self.run_case(frame, ticks, costs=Costs(commission_per_lot=20., slippage=.1),
                               swap=SwapPolicy(5., 5., 1.))
        self.assertEqual(result["ledger"][1]["stop"], result["ledger"][1]["initial_stop"])
        self.assertEqual(result["ledger"][1]["stop_updates"], 0)
        self.assertEqual(result["recovery_be"]["be_adjustments"], [])

    def test_enabled_mode_requires_explicit_swap_and_strict_bool(self):
        frame, ticks = self.recovery_fixture()
        for invalid in (None, object()):
            with self.subTest(swap=invalid), self.assertRaises(ValueError):
                self.run_case(frame, ticks, swap=invalid)
        for invalid in (None, 0, 1, "true"):
            with self.subTest(enabled=invalid), self.assertRaises(ValueError):
                self.run_case(frame, ticks, enabled=invalid)

    def test_cent_loss_flags_do_not_round_a_small_realized_balance_loss_out_of_gate(self):
        frame = frame_at(["2026-04-06T12:00Z", "2026-04-07T12:00Z"],
                         [1, 1], atr=[.0016, 1.])
        ticks = tape_at(["2026-04-06T12:15Z", "2026-04-06T12:15:01Z",
                         "2026-04-07T12:15Z", "2026-04-07T12:30Z"],
                        [100., 99.996, 100., 100.], spread=0.)
        result = self.run_case(frame, ticks, engine=cent_variant(replay))
        self.assertEqual(result["trades"], 2)
        self.assertAlmostEqual(result["ledger"][0]["net"], -.004)
        decision = result["recovery_be"]["entry_decisions"][1]
        self.assertAlmostEqual(decision["balance"], 199.996)
        self.assertTrue(decision["eligible"])

    def test_disabled_control_preserves_buy_sell_protection_and_swap_in_all_six_views(self):
        for direction in (1, -1):
            frame, ticks = self.recovering_be_fixture(direction)
            for costs in (Costs(), Costs(extra_spread=.2, slippage=.1),
                          Costs(extra_spread=.2, slippage=.1, commission_per_lot=7)):
                for cent in (False, True):
                    with self.subTest(direction=direction, costs=costs, cent=cent):
                        previous = cent_variant(previous_replay) if cent else previous_replay
                        actual = cent_variant(replay) if cent else replay
                        kwargs = dict(start=frame.index[0].normalize(),
                                      end=pd.Timestamp(int(ticks[0][-1]), unit="ms", tz="UTC")
                                      + pd.Timedelta(seconds=1), swap_policy=VALID_SWAP,
                                      capture_events=True, capture_context=True)
                        expected = previous(frame, ticks, BROKER, native_rules(), costs, **kwargs)
                        observed = actual(frame, ticks, BROKER, native_rules(), costs,
                                          recovery_be=False, **kwargs)
                        self.assertEqual(observed, expected)

    def test_disabled_control_matches_complete_native_result_in_all_cost_accounting_views(self):
        frame = frame_at(["2026-04-06T00:00Z", "2026-04-06T00:15Z",
                          "2026-04-06T00:30Z", "2026-04-06T00:45Z"],
                         [1, 0, 1, 0], atr=6.0)
        ticks = tape_at(["2026-04-06T00:15Z", "2026-04-06T00:15:01Z",
                         "2026-04-06T00:30Z", "2026-04-06T00:45:02Z",
                         "2026-04-06T01:00Z"], [100.0, 82.2, 100.0, 100.0, 100.0])
        for costs in (Costs(), Costs(extra_spread=.2, slippage=.1),
                      Costs(extra_spread=.2, slippage=.1, commission_per_lot=7)):
            for cent in (False, True):
                with self.subTest(costs=costs, cent=cent):
                    expected_engine = cent_variant(previous_replay) if cent else previous_replay
                    actual_engine = cent_variant(replay) if cent else replay
                    kwargs = dict(start=frame.index[0].normalize(),
                                  end=pd.Timestamp(int(ticks[0][-1]), unit="ms", tz="UTC")
                                  + pd.Timedelta(seconds=1), swap_policy=VALID_SWAP,
                                  capture_events=True, capture_context=True)
                    expected = expected_engine(frame, ticks, BROKER, native_rules(), costs, **kwargs)
                    actual = actual_engine(frame, ticks, BROKER, native_rules(), costs,
                                           recovery_be=False, **kwargs)
                    self.assertEqual(actual, expected)
                    self.assertNotIn("recovery_be", actual)


if __name__ == "__main__":
    unittest.main()
