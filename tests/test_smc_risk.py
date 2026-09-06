import unittest
from scripts.smc.risk import calculate_lot_size, LotResult
from scripts.smc.types import Direction, OrderIntentType, SetupSignal, OrderIntent, AccountState


class TestSMCRiskCalculator(unittest.TestCase):
    def test_standard_valid_lot_calculation(self):
        # Balance = $10,000, Risk = 0.5% ($50)
        # Entry = 2000.00, SL = 1996.00 -> raw distance = $4.00
        # Spread buffer = $0.30 -> total SL distance = $4.30
        # Denominator = 4.30 * 100 = 430
        # Raw lot = 50 / 430 = 0.116279...
        # Floored to 0.01 step = 0.11
        result = calculate_lot_size(
            balance=10000.0,
            entry_price=2000.00,
            sl_price=1996.00,
            risk_pct=0.005,
            spread_buffer=0.30,
            max_sl_cap=6.00
        )
        self.assertIsInstance(result, LotResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 0.11)
        self.assertAlmostEqual(result.sl_distance, 4.30, places=2)
        self.assertAlmostEqual(result.risk_amount, 50.0, places=2)

    def test_max_sl_cap_rejection(self):
        # SL distance before buffer = $6.00 + $0.30 = $6.30 > $6.00 max cap
        # Should be skipped (lot_size = 0.0, is_valid = False)
        result = calculate_lot_size(
            balance=10000.0,
            entry_price=2000.00,
            sl_price=1994.00,
            risk_pct=0.005,
            spread_buffer=0.30,
            max_sl_cap=6.00
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.lot_size, 0.0)
        self.assertIn("SL distance exceeds max cap", result.reason)

    def test_min_lot_clamping(self):
        # Balance = $500, Risk = 0.5% ($2.50)
        # SL distance = $5.00 * 100 = 500
        # Raw lot = 2.50 / 500 = 0.005 -> below min_lot (0.01)
        # Should be clamped to 0.01 if valid or handled gracefully
        result = calculate_lot_size(
            balance=500.0,
            entry_price=2000.00,
            sl_price=1995.30,
            risk_pct=0.005,
            spread_buffer=0.30,
            min_lot=0.01
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 0.01)

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
            max_lot=10.0
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.lot_size, 10.0)

    def test_zero_or_negative_balance(self):
        result = calculate_lot_size(
            balance=0.0,
            entry_price=2000.00,
            sl_price=1996.00
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.lot_size, 0.0)

    def test_zero_sl_distance(self):
        result = calculate_lot_size(
            balance=10000.0,
            entry_price=2000.00,
            sl_price=2000.00,
            spread_buffer=0.0
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.lot_size, 0.0)


class TestSMCTypes(unittest.TestCase):
    def test_enums_and_dataclasses(self):
        self.assertEqual(Direction.BUY.value, "BUY")
        self.assertEqual(Direction.SELL.value, "SELL")
        self.assertEqual(OrderIntentType.PLACE_LIMIT.value, "PLACE_LIMIT")
        self.assertEqual(OrderIntentType.MOVE_SL_TO_BE.value, "MOVE_SL_TO_BE")


if __name__ == "__main__":
    unittest.main()
