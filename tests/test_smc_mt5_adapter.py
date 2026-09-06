import unittest
from datetime import datetime, timezone
from scripts.smc.types import Direction, OrderIntentType, OrderIntent
from scripts.smc.mt5_adapter import SMCExecutionAdapter, ExecutionResult


class TestSMCMT5Adapter(unittest.TestCase):
    def setUp(self):
        # Initialize in dry-run / mock mode so it runs without real MT5 connection on Mac
        self.adapter = SMCExecutionAdapter(symbol="XAUUSD", dry_run=True)

    def test_place_limit_order_dry_run(self):
        intent = OrderIntent(
            intent_type=OrderIntentType.PLACE_LIMIT,
            direction=Direction.BUY,
            limit_price=2014.0,
            sl_price=2008.2,
            tp_price=2025.6,
            lot_size=0.10,
            reason="Test Limit Buy"
        )
        res = self.adapter.execute_intent(intent)
        self.assertIsInstance(res, ExecutionResult)
        self.assertTrue(res.success)
        self.assertIn("DRY_RUN", res.message)

    def test_move_be_order_dry_run(self):
        intent = OrderIntent(
            intent_type=OrderIntentType.MOVE_SL_TO_BE,
            direction=Direction.BUY,
            limit_price=2014.0,
            sl_price=2014.0,
            reason="Move to BE"
        )
        res = self.adapter.execute_intent(intent)
        self.assertTrue(res.success)

    def test_sqlite_journaling(self):
        # Log an event and verify it persists in SQLite
        db_path = ":memory:" # in-memory SQLite for testing
        adapter = SMCExecutionAdapter(symbol="XAUUSD", dry_run=True, db_path=db_path)
        adapter.log_lifecycle_event(
            event_type="PLACE_LIMIT",
            direction="BUY",
            entry_price=2014.0,
            sl_price=2008.2,
            tp_price=2025.6,
            lot_size=0.10,
            reason="Test Log"
        )
        logs = adapter.get_lifecycle_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["event_type"], "PLACE_LIMIT")
        self.assertEqual(logs[0]["entry_price"], 2014.0)


if __name__ == "__main__":
    unittest.main()
