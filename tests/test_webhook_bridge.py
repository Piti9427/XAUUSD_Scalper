import unittest
from unittest.mock import Mock
from fastapi.testclient import TestClient


class TestWebhookBridgeAuth(unittest.TestCase):
    """Ticket 01: Webhook Ingestion Skeleton & Token Authentication."""

    def setUp(self):
        from scripts.webhook_bridge import create_app
        self.secret_token = "TEST_SECRET_TOKEN_123"
        self.app = create_app(auth_token=self.secret_token, dry_run=True)
        self.client = TestClient(self.app)

    def tearDown(self):
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()

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
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()
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

    def test_broker_rejection_does_not_claim_placement_or_send_card(self):
        from scripts.smc.mt5_adapter import ExecutionResult
        notifier = Mock(enabled=True)
        payload = {
            "event": "SETUP_PENDING", "order_id": "REJECTED_1",
            "symbol": "XAUUSD", "dir": "BUY", "type": "SMC_PRIME",
            "limit": 4050.0, "sl": 4045.0, "tp1": 4055.0,
            "tp2": 4062.5,
        }
        from scripts.webhook_bridge import create_app
        app = create_app(
            auth_token=self.secret_token, dry_run=True,
            db_path=self.db_path + ".rejected", notifier=notifier,
        )
        app.state.adapter.execute_intent = Mock(
            return_value=ExecutionResult(False, None, "broker rejected")
        )
        try:
            client = TestClient(app)
            response = client.post("/webhook/tradingview", json=payload, headers=self.headers)
            self.assertEqual(response.json()["status"], "rejected")
            notifier.send_message.assert_not_called()
        finally:
            app.state.adapter.close()

    def test_live_setup_without_cost_model_is_rejected_before_broker(self):
        self.app.state.adapter.dry_run = False
        self.app.state.adapter.get_account_equity = Mock(return_value=6000.0)
        self.app.state.adapter.get_risk_snapshot = Mock(return_value={
            "balance": 10000.0, "equity": 6000.0,
            "min_lot": 0.01, "max_lot": 5.0,
            "lot_step": 0.01, "contract_size": 100.0,
        })
        self.app.state.adapter.execute_intent = Mock()
        response = self.client.post(
            "/webhook/tradingview",
            json={"event": "SETUP_PENDING", "order_id": "COST_MISSING_1",
                  "symbol": "XAUUSD", "dir": "BUY", "type": "SMC_PRIME",
                  "limit": 4050.0, "sl": 4045.0,
                  "tp1": 4055.0, "tp2": 4062.5},
            headers=self.headers,
        )
        self.assertEqual(response.json()["status"], "rejected")
        self.app.state.adapter.execute_intent.assert_not_called()

    def test_live_setup_uses_broker_equity_volume_and_cost_model(self):
        from scripts.webhook_bridge import create_app
        from scripts.smc.mt5_adapter import ExecutionResult
        app = create_app(
            auth_token=self.secret_token, dry_run=True,
            db_path=self.db_path + ".live-risk",
            account_balance=10000.0, risk_pct=0.01,
            commission_per_lot=10.0, slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.get_risk_snapshot = Mock(return_value={
            "balance": 10000.0, "equity": 6000.0,
            "min_lot": 0.01, "max_lot": 5.0,
            "lot_step": 0.01, "contract_size": 100.0,
        })
        app.state.adapter.get_open_exposure = Mock(return_value=[])
        app.state.adapter.execute_intent = Mock(
            return_value=ExecutionResult(True, 42, "accepted")
        )
        try:
            response = TestClient(app).post(
                "/webhook/tradingview",
                json={"event": "SETUP_PENDING", "order_id": "LIVE_RISK_1",
                      "symbol": "XAUUSD", "dir": "BUY", "type": "SMC_PRIME",
                      "limit": 4050.0, "sl": 4045.0,
                      "tp1": 4055.0, "tp2": 4062.5},
                headers=self.headers,
            )
            self.assertEqual(response.json()["status"], "success")
            self.assertEqual(response.json()["lot_size"], 0.10)
            self.assertEqual(app.state.adapter.execute_intent.call_args.args[0].lot_size, 0.10)
        finally:
            app.state.adapter.close()

    def test_live_setup_blocks_when_broker_has_existing_exposure(self):
        from scripts.webhook_bridge import create_app
        from scripts.smc.mt5_adapter import ExecutionResult
        app = create_app(
            auth_token=self.secret_token, dry_run=True,
            db_path=self.db_path + ".exposure", risk_pct=0.01,
            commission_per_lot=10.0, slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.get_risk_snapshot = Mock(return_value={
            "balance": 10000.0, "equity": 6000.0,
            "min_lot": 0.01, "max_lot": 5.0,
            "lot_step": 0.01, "contract_size": 100.0,
        })
        app.state.adapter.get_open_exposure = Mock(return_value=["unknown-position"])
        app.state.adapter.execute_intent = Mock(
            return_value=ExecutionResult(True, 42, "accepted")
        )
        try:
            response = TestClient(app).post(
                "/webhook/tradingview",
                json={"event": "SETUP_PENDING", "order_id": "EXPOSURE_1",
                      "symbol": "XAUUSD", "dir": "BUY", "type": "SMC_PRIME",
                      "limit": 4050.0, "sl": 4045.0,
                      "tp1": 4055.0, "tp2": 4062.5},
                headers=self.headers,
            )
            self.assertEqual(response.json()["status"], "rejected")
            app.state.adapter.execute_intent.assert_not_called()
        finally:
            app.state.adapter.close()

    def test_live_setup_claim_blocks_second_order_across_app_restart(self):
        from scripts.webhook_bridge import create_app
        from scripts.smc.mt5_adapter import ExecutionResult

        def make_app():
            app = create_app(
                auth_token=self.secret_token, dry_run=True,
                db_path=self.db_path + ".claims", risk_pct=0.01,
                commission_per_lot=10.0, slippage_allowance=0.5,
            )
            app.state.adapter.dry_run = False
            app.state.adapter.get_risk_snapshot = Mock(return_value={
                "balance": 10000.0, "equity": 6000.0,
                "min_lot": 0.01, "max_lot": 5.0,
                "lot_step": 0.01, "contract_size": 100.0,
            })
            app.state.adapter.get_open_exposure = Mock(return_value=[])
            app.state.adapter.execute_intent = Mock(
                return_value=ExecutionResult(True, 42, "accepted")
            )
            return app

        def payload(order_id):
            return {"event": "SETUP_PENDING", "order_id": order_id,
                    "symbol": "XAUUSD", "dir": "BUY", "type": "SMC_PRIME",
                    "limit": 4050.0, "sl": 4045.0,
                    "tp1": 4055.0, "tp2": 4062.5}

        first = make_app()
        try:
            first_response = TestClient(first).post(
                "/webhook/tradingview", json=payload("CLAIM_A"), headers=self.headers
            )
            self.assertEqual(first_response.json()["status"], "success")
            receipt_id = first_response.json()["receipt_id"]
        finally:
            first.state.adapter.close()

        second = make_app()
        try:
            duplicate_response = TestClient(second).post(
                "/webhook/tradingview", json=payload("CLAIM_A"), headers=self.headers
            )
            self.assertEqual(duplicate_response.json()["status"], "ignored_duplicate")
            self.assertEqual(duplicate_response.json()["receipt_id"], receipt_id)
            changed = payload("CLAIM_A")
            changed["sl"] = 4044.0
            conflict_response = TestClient(second).post(
                "/webhook/tradingview", json=changed, headers=self.headers
            )
            self.assertEqual(conflict_response.json()["status"], "rejected")
            second_response = TestClient(second).post(
                "/webhook/tradingview", json=payload("CLAIM_B"), headers=self.headers
            )
            self.assertEqual(second_response.json()["status"], "rejected")
            second.state.adapter.execute_intent.assert_not_called()
        finally:
            second.state.adapter.close()

    def test_live_confirmed_cancel_releases_claim_for_next_setup(self):
        from scripts.webhook_bridge import create_app
        from scripts.smc.mt5_adapter import ExecutionResult
        app = create_app(
            auth_token=self.secret_token, dry_run=True,
            db_path=self.db_path + ".release", risk_pct=0.01,
            commission_per_lot=10.0, slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.get_risk_snapshot = Mock(return_value={
            "balance": 10000.0, "equity": 6000.0,
            "min_lot": 0.01, "max_lot": 5.0,
            "lot_step": 0.01, "contract_size": 100.0,
        })
        app.state.adapter.get_open_exposure = Mock(return_value=[])
        app.state.adapter.execute_intent = Mock(
            return_value=ExecutionResult(True, 42, "accepted")
        )
        client = TestClient(app)
        def setup(oid):
            return client.post(
                "/webhook/tradingview",
                json={"event": "SETUP_PENDING", "order_id": oid,
                      "symbol": "XAUUSD", "dir": "BUY", "type": "SMC_PRIME",
                      "limit": 4050.0, "sl": 4045.0,
                      "tp1": 4055.0, "tp2": 4062.5},
                headers=self.headers,
            )
        try:
            self.assertEqual(setup("RELEASE_A").json()["status"], "success")
            cancel = client.post(
                "/webhook/tradingview",
                json={"event": "ORDER_CANCELED", "order_id": "RELEASE_A"},
                headers=self.headers,
            )
            self.assertEqual(cancel.json()["status"], "success")
            self.assertEqual(setup("RELEASE_B").json()["status"], "success")
            close = client.post(
                "/webhook/tradingview",
                json={"event": "TRADE_CLOSED", "order_id": "RELEASE_B",
                      "reason": "manual close", "pnl_dollar": 0.0},
                headers=self.headers,
            )
            self.assertEqual(close.json()["status"], "success")
            self.assertEqual(setup("RELEASE_C").json()["status"], "success")
        finally:
            app.state.adapter.close()

    def test_live_order_filled_rejects_when_broker_has_no_matching_position(self):
        from scripts.webhook_bridge import create_app
        app = create_app(
            auth_token=self.secret_token, dry_run=True,
            db_path=self.db_path + ".live_fill_reject", risk_pct=0.01,
            commission_per_lot=10.0, slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.get_matching_position = Mock(return_value=None)
        app.state.adapter.log_lifecycle_event = Mock()
        try:
            client = TestClient(app)
            fill_payload = {
                "event": "ORDER_FILLED",
                "order_id": "XAUUSD_PHANTOM",
                "symbol": "XAUUSD",
                "dir": "BUY",
                "type": "SMC_PRIME",
                "entry": 4050.00,
                "sl": 4045.00,
                "tp1": 4055.00,
                "tp2": 4062.50,
            }
            res = client.post("/webhook/tradingview", json=fill_payload, headers=self.headers)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["status"], "rejected")
            self.assertIn("Broker has no open position", res.json()["reason"])
            app.state.adapter.log_lifecycle_event.assert_not_called()
        finally:
            app.state.adapter.close()

    def test_live_order_filled_uses_broker_position_fill_price_and_ticket(self):
        from types import SimpleNamespace
        from scripts.webhook_bridge import create_app
        app = create_app(
            auth_token=self.secret_token, dry_run=True,
            db_path=self.db_path + ".live_fill_match", risk_pct=0.01,
            commission_per_lot=10.0, slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        broker_pos = SimpleNamespace(ticket=999888, price_open=4049.50, volume=0.02)
        app.state.adapter.get_matching_position = Mock(return_value=broker_pos)
        app.state.adapter.log_lifecycle_event = Mock()
        try:
            client = TestClient(app)
            fill_payload = {
                "event": "ORDER_FILLED",
                "order_id": "XAUUSD_REAL_FILL",
                "symbol": "XAUUSD",
                "dir": "BUY",
                "type": "SMC_PRIME",
                "entry": 4050.00,
                "sl": 4045.00,
                "tp1": 4055.00,
                "tp2": 4062.50,
            }
            res = client.post("/webhook/tradingview", json=fill_payload, headers=self.headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["entry"], 4049.50)
            self.assertEqual(data["ticket"], 999888)
            app.state.adapter.log_lifecycle_event.assert_called_once_with(
                event_type="ORDER_FILLED",
                direction="BUY",
                entry_price=4049.50,
                sl_price=4045.00,
                tp_price=4062.50,
                order_id="XAUUSD_REAL_FILL",
                ticket=999888,
                reason="TradingView Alert Fill Confirmation (Broker Verified)",
            )
        finally:
            app.state.adapter.close()

    def test_live_trade_closed_uses_broker_deal_pnl_instead_of_payload(self):
        from scripts.webhook_bridge import create_app
        from scripts.smc.mt5_adapter import ExecutionResult
        app = create_app(
            auth_token=self.secret_token, dry_run=True,
            db_path=self.db_path + ".live_trade_closed", risk_pct=0.01,
            commission_per_lot=10.0, slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.execute_intent = Mock(return_value=ExecutionResult(True, 999888, "Closed on broker"))
        app.state.adapter.get_open_exposure = Mock(return_value=[])
        app.state.adapter.get_realized_pnl_for_order = Mock(return_value=-150.0)
        app.state.adapter.log_lifecycle_event = Mock()
        try:
            client = TestClient(app)
            close_payload = {
                "event": "TRADE_CLOSED",
                "order_id": "XAUUSD_REAL_CLOSE",
                "symbol": "XAUUSD",
                "reason": "SL_HIT",
                "pnl_dollar": 50.0,
                "pnl_r": 1.0,
            }
            res = client.post("/webhook/tradingview", json=close_payload, headers=self.headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["pnl_dollar"], -150.0)
            app.state.adapter.log_lifecycle_event.assert_called_once()
            call_kwargs = app.state.adapter.log_lifecycle_event.call_args.kwargs
            self.assertEqual(call_kwargs["pnl_dollar"], -150.0)
        finally:
            app.state.adapter.close()

    def test_live_setup_broker_rejection_frees_inbox_for_subsequent_setup(self):
        from scripts.webhook_bridge import create_app
        from scripts.smc.mt5_adapter import ExecutionResult
        app = create_app(
            auth_token=self.secret_token, dry_run=True,
            db_path=self.db_path + ".live_broker_reject", risk_pct=0.01,
            commission_per_lot=10.0, slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.get_risk_snapshot = Mock(return_value={
            "balance": 10000.0, "equity": 10000.0,
            "min_lot": 0.01, "max_lot": 5.0,
            "lot_step": 0.01, "contract_size": 100.0,
        })
        app.state.adapter.get_open_exposure = Mock(return_value=[])
        app.state.adapter.execute_intent = Mock(side_effect=[
            ExecutionResult(False, None, "Margin exceeded"),
            ExecutionResult(True, 12345, "Accepted"),
        ])
        def payload(oid):
            return {
                "event": "SETUP_PENDING", "order_id": oid,
                "symbol": "XAUUSD", "dir": "BUY", "type": "SMC_PRIME",
                "limit": 4050.0, "sl": 4045.0, "tp1": 4055.0, "tp2": 4062.5
            }
        try:
            client = TestClient(app)
            res1 = client.post("/webhook/tradingview", json=payload("ORDER_REJECT_A"), headers=self.headers)
            self.assertEqual(res1.status_code, 200)
            self.assertEqual(res1.json()["status"], "rejected")

            # Second setup must NOT be blocked with 'busy'
            res2 = client.post("/webhook/tradingview", json=payload("ORDER_REJECT_B"), headers=self.headers)
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(res2.json()["status"], "success")
        finally:
            app.state.adapter.close()

    def test_live_setup_timeout_or_error_marks_uncertain_and_blocks_subsequent(self):
        from scripts.webhook_bridge import create_app
        app = create_app(
            auth_token=self.secret_token, dry_run=True,
            db_path=self.db_path + ".live_timeout", risk_pct=0.01,
            commission_per_lot=10.0, slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.get_risk_snapshot = Mock(return_value={
            "balance": 10000.0, "equity": 10000.0,
            "min_lot": 0.01, "max_lot": 5.0,
            "lot_step": 0.01, "contract_size": 100.0,
        })
        app.state.adapter.get_open_exposure = Mock(return_value=[])
        app.state.adapter.execute_intent = Mock(side_effect=TimeoutError("Broker socket timed out"))
        def payload(oid):
            return {
                "event": "SETUP_PENDING", "order_id": oid,
                "symbol": "XAUUSD", "dir": "BUY", "type": "SMC_PRIME",
                "limit": 4050.0, "sl": 4045.0, "tp1": 4055.0, "tp2": 4062.5
            }
        try:
            client = TestClient(app)
            res1 = client.post("/webhook/tradingview", json=payload("ORDER_TIMEOUT_1"), headers=self.headers)
            self.assertEqual(res1.status_code, 200)
            self.assertEqual(res1.json()["status"], "uncertain")

            status_info = app.state.adapter.get_setup_status("ORDER_TIMEOUT_1")
            self.assertEqual(status_info["status"], "uncertain")

            # Subsequent setup must be rejected because an uncertain claim is active
            res2 = client.post("/webhook/tradingview", json=payload("ORDER_TIMEOUT_2"), headers=self.headers)
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(res2.json()["status"], "rejected")
            self.assertIn("broker reconciliation required", res2.json()["reason"].lower())
        finally:
            app.state.adapter.close()

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
        try:
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
        finally:
            if hasattr(small_app.state, "adapter") and small_app.state.adapter:
                small_app.state.adapter.close()


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
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()
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

    def test_rejected_partial_requests_full_close_without_be(self):
        from scripts.smc.mt5_adapter import ExecutionResult
        from scripts.smc.types import OrderIntentType
        self.app.state.adapter.execute_intent = Mock(side_effect=[
            ExecutionResult(False, None, "partial rejected"),
            ExecutionResult(True, 42, "closed"),
        ])
        response = self.client.post(
            "/webhook/tradingview",
            json={"event": "TP1_HIT_MOVE_BE", "order_id": "TP1_REJECTED_1",
                  "entry": 4050.0, "new_sl": 4050.1},
            headers=self.headers,
        )
        calls = self.app.state.adapter.execute_intent.call_args_list
        self.assertEqual([call.args[0].intent_type for call in calls], [
            OrderIntentType.PARTIAL_CLOSE, OrderIntentType.CLOSE_MARKET,
        ])
        self.assertEqual(response.json()["status"], "closed_for_safety")

    def test_rejected_be_after_partial_requests_runner_close(self):
        from scripts.smc.mt5_adapter import ExecutionResult
        from scripts.smc.types import OrderIntentType
        self.app.state.adapter.execute_intent = Mock(side_effect=[
            ExecutionResult(True, 42, "partial done"),
            ExecutionResult(False, 42, "BE rejected"),
            ExecutionResult(True, 42, "runner closed"),
        ])
        response = self.client.post(
            "/webhook/tradingview",
            json={"event": "TP1_HIT_MOVE_BE", "order_id": "BE_REJECTED_1",
                  "entry": 4050.0, "new_sl": 4050.1},
            headers=self.headers,
        )
        calls = self.app.state.adapter.execute_intent.call_args_list
        self.assertEqual([call.args[0].intent_type for call in calls], [
            OrderIntentType.PARTIAL_CLOSE, OrderIntentType.MOVE_SL_TO_BE,
            OrderIntentType.CLOSE_MARKET,
        ])
        self.assertEqual(response.json()["status"], "closed_for_safety")


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
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()
        self.temp_dir.cleanup()

    def test_rejected_close_does_not_record_trade_closed(self):
        from unittest.mock import Mock
        from scripts.smc.mt5_adapter import ExecutionResult
        self.app.state.adapter.execute_intent = Mock(
            return_value=ExecutionResult(False, None, "close rejected")
        )
        response = self.client.post(
            "/webhook/tradingview",
            json={"event": "TRADE_CLOSED", "order_id": "CLOSE_REJECTED_1",
                  "reason": "STOP LOSS HIT", "pnl_dollar": -50.0},
            headers=self.headers,
        )
        self.assertEqual(response.json()["status"], "rejected")
        self.assertFalse(any(
            row["event_type"] == "TRADE_CLOSED"
            for row in self.app.state.adapter.get_lifecycle_logs()
        ))

    def test_rejected_cancel_does_not_record_order_canceled(self):
        from scripts.smc.mt5_adapter import ExecutionResult
        self.app.state.adapter.execute_intent = Mock(
            return_value=ExecutionResult(False, None, "cancel rejected")
        )
        response = self.client.post(
            "/webhook/tradingview",
            json={"event": "ORDER_CANCELED", "order_id": "CANCEL_REJECTED_1"},
            headers=self.headers,
        )
        self.assertEqual(response.json()["status"], "rejected")
        self.assertFalse(any(
            row["event_type"] == "ORDER_CANCELED"
            for row in self.app.state.adapter.get_lifecycle_logs()
        ))

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
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()
        self.temp_dir.cleanup()

    def test_circuit_breaker_halts_after_2_daily_losses(self):
        # 1. Simulate 2 consecutive loss trades today in SQLite
        from scripts.smc.mt5_adapter import SMCExecutionAdapter
        adapter = SMCExecutionAdapter(dry_run=True, db_path=self.db_path)
        try:
            adapter.log_lifecycle_event(event_type="TRADE_CLOSED", pnl_dollar=-100.0, pnl_r=-1.0, reason="SL Hit 1")
            adapter.log_lifecycle_event(event_type="TRADE_CLOSED", pnl_dollar=-100.0, pnl_r=-1.0, reason="SL Hit 2")
        finally:
            adapter.close()

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


class TestWebhookBridgeAsyncPatterns(unittest.TestCase):
    """Verifies Async Python Patterns (BackgroundTasks, In-Memory Idempotency, Health Telemetry)."""

    def setUp(self):
        from unittest.mock import MagicMock
        from scripts.webhook_bridge import create_app

        self.mock_notifier = MagicMock()
        self.mock_notifier.enabled = True
        self.secret_token = "ASYNC_TEST_TOKEN_789"
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=":memory:",
            account_balance=10000.0,
            risk_pct=0.01,
            notifier=self.mock_notifier,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret_token}"}

    def tearDown(self):
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()

    def test_telegram_background_task_dispatched(self):
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_ASYNC_01",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
            "time": "2026-09-14 10:00:00",
        }
        res = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")
        # Ensure Telegram message was dispatched via BackgroundTasks
        self.mock_notifier.send_message.assert_called_once()
        card_content = self.mock_notifier.send_message.call_args[0][0]
        self.assertIn("ORDER ACCEPTED (PENDING)", card_content)
        self.assertNotIn("ORDER FILLED", card_content)

    def test_two_tier_idempotency_fast_path(self):
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_ASYNC_02",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
            "time": "2026-09-14 10:00:00",
        }
        res1 = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["status"], "success")

        # Second delivery must hit in-memory cache and be rejected as duplicate
        res2 = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["status"], "ignored_duplicate")

    def test_health_check_async_telemetry(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("mt5_connected", data)
        self.assertIn("account_equity", data)
        self.assertIn("daily_realized_losses", data)
        self.assertIn("circuit_breaker_tripped", data)
        self.assertFalse(data["circuit_breaker_tripped"])


class TestCodeReviewHardeningFixes(unittest.TestCase):
    """Verifies F2 (ORDER_FILLED inbox update), F3 (TRADE_CLOSED normal TP2 close), and F4 (configurable R-multiples)."""

    def setUp(self):
        import tempfile
        import os
        from scripts.webhook_bridge import create_app
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_fixes.db")
        self.secret_token = "TEST_FIXES_SECRET"
        self.headers = {"Authorization": f"Bearer {self.secret_token}"}

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_f2_order_filled_updates_setup_inbox_to_accepted_with_ticket(self):
        from types import SimpleNamespace
        from scripts.webhook_bridge import create_app
        app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
        )
        try:
            # Seed inbox with claimed setup
            app.state.adapter.claim_setup({"order_id": "SETUP_F2", "limit": 4050.0, "sl": 4045.0})
            inbox_before = app.state.adapter.get_setup_status("SETUP_F2")
            self.assertEqual(inbox_before["status"], "claimed")
            self.assertIsNone(inbox_before["ticket"])

            app.state.adapter.dry_run = False
            broker_pos = SimpleNamespace(ticket=777888, price_open=4050.0, volume=0.10)
            app.state.adapter.get_matching_position = Mock(return_value=broker_pos)

            client = TestClient(app)
            fill_payload = {
                "event": "ORDER_FILLED",
                "order_id": "SETUP_F2",
                "symbol": "XAUUSD",
                "dir": "BUY",
                "entry": 4050.00,
                "sl": 4045.00,
                "tp1": 4055.00,
                "tp2": 4062.50,
            }
            res = client.post("/webhook/tradingview", json=fill_payload, headers=self.headers)
            self.assertEqual(res.status_code, 200)

            inbox_after = app.state.adapter.get_setup_status("SETUP_F2")
            self.assertEqual(inbox_after["status"], "accepted")
            self.assertEqual(inbox_after["ticket"], 777888)
        finally:
            app.state.adapter.close()

    def test_f3_trade_closed_finalizes_when_broker_position_already_closed_by_tp(self):
        from scripts.smc.mt5_adapter import ExecutionResult
        from scripts.webhook_bridge import create_app
        app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
        )
        try:
            # Simulate broker returning 'Target position not found' on CLOSE_MARKET (e.g. TP2 already hit)
            app.state.adapter.execute_intent = Mock(
                return_value=ExecutionResult(False, None, "Target position not found")
            )
            client = TestClient(app)
            payload = {
                "event": "TRADE_CLOSED",
                "order_id": "TP2_ALREADY_CLOSED",
                "symbol": "XAUUSD",
                "reason": "TP2_RUNNER_HIT",
                "dir": "BUY",
                "exit_price": 4062.50,
            }
            res = client.post("/webhook/tradingview", json=payload, headers=self.headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["action"], "TRADE_CLOSED")
            self.assertEqual(data["pnl_r"], 2.5)

            # Confirm lifecycle log was written
            logs = app.state.adapter.get_lifecycle_logs()
            tc_logs = [log for log in logs if log["event_type"] == "TRADE_CLOSED" and log["order_id"] == "TP2_ALREADY_CLOSED"]
            self.assertEqual(len(tc_logs), 1)
        finally:
            app.state.adapter.close()

    def test_f4_custom_r_multiples_configured_via_create_app(self):
        from scripts.webhook_bridge import create_app
        app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
            account_balance=10000.0,
            risk_pct=0.01,
            tp_r=3.5,
            partial_tp_r=1.5,
        )
        try:
            client = TestClient(app)
            # 1. Test TP2 with tp_r=3.5
            res_tp2 = client.post("/webhook/tradingview", json={
                "event": "TRADE_CLOSED",
                "order_id": "ORDER_TP2_CUSTOM",
                "symbol": "XAUUSD",
                "reason": "TP2_RUNNER_HIT",
            }, headers=self.headers)
            self.assertEqual(res_tp2.status_code, 200)
            data_tp2 = res_tp2.json()
            self.assertEqual(data_tp2["pnl_r"], 3.5)
            self.assertEqual(data_tp2["pnl_dollar"], 350.0)

            # 2. Test TP1 with partial_tp_r=1.5
            res_tp1 = client.post("/webhook/tradingview", json={
                "event": "TRADE_CLOSED",
                "order_id": "ORDER_TP1_CUSTOM",
                "symbol": "XAUUSD",
                "reason": "TP1_SCALE_OUT",
            }, headers=self.headers)
            self.assertEqual(res_tp1.status_code, 200)
            data_tp1 = res_tp1.json()
            self.assertEqual(data_tp1["pnl_r"], 1.5)
            self.assertEqual(data_tp1["pnl_dollar"], 150.0)
        finally:
            app.state.adapter.close()


class TestWebhookFoundationGates(unittest.TestCase):
    def setUp(self):
        import tempfile
        import os
        from scripts.webhook_bridge import create_app
        from scripts.smc.broker_identity import BrokerIdentityReport
        from scripts.smc.risk_halt import new_risk_halt_state, save_risk_halt_state

        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_trades.db")
        self.halt_path = os.path.join(self.temp_dir.name, "risk_halt.json")
        halted = new_risk_halt_state(500.0)
        halted.drawdown_halt = True
        save_risk_halt_state(__import__("pathlib").Path(self.halt_path), halted)
        self.secret_token = "TEST_SECRET_FOUNDATION"
        self.failing_identity = BrokerIdentityReport(
            ok=False,
            broker_server=None,
            account_login=None,
            currency=None,
            trade_mode=None,
            symbol=None,
            reasons=("demo_required",),
        )
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
            account_balance=500.0,
            risk_halt_path=self.halt_path,
            identity_gate=lambda: self.failing_identity,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret_token}"}

    def tearDown(self):
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()
        self.temp_dir.cleanup()

    def test_risk_halt_blocks_setup_pending(self):
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_HALT_1",
            "symbol": "XAUUSD",
            "dir": "BUY",
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
        self.assertIn("risk halt", data["reason"].lower())

    def test_identity_gate_blocks_when_halt_cleared(self):
        from scripts.smc.risk_halt import new_risk_halt_state, save_risk_halt_state
        from pathlib import Path

        save_risk_halt_state(Path(self.halt_path), new_risk_halt_state(500.0))
        # Recreate app so loaded halt is clear; keep failing identity.
        from scripts.webhook_bridge import create_app
        self.app.state.adapter.close()
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
            account_balance=500.0,
            risk_halt_path=self.halt_path,
            identity_gate=lambda: self.failing_identity,
        )
        self.client = TestClient(self.app)
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_ID_1",
            "symbol": "XAUUSD",
            "dir": "BUY",
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
        self.assertIn("identity", data["reason"].lower())

    def test_two_net_losses_trip_risk_halt_on_next_setup(self):
        from scripts.smc.broker_identity import BrokerIdentityReport
        from scripts.smc.risk_halt import new_risk_halt_state, save_risk_halt_state, load_risk_halt_state
        from scripts.webhook_bridge import create_app
        from pathlib import Path
        import os

        ok_identity = BrokerIdentityReport(
            ok=True,
            broker_server="Exness-MT5Trial",
            account_login=1,
            currency="USD",
            trade_mode=0,
            symbol="XAUUSD",
            reasons=(),
        )
        save_risk_halt_state(Path(self.halt_path), new_risk_halt_state(500.0))
        self.app.state.adapter.close()
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
            account_balance=500.0,
            risk_halt_path=self.halt_path,
            identity_gate=lambda: ok_identity,
            max_daily_losses=99,  # isolate foundation halt from ADR-011 circuit
        )
        self.client = TestClient(self.app)

        for oid in ("LOSS_1", "LOSS_2"):
            res = self.client.post(
                "/webhook/tradingview",
                json={
                    "event": "TRADE_CLOSED",
                    "order_id": oid,
                    "symbol": "XAUUSD",
                    "reason": "SL_HIT",
                    "pnl_r": -1.0,
                    "pnl_dollar": -2.5,
                    "time": "2026-09-14 14:00:00",
                },
                headers=self.headers,
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["status"], "success")

        halted = load_risk_halt_state(Path(self.halt_path))
        self.assertIsNotNone(halted)
        self.assertGreaterEqual(halted.net_losing_trades_today, 2)
        self.assertTrue(halted.halted)

        setup = self.client.post(
            "/webhook/tradingview",
            json={
                "event": "SETUP_PENDING",
                "order_id": "AFTER_TWO_LOSSES",
                "symbol": "XAUUSD",
                "dir": "BUY",
                "limit": 4050.00,
                "sl": 4045.00,
                "tp1": 4055.00,
                "tp2": 4062.50,
                "time": "2026-09-14 15:00:00",
            },
            headers=self.headers,
        )
        self.assertEqual(setup.status_code, 200)
        data = setup.json()
        self.assertEqual(data["status"], "rejected")
        self.assertIn("risk halt", data["reason"].lower())

    def test_risk_halt_reports_flatten_actions_field(self):
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_HALT_FLAT",
            "symbol": "XAUUSD",
            "dir": "BUY",
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
        self.assertIn("flatten_actions", data)
        self.assertIsInstance(data["flatten_actions"], list)

    def test_incomplete_broker_equity_blocks_without_resetting_marks(self):
        from scripts.smc.broker_identity import BrokerIdentityReport
        from scripts.smc.risk_halt import new_risk_halt_state, save_risk_halt_state, load_risk_halt_state
        from scripts.webhook_bridge import create_app
        from pathlib import Path
        from unittest.mock import Mock

        ok_identity = BrokerIdentityReport(
            ok=True,
            broker_server="Exness-MT5Trial",
            account_login=1,
            currency="USD",
            trade_mode=0,
            symbol="XAUUSD",
            reasons=(),
        )
        state = new_risk_halt_state(500.0)
        state.high_water_equity = 520.0
        state.net_losing_trades_today = 1
        save_risk_halt_state(Path(self.halt_path), state)

        self.app.state.adapter.close()
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
            account_balance=500.0,
            risk_halt_path=self.halt_path,
            identity_gate=lambda: ok_identity,
            max_daily_losses=99,
        )
        # Simulate live path without requiring a real MT5 terminal.
        self.app.state.adapter.dry_run = False
        self.app.state.adapter.connected = True
        self.app.state.adapter.get_account_equity = Mock(return_value=None)
        self.app.state.adapter.get_open_exposure = Mock(return_value=[])
        self.client = TestClient(self.app)

        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_HIST_INCOMPLETE",
            "symbol": "XAUUSD",
            "dir": "BUY",
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
        self.assertIn("history_ready=False", data["reason"])

        restored = load_risk_halt_state(Path(self.halt_path))
        self.assertIsNotNone(restored)
        self.assertEqual(restored.high_water_equity, 520.0)
        self.assertEqual(restored.net_losing_trades_today, 1)
        self.assertFalse(restored.history_ready)


if __name__ == "__main__":
    unittest.main()
