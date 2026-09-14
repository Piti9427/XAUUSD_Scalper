import unittest
import tempfile
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from types import SimpleNamespace

from scripts.smc.mt5_adapter import SMCExecutionAdapter
from scripts.smc.types import Direction, OrderIntentType, OrderIntent


class TestScrutinizeFixesRepro(unittest.TestCase):
    """Reproduces the critical fail paths identified in the Scrutinize analysis."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "repro_scrutinize.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_repro_place_limit_order_send_returns_none_raises_attribute_error(self):
        """
        Fail Path 1: MT5 terminal disconnect / IPC error returns None from order_send().
        Currently, PLACE_LIMIT accesses result.retcode directly, raising AttributeError!
        """
        broker = Mock()
        broker.initialize.return_value = True
        broker.ORDER_TYPE_BUY_LIMIT = 2
        broker.TRADE_ACTION_PENDING = 5
        broker.ORDER_TIME_GTC = 0
        broker.order_send.return_value = None

        with patch("scripts.smc.mt5_adapter.mt5", broker):
            adapter = SMCExecutionAdapter(dry_run=False, db_path=self.db_path)
            try:
                intent = OrderIntent(
                    intent_type=OrderIntentType.PLACE_LIMIT,
                    direction=Direction.BUY,
                    limit_price=2000.0,
                    sl_price=1990.0,
                    tp_price=2025.0,
                    lot_size=0.1,
                    order_id="TEST_NONE_PLACE",
                )
                res = adapter.execute_intent(intent)
                self.assertFalse(res.success)
                self.assertIn("None", res.message)
            finally:
                adapter.close()

    def test_repro_tick_none_raises_attribute_error(self):
        """
        Fail Path 2: If symbol tick feed is offline, symbol_info_tick() returns None.
        Currently, PARTIAL_CLOSE and CLOSE_MARKET access tick.bid/tick.ask directly, raising AttributeError!
        """
        broker = Mock()
        broker.initialize.return_value = True
        broker.symbol_info_tick.return_value = None
        mock_pos = SimpleNamespace(ticket=123, type=0, volume=0.2, comment="SMC_TEST_TICK")
        broker.positions_get.return_value = [mock_pos]

        with patch("scripts.smc.mt5_adapter.mt5", broker):
            adapter = SMCExecutionAdapter(dry_run=False, db_path=self.db_path)
            try:
                intent = OrderIntent(
                    intent_type=OrderIntentType.CLOSE_MARKET,
                    order_id="TEST_TICK",
                    ticket=123,
                )
                res = adapter.execute_intent(intent)
                self.assertFalse(res.success)
                self.assertIn("tick", res.message.lower())
            finally:
                adapter.close()

    def test_repro_cross_midnight_realized_pnl_returns_none(self):
        """
        Fail Path 3: A trade opened yesterday at 23:50 UTC and closing after 00:00 UTC
        has deals from yesterday. Currently, get_realized_pnl_for_order truncates to today 00:00 UTC,
        so history_deals_get is called only from 00:00 UTC, missing yesterday's deal!
        """
        broker = Mock()
        broker.initialize.return_value = True

        recorded_from_dates = []

        def mock_history_deals_get(from_date, to_date):
            recorded_from_dates.append(from_date)
            # If from_date is today 00:00, deal from yesterday is excluded!
            deal_time = datetime.now(timezone.utc) - timedelta(days=1)
            if from_date <= deal_time:
                mock_deal = SimpleNamespace(
                    comment="SMC_OVERNIGHT",
                    profit=150.0,
                    commission=-3.0,
                    swap=-1.5,
                    fee=0.0,
                )
                return [mock_deal]
            return []

        broker.history_deals_get.side_effect = mock_history_deals_get

        with patch("scripts.smc.mt5_adapter.mt5", broker):
            adapter = SMCExecutionAdapter(dry_run=False, db_path=self.db_path)
            try:
                # Add setup in inbox with created_at = 1 day ago
                yesterday_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
                with adapter._claim_lock:
                    adapter.conn.execute(
                        "INSERT INTO setup_inbox (receipt_id, order_id, payload_json, payload_hash, status, created_at) "
                        "VALUES ('rec1', 'OVERNIGHT', '{}', 'hash', 'accepted', ?)",
                        (yesterday_iso,),
                    )
                    adapter.conn.commit()

                pnl = adapter.get_realized_pnl_for_order("OVERNIGHT")
                self.assertIsNotNone(pnl, "Cross-midnight deal must be found using lookback or created_at")
                self.assertEqual(pnl, 145.5)
            finally:
                adapter.close()

    def test_repro_reconcile_uncertain_does_not_reject_filled_order(self):
        """
        Fail Path 4: An uncertain order that was filled on broker has state ORDER_STATE_FILLED
        in history_orders_get. Currently, reconcile_uncertain marks it as 'rejected'!
        """
        broker = Mock()
        broker.initialize.return_value = True
        broker.orders_get.return_value = []
        broker.positions_get.return_value = []

        ORDER_STATE_FILLED = 1
        broker.ORDER_STATE_FILLED = ORDER_STATE_FILLED
        mock_hist_order = SimpleNamespace(
            comment="SMC_FILLED_ORDER",
            ticket=777888,
            state=ORDER_STATE_FILLED,
        )
        broker.history_orders_get.return_value = [mock_hist_order]

        with patch("scripts.smc.mt5_adapter.mt5", broker):
            adapter = SMCExecutionAdapter(dry_run=False, db_path=self.db_path)
            try:
                adapter.claim_setup({"order_id": "FILLED_ORDER"})
                adapter.update_setup_status("FILLED_ORDER", "uncertain")

                outcome = adapter.reconcile_uncertain("FILLED_ORDER")
                # Under the bug, outcome is 'rejected'. It should NOT be rejected when order was filled!
                self.assertNotEqual(outcome, "rejected", "Filled order in history must not be marked rejected")
            finally:
                adapter.close()

    def test_repro_telegram_cards_alignment_for_sell_and_lots(self):
        """
        Fail Path 5: Webhook notifications hardcode BUY and 0.01 lots.
        """
        from scripts.webhook_bridge import create_app
        from fastapi.testclient import TestClient

        mock_notifier = Mock()
        mock_notifier.enabled = True
        captured_cards = []
        mock_notifier.send_message.side_effect = lambda card: captured_cards.append(card)

        app = create_app(
            auth_token="NOTIF_SECRET",
            dry_run=True,
            db_path=self.db_path,
            notifier=mock_notifier,
        )
        client = TestClient(app)
        headers = {"Authorization": "Bearer NOTIF_SECRET"}

        try:
            # 1. ORDER_FILLED with SELL and 0.50 lots
            client.post(
                "/webhook/tradingview",
                json={
                    "event": "ORDER_FILLED",
                    "order_id": "SELL_100",
                    "dir": "SELL",
                    "entry": 2500.0,
                    "sl": 2505.0,
                    "tp1": 2495.0,
                    "lot_size": 0.50,
                },
                headers=headers,
            )
            # 2. TP1_HIT_MOVE_BE for SELL
            client.post(
                "/webhook/tradingview",
                json={
                    "event": "TP1_HIT_MOVE_BE",
                    "order_id": "SELL_100",
                    "dir": "SELL",
                    "entry": 2500.0,
                    "new_sl": 2499.90,
                    "lot_size": 0.50,
                },
                headers=headers,
            )
            # 3. TRADE_CLOSED for SELL
            client.post(
                "/webhook/tradingview",
                json={
                    "event": "TRADE_CLOSED",
                    "order_id": "SELL_100",
                    "dir": "SELL",
                    "reason": "TP2 HIT 🎯",
                    "pnl_r": 2.5,
                    "pnl_dollar": 125.0,
                },
                headers=headers,
            )

            self.assertEqual(len(captured_cards), 3)
            # Under the bug, ORDER_FILLED reports 0.01 Lots instead of 0.50 Lots!
            self.assertIn("0.50 Lot", captured_cards[0], "ORDER_FILLED must display actual lot size")
            # Under the bug, TP1 card reports BUY instead of SELL!
            self.assertIn("SELL", captured_cards[1], "TP1 card must reflect SELL direction")
            # Under the bug, TRADE_CLOSED reports BUY instead of SELL!
            self.assertIn("SELL", captured_cards[2], "TRADE_CLOSED card must reflect SELL direction")
        finally:
            if hasattr(app.state, "adapter") and app.state.adapter:
                app.state.adapter.close()


if __name__ == "__main__":
    unittest.main()
