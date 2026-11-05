"""Deterministic budget/pause/Net-BE contracts; no economic qualification."""

import math
import unittest

from scripts.research.c22_risk_policy import (
    BudgetPauseState,
    RiskOverlay,
    evaluate_budget,
    net_break_even,
)


DAY_MS = 24 * 60 * 60 * 1000


class RiskBudgetPolicyTests(unittest.TestCase):
    def decision(self, overlay=None, state=None, **changes):
        values = dict(
            equity=200.0, day_start=200.0, peak=200.0, risk=10.0, stamp_ms=1000, signal_ms=1000
        )
        values.update(changes)
        return evaluate_budget(overlay or RiskOverlay(), state or BudgetPauseState(), **values)

    def test_daily_budget_rejects_exact_floor_and_preserves_per_trade_cap_witness(self):
        overlay = RiskOverlay(daily_budget=True)
        exact = self.decision(overlay, equity=190.0, risk=10.0)
        self.assertFalse(exact.allowed)
        self.assertIn("daily_budget", exact.reasons)
        self.assertTrue(self.decision(overlay, equity=190.0, risk=9.999).allowed)
        # Native initial10% admission can pass this risk despite a9% day loss.
        self.assertLess(18.101, 182.0 * 0.1)
        self.assertIn("daily_budget", self.decision(overlay, equity=182.0, risk=18.101).reasons)

    def test_drawdown_budget_uses_equity_high_water_and_rejects_exact_floor(self):
        overlay = RiskOverlay(drawdown_budget=True)
        self.assertIn("drawdown_budget", self.decision(overlay, equity=130.0, risk=10.0).reasons)
        self.assertTrue(self.decision(overlay, equity=130.0, risk=9.999).allowed)
        # Same closing balance cannot replace a larger executable floating peak.
        self.assertTrue(self.decision(overlay, equity=130.0, peak=150.0, risk=10.0).allowed)
        self.assertIn(
            "drawdown_budget", self.decision(overlay, equity=130.0, peak=200.0, risk=10.0).reasons
        )

    def test_daily_and_drawdown_failures_are_independent_and_both_recorded(self):
        state = BudgetPauseState()
        result = self.decision(
            RiskOverlay(daily_budget=True, drawdown_budget=True, dd_pause_hours=24),
            state,
            equity=190.0,
            day_start=220.0,
            peak=320.0,
            risk=10.0,
        )
        self.assertFalse(result.allowed)
        self.assertIn("daily_budget", result.reasons)
        self.assertIn("drawdown_budget", result.reasons)
        self.assertTrue(result.started_pause)
        self.assertEqual(state.pause_started_ms, 1000)

    def test_invalid_or_missing_budget_evidence_fails_closed(self):
        for key in ("equity", "day_start", "peak", "risk"):
            for value in (None, float("nan"), float("inf"), -1.0, 0.0):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ValueError):
                        self.decision(
                            RiskOverlay(daily_budget=True, drawdown_budget=True), **{key: value}
                        )

    def test_invalid_overlay_combinations_and_non_boolean_flags_are_rejected(self):
        for changes in (
            {"dd_pause_hours": 24},
            {"dd_pause_hours": -1},
            {"drawdown_budget": True, "dd_pause_hours": 12},
            {"daily_budget": "true"},
            {"net_be_first": 1},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    RiskOverlay(**changes)

    def test_pause_clock_starts_once_and_rejections_never_extend_24_hours(self):
        state = BudgetPauseState()
        overlay = RiskOverlay(drawdown_budget=True, dd_pause_hours=24)
        first = self.decision(overlay, state, equity=130.0, risk=10.0, stamp_ms=0, signal_ms=0)
        self.assertTrue(first.started_pause)
        self.assertEqual(state.pause_started_ms, 0)
        self.assertEqual(state.resume_not_before_ms, DAY_MS)
        for number, hour in enumerate((1, 12, 23), 1):
            later = self.decision(
                overlay,
                state,
                equity=160.0,
                risk=5.0,
                stamp_ms=hour * 3600000,
                signal_ms=hour * 3600000,
            )
            self.assertFalse(later.allowed)
            self.assertIn("dd_pause", later.reasons)
            self.assertFalse(later.started_pause)
            self.assertEqual(state.resume_not_before_ms, DAY_MS)
            self.assertEqual(state.episodes, 1)

    def test_exact_24_hour_boundary_requires_new_signal_and_all_budgets(self):
        overlay = RiskOverlay(daily_budget=True, drawdown_budget=True, dd_pause_hours=24)
        state = BudgetPauseState()
        self.decision(
            overlay, state, equity=130.0, day_start=130.0, risk=10.0, stamp_ms=0, signal_ms=0
        )
        blocked = self.decision(
            overlay,
            state,
            equity=160.0,
            day_start=180.0,
            risk=5.0,
            stamp_ms=DAY_MS,
            signal_ms=DAY_MS,
        )
        self.assertFalse(blocked.allowed)
        self.assertIn("daily_budget", blocked.reasons)
        self.assertFalse(blocked.resumed)
        resumed = self.decision(
            overlay,
            state,
            equity=160.0,
            day_start=160.0,
            risk=5.0,
            stamp_ms=DAY_MS + 900000,
            signal_ms=DAY_MS + 900000,
        )
        self.assertTrue(resumed.allowed)
        self.assertTrue(resumed.resumed)
        self.assertEqual(state.resumes, 1)

    def test_signal_seen_during_pause_cannot_be_replayed_after_deadline(self):
        overlay = RiskOverlay(drawdown_budget=True, dd_pause_hours=24)
        state = BudgetPauseState()
        self.decision(overlay, state, equity=130.0, risk=10.0, stamp_ms=0, signal_ms=0)
        self.decision(
            overlay,
            state,
            equity=160.0,
            risk=5.0,
            stamp_ms=DAY_MS - 900000,
            signal_ms=DAY_MS - 900000,
        )
        old = self.decision(
            overlay, state, equity=160.0, risk=5.0, stamp_ms=DAY_MS, signal_ms=DAY_MS - 900000
        )
        self.assertFalse(old.allowed)
        self.assertIn("stale_signal", old.reasons)
        self.assertFalse(old.resumed)
        fresh = self.decision(
            overlay, state, equity=160.0, risk=5.0, stamp_ms=DAY_MS + 1, signal_ms=DAY_MS + 1
        )
        self.assertTrue(fresh.allowed)

    def test_flat_equity_below_dd_floor_remains_stopped_without_reset(self):
        overlay = RiskOverlay(drawdown_budget=True, dd_pause_hours=24)
        state = BudgetPauseState()
        self.decision(overlay, state, equity=119.0, risk=1.0, stamp_ms=0, signal_ms=0)
        result = self.decision(
            overlay, state, equity=119.0, risk=0.01, stamp_ms=2 * DAY_MS, signal_ms=2 * DAY_MS
        )
        self.assertFalse(result.allowed)
        self.assertIn("drawdown_budget", result.reasons)
        self.assertEqual(state.pause_started_ms, 0)
        self.assertEqual(state.resumes, 0)

    def test_completed_pause_can_start_a_new_episode_without_losing_history(self):
        overlay = RiskOverlay(drawdown_budget=True, dd_pause_hours=24)
        state = BudgetPauseState()
        self.decision(overlay, state, equity=130.0, risk=10.0, stamp_ms=0, signal_ms=0)
        self.assertTrue(
            self.decision(
                overlay, state, equity=160.0, risk=5.0, stamp_ms=DAY_MS, signal_ms=DAY_MS
            ).resumed
        )
        again = self.decision(
            overlay,
            state,
            equity=130.0,
            risk=10.0,
            stamp_ms=DAY_MS + 900000,
            signal_ms=DAY_MS + 900000,
        )
        self.assertTrue(again.started_pause)
        self.assertEqual(state.episodes, 2)
        self.assertEqual(state.resumes, 1)
        self.assertEqual(state.resume_not_before_ms, 2 * DAY_MS + 900000)

    def test_pause_state_round_trip_preserves_clock_and_signal_without_resuming_early(self):
        overlay = RiskOverlay(drawdown_budget=True, dd_pause_hours=24)
        original = BudgetPauseState()
        self.decision(overlay, original, equity=130.0, risk=10.0, stamp_ms=0, signal_ms=0)
        saved = original.snapshot()
        restored = BudgetPauseState.restore(saved)
        self.assertEqual(restored.snapshot(), saved)
        result = self.decision(
            overlay, restored, equity=160.0, risk=5.0, stamp_ms=DAY_MS - 1, signal_ms=DAY_MS - 1
        )
        self.assertFalse(result.allowed)
        self.assertEqual(restored.resume_not_before_ms, DAY_MS)


class NetBreakEvenPolicyTests(unittest.TestCase):
    def level(self, **changes):
        values = dict(
            entry=100.0,
            direction=1,
            fee=0.2,
            factor=1.0,
            slippage=0.1,
            accrued_swap=-0.4,
            grid=0.01,
        )
        values.update(changes)
        return net_break_even(**values)

    def test_debit_swap_is_covered_once_without_double_counting_entry_slippage(self):
        level = self.level()
        self.assertAlmostEqual(level, 100.7)
        self.assertAlmostEqual((level - 100.0) - 0.2 - 0.1 - 0.4, 0.0)
        self.assertNotAlmostEqual(level, 100.8)

    def test_signed_swap_credit_can_place_net_be_below_buy_entry(self):
        level = self.level(accrued_swap=0.5)
        self.assertAlmostEqual(level, 99.8)
        self.assertAlmostEqual((level - 100.0) - 0.2 - 0.1 + 0.5, 0.0)

    def test_buy_rounds_up_sell_rounds_down_on_non_decimal_grid(self):
        buy = self.level(fee=0.01, accrued_swap=-0.02, slippage=0.03, grid=0.25)
        sell = self.level(direction=-1, fee=0.01, accrued_swap=-0.02, slippage=0.03, grid=0.25)
        self.assertEqual(buy, 100.25)
        self.assertEqual(sell, 99.75)
        self.assertGreaterEqual(buy - 100.0 - 0.06, 0)
        self.assertGreaterEqual(100.0 - sell - 0.06, 0)

    def test_later_swap_is_not_a_lifetime_net_floor(self):
        level = self.level()
        first_net = level - 100.0 - 0.2 - 0.1 - 0.4
        later_net = level - 100.0 - 0.2 - 0.1 - 0.9
        self.assertAlmostEqual(first_net, 0.0)
        self.assertLess(later_net, 0.0)

    def test_invalid_net_be_geometry_or_cost_input_is_rejected(self):
        for changes in (
            {"direction": 0},
            {"factor": 0},
            {"grid": 0},
            {"accrued_swap": math.nan},
            {"entry": math.inf},
            {"fee": -1},
            {"slippage": -0.1},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.level(**changes)


if __name__ == "__main__":
    unittest.main()
