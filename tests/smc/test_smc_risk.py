import unittest
from scripts.smc.risk import calculate_lot_size, check_fixed_lot_risk, LotResult, frozen_initial_r
from scripts.smc.types import Direction, OrderIntentType


class TestSMCRiskCalculator(unittest.TestCase):
    def test_standard_valid_lot_calculation(self):
        # Balance = $10,000, Risk = 0.5% ($50)
        # Entry = 2000.00, SL = 1996.00 -> raw distance = $4.00
        # Spread buffer = $0.30 -> total SL distance = $4.30
        # Denominator = 4.30 * 100 = 430
        # Raw lot = 50 / 430 = 0.116279...
        # Floored to two 0.01-step legs = 0.10
        result = calculate_lot_size(
            balance=10000.0,
            entry_price=2000.00,
            sl_price=1996.00,
            risk_pct=0.005,
            spread_buffer=0.30,
            max_sl_cap=6.00,
        )
        self.assertIsInstance(result, LotResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 0.10)
        self.assertAlmostEqual(result.sl_distance, 4.30, places=2)
        self.assertAlmostEqual(result.risk_amount, 43.0, places=2)

    def test_max_sl_cap_rejection(self):
        # SL distance before buffer = $6.00 + $0.30 = $6.30 > $6.00 max cap
        # Should be skipped (lot_size = 0.0, is_valid = False)
        result = calculate_lot_size(
            balance=200.0,
            entry_price=2000.00,
            sl_price=1994.00,
            risk_pct=0.005,
            spread_buffer=0.30,
            max_sl_cap=6.00,
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.lot_size, 0.0)
        self.assertIn("SL distance exceeds max cap", result.reason)

    def test_min_lot_that_exceeds_configured_risk_is_rejected(self):
        # Balance = $500, Risk = 0.5% ($2.50)
        # SL distance = $5.00 * 100 = 500
        # Raw lot = 2.50 / 500 = 0.005 -> below min_lot (0.01)
        # Min lot 0.01 * 5.00 * 100 = $5.00 risk, above $2.50 budget.
        result = calculate_lot_size(
            balance=500.0,
            entry_price=2000.00,
            sl_price=1995.30,
            risk_pct=0.005,
            spread_buffer=0.30,
            min_lot=0.01,
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.lot_size, 0.0)

    def test_strict_small_account_risk_gate_rejects_over_risk(self):
        # Balance = $500. SL distance = $10.30.
        # Min lot 0.01 * 10.30 * 100 = $10.30 risk (2.06% > 1.5% max cap = $7.50).
        # ADR-020: Must reject setup to protect small account!
        result = calculate_lot_size(
            balance=500.0,
            entry_price=2000.00,
            sl_price=1990.00,
            risk_pct=0.005,
            spread_buffer=0.30,
            min_lot=0.01,
            max_risk_cap_pct=0.015,
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.lot_size, 0.0)
        self.assertIn("Risk cap: min lot risks", result.reason)

    def test_max_lot_clamping(self):
        # Large account $500,000 with very small SL distance ($1.00)
        # Risk = $2500, Denominator = 100
        # Raw lot = 25.0 -> should clamp to max_lot (10.0)
        result = calculate_lot_size(
            balance=500000.0,
            entry_price=2000.00,
            sl_price=1999.30,
            risk_pct=0.005,
            spread_buffer=0.30,
            max_lot=10.0,
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 10.0)

    def test_lot_is_rounded_down_to_two_broker_steps_for_equal_scale_out(self):
        # $35 budget / ($10 SL * 100) permits 0.03 lot, but 0.03
        # cannot be divided into two 0.01-step broker orders.
        result = calculate_lot_size(
            balance=3500.0,
            entry_price=2000.0,
            sl_price=1990.0,
            risk_pct=0.01,
            spread_buffer=0.0,
            lot_step=0.01,
            min_lot=0.01,
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 0.02)

    def test_broker_max_lot_is_also_split_compatible(self):
        result = calculate_lot_size(
            balance=100000.0,
            entry_price=2000.0,
            sl_price=1990.0,
            risk_pct=0.01,
            spread_buffer=0.0,
            max_lot=0.03,
            lot_step=0.01,
            min_lot=0.01,
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 0.02)

    def test_equity_below_balance_limits_risk_budget(self):
        result = calculate_lot_size(
            balance=10000.0,
            equity=5000.0,
            entry_price=2000.0,
            sl_price=1990.0,
            risk_pct=0.01,
            spread_buffer=0.0,
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 0.04)
        self.assertEqual(result.risk_amount, 40.0)

    def test_commission_and_slippage_are_included_in_budget(self):
        result = calculate_lot_size(
            balance=5000.0,
            entry_price=2000.0,
            sl_price=1990.0,
            risk_pct=0.01,
            spread_buffer=0.0,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 0.04)
        self.assertAlmostEqual(result.risk_amount, 42.4)

    def test_generic_sizing_keeps_configured_five_percent_budget(self):
        result = calculate_lot_size(
            balance=200,
            entry_price=2600,
            sl_price=2588,
            risk_pct=0.05,
            max_risk_cap_pct=0.10,
        )
        self.assertFalse(result.is_valid)
        self.assertIn("configured risk of 5.0%", result.reason)

    def test_pure_b1_accepts_fixed_lot_between_five_and_ten_percent(self):
        result = check_fixed_lot_risk(
            equity=200,
            entry_price=2600,
            sl_price=2588,
            lot_size=0.01,
            spread_buffer=0.30,
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 0.01)
        self.assertEqual(result.risk_amount, 12.30)

    def test_pure_b1_rejects_above_ten_percent_with_costs(self):
        result = check_fixed_lot_risk(
            equity=200,
            entry_price=2600,
            sl_price=2581,
            lot_size=0.01,
            spread_buffer=0.30,
            slippage_allowance=0.50,
            commission_per_lot=30,
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.lot_size, 0)
        self.assertEqual(result.risk_amount, 20.10)

    def test_pure_b1_does_not_size_up_when_stop_is_narrow(self):
        result = check_fixed_lot_risk(
            equity=200,
            entry_price=2600,
            sl_price=2598,
            lot_size=0.01,
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 0.01)

    def test_pure_b1_rejects_other_lot_even_under_cap(self):
        result = check_fixed_lot_risk(
            equity=200,
            entry_price=2600,
            sl_price=2598,
            lot_size=0.02,
        )
        self.assertFalse(result.is_valid)

    def test_pure_b1_rejects_broker_volume_mismatch(self):
        result = check_fixed_lot_risk(
            equity=200,
            entry_price=2600,
            sl_price=2598,
            lot_size=0.01,
            min_lot=0.02,
        )
        self.assertFalse(result.is_valid)

    def test_pure_b1_rejects_off_step_volume(self):
        result = check_fixed_lot_risk(
            equity=200,
            entry_price=2600,
            sl_price=2598,
            lot_size=0.01,
            min_lot=0.005,
            lot_step=0.01,
        )
        self.assertFalse(result.is_valid)

    def test_pure_b1_requires_live_cost_model(self):
        result = check_fixed_lot_risk(
            equity=200,
            entry_price=2600,
            sl_price=2598,
            require_cost_model=True,
        )
        self.assertFalse(result.is_valid)
        self.assertIn("Missing commission or slippage", result.reason)

    def test_pure_b1_cap_uses_current_equity(self):
        result = check_fixed_lot_risk(
            equity=100,
            entry_price=2600,
            sl_price=2588,
            lot_size=0.01,
        )
        self.assertFalse(result.is_valid)

    def test_strict_cost_model_rejects_missing_allowance(self):
        result = calculate_lot_size(
            balance=5000.0,
            entry_price=2000.0,
            sl_price=1990.0,
            risk_pct=0.01,
            spread_buffer=0.0,
            commission_per_lot=10.0,
            require_cost_model=True,
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.lot_size, 0.0)

    def test_negative_cost_allowance_is_rejected(self):
        result = calculate_lot_size(
            balance=5000.0,
            entry_price=2000.0,
            sl_price=1990.0,
            risk_pct=0.01,
            spread_buffer=0.0,
            commission_per_lot=-10.0,
            slippage_allowance=0.0,
            require_cost_model=True,
        )
        self.assertFalse(result.is_valid)

    def test_broker_millilot_step_is_preserved(self):
        result = calculate_lot_size(
            balance=500.0,
            entry_price=2000.0,
            sl_price=1990.0,
            risk_pct=0.01,
            spread_buffer=0.0,
            min_lot=0.001,
            lot_step=0.001,
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 0.004)

    def test_zero_or_negative_balance(self):
        result = calculate_lot_size(balance=0.0, entry_price=2000.00, sl_price=1996.00)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.lot_size, 0.0)

    def test_zero_sl_distance(self):
        result = calculate_lot_size(
            balance=200.0, entry_price=2000.00, sl_price=2000.00, spread_buffer=0.0
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.lot_size, 0.0)

    def test_valid_lot_never_exceeds_risk_budget(self):
        result = calculate_lot_size(
            balance=10000.0,
            entry_price=2000.00,
            sl_price=1996.00,
            risk_pct=0.005,
            spread_buffer=0.30,
        )
        self.assertTrue(result.is_valid)
        self.assertLessEqual(result.risk_amount, 10000.0 * 0.005 + 1e-6)

    def test_frozen_initial_r_ignores_later_volume_change(self):
        # Entry risk locked at 0.10 lot * $5 SL * 100 = $50.
        r = frozen_initial_r(
            pnl_dollars=25.0,
            initial_sl_distance=5.0,
            filled_lot=0.10,
            contract_size=100.0,
        )
        self.assertEqual(r, 0.5)


class TestSMCTypes(unittest.TestCase):
    def test_enums_and_dataclasses(self):
        self.assertEqual(Direction.BUY.value, "BUY")
        self.assertEqual(Direction.SELL.value, "SELL")
        self.assertEqual(OrderIntentType.PLACE_LIMIT.value, "PLACE_LIMIT")
        self.assertEqual(OrderIntentType.MOVE_SL_TO_BE.value, "MOVE_SL_TO_BE")


if __name__ == "__main__":
    unittest.main()
