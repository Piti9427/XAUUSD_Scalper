import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

# Wall-clock may be outside London/NY admission windows; bypass for fixture SETUP
# paths. Dedicated test_out_of_session_rejects_setup_pending restores real gate.
_SESSION_PATCHER = patch("scripts.webhook.setup_time_gates.is_in_session", return_value=True)
_SESSION_PATCHER.start()


def tearDownModule():
    _SESSION_PATCHER.stop()


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
            account_balance=10000.0,
            db_path=self.db_path,
            risk_pct=0.01,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret_token}"}

    def tearDown(self):
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()
        self.temp_dir.cleanup()

    def test_setup_pending_valid_buy_limit(self):
        from datetime import datetime, timezone

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
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
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
            "event": "SETUP_PENDING",
            "order_id": "REJECTED_1",
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.0,
            "sl": 4045.0,
            "tp1": 4055.0,
            "tp2": 4062.5,
        }
        from scripts.webhook_bridge import create_app

        app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path + ".rejected",
            notifier=notifier,
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
        self.app.state.adapter.get_risk_snapshot = Mock(
            return_value={
                "balance": 10000.0,
                "equity": 6000.0,
                "min_lot": 0.01,
                "max_lot": 5.0,
                "lot_step": 0.01,
                "contract_size": 100.0,
                "margin_free": 5500.0,
                "trade_allowed": 1.0,
                "point": 0.01,
                "stops_level": 0.0,
                "freeze_level": 0.0,
            }
        )
        self.app.state.adapter.execute_intent = Mock()
        response = self.client.post(
            "/webhook/tradingview",
            json={
                "event": "SETUP_PENDING",
                "order_id": "COST_MISSING_1",
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": "XAUUSD",
                "dir": "BUY",
                "type": "SMC_PRIME",
                "limit": 4050.0,
                "sl": 4045.0,
                "tp1": 4055.0,
                "tp2": 4062.5,
            },
            headers=self.headers,
        )
        self.assertEqual(response.json()["status"], "rejected")
        self.app.state.adapter.execute_intent.assert_not_called()

    def test_live_setup_uses_broker_equity_volume_and_cost_model(self):
        from scripts.webhook_bridge import create_app
        from scripts.smc.mt5_adapter import ExecutionResult

        app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path + ".live-risk",
            risk_pct=0.01,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.get_risk_snapshot = Mock(
            return_value={
                "balance": 10000.0,
                "equity": 6000.0,
                "min_lot": 0.01,
                "max_lot": 5.0,
                "lot_step": 0.01,
                "contract_size": 100.0,
                "margin_free": 5500.0,
                "trade_allowed": 1.0,
                "point": 0.01,
                "stops_level": 0.0,
                "freeze_level": 0.0,
            }
        )
        app.state.adapter.get_open_exposure = Mock(return_value=[])
        app.state.adapter.execute_intent = Mock(return_value=ExecutionResult(True, 42, "accepted"))
        try:
            response = TestClient(app).post(
                "/webhook/tradingview",
                json={
                    "event": "SETUP_PENDING",
                    "order_id": "LIVE_RISK_1",
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "symbol": "XAUUSD",
                    "dir": "BUY",
                    "type": "SMC_PRIME",
                    "limit": 4050.0,
                    "sl": 4045.0,
                    "tp1": 4055.0,
                    "tp2": 4062.5,
                },
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
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path + ".exposure",
            risk_pct=0.01,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.get_risk_snapshot = Mock(
            return_value={
                "balance": 10000.0,
                "equity": 6000.0,
                "min_lot": 0.01,
                "max_lot": 5.0,
                "lot_step": 0.01,
                "contract_size": 100.0,
                "margin_free": 5500.0,
                "trade_allowed": 1.0,
                "point": 0.01,
                "stops_level": 0.0,
                "freeze_level": 0.0,
            }
        )
        app.state.adapter.get_open_exposure = Mock(return_value=["unknown-position"])
        app.state.adapter.execute_intent = Mock(return_value=ExecutionResult(True, 42, "accepted"))
        try:
            response = TestClient(app).post(
                "/webhook/tradingview",
                json={
                    "event": "SETUP_PENDING",
                    "order_id": "EXPOSURE_1",
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "symbol": "XAUUSD",
                    "dir": "BUY",
                    "type": "SMC_PRIME",
                    "limit": 4050.0,
                    "sl": 4045.0,
                    "tp1": 4055.0,
                    "tp2": 4062.5,
                },
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
                auth_token=self.secret_token,
                dry_run=True,
                account_balance=10000.0,
                db_path=self.db_path + ".claims",
                risk_pct=0.01,
                commission_per_lot=10.0,
                slippage_allowance=0.5,
            )
            app.state.adapter.dry_run = False
            app.state.adapter.get_risk_snapshot = Mock(
                return_value={
                    "balance": 10000.0,
                    "equity": 6000.0,
                    "min_lot": 0.01,
                    "max_lot": 5.0,
                    "lot_step": 0.01,
                    "contract_size": 100.0,
                    "margin_free": 5500.0,
                    "trade_allowed": 1.0,
                    "point": 0.01,
                    "stops_level": 0.0,
                    "freeze_level": 0.0,
                }
            )
            app.state.adapter.get_open_exposure = Mock(return_value=[])
            app.state.adapter.execute_intent = Mock(
                return_value=ExecutionResult(True, 42, "accepted")
            )
            return app

        def payload(order_id):
            return {
                "event": "SETUP_PENDING",
                "order_id": order_id,
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": "XAUUSD",
                "dir": "BUY",
                "type": "SMC_PRIME",
                "limit": 4050.0,
                "sl": 4045.0,
                "tp1": 4055.0,
                "tp2": 4062.5,
            }

        initial_claim = payload("CLAIM_A")
        first = make_app()
        try:
            first_response = TestClient(first).post(
                "/webhook/tradingview", json=initial_claim, headers=self.headers
            )
            self.assertEqual(first_response.json()["status"], "success")
            receipt_id = first_response.json()["receipt_id"]
        finally:
            first.state.adapter.close()

        second = make_app()
        try:
            duplicate_response = TestClient(second).post(
                "/webhook/tradingview", json=dict(initial_claim), headers=self.headers
            )
            self.assertEqual(duplicate_response.json()["status"], "ignored_duplicate")
            self.assertEqual(duplicate_response.json()["receipt_id"], receipt_id)
            changed = dict(initial_claim)
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
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path + ".release",
            risk_pct=0.01,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.get_risk_snapshot = Mock(
            return_value={
                "balance": 10000.0,
                "equity": 6000.0,
                "min_lot": 0.01,
                "max_lot": 5.0,
                "lot_step": 0.01,
                "contract_size": 100.0,
                "margin_free": 5500.0,
                "trade_allowed": 1.0,
                "point": 0.01,
                "stops_level": 0.0,
                "freeze_level": 0.0,
            }
        )
        app.state.adapter.get_open_exposure = Mock(return_value=[])
        app.state.adapter.execute_intent = Mock(return_value=ExecutionResult(True, 42, "accepted"))
        app.state.adapter.get_realized_pnl_for_order = Mock(return_value=0.0)
        client = TestClient(app)

        def setup(oid):
            return client.post(
                "/webhook/tradingview",
                json={
                    "event": "SETUP_PENDING",
                    "order_id": oid,
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "symbol": "XAUUSD",
                    "dir": "BUY",
                    "type": "SMC_PRIME",
                    "limit": 4050.0,
                    "sl": 4045.0,
                    "tp1": 4055.0,
                    "tp2": 4062.5,
                },
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
                json={
                    "event": "TRADE_CLOSED",
                    "order_id": "RELEASE_B",
                    "reason": "manual close",
                    "pnl_dollar": 0.0,
                },
                headers=self.headers,
            )
            self.assertEqual(close.json()["status"], "success")
            self.assertEqual(setup("RELEASE_C").json()["status"], "success")
        finally:
            app.state.adapter.close()

    def test_live_order_filled_rejects_when_broker_has_no_matching_position(self):
        from scripts.webhook_bridge import create_app

        app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path + ".live_fill_reject",
            risk_pct=0.01,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
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
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path + ".live_fill_match",
            risk_pct=0.01,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
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
                lot_size=0.02,
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
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path + ".live_trade_closed",
            risk_pct=0.01,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.execute_intent = Mock(
            return_value=ExecutionResult(True, 999888, "Closed on broker")
        )
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

    def test_live_trade_closed_without_broker_pnl_rejects_tv_invent_halt(self):
        """Live close must not halt/notify on TradingView cash when broker cashflow miss."""
        import os
        from scripts.webhook_bridge import create_app
        from scripts.smc.mt5_adapter import ExecutionResult

        halt_path = self.db_path + ".halt_no_broker_pnl.json"
        app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path + ".live_no_broker_pnl",
            risk_pct=0.01,
            risk_halt_path=halt_path,
            max_daily_losses=2,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.execute_intent = Mock(
            return_value=ExecutionResult(True, 999888, "Closed on broker")
        )
        app.state.adapter.get_open_exposure = Mock(return_value=[])
        app.state.adapter.get_realized_pnl_for_order = Mock(return_value=None)
        try:
            client = TestClient(app)
            res = client.post(
                "/webhook/tradingview",
                json={
                    "event": "TRADE_CLOSED",
                    "order_id": "TV_INVENT_LOSS",
                    "reason": "SL_HIT",
                    "pnl_dollar": -200.0,
                    "pnl_r": -1.0,
                },
                headers=self.headers,
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "reconcile_required")
            self.assertIsNone(data["pnl_dollar"])
            self.assertEqual(app.state.risk_halt.net_losing_trades_today, 0)
        finally:
            app.state.adapter.close()
            if os.path.exists(halt_path):
                os.unlink(halt_path)

    def test_live_setup_broker_rejection_frees_inbox_for_subsequent_setup(self):
        from scripts.webhook_bridge import create_app
        from scripts.smc.mt5_adapter import ExecutionResult

        app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path + ".live_broker_reject",
            risk_pct=0.01,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.get_risk_snapshot = Mock(
            return_value={
                "balance": 10000.0,
                "equity": 10000.0,
                "min_lot": 0.01,
                "max_lot": 5.0,
                "lot_step": 0.01,
                "contract_size": 100.0,
                "margin_free": 9000.0,
                "trade_allowed": 1.0,
                "point": 0.01,
                "stops_level": 0.0,
                "freeze_level": 0.0,
            }
        )
        app.state.adapter.get_open_exposure = Mock(return_value=[])
        app.state.adapter.execute_intent = Mock(
            side_effect=[
                ExecutionResult(False, None, "Margin exceeded"),
                ExecutionResult(True, 12345, "Accepted"),
            ]
        )

        def payload(oid):
            return {
                "event": "SETUP_PENDING",
                "order_id": oid,
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": "XAUUSD",
                "dir": "BUY",
                "type": "SMC_PRIME",
                "limit": 4050.0,
                "sl": 4045.0,
                "tp1": 4055.0,
                "tp2": 4062.5,
            }

        try:
            client = TestClient(app)
            res1 = client.post(
                "/webhook/tradingview", json=payload("ORDER_REJECT_A"), headers=self.headers
            )
            self.assertEqual(res1.status_code, 200)
            self.assertEqual(res1.json()["status"], "rejected")

            # Second setup must NOT be blocked with 'busy'
            res2 = client.post(
                "/webhook/tradingview", json=payload("ORDER_REJECT_B"), headers=self.headers
            )
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(res2.json()["status"], "success")
        finally:
            app.state.adapter.close()

    def test_live_setup_timeout_or_error_marks_uncertain_and_blocks_subsequent(self):
        from scripts.webhook_bridge import create_app

        app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path + ".live_timeout",
            risk_pct=0.01,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
        )
        app.state.adapter.dry_run = False
        app.state.adapter.get_risk_snapshot = Mock(
            return_value={
                "balance": 10000.0,
                "equity": 10000.0,
                "min_lot": 0.01,
                "max_lot": 5.0,
                "lot_step": 0.01,
                "contract_size": 100.0,
                "margin_free": 9000.0,
                "trade_allowed": 1.0,
                "point": 0.01,
                "stops_level": 0.0,
                "freeze_level": 0.0,
            }
        )
        app.state.adapter.get_open_exposure = Mock(return_value=[])
        app.state.adapter.execute_intent = Mock(side_effect=TimeoutError("Broker socket timed out"))

        def payload(oid):
            return {
                "event": "SETUP_PENDING",
                "order_id": oid,
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": "XAUUSD",
                "dir": "BUY",
                "type": "SMC_PRIME",
                "limit": 4050.0,
                "sl": 4045.0,
                "tp1": 4055.0,
                "tp2": 4062.5,
            }

        try:
            client = TestClient(app)
            res1 = client.post(
                "/webhook/tradingview", json=payload("ORDER_TIMEOUT_1"), headers=self.headers
            )
            self.assertEqual(res1.status_code, 200)
            self.assertEqual(res1.json()["status"], "uncertain")

            status_info = app.state.adapter.get_setup_status("ORDER_TIMEOUT_1")
            self.assertEqual(status_info["status"], "uncertain")

            # Subsequent setup must be rejected because an uncertain claim is active
            res2 = client.post(
                "/webhook/tradingview", json=payload("ORDER_TIMEOUT_2"), headers=self.headers
            )
            self.assertEqual(res2.status_code, 200)
            self.assertEqual(res2.json()["status"], "rejected")
            self.assertIn("broker reconciliation required", res2.json()["reason"].lower())
        finally:
            app.state.adapter.close()

    def test_setup_pending_idempotency_duplicate_ignored(self):
        payload = {
            "event": "SETUP_PENDING",
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
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
            account_balance=100.0,
            db_path=self.db_path,
            risk_pct=0.01,
        )
        try:
            small_client = TestClient(small_app)
            payload = {
                "event": "SETUP_PENDING",
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": "XAUUSD_103",
                "symbol": "XAUUSD",
                "dir": "BUY",
                "type": "SMC_PRIME",
                "limit": 4050.00,
                "sl": 4030.00,  # $20.00 SL distance -> 0.01 lot = $200 risk = 200% of $100 balance > 1.5%
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
        # Explicit opt-in: foundation defaults keep partial/BE off.
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path,
            risk_pct=0.01,
            partial_tp_enabled=True,
            be_enabled=True,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret_token}"}

    def tearDown(self):
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()
        self.temp_dir.cleanup()

    def test_tp1_rejected_when_foundation_partial_be_disabled(self):
        import tempfile
        import os
        from scripts.webhook_bridge import create_app

        tmp = tempfile.TemporaryDirectory()
        try:
            app = create_app(
                auth_token=self.secret_token,
                dry_run=True,
                account_balance=10000.0,
                db_path=os.path.join(tmp.name, "foundation.db"),
                # defaults: partial_tp_enabled=False, be_enabled=False
            )
            client = TestClient(app)
            res = client.post(
                "/webhook/tradingview",
                json={
                    "event": "TP1_HIT_MOVE_BE",
                    "order_id": "FOUNDATION_NO_TP1",
                    "entry": 4050.0,
                    "new_sl": 4050.1,
                    "dir": "BUY",
                },
                headers=self.headers,
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "rejected")
            self.assertIn("partial_tp_enabled", data["reason"])
            self.assertIn("be_enabled", data["reason"])
            app.state.adapter.close()
        finally:
            tmp.cleanup()

    def test_tp1_rejects_new_sl_off_breakeven_band(self):
        res = self.client.post(
            "/webhook/tradingview",
            json={
                "event": "TP1_HIT_MOVE_BE",
                "order_id": "BAD_BE_SL",
                "entry": 4050.0,
                "new_sl": 4100.0,  # unconstrained invent BE
                "dir": "BUY",
            },
            headers=self.headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "rejected")
        self.assertIn("new_sl", data["reason"])

    def test_order_filled_and_tp1_partial_close_and_be(self):
        # 1. Place limit
        setup_payload = {
            "event": "SETUP_PENDING",
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "order_id": "XAUUSD_201",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
        }
        res_setup = self.client.post(
            "/webhook/tradingview", json=setup_payload, headers=self.headers
        )
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

        self.app.state.adapter.execute_intent = Mock(
            side_effect=[
                ExecutionResult(False, None, "partial rejected"),
                ExecutionResult(True, 42, "closed"),
            ]
        )
        response = self.client.post(
            "/webhook/tradingview",
            json={
                "event": "TP1_HIT_MOVE_BE",
                "order_id": "TP1_REJECTED_1",
                "entry": 4050.0,
                "new_sl": 4050.1,
            },
            headers=self.headers,
        )
        calls = self.app.state.adapter.execute_intent.call_args_list
        self.assertEqual(
            [call.args[0].intent_type for call in calls],
            [
                OrderIntentType.PARTIAL_CLOSE,
                OrderIntentType.CLOSE_MARKET,
            ],
        )
        self.assertEqual(response.json()["status"], "closed_for_safety")

    def test_rejected_be_after_partial_requests_runner_close(self):
        from scripts.smc.mt5_adapter import ExecutionResult
        from scripts.smc.types import OrderIntentType

        self.app.state.adapter.execute_intent = Mock(
            side_effect=[
                ExecutionResult(True, 42, "partial done"),
                ExecutionResult(False, 42, "BE rejected"),
                ExecutionResult(True, 42, "runner closed"),
            ]
        )
        response = self.client.post(
            "/webhook/tradingview",
            json={
                "event": "TP1_HIT_MOVE_BE",
                "order_id": "BE_REJECTED_1",
                "entry": 4050.0,
                "new_sl": 4050.1,
            },
            headers=self.headers,
        )
        calls = self.app.state.adapter.execute_intent.call_args_list
        self.assertEqual(
            [call.args[0].intent_type for call in calls],
            [
                OrderIntentType.PARTIAL_CLOSE,
                OrderIntentType.MOVE_SL_TO_BE,
                OrderIntentType.CLOSE_MARKET,
            ],
        )
        self.assertEqual(response.json()["status"], "closed_for_safety")

    def test_live_tp1_rejects_before_partial_when_freeze_blocks_be(self):
        from scripts.smc.mt5_adapter import ExecutionResult

        self.app.state.adapter.dry_run = False
        self.app.state.adapter.get_risk_snapshot = Mock(
            return_value={
                "balance": 10000.0,
                "equity": 10000.0,
                "min_lot": 0.01,
                "max_lot": 5.0,
                "lot_step": 0.01,
                "contract_size": 100.0,
                "margin_free": 9000.0,
                "trade_allowed": 1.0,
                "point": 0.01,
                "stops_level": 0.0,
                "freeze_level": 50.0,
            }
        )
        self.app.state.adapter.get_market_quotes = Mock(
            return_value={
                "bid": 4050.2,
                "ask": 4050.4,
            }
        )
        self.app.state.adapter.execute_intent = Mock(
            return_value=ExecutionResult(True, 42, "should not run")
        )
        response = self.client.post(
            "/webhook/tradingview",
            json={
                "event": "TP1_HIT_MOVE_BE",
                "order_id": "FREEZE_BLOCK_1",
                "entry": 4050.0,
                "new_sl": 4050.0,
                "dir": "BUY",
            },
            headers=self.headers,
        )
        self.assertEqual(response.json()["status"], "rejected")
        self.assertIn("rejected_freeze_level", response.json()["reason"])
        self.app.state.adapter.execute_intent.assert_not_called()


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
            account_balance=10000.0,
            db_path=self.db_path,
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
            json={
                "event": "TRADE_CLOSED",
                "order_id": "CLOSE_REJECTED_1",
                "reason": "STOP LOSS HIT",
                "pnl_dollar": -50.0,
            },
            headers=self.headers,
        )
        self.assertEqual(response.json()["status"], "rejected")
        self.assertFalse(
            any(
                row["event_type"] == "TRADE_CLOSED"
                for row in self.app.state.adapter.get_lifecycle_logs()
            )
        )

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
        self.assertFalse(
            any(
                row["event_type"] == "ORDER_CANCELED"
                for row in self.app.state.adapter.get_lifecycle_logs()
            )
        )

    def test_order_canceled_ttl_expiration(self):
        # 1. Setup pending limit
        setup_payload = {
            "event": "SETUP_PENDING",
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "order_id": "XAUUSD_301",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
        }
        res_setup = self.client.post(
            "/webhook/tradingview", json=setup_payload, headers=self.headers
        )
        self.assertEqual(res_setup.status_code, 200)

        # 2. Cancel order
        cancel_payload = {
            "event": "ORDER_CANCELED",
            "order_id": "XAUUSD_301",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "reason": "TTL_EXPIRED (4 bars elapsed)",
        }
        res_cancel = self.client.post(
            "/webhook/tradingview", json=cancel_payload, headers=self.headers
        )
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
        res_close = self.client.post(
            "/webhook/tradingview", json=close_payload, headers=self.headers
        )
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
            account_balance=10000.0,
            db_path=self.db_path,
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
            adapter.log_lifecycle_event(
                event_type="TRADE_CLOSED", pnl_dollar=-100.0, pnl_r=-1.0, reason="SL Hit 1"
            )
            adapter.log_lifecycle_event(
                event_type="TRADE_CLOSED", pnl_dollar=-100.0, pnl_r=-1.0, reason="SL Hit 2"
            )
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
        # Time at 21:15 UTC (after 20:55 rollover cutoff). Session gate would
        # also reject; force session ok so ADR-007 rollover remains covered.
        from unittest.mock import patch

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
        with patch("scripts.webhook.setup_time_gates.is_in_session", return_value=True):
            res = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "rejected")
        self.assertIn("Rollover", data["reason"])

    def test_out_of_session_rejects_setup_pending(self):
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_OUT_SESSION",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "type": "SMC_PRIME",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
            "time": "2026-03-02T11:00:00+00:00",  # between London and NY windows
        }
        _SESSION_PATCHER.stop()
        try:
            res = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        finally:
            _SESSION_PATCHER.start()
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "rejected")
        self.assertIn("out_of_session", data["reason"])


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
            account_balance=10000.0,
            db_path=":memory:",
            risk_pct=0.01,
            notifier=self.mock_notifier,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret_token}"}

    def tearDown(self):
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()

    def test_telegram_background_task_dispatched(self):
        from datetime import datetime, timezone

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
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
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
        from datetime import datetime, timezone

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
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
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
            account_balance=10000.0,
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
            account_balance=10000.0,
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
                "entry": 4050.0,
                "sl": 4040.0,
                "exit_price": 4075.0,
            }
            res = client.post("/webhook/tradingview", json=payload, headers=self.headers)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["action"], "TRADE_CLOSED")
            self.assertEqual(data["pnl_r"], 2.5)

            # Confirm lifecycle log was written
            logs = app.state.adapter.get_lifecycle_logs()
            tc_logs = [
                log
                for log in logs
                if log["event_type"] == "TRADE_CLOSED" and log["order_id"] == "TP2_ALREADY_CLOSED"
            ]
            self.assertEqual(len(tc_logs), 1)
        finally:
            app.state.adapter.close()

    def test_f4_custom_r_multiples_configured_via_create_app(self):
        from scripts.webhook_bridge import create_app

        app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path,
            risk_pct=0.01,
            tp_r=3.5,
            partial_tp_r=1.5,
        )
        try:
            client = TestClient(app)
            # Reason-only payload must NOT invent R from tp_r config.
            res_reason_only = client.post(
                "/webhook/tradingview",
                json={
                    "event": "TRADE_CLOSED",
                    "order_id": "ORDER_REASON_ONLY",
                    "symbol": "XAUUSD",
                    "reason": "TP2_RUNNER_HIT",
                },
                headers=self.headers,
            )
            self.assertEqual(res_reason_only.status_code, 200)
            self.assertIsNone(res_reason_only.json()["pnl_r"])
            self.assertIsNone(res_reason_only.json()["pnl_dollar"])

            # Explicit payload wins (operator/broker evidence).
            res_tp2 = client.post(
                "/webhook/tradingview",
                json={
                    "event": "TRADE_CLOSED",
                    "order_id": "ORDER_TP2_CUSTOM",
                    "symbol": "XAUUSD",
                    "reason": "TP2_RUNNER_HIT",
                    "pnl_r": 3.5,
                    "pnl_dollar": 350.0,
                },
                headers=self.headers,
            )
            self.assertEqual(res_tp2.status_code, 200)
            data_tp2 = res_tp2.json()
            self.assertEqual(data_tp2["pnl_r"], 3.5)
            self.assertEqual(data_tp2["pnl_dollar"], 350.0)

            res_tp1 = client.post(
                "/webhook/tradingview",
                json={
                    "event": "TRADE_CLOSED",
                    "order_id": "ORDER_TP1_CUSTOM",
                    "symbol": "XAUUSD",
                    "reason": "TP1_SCALE_OUT",
                    "pnl_r": 1.5,
                    "pnl_dollar": 150.0,
                },
                headers=self.headers,
            )
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
        halted = new_risk_halt_state(10000.0)
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
            account_balance=10000.0,
            db_path=self.db_path,
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

        save_risk_halt_state(Path(self.halt_path), new_risk_halt_state(10000.0))
        # Recreate app so loaded halt is clear; keep failing identity.
        from scripts.webhook_bridge import create_app

        self.app.state.adapter.close()
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path,
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
        from scripts.smc.risk_halt import (
            new_risk_halt_state,
            save_risk_halt_state,
            load_risk_halt_state,
        )
        from scripts.webhook_bridge import create_app
        from pathlib import Path

        ok_identity = BrokerIdentityReport(
            ok=True,
            broker_server="Exness-MT5Trial",
            account_login=1,
            currency="USD",
            trade_mode=0,
            symbol="XAUUSD",
            reasons=(),
        )
        save_risk_halt_state(Path(self.halt_path), new_risk_halt_state(10000.0))
        self.app.state.adapter.close()
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path,
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
        from scripts.smc.risk_halt import (
            new_risk_halt_state,
            save_risk_halt_state,
            load_risk_halt_state,
        )
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
        state = new_risk_halt_state(10000.0)
        state.high_water_equity = 520.0
        state.net_losing_trades_today = 1
        save_risk_halt_state(Path(self.halt_path), state)

        self.app.state.adapter.close()
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path,
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

    def test_stale_event_time_blocks_setup_pending(self):
        from scripts.smc.broker_identity import BrokerIdentityReport
        from scripts.smc.risk_halt import new_risk_halt_state, save_risk_halt_state
        from scripts.webhook_bridge import create_app
        from pathlib import Path

        ok_identity = BrokerIdentityReport(
            ok=True,
            broker_server="Exness-MT5Trial",
            account_login=1,
            currency="USD",
            trade_mode=0,
            symbol="XAUUSD",
            reasons=(),
        )
        save_risk_halt_state(Path(self.halt_path), new_risk_halt_state(10000.0))
        self.app.state.adapter.close()
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path,
            risk_halt_path=self.halt_path,
            identity_gate=lambda: ok_identity,
            max_daily_losses=99,
        )
        self.client = TestClient(self.app)
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_STALE_BAR",
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
        self.assertIn("stale_market_bar", data["reason"])

    def test_missing_margin_free_blocks_live_setup(self):
        from scripts.smc.broker_identity import BrokerIdentityReport
        from scripts.smc.risk_halt import new_risk_halt_state, save_risk_halt_state
        from scripts.webhook_bridge import create_app
        from pathlib import Path
        from unittest.mock import Mock
        from datetime import datetime, timezone

        ok_identity = BrokerIdentityReport(
            ok=True,
            broker_server="Exness-MT5Trial",
            account_login=1,
            currency="USD",
            trade_mode=0,
            symbol="XAUUSD",
            reasons=(),
        )
        save_risk_halt_state(Path(self.halt_path), new_risk_halt_state(10000.0))
        self.app.state.adapter.close()
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path,
            risk_halt_path=self.halt_path,
            identity_gate=lambda: ok_identity,
            max_daily_losses=99,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
        )
        self.app.state.adapter.dry_run = False
        self.app.state.adapter.connected = True
        self.app.state.adapter.get_account_equity = Mock(return_value=10000.0)
        self.app.state.adapter.get_risk_snapshot = Mock(
            return_value={
                "balance": 10000.0,
                "equity": 10000.0,
                "min_lot": 0.01,
                "max_lot": 5.0,
                "lot_step": 0.01,
                "contract_size": 100.0,
                # margin_free intentionally omitted
            }
        )
        self.app.state.adapter.get_open_exposure = Mock(return_value=[])
        self.client = TestClient(self.app)
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_NO_MARGIN",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        res = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "rejected")
        self.assertIn("missing_margin_free", data["reason"])

    def test_terminal_setup_registry_blocks_revive_after_restart(self):
        """Scenario 8: expired SETUP_ID must not revive via webhook after process restart."""
        import os
        from pathlib import Path
        from datetime import datetime, timezone
        from scripts.smc.broker_identity import BrokerIdentityReport
        from scripts.smc.risk_halt import new_risk_halt_state, save_risk_halt_state
        from scripts.smc.setup_identity import SetupRegistry, load_setup_registry
        from scripts.webhook_bridge import create_app

        registry_path = Path(self.temp_dir.name) / "setup_registry.json"
        prior = SetupRegistry(_persist_path=registry_path)
        prior.mark_terminal("SMC_REVIVE_1", "ttl_expired")

        ok_identity = BrokerIdentityReport(
            ok=True,
            broker_server="Exness-MT5Trial",
            account_login=1,
            currency="USD",
            trade_mode=0,
            symbol="XAUUSD",
            reasons=(),
        )
        save_risk_halt_state(Path(self.halt_path), new_risk_halt_state(10000.0))
        self.app.state.adapter.close()
        fresh_db = os.path.join(self.temp_dir.name, "revive_trades.db")
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=fresh_db,
            risk_halt_path=self.halt_path,
            identity_gate=lambda: ok_identity,
            max_daily_losses=99,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
            setup_registry_path=str(registry_path),
        )
        self.client = TestClient(self.app)
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "SMC_REVIVE_1",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "limit": 4050.00,
            "sl": 4045.00,
            "tp1": 4055.00,
            "tp2": 4062.50,
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        res = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "rejected")
        self.assertIn("setup_id_terminal", data["reason"])
        # Disk still holds terminal mark for the next process.
        reloaded = load_setup_registry(registry_path)
        self.assertTrue(reloaded.is_blocked("SMC_REVIVE_1"))

    def test_order_canceled_marks_setup_terminal(self):
        """ORDER_CANCELED (TTL) stamps registry so a new app cannot re-admit."""
        import os
        from pathlib import Path
        from scripts.smc.setup_identity import load_setup_registry
        from scripts.webhook_bridge import create_app

        registry_path = Path(self.temp_dir.name) / "setup_registry_cancel.json"
        self.app.state.adapter.close()
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path,
            setup_registry_path=str(registry_path),
        )
        self.client = TestClient(self.app)
        cancel = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "ORDER_CANCELED",
                "order_id": "SMC_TTL_1",
                "reason": "TTL_EXPIRED",
            },
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.json()["status"], "success")

        # Fresh process + fresh webhook DB: only registry should block revive.
        fresh_db = os.path.join(self.temp_dir.name, "after_cancel.db")
        self.app.state.adapter.close()
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=fresh_db,
            setup_registry_path=str(registry_path),
            max_daily_losses=99,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
        )
        self.client = TestClient(self.app)
        from datetime import datetime, timezone

        revive = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "SETUP_PENDING",
                "order_id": "SMC_TTL_1",
                "symbol": "XAUUSD",
                "dir": "BUY",
                "limit": 4050.00,
                "sl": 4045.00,
                "tp1": 4055.00,
                "tp2": 4062.50,
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        self.assertEqual(revive.status_code, 200)
        self.assertEqual(revive.json()["status"], "rejected")
        self.assertIn("setup_id_terminal", revive.json()["reason"])
        self.assertEqual(
            load_setup_registry(registry_path).terminal_reason("SMC_TTL_1"),
            "TTL_EXPIRED",
        )

    def test_stops_geometry_blocks_tight_sl(self):
        from scripts.smc.broker_identity import BrokerIdentityReport
        from scripts.smc.risk_halt import new_risk_halt_state, save_risk_halt_state
        from scripts.webhook_bridge import create_app
        from pathlib import Path
        from unittest.mock import Mock
        from datetime import datetime, timezone

        ok_identity = BrokerIdentityReport(
            ok=True,
            broker_server="Exness-MT5Trial",
            account_login=1,
            currency="USD",
            trade_mode=0,
            symbol="XAUUSD",
            reasons=(),
        )
        save_risk_halt_state(Path(self.halt_path), new_risk_halt_state(10000.0))
        self.app.state.adapter.close()
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db_path,
            risk_halt_path=self.halt_path,
            identity_gate=lambda: ok_identity,
            max_daily_losses=99,
            commission_per_lot=10.0,
            slippage_allowance=0.5,
            risk_pct=0.01,
        )
        self.app.state.adapter.dry_run = False
        self.app.state.adapter.connected = True
        self.app.state.adapter.get_account_equity = Mock(return_value=10000.0)
        self.app.state.adapter.get_risk_snapshot = Mock(
            return_value={
                "balance": 10000.0,
                "equity": 10000.0,
                "min_lot": 0.01,
                "max_lot": 5.0,
                "lot_step": 0.01,
                "contract_size": 100.0,
                "margin_free": 9000.0,
                "trade_allowed": 1.0,
                "point": 0.01,
                "stops_level": 50.0,  # requires $0.50 min SL distance
                "freeze_level": 0.0,
            }
        )
        self.app.state.adapter.get_open_exposure = Mock(return_value=[])
        self.client = TestClient(self.app)
        payload = {
            "event": "SETUP_PENDING",
            "order_id": "XAUUSD_TIGHT_SL",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "limit": 4050.00,
            "sl": 4049.90,  # 0.10 < 0.50
            "tp1": 4055.00,
            "tp2": 4062.50,
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        res = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "rejected")
        self.assertIn("sl_inside_stops_level", data["reason"])


class TestWebhookFoundationRiskDefault(unittest.TestCase):
    def test_create_app_defaults_to_half_percent_risk(self):
        import inspect
        from scripts.webhook_bridge import create_app

        default = inspect.signature(create_app).parameters["risk_pct"].default
        self.assertEqual(default, 0.005)


class TestWebhookClockTimeExit(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from scripts.webhook_bridge import create_app

        self.Path = Path
        self.secret = "CLOCK_SECRET"
        self.db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db.close()
        self.app = create_app(
            auth_token=self.secret,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db.name,
            max_hold_bars=2,
            bar_minutes=5,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret}"}

    def tearDown(self):
        self.app.state.adapter.conn.close()
        self.Path(self.db.name).unlink(missing_ok=True)

    def test_clock_closes_stale_fill_without_new_bar(self):
        from datetime import datetime, timezone, timedelta

        adapter = self.app.state.adapter
        # Seed open_time = now - 20m so 2*5m max hold is exceeded.
        recent_old = datetime.now(timezone.utc) - timedelta(minutes=20)
        adapter.log_lifecycle_event(
            event_type="ORDER_FILLED",
            order_id="CLOCK_FILL_1",
            direction="BUY",
            timestamp=recent_old.isoformat(),
        )

        res = self.client.post("/internal/clock", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["action"], "CLOCK_TICK")
        self.assertEqual(data["checked"], 1)
        self.assertEqual(len(data["exits"]), 1)
        self.assertEqual(data["exits"][0]["status"], "success")
        self.assertIn("TIME_EXIT", data["exits"][0]["reason"])

        # Second tick: already closed — no duplicate exit
        res2 = self.client.post("/internal/clock", headers=self.headers)
        self.assertEqual(res2.json()["checked"], 0)
        self.assertEqual(res2.json()["exits"], [])

    def test_clock_syncs_classified_account_pnl_deals(self):
        """Stories 5–7: clock discloses bot/manual/cash_flow deals without inventing equity."""
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts.smc.account_pnl_sync import DEAL_TYPE_BALANCE, DEAL_TYPE_BUY
        from scripts.webhook_bridge import create_app
        import tempfile

        db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db.close()
        app = create_app(
            auth_token=self.secret, dry_run=True, account_balance=10000.0, db_path=db.name
        )
        client = TestClient(app)
        try:
            adapter = app.state.adapter
            adapter.connected = True
            deals = [
                SimpleNamespace(
                    ticket=101,
                    type=DEAL_TYPE_BUY,
                    comment="SMC_BOT1",
                    profit=5.0,
                    commission=0.0,
                    swap=0.0,
                    fee=0.0,
                ),
                SimpleNamespace(
                    ticket=102,
                    type=DEAL_TYPE_BUY,
                    comment="hand trade",
                    profit=-3.0,
                    commission=0.0,
                    swap=0.0,
                    fee=0.0,
                ),
                SimpleNamespace(
                    ticket=103,
                    type=DEAL_TYPE_BALANCE,
                    comment="",
                    profit=50.0,
                    commission=0.0,
                    swap=0.0,
                    fee=0.0,
                ),
            ]
            with patch.object(adapter, "fetch_recent_broker_deals", return_value=deals):
                res = client.post(
                    "/internal/clock",
                    headers={"Authorization": f"Bearer {self.secret}"},
                )
            self.assertEqual(res.status_code, 200)
            rows = res.json()["account_pnl"]
            self.assertEqual(len(rows), 3)
            by_ticket = {r["ticket"]: r for r in rows}
            self.assertEqual(by_ticket[101]["source"], "bot")
            self.assertEqual(by_ticket[102]["source"], "manual")
            self.assertEqual(by_ticket[103]["source"], "cash_flow")
            # Idempotent second tick
            with patch.object(adapter, "fetch_recent_broker_deals", return_value=deals):
                res2 = client.post(
                    "/internal/clock",
                    headers={"Authorization": f"Bearer {self.secret}"},
                )
            self.assertEqual(res2.json()["account_pnl"], [])
        finally:
            app.state.adapter.conn.close()
            self.Path(db.name).unlink(missing_ok=True)

    def test_clock_reconciles_uncertain_setup_against_broker(self):
        """Story 35: clock must reconcile uncertain intents — never leave them forever."""
        from types import SimpleNamespace
        from unittest.mock import patch
        from scripts.webhook_bridge import create_app
        import tempfile

        db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db.close()
        app = create_app(
            auth_token=self.secret, dry_run=True, account_balance=10000.0, db_path=db.name
        )
        client = TestClient(app)
        try:
            adapter = app.state.adapter
            adapter.claim_setup({"order_id": "UNCERTAIN_CLOCK_1"})
            adapter.update_setup_status("UNCERTAIN_CLOCK_1", "uncertain")
            broker = SimpleNamespace(
                orders_get=lambda symbol=None: [
                    SimpleNamespace(ticket=777, comment="SMC_UNCERTAIN_CLOCK_1")
                ],
                positions_get=lambda symbol=None: [],
                history_orders_get=lambda *a, **k: [],
            )
            # Force live reconcile path while keeping dry_run adapter DB.
            adapter.connected = True
            with patch("scripts.smc.mt5_adapter.runtime.mt5", broker):
                res = client.post(
                    "/internal/clock",
                    headers={"Authorization": f"Bearer {self.secret}"},
                )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(len(data["uncertain"]), 1)
            self.assertEqual(data["uncertain"][0]["order_id"], "UNCERTAIN_CLOCK_1")
            self.assertEqual(data["uncertain"][0]["outcome"], "accepted")
            info = adapter.get_setup_status("UNCERTAIN_CLOCK_1")
            self.assertEqual(info["status"], "accepted")
            self.assertEqual(info["ticket"], 777)
        finally:
            app.state.adapter.conn.close()
            self.Path(db.name).unlink(missing_ok=True)

    def test_clock_idle_without_max_hold_still_runs_lifecycle(self):
        from scripts.webhook_bridge import create_app
        import tempfile

        db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db.close()
        app = create_app(
            auth_token=self.secret, dry_run=True, account_balance=10000.0, db_path=db.name
        )
        client = TestClient(app)
        try:
            res = client.post(
                "/internal/clock",
                headers={"Authorization": f"Bearer {self.secret}"},
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            # Rollover planner remains armed even when max_hold unset.
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["exits"], [])
            self.assertEqual(data["cancels"], [])
            self.assertIn("lifecycle", data)
            self.assertEqual(data["lifecycle"]["ttl_cancels"], [])
            self.assertIsNone(data.get("max_hold_bars"))
        finally:
            app.state.adapter.conn.close()
            self.Path(db.name).unlink(missing_ok=True)

    def test_clock_rollover_closes_open_fill_at_cutoff(self):
        from datetime import datetime, timezone
        from unittest.mock import patch
        from scripts.webhook_bridge import create_app
        import tempfile

        db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db.close()
        app = create_app(
            auth_token=self.secret,
            dry_run=True,
            account_balance=10000.0,
            db_path=db.name,
            # max_hold unset — rollover must still flatten
            rollover_hour_utc=20,
            rollover_minute_utc=55,
        )
        client = TestClient(app)
        try:
            adapter = app.state.adapter
            adapter.log_lifecycle_event(
                event_type="ORDER_FILLED",
                order_id="ROLL_FILL_1",
                direction="BUY",
                timestamp="2026-03-02T18:00:00+00:00",
            )
            fake_now = datetime(2026, 3, 2, 20, 55, tzinfo=timezone.utc)
            with patch("scripts.webhook.clock_routes.datetime") as mock_dt:
                mock_dt.now.return_value = fake_now
                mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
                # Keep timezone utilities working if referenced
                mock_dt.now = lambda tz=None: fake_now
                res = client.post(
                    "/internal/clock",
                    headers={"Authorization": f"Bearer {self.secret}"},
                )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(len(data["exits"]), 1)
            self.assertEqual(data["exits"][0]["order_id"], "ROLL_FILL_1")
            self.assertIn("ROLLOVER", data["exits"][0]["reason"].upper())
            # Dry-run has no live quotes → disclose; do not invent exit price.
            disclosures = data.get("missing_quote_disclosures") or []
            self.assertTrue(
                any(
                    d.get("order_id") == "ROLL_FILL_1" and d.get("context") == "session_flat_exit"
                    for d in disclosures
                ),
                msg=data,
            )
            # PnL must stay unset without broker deal evidence.
            self.assertIsNone(data["exits"][0].get("pnl_dollar"))
        finally:
            app.state.adapter.conn.close()
            self.Path(db.name).unlink(missing_ok=True)

    def test_clock_runs_ttl_lifecycle_reconciliation(self):
        from datetime import datetime, timezone, timedelta
        from scripts.webhook_bridge import create_app
        import tempfile

        db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db.close()
        app = create_app(
            auth_token=self.secret,
            dry_run=True,
            account_balance=10000.0,
            db_path=db.name,
            max_hold_bars=2,
            bar_minutes=5,
            order_ttl_bars=4,
        )
        client = TestClient(app)
        try:
            adapter = app.state.adapter
            adapter.claim_setup({"order_id": "TTL_CLOCK_1", "limit": 4050.0})
            adapter.update_setup_status("TTL_CLOCK_1", "accepted", ticket=1)
            old = datetime.now(timezone.utc) - timedelta(minutes=30)
            with adapter._claim_lock:
                adapter.conn.execute(
                    "UPDATE setup_inbox SET created_at = ? WHERE order_id = ?",
                    (old.isoformat(), "TTL_CLOCK_1"),
                )
                adapter.conn.commit()
            res = client.post("/internal/clock", headers=self.headers)
            self.assertEqual(res.status_code, 200)
            lifecycle = res.json()["lifecycle"]
            self.assertEqual(len(lifecycle["ttl_cancels"]), 1)
            self.assertEqual(lifecycle["ttl_cancels"][0]["order_id"], "TTL_CLOCK_1")
            # Scenario 8: TTL must block revive of the same setup identity.
            self.assertTrue(app.state.setup_registry.is_blocked("TTL_CLOCK_1"))
            ok, reason = app.state.setup_registry.admit("TTL_CLOCK_1")
            self.assertFalse(ok)
            self.assertIn("ttl", reason.lower())
        finally:
            app.state.adapter.conn.close()
            self.Path(db.name).unlink(missing_ok=True)

    def test_clock_cancels_unfilled_pending_on_news_blackout(self):
        from datetime import datetime, timezone, timedelta
        from scripts.smc.news import NewsManager, NewsEvent
        from scripts.webhook_bridge import create_app
        import tempfile

        db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db.close()
        news = NewsManager()
        news.events = [
            NewsEvent(
                time=datetime.now(timezone.utc) + timedelta(minutes=5),
                currency="USD",
                impact="HIGH",
                name="NFP",
            )
        ]
        news.schedule_known = True
        app = create_app(
            auth_token=self.secret,
            dry_run=True,
            account_balance=10000.0,
            db_path=db.name,
            news_manager=news,
            # max_hold unset: news cancel must still run
        )
        client = TestClient(app)
        try:
            adapter = app.state.adapter
            adapter.claim_setup({"order_id": "NEWS_PEND_1", "limit": 2000.0})
            adapter.update_setup_status("NEWS_PEND_1", "accepted", ticket=1)
            res = client.post(
                "/internal/clock",
                headers={"Authorization": f"Bearer {self.secret}"},
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(len(data["cancels"]), 1)
            self.assertEqual(data["cancels"][0]["order_id"], "NEWS_PEND_1")
            self.assertEqual(data["cancels"][0]["status"], "success")
            self.assertEqual(data["exits"], [])
        finally:
            app.state.adapter.conn.close()
            self.Path(db.name).unlink(missing_ok=True)

    def test_trade_closed_reason_only_does_not_invent_pnl_or_circuit_loss(self):
        from scripts.smc.mt5_adapter import SMCExecutionAdapter

        res = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "TRADE_CLOSED",
                "order_id": "REASON_ONLY_1",
                "reason": "STOP LOSS HIT 🛑",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsNone(data["pnl_r"])
        self.assertIsNone(data["pnl_dollar"])

        geo = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "TRADE_CLOSED",
                "order_id": "GEO_R_ONLY",
                "dir": "BUY",
                "entry": 100.0,
                "sl": 90.0,
                "exit_price": 120.0,
                "reason": "TP",
            },
        ).json()
        self.assertEqual(geo["pnl_r"], 2.0)
        self.assertIsNone(geo["pnl_dollar"])

        adapter = SMCExecutionAdapter(dry_run=True, db_path=self.db.name)
        try:
            # Reason-only + geometry-only must not invent circuit losses.
            self.assertEqual(adapter.get_daily_realized_losses(), 0)
        finally:
            adapter.close()

    def test_trade_closed_webhook_skipped_when_lifecycle_already_logged(self):
        adapter = self.app.state.adapter
        adapter.log_lifecycle_event(
            event_type="TRADE_CLOSED",
            order_id="LC_DUP_1",
            pnl_dollar=-10.0,
            pnl_r=-1.0,
            reason="broker_lifecycle_close_detected",
        )
        before_losses = adapter.get_daily_realized_losses()
        res = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "TRADE_CLOSED",
                "order_id": "LC_DUP_1",
                "reason": "SL_HIT",
                "pnl_dollar": -10.0,
                "pnl_r": -1.0,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ignored_duplicate")
        self.assertEqual(adapter.get_daily_realized_losses(), before_losses)
        closed_rows = [
            row
            for row in adapter.get_lifecycle_logs()
            if row.get("event_type") == "TRADE_CLOSED" and row.get("order_id") == "LC_DUP_1"
        ]
        self.assertEqual(len(closed_rows), 1)

    def test_clock_marks_order_filled_processed_after_lifecycle_fill(self):
        from unittest.mock import patch

        adapter = self.app.state.adapter
        adapter.claim_setup({"order_id": "LC_FILL_1", "limit": 4050.0})
        adapter.update_setup_status("LC_FILL_1", "accepted", ticket=42)
        fake_lifecycle = {
            "ttl_cancels": [],
            "broker_fills": [{"order_id": "LC_FILL_1", "ticket": 42}],
            "broker_closes": [],
        }
        with patch(
            "scripts.smc.broker_lifecycle.reconcile_broker_lifecycle",
            return_value=fake_lifecycle,
        ):
            res = self.client.post("/internal/clock", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(adapter.is_webhook_processed("LC_FILL_1", "ORDER_FILLED"))
        dup = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "ORDER_FILLED",
                "order_id": "LC_FILL_1",
                "dir": "BUY",
                "entry": 4050.0,
                "sl": 4045.0,
                "lot_size": 0.01,
            },
        )
        self.assertEqual(dup.json()["status"], "ignored_duplicate")

    def test_order_filled_webhook_skipped_when_lifecycle_event_exists(self):
        adapter = self.app.state.adapter
        adapter.log_lifecycle_event(
            event_type="ORDER_FILLED",
            order_id="LC_FILL_LEDGER_1",
            direction="BUY",
            entry_price=4050.0,
            sl_price=4045.0,
            lot_size=0.01,
        )
        res = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "ORDER_FILLED",
                "order_id": "LC_FILL_LEDGER_1",
                "dir": "BUY",
                "entry": 4050.0,
                "sl": 4045.0,
                "lot_size": 0.01,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ignored_duplicate")
        filled = [
            row
            for row in adapter.get_lifecycle_logs()
            if row.get("event_type") == "ORDER_FILLED" and row.get("order_id") == "LC_FILL_LEDGER_1"
        ]
        self.assertEqual(len(filled), 1)

    def test_trade_closed_uses_frozen_initial_r_from_fill_geometry(self):
        """Dollar PnL + entry/SL/lot → R uses frozen initial denominator."""
        res = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "TRADE_CLOSED",
                "order_id": "FROZEN_R_1",
                "dir": "BUY",
                "entry": 2000.0,
                "sl": 1990.0,
                "lot_size": 0.01,
                "pnl_dollar": 10.0,
                "reason": "MANUAL_FLAT",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["action"], "TRADE_CLOSED")
        # risk = 10 * 0.01 * 100 = 10; pnl 10 → 1.0R
        self.assertEqual(data["pnl_r"], 1.0)


class TestWebhookDryRunSetupInbox(unittest.TestCase):
    def test_dry_run_setup_claims_inbox_for_clock_cancels(self):
        """Staging dry-run must track pendings so news/H1/TTL clock paths work."""
        from scripts.webhook_bridge import create_app
        import tempfile
        from pathlib import Path

        db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db.close()
        secret = "DRY_CLAIM_SECRET"
        app = create_app(
            auth_token=secret,
            dry_run=True,
            account_balance=10000.0,
            db_path=db.name,
            commission_per_lot=0.0,
            slippage_allowance=0.0,
        )
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {secret}"}
        try:
            res = client.post(
                "/webhook/tradingview",
                headers=headers,
                json={
                    "event": "SETUP_PENDING",
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "order_id": "DRY_CLAIM_1",
                    "dir": "BUY",
                    "limit": 2400.0,
                    "sl": 2390.0,
                    "tp1": 2420.0,
                },
            )
            self.assertEqual(res.status_code, 200)
            body = res.json()
            self.assertEqual(body["status"], "success")
            self.assertIn("receipt_id", body)
            adapter = app.state.adapter
            self.assertIn("DRY_CLAIM_1", adapter.list_unfilled_pendings())
            self.assertEqual(adapter.get_pending_direction("DRY_CLAIM_1"), "BUY")
            info = adapter.get_setup_status("DRY_CLAIM_1")
            self.assertEqual(info["status"], "accepted")

            res2 = client.post(
                "/webhook/tradingview",
                headers=headers,
                json={
                    "event": "SETUP_PENDING",
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "order_id": "DRY_CLAIM_2",
                    "dir": "SELL",
                    "limit": 2390.0,
                    "sl": 2400.0,
                    "tp1": 2370.0,
                },
            )
            self.assertEqual(res2.json()["status"], "rejected")
            self.assertIn("busy", res2.json()["reason"].lower())
        finally:
            app.state.adapter.close()
            Path(db.name).unlink(missing_ok=True)


class TestWebhookH1BiasGate(unittest.TestCase):
    """Scenario 8: webhook path must honor known H1 bias like orchestrator."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from scripts.webhook_bridge import create_app

        self.Path = Path
        self.secret = "H1_BIAS_SECRET"
        self.db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db.close()
        self.app = create_app(
            auth_token=self.secret,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db.name,
            commission_per_lot=0.0,
            slippage_allowance=0.0,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret}"}

    def tearDown(self):
        self.app.state.adapter.conn.close()
        self.Path(self.db.name).unlink(missing_ok=True)

    def test_setup_uses_live_h1_bias_when_payload_omits_bias(self):
        """Live Gate C: TV omit h1_bias → broker H1 still blocks opposing SETUP."""
        from unittest.mock import patch

        with patch.object(
            self.app.state.adapter,
            "resolve_live_h1_bias",
            return_value=("SELL", True),
        ):
            res = self.client.post(
                "/webhook/tradingview",
                headers=self.headers,
                json={
                    "event": "SETUP_PENDING",
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "order_id": "H1_LIVE_SETUP_1",
                    "dir": "BUY",
                    "limit": 2400.0,
                    "sl": 2390.0,
                    "tp1": 2420.0,
                },
            )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "rejected")
        self.assertIn("h1_bias", body["reason"])
        self.assertTrue(self.app.state.setup_registry.is_blocked("H1_LIVE_SETUP_1"))

    def test_setup_does_not_invent_h1_reject_when_live_bias_unknown(self):
        from unittest.mock import patch

        with patch.object(
            self.app.state.adapter,
            "resolve_live_h1_bias",
            return_value=(None, False),
        ):
            res = self.client.post(
                "/webhook/tradingview",
                headers=self.headers,
                json={
                    "event": "SETUP_PENDING",
                    "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "order_id": "H1_LIVE_SETUP_OK",
                    "dir": "BUY",
                    "limit": 2400.0,
                    "sl": 2390.0,
                    "tp1": 2420.0,
                },
            )
        self.assertEqual(res.json()["status"], "success")

    def test_setup_pending_rejected_when_known_h1_bias_conflicts(self):
        res = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "SETUP_PENDING",
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": "H1_BLOCK_1",
                "dir": "BUY",
                "limit": 2400.0,
                "sl": 2390.0,
                "tp1": 2420.0,
                "h1_bias": "SELL",
                "h1_bias_known": True,
            },
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "rejected")
        self.assertIn("h1_bias", body["reason"])
        self.assertTrue(self.app.state.setup_registry.is_blocked("H1_BLOCK_1"))

    def test_clock_cancels_pending_when_known_h1_bias_flips(self):
        adapter = self.app.state.adapter
        place = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "SETUP_PENDING",
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": "H1_FLIP_1",
                "dir": "BUY",
                "limit": 2400.0,
                "sl": 2390.0,
                "tp1": 2420.0,
            },
        )
        self.assertEqual(place.status_code, 200)
        self.assertEqual(place.json()["status"], "success")
        self.assertIn("H1_FLIP_1", adapter.list_unfilled_pendings())

        res = self.client.post(
            "/internal/clock",
            headers=self.headers,
            json={"h1_bias": "SELL", "h1_bias_known": True},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        cancels = data.get("h1_bias_cancels") or []
        self.assertTrue(cancels, msg=data)
        self.assertEqual(cancels[0]["order_id"], "H1_FLIP_1")
        self.assertEqual(cancels[0]["status"], "success")
        self.assertIn("h1_bias", cancels[0]["reason"])
        self.assertTrue(self.app.state.setup_registry.is_blocked("H1_FLIP_1"))
        self.assertNotIn("H1_FLIP_1", adapter.list_unfilled_pendings())

    def test_clock_cancels_pending_on_sl_before_fill_ohlc(self):
        adapter = self.app.state.adapter
        place = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "SETUP_PENDING",
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": "SLBF_CLK_1",
                "dir": "BUY",
                "limit": 2400.0,
                "sl": 2390.0,
                "tp1": 2420.0,
            },
        )
        self.assertEqual(place.status_code, 200)
        self.assertEqual(place.json()["status"], "success")
        self.assertIn("SLBF_CLK_1", adapter.list_unfilled_pendings())

        res = self.client.post(
            "/internal/clock",
            headers=self.headers,
            json={"high": 2395.0, "low": 2388.0},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        cancels = data.get("sl_before_fill_cancels") or []
        self.assertTrue(cancels, msg=data)
        self.assertEqual(cancels[0]["order_id"], "SLBF_CLK_1")
        self.assertEqual(cancels[0]["status"], "success")
        self.assertEqual(cancels[0]["reason"], "sl_before_fill")
        self.assertTrue(self.app.state.setup_registry.is_blocked("SLBF_CLK_1"))
        self.assertNotIn("SLBF_CLK_1", adapter.list_unfilled_pendings())

    def test_clock_discloses_missing_quote_for_pending_sl_check(self):
        """B15: no OHLC/live quotes → disclose; do not invent bar or cancel."""
        from unittest.mock import patch

        adapter = self.app.state.adapter
        place = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "SETUP_PENDING",
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": "MISS_Q_1",
                "dir": "BUY",
                "limit": 2400.0,
                "sl": 2390.0,
                "tp1": 2420.0,
            },
        )
        self.assertEqual(place.json()["status"], "success")
        with patch.object(adapter, "get_market_quotes", return_value=None):
            res = self.client.post("/internal/clock", headers=self.headers, json={})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        disclosures = data.get("missing_quote_disclosures") or []
        self.assertTrue(disclosures, msg=data)
        self.assertEqual(disclosures[0]["order_id"], "MISS_Q_1")
        self.assertEqual(disclosures[0]["reason"], "missing_quote")
        self.assertEqual(data.get("sl_before_fill_cancels") or [], [])
        self.assertIn("MISS_Q_1", adapter.list_unfilled_pendings())
        self.assertFalse(self.app.state.setup_registry.is_blocked("MISS_Q_1"))

    def test_clock_uses_live_h1_bias_when_body_omits_bias(self):
        """Live Gate C cron (empty body) must still cancel on broker H1 bias."""
        from unittest.mock import patch

        adapter = self.app.state.adapter
        place = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "SETUP_PENDING",
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": "H1_LIVE_1",
                "dir": "BUY",
                "limit": 2400.0,
                "sl": 2390.0,
                "tp1": 2420.0,
            },
        )
        self.assertEqual(place.json()["status"], "success")
        with patch.object(
            adapter,
            "resolve_live_h1_bias",
            return_value=("SELL", True),
        ):
            res = self.client.post("/internal/clock", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        cancels = res.json().get("h1_bias_cancels") or []
        self.assertTrue(cancels, msg=res.json())
        self.assertEqual(cancels[0]["order_id"], "H1_LIVE_1")
        self.assertNotIn("H1_LIVE_1", adapter.list_unfilled_pendings())

    def test_clock_does_not_invent_h1_cancel_when_live_bias_unknown(self):
        from unittest.mock import patch

        adapter = self.app.state.adapter
        place = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "SETUP_PENDING",
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": "H1_LIVE_UNK",
                "dir": "BUY",
                "limit": 2400.0,
                "sl": 2390.0,
                "tp1": 2420.0,
            },
        )
        self.assertEqual(place.json()["status"], "success")
        with patch.object(
            adapter,
            "resolve_live_h1_bias",
            return_value=(None, False),
        ):
            res = self.client.post("/internal/clock", headers=self.headers)
        self.assertEqual(res.json().get("h1_bias_cancels") or [], [])
        self.assertIn("H1_LIVE_UNK", adapter.list_unfilled_pendings())

    def test_unknown_h1_bias_does_not_invent_clock_cancel(self):
        adapter = self.app.state.adapter
        place = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "SETUP_PENDING",
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": "H1_UNKNOWN_1",
                "dir": "BUY",
                "limit": 2400.0,
                "sl": 2390.0,
                "tp1": 2420.0,
            },
        )
        self.assertEqual(place.json()["status"], "success")
        res = self.client.post("/internal/clock", headers=self.headers, json={})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("h1_bias_cancels") or [], [])
        self.assertIn("H1_UNKNOWN_1", adapter.list_unfilled_pendings())


class TestWebhookClockRiskHaltFlatten(unittest.TestCase):
    """Story 10: clock must cancel unfilled pendings when risk halt is active."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from scripts.webhook_bridge import create_app
        from scripts.smc.risk_halt import new_risk_halt_state, save_risk_halt_state

        self.Path = Path
        self.secret = "RISK_HALT_CLOCK_SECRET"
        self.db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db.close()
        self.halt_path = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.halt_path.close()
        # Start NOT halted so SETUP can place.
        save_risk_halt_state(Path(self.halt_path.name), new_risk_halt_state(10000.0))
        self.app = create_app(
            auth_token=self.secret,
            dry_run=True,
            account_balance=10000.0,
            db_path=self.db.name,
            risk_halt_path=self.halt_path.name,
            commission_per_lot=0.0,
            slippage_allowance=0.0,
            max_daily_losses=99,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret}"}

    def tearDown(self):
        self.app.state.adapter.conn.close()
        self.Path(self.db.name).unlink(missing_ok=True)
        self.Path(self.halt_path.name).unlink(missing_ok=True)

    def test_clock_cancels_pending_when_risk_halt_trips(self):
        adapter = self.app.state.adapter
        place = self.client.post(
            "/webhook/tradingview",
            headers=self.headers,
            json={
                "event": "SETUP_PENDING",
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": "HALT_CLK_1",
                "dir": "BUY",
                "limit": 2400.0,
                "sl": 2390.0,
                "tp1": 2420.0,
            },
        )
        self.assertEqual(place.status_code, 200)
        self.assertEqual(place.json()["status"], "success")
        self.assertIn("HALT_CLK_1", adapter.list_unfilled_pendings())

        # Trip halt after pending exists (clock path, not SETUP reject path).
        self.app.state.risk_halt.drawdown_halt = True

        res = self.client.post("/internal/clock", headers=self.headers, json={})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        cancels = data.get("risk_halt_cancels") or []
        self.assertTrue(cancels, msg=data)
        self.assertEqual(cancels[0]["order_id"], "HALT_CLK_1")
        self.assertEqual(cancels[0]["status"], "success")
        self.assertEqual(cancels[0]["reason"], "foundation_risk_halt")
        self.assertTrue(self.app.state.setup_registry.is_blocked("HALT_CLK_1"))
        self.assertNotIn("HALT_CLK_1", adapter.list_unfilled_pendings())


if __name__ == "__main__":
    unittest.main()
