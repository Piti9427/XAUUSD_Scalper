import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from scripts.smc.types import Direction, OrderIntentType, OrderIntent
from scripts.smc.mt5_adapter import SMCExecutionAdapter, ExecutionResult


class TestSMCMT5Adapter(unittest.TestCase):
    def setUp(self):
        # Initialize in dry-run / mock mode so it runs without real MT5 connection on Mac
        self.adapter = SMCExecutionAdapter(symbol="XAUUSD", dry_run=True, db_path=":memory:")

    def tearDown(self):
        self.adapter.close()

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
        try:
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
        finally:
            adapter.close()
        self.assertEqual(logs[0]["entry_price"], 2014.0)

    def test_live_cancel_rejected_by_broker_is_not_recorded_as_success(self):
        broker = Mock()
        broker.TRADE_ACTION_REMOVE = 8
        broker.TRADE_RETCODE_DONE = 10009
        broker.orders_get.return_value = [SimpleNamespace(ticket=42, comment="SMC_owned-1")]
        broker.order_send.return_value = SimpleNamespace(retcode=10019, comment="rejected")
        self.adapter.dry_run = False
        with patch("scripts.smc.mt5_adapter.mt5", broker):
            result = self.adapter.execute_intent(OrderIntent(
                intent_type=OrderIntentType.CANCEL_LIMIT, order_id="owned-1"
            ))
        self.assertFalse(result.success)
        self.assertFalse(any(
            row["event_type"] == "CANCEL_LIMIT"
            for row in self.adapter.get_lifecycle_logs()
        ))

    def test_live_market_close_rejected_by_broker_is_not_recorded_as_success(self):
        broker = Mock()
        broker.ORDER_TYPE_BUY = 0
        broker.ORDER_TYPE_SELL = 1
        broker.TRADE_ACTION_DEAL = 1
        broker.TRADE_RETCODE_DONE = 10009
        broker.positions_get.return_value = [SimpleNamespace(
            ticket=42, comment="SMC_owned-2", type=broker.ORDER_TYPE_BUY,
            volume=0.02,
        )]
        broker.symbol_info_tick.return_value = SimpleNamespace(bid=4050.0, ask=4050.3)
        broker.order_send.return_value = SimpleNamespace(retcode=10019, comment="rejected")
        self.adapter.dry_run = False
        with patch("scripts.smc.mt5_adapter.mt5", broker):
            result = self.adapter.execute_intent(OrderIntent(
                intent_type=OrderIntentType.CLOSE_MARKET, order_id="owned-2"
            ))
        self.assertFalse(result.success)
        self.assertFalse(any(
            row["event_type"] == "CLOSE_MARKET"
            for row in self.adapter.get_lifecycle_logs()
        ))

    def test_live_cancel_matches_exact_owned_order_id(self):
        broker = Mock()
        broker.TRADE_ACTION_REMOVE = 8
        broker.TRADE_RETCODE_DONE = 10009
        broker.orders_get.return_value = [
            SimpleNamespace(ticket=41, comment="SMC_other-owned-3"),
            SimpleNamespace(ticket=42, comment="SMC_owned-3"),
        ]
        broker.order_send.return_value = SimpleNamespace(retcode=10009, comment="done")
        self.adapter.dry_run = False
        with patch("scripts.smc.mt5_adapter.mt5", broker):
            result = self.adapter.execute_intent(OrderIntent(
                intent_type=OrderIntentType.CANCEL_LIMIT, order_id="owned-3"
            ))
        self.assertTrue(result.success)
        broker.order_send.assert_called_once_with({"action": 8, "order": 42})

    def test_live_be_rejected_by_broker_is_not_recorded_as_success(self):
        broker = Mock()
        broker.TRADE_ACTION_SLTP = 6
        broker.TRADE_RETCODE_DONE = 10009
        broker.positions_get.return_value = [SimpleNamespace(
            ticket=42, comment="SMC_owned-4", tp=4062.5,
        )]
        broker.order_send.return_value = SimpleNamespace(retcode=10019, comment="rejected")
        self.adapter.dry_run = False
        with patch("scripts.smc.mt5_adapter.mt5", broker):
            result = self.adapter.execute_intent(OrderIntent(
                intent_type=OrderIntentType.MOVE_SL_TO_BE,
                order_id="owned-4", sl_price=4050.0,
            ))
        self.assertFalse(result.success)
        self.assertFalse(any(
            row["event_type"] == "MOVE_SL_TO_BE"
            for row in self.adapter.get_lifecycle_logs()
        ))

    def test_live_partial_rejected_by_broker_is_not_recorded_as_success(self):
        broker = Mock()
        broker.ORDER_TYPE_BUY = 0
        broker.ORDER_TYPE_SELL = 1
        broker.TRADE_ACTION_DEAL = 1
        broker.TRADE_RETCODE_DONE = 10009
        broker.ORDER_TIME_GTC = 0
        broker.positions_get.return_value = [SimpleNamespace(
            ticket=42, comment="SMC_owned-5", type=broker.ORDER_TYPE_BUY,
            volume=0.04,
        )]
        broker.symbol_info_tick.return_value = SimpleNamespace(bid=4055.0, ask=4055.3)
        broker.order_send.return_value = SimpleNamespace(retcode=10019, comment="rejected")
        self.adapter.dry_run = False
        with patch("scripts.smc.mt5_adapter.mt5", broker):
            result = self.adapter.execute_intent(OrderIntent(
                intent_type=OrderIntentType.PARTIAL_CLOSE,
                order_id="owned-5", lot_size=0.02,
            ))
        self.assertFalse(result.success)
        self.assertFalse(any(
            row["event_type"] == "PARTIAL_CLOSE"
            for row in self.adapter.get_lifecycle_logs()
        ))

    def test_live_mode_without_mt5_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("scripts.smc.mt5_adapter.mt5", None):
                with self.assertRaises(RuntimeError):
                    SMCExecutionAdapter(
                        dry_run=False, db_path=str(Path(directory) / "trades.db")
                    )

    def test_live_risk_snapshot_reads_balance_equity_and_symbol_volume(self):
        broker = Mock()
        broker.account_info.return_value = SimpleNamespace(balance=10000.0, equity=6000.0)
        broker.symbol_info.return_value = SimpleNamespace(
            volume_min=0.01, volume_max=5.0, volume_step=0.01,
            trade_contract_size=100.0,
        )
        self.adapter.dry_run = False
        self.adapter.connected = True
        with patch("scripts.smc.mt5_adapter.mt5", broker):
            snapshot = self.adapter.get_risk_snapshot()
        self.assertEqual(snapshot["balance"], 10000.0)
        self.assertEqual(snapshot["equity"], 6000.0)
        self.assertEqual(snapshot["min_lot"], 0.01)
        self.assertEqual(snapshot["max_lot"], 5.0)
        self.assertEqual(snapshot["lot_step"], 0.01)
        self.assertEqual(snapshot["contract_size"], 100.0)


if __name__ == "__main__":
    unittest.main()
