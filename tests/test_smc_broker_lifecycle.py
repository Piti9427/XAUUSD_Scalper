import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from types import SimpleNamespace

from scripts.smc.broker_lifecycle import pending_ttl_elapsed, reconcile_broker_lifecycle
from scripts.smc.mt5_adapter import SMCExecutionAdapter


class BrokerLifecycleTests(unittest.TestCase):
    def test_pending_ttl_elapsed_boundary(self):
        created = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
        now = created + timedelta(minutes=20)
        self.assertTrue(pending_ttl_elapsed(created, now, ttl_bars=4, bar_minutes=5))
        self.assertFalse(pending_ttl_elapsed(created, now, ttl_bars=5, bar_minutes=5))

    def test_ttl_cancel_releases_inbox_in_dry_run(self):
        adapter = SMCExecutionAdapter(symbol="XAUUSD", dry_run=True, db_path=":memory:")
        try:
            adapter.claim_setup({"order_id": "TTL_1", "limit": 4050.0})
            adapter.update_setup_status("TTL_1", "accepted", ticket=1)
            old = datetime.now(timezone.utc) - timedelta(minutes=30)
            with adapter._claim_lock:
                adapter.conn.execute(
                    "UPDATE setup_inbox SET created_at = ? WHERE order_id = ?",
                    (old.isoformat(), "TTL_1"),
                )
                adapter.conn.commit()
            now = datetime.now(timezone.utc)
            result = reconcile_broker_lifecycle(
                adapter,
                now=now,
                order_ttl_bars=4,
                bar_minutes=5,
            )
            self.assertEqual(len(result["ttl_cancels"]), 1)
            self.assertEqual(result["ttl_cancels"][0]["order_id"], "TTL_1")
            self.assertEqual(result["ttl_cancels"][0]["status"], "success")
            status = adapter.get_setup_status("TTL_1")
            self.assertEqual(status["status"], "closed")
            self.assertTrue(adapter.has_lifecycle_event("TTL_1", "ORDER_CANCELED"))
        finally:
            adapter.close()

    def test_broker_fill_and_close_detection_live_mock(self):
        adapter = SMCExecutionAdapter(symbol="XAUUSD", dry_run=True, db_path=":memory:")
        try:
            adapter.claim_setup({"order_id": "LIFE_1", "limit": 4050.0})
            adapter.update_setup_status("LIFE_1", "accepted", ticket=99)
            adapter.dry_run = False
            adapter.connected = True
            broker = SimpleNamespace(
                positions_get=lambda symbol: [
                    SimpleNamespace(
                        ticket=99,
                        comment="SMC_LIFE_1",
                        type=0,
                        price_open=4050.0,
                        sl=4045.0,
                        volume=0.01,
                    )
                ],
                orders_get=lambda symbol: [],
                history_deals_get=lambda a, b: [
                    SimpleNamespace(
                        comment="SMC_LIFE_1",
                        profit=12.5,
                        commission=-0.5,
                        swap=0.0,
                        fee=0.0,
                    )
                ],
            )
            with patch("scripts.smc.mt5_adapter.mt5", broker):
                fill_res = reconcile_broker_lifecycle(
                    adapter,
                    now=datetime.now(timezone.utc),
                    order_ttl_bars=4,
                    bar_minutes=5,
                )
            self.assertEqual(len(fill_res["broker_fills"]), 1)
            self.assertEqual(fill_res["broker_fills"][0]["status"], "filled")
            self.assertTrue(adapter.has_lifecycle_event("LIFE_1", "ORDER_FILLED"))

            broker.positions_get = lambda symbol: []
            with patch("scripts.smc.mt5_adapter.mt5", broker):
                close_res = reconcile_broker_lifecycle(
                    adapter,
                    now=datetime.now(timezone.utc),
                    order_ttl_bars=4,
                    bar_minutes=5,
                )
            self.assertEqual(len(close_res["broker_closes"]), 1)
            self.assertTrue(adapter.has_lifecycle_event("LIFE_1", "TRADE_CLOSED"))
            self.assertEqual(adapter.get_setup_status("LIFE_1")["status"], "closed")
        finally:
            adapter.close()

    def test_partial_fill_keeps_residual_and_logs_event(self):
        adapter = SMCExecutionAdapter(symbol="XAUUSD", dry_run=True, db_path=":memory:")
        try:
            adapter.claim_setup({"order_id": "PART_1", "limit": 4050.0})
            adapter.update_setup_status("PART_1", "accepted", ticket=42)
            adapter.dry_run = False
            adapter.connected = True
            broker = SimpleNamespace(
                positions_get=lambda symbol: [
                    SimpleNamespace(
                        ticket=42,
                        comment="SMC_PART_1",
                        type=0,
                        price_open=4050.0,
                        sl=4045.0,
                        volume=0.02,
                    )
                ],
                orders_get=lambda symbol: [
                    SimpleNamespace(
                        ticket=43,
                        comment="SMC_PART_1",
                        volume_current=0.02,
                        volume_initial=0.04,
                    )
                ],
                history_deals_get=lambda a, b: [],
            )
            with patch("scripts.smc.mt5_adapter.mt5", broker):
                result = reconcile_broker_lifecycle(
                    adapter,
                    now=datetime.now(timezone.utc),
                    order_ttl_bars=4,
                    bar_minutes=5,
                )
            self.assertEqual(len(result["broker_fills"]), 1)
            self.assertEqual(result["broker_fills"][0]["status"], "partial_fill_with_residual")
            self.assertEqual(result["broker_fills"][0]["residual_pending_volume"], 0.02)
            self.assertTrue(adapter.has_lifecycle_event("PART_1", "ORDER_FILLED"))
            self.assertTrue(adapter.has_lifecycle_event("PART_1", "PARTIAL_FILL_RESIDUAL"))
            self.assertEqual(adapter.get_setup_status("PART_1")["status"], "accepted")
        finally:
            adapter.close()

    def test_fill_during_cancel_is_retained(self):
        adapter = SMCExecutionAdapter(symbol="XAUUSD", dry_run=True, db_path=":memory:")
        try:
            adapter.claim_setup({"order_id": "CANCEL_FILL", "limit": 4050.0})
            adapter.update_setup_status("CANCEL_FILL", "accepted", ticket=7)
            adapter.log_lifecycle_event(
                event_type="ORDER_CANCELED",
                order_id="CANCEL_FILL",
                reason="cancel_requested",
            )
            adapter.dry_run = False
            adapter.connected = True
            broker = SimpleNamespace(
                positions_get=lambda symbol: [
                    SimpleNamespace(
                        ticket=7,
                        comment="SMC_CANCEL_FILL",
                        type=0,
                        price_open=4050.0,
                        sl=4045.0,
                        volume=0.01,
                    )
                ],
                orders_get=lambda symbol: [],
                history_deals_get=lambda a, b: [],
            )
            with patch("scripts.smc.mt5_adapter.mt5", broker):
                result = reconcile_broker_lifecycle(
                    adapter,
                    now=datetime.now(timezone.utc),
                    order_ttl_bars=4,
                    bar_minutes=5,
                )
            self.assertEqual(result["broker_fills"][0]["status"], "filled_during_cancel")
            self.assertTrue(adapter.has_lifecycle_event("CANCEL_FILL", "ORDER_FILLED"))
        finally:
            adapter.close()


if __name__ == "__main__":
    unittest.main()
