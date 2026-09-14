import unittest
from fastapi.testclient import TestClient


class TestWebhookBridgeAuth(unittest.TestCase):
    """Ticket 01: Webhook Ingestion Skeleton & Token Authentication."""

    def setUp(self):
        from scripts.webhook_bridge import create_app
        self.secret_token = "TEST_SECRET_TOKEN_123"
        self.app = create_app(auth_token=self.secret_token, dry_run=True)
        self.client = TestClient(self.app)

    def test_health_check_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["mode"], "dry-run")
        self.assertIn("uptime_seconds", data)

    def test_webhook_unauthorized_missing_token(self):
        payload = {"event": "PING"}
        response = self.client.post("/webhook/tradingview", json=payload)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid or missing authorization token")

    def test_webhook_unauthorized_invalid_token(self):
        payload = {"event": "PING"}
        headers = {"Authorization": "Bearer WRONG_TOKEN"}
        response = self.client.post("/webhook/tradingview", json=payload, headers=headers)
        self.assertEqual(response.status_code, 401)

    def test_webhook_authorized_valid_token(self):
        payload = {"event": "PING"}
        headers = {"Authorization": f"Bearer {self.secret_token}"}
        response = self.client.post("/webhook/tradingview", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")


class TestWebhookBridgeLimitExecution(unittest.TestCase):
    """Ticket 02: Pending Limit Order Execution & Dynamic Risk Gate."""

    def setUp(self):
        import tempfile
        import os
        from scripts.webhook_bridge import create_app
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_trades.db")
        self.secret_token = "TEST_SECRET_TOKEN_456"
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
            account_balance=10000.0,
            risk_pct=0.01,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret_token}"}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_setup_pending_valid_buy_limit(self):
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_101",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
            "ttl": 4,
            "time": "2026-09-14 10:00:00",
        }
        response = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["action"], "LIMIT_PLACED")
        self.assertEqual(data["order_id"], "XAUUSD_101")
        self.assertGreater(data["lot_size"], 0.0)

    def test_setup_pending_idempotency_duplicate_ignored(self):
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_102",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
        }
        res1 = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["status"], "success")

        # Second delivery of same event and order_id must be ignored
        res2 = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["status"], "ignored_duplicate")
        self.assertEqual(data2["order_id"], "XAUUSD_102")

    def test_setup_pending_small_account_risk_gate_rejected(self):
        from scripts.webhook_bridge import create_app
        # Small account ($100 balance) with high SL distance ($20.00)
        small_app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
            account_balance=100.0,
            risk_pct=0.01,
        )
        small_client = TestClient(small_app)
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_103",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4030.00, # $20.00 SL distance -> 0.01 lot = $200 risk = 200% of $100 balance > 1.5%
            "tp1": 4070.00,
            "tp2": 4100.00,
        }
        res = small_client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "rejected")
        self.assertIn("ADR-020", data["reason"])


class TestWebhookBridgeScaleOutAndBE(unittest.TestCase):
    """Ticket 03: Two-Tier Scale-Out & Breakeven Relocation."""

    def setUp(self):
        import tempfile
        import os
        from scripts.webhook_bridge import create_app
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_trades_scaleout.db")
        self.secret_token = "TEST_SECRET_TOKEN_789"
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
            account_balance=10000.0,
            risk_pct=0.01,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret_token}"}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_order_filled_and_tp1_partial_close_and_be(self):
        # 1. Place limit
        setup_payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_201",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
        }
        res_setup = self.client.post("/webhook/tradingview", json=setup_payload, headers=self.headers)
        self.assertEqual(res_setup.status_code, 200)
        self.assertEqual(res_setup.json()["status"], "success")

        # 2. Order Filled
        fill_payload = {
            "event": "ORDER_FILLED",
            "order_id": "XAUUSD_201",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "entry": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
        }
        res_fill = self.client.post("/webhook/tradingview", json=fill_payload, headers=self.headers)
        self.assertEqual(res_fill.status_code, 200)
        data_fill = res_fill.json()
        self.assertEqual(data_fill["status"], "success")
        self.assertEqual(data_fill["action"], "ORDER_RECORDED")

        # 3. TP1 Hit & Move BE (50% partial close + SL to BE)
        tp1_payload = {
            "event": "TP1_HIT_MOVE_BE",
            "order_id": "XAUUSD_201",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "action": "PARTIAL_CLOSE",
            "close_percent": 50,
            "entry": 4050.00,
            "new_sl": 4050.10,
        }
        res_tp1 = self.client.post("/webhook/tradingview", json=tp1_payload, headers=self.headers)
        self.assertEqual(res_tp1.status_code, 200)
        data_tp1 = res_tp1.json()
        self.assertEqual(data_tp1["status"], "success")
        self.assertEqual(data_tp1["action"], "PARTIAL_CLOSE_AND_BE_MOVED")
        self.assertEqual(data_tp1["new_sl"], 4050.10)


class TestWebhookBridgeCancellationAndClosing(unittest.TestCase):
    """Ticket 04: Order Cancellation & Telegram Lifecycle Alerts."""

    def setUp(self):
        import tempfile
        import os
        from scripts.webhook_bridge import create_app
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_trades_cancel.db")
        self.secret_token = "TEST_SECRET_TOKEN_999"
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
            account_balance=10000.0,
            risk_pct=0.01,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret_token}"}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_order_canceled_ttl_expiration(self):
        # 1. Setup pending limit
        setup_payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_301",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
        }
        res_setup = self.client.post("/webhook/tradingview", json=setup_payload, headers=self.headers)
        self.assertEqual(res_setup.status_code, 200)

        # 2. Cancel order
        cancel_payload = {
            "event": "ORDER_CANCELED",
            "order_id": "XAUUSD_301",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "reason": "TTL_EXPIRED (4 bars elapsed)",
        }
        res_cancel = self.client.post("/webhook/tradingview", json=cancel_payload, headers=self.headers)
        self.assertEqual(res_cancel.status_code, 200)
        data_cancel = res_cancel.json()
        self.assertEqual(data_cancel["status"], "success")
        self.assertEqual(data_cancel["action"], "ORDER_CANCELED")
        self.assertIn("TTL_EXPIRED", data_cancel["reason"])

    def test_trade_closed_finalization(self):
        close_payload = {
            "event": "TRADE_CLOSED",
            "order_id": "XAUUSD_302",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "reason": "FULL TP2 HIT (+2.5R) 🎯",
        }
        res_close = self.client.post("/webhook/tradingview", json=close_payload, headers=self.headers)
        self.assertEqual(res_close.status_code, 200)
        data_close = res_close.json()
        self.assertEqual(data_close["status"], "success")
        self.assertEqual(data_close["action"], "TRADE_CLOSED")


class TestWebhookBridgeRiskShield(unittest.TestCase):
    """Ticket 05: Circuit Breaker, News Blackout & Rollover Shield."""

    def setUp(self):
        import tempfile
        import os
        from scripts.webhook_bridge import create_app
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_trades_shield.db")
        self.secret_token = "TEST_SECRET_TOKEN_SHIELD"
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
            account_balance=10000.0,
            risk_pct=0.01,
            max_daily_losses=2,
            rollover_hour_utc=20,
            rollover_minute_utc=55,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret_token}"}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_circuit_breaker_halts_after_2_daily_losses(self):
        # 1. Simulate 2 consecutive loss trades today in SQLite
        from scripts.smc.mt5_adapter import SMCExecutionAdapter
        adapter = SMCExecutionAdapter(dry_run=True, db_path=self.db_path)
        adapter.log_lifecycle_event(event_type="TRADE_CLOSED", pnl_dollar=-100.0, pnl_r=-1.0, reason="SL Hit 1")
        adapter.log_lifecycle_event(event_type="TRADE_CLOSED", pnl_dollar=-100.0, pnl_r=-1.0, reason="SL Hit 2")

        # 2. Try to place new setup
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_401",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
            "time": "2026-09-14 14:00:00",
        }
        res = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "rejected")
        self.assertIn("Circuit Breaker", data["reason"])

    def test_rollover_flat_rejects_late_setups(self):
        # Time at 21:15 UTC (after 20:55 rollover cutoff)
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_402",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
            "time": "2026-09-14 21:15:00",
        }
        res = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "rejected")
        self.assertIn("Rollover", data["reason"])


if __name__ == "__main__":
    unittest.main()




