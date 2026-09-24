import unittest
import tempfile
import os
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from scripts.webhook_bridge import create_app
from scripts.smc.mt5_adapter import SMCExecutionAdapter
from scripts.smc.orchestrator import StrategyOrchestrator
from scripts.smc.types import Direction, Position, AccountState


class TestVerdictRepro(unittest.TestCase):
    """Reproduces the exact fail paths identified in the Scrutinize verdict."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "repro.db")
        self.secret = "REPRO_SECRET"
        self.app = create_app(
            auth_token=self.secret,
            dry_run=True,
            db_path=self.db_path,
            account_balance=10000.0,
            risk_pct=0.01,
            max_daily_losses=2,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret}"}

    def tearDown(self):
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()
        self.temp_dir.cleanup()

    def test_repro_trade_closed_webhook_does_not_trip_circuit_breaker(self):
        """
        Reason-only STOP LOSS must NOT invent circuit-breaker losses.
        Explicit negative pnl_r/pnl_dollar is required.
        """
        for i in [1, 2]:
            payload = {
                "event": "TRADE_CLOSED",
                "order_id": f"ORDER_{i}",
                "symbol": "XAUUSD",
                "reason": "STOP LOSS HIT 🛑",
                "time": "2026-09-14 10:00:00",
            }
            res = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
            self.assertEqual(res.status_code, 200)

        adapter = SMCExecutionAdapter(dry_run=True, db_path=self.db_path)
        try:
            loss_count = adapter.get_daily_realized_losses("2026-09-14")
            self.assertEqual(
                loss_count,
                0,
                "Reason-only closes must not invent circuit-breaker losses",
            )
        finally:
            adapter.close()

        for i in [3, 4]:
            payload = {
                "event": "TRADE_CLOSED",
                "order_id": f"ORDER_{i}",
                "symbol": "XAUUSD",
                "reason": "STOP LOSS HIT 🛑",
                "pnl_r": -1.0,
                "pnl_dollar": -50.0,
                "time": "2026-09-14 11:00:00",
            }
            res = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
            self.assertEqual(res.status_code, 200)

        adapter = SMCExecutionAdapter(dry_run=True, db_path=self.db_path)
        try:
            loss_count = adapter.get_daily_realized_losses("2026-09-14")
            self.assertEqual(loss_count, 2)
        finally:
            adapter.close()

    def test_repro_trade_closed_rollover_must_dispatch_close(self):
        """
        Fail Path 2: Sending TRADE_CLOSED with 'ROLLOVER FLAT' must dispatch
        CLOSE_MARKET to the broker adapter, not just log to SQLite.
        """
        payload = {
            "event": "TRADE_CLOSED",
            "order_id": "ORDER_ROLLOVER_1",
            "symbol": "XAUUSD",
            "reason": "ROLLOVER FLAT (20:55 UTC) ⏰",
            "time": "2026-09-14 20:55:00",
        }
        res = self.client.post("/webhook/tradingview", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn(
            "execution", data, "TRADE_CLOSED must execute position liquidation on adapter"
        )
        self.assertTrue(data["execution"]["success"])

    def test_repro_orchestrator_short_tp_ignores_ask_spread(self):
        """
        Fail Path 3: Current orchestrator does NOT add spread_buffer to bar['low'].
        For SELL trade, it compares raw bar['low'] <= tp_price without Ask spread.
        """
        orch = StrategyOrchestrator()
        account = AccountState(balance=10000.0, equity=10000.0)
        pos = Position(
            direction=Direction.SELL,
            entry_price=2500.0,
            sl_price=2505.0,
            tp_price=2490.0,
            lot_size=0.10,
            open_time=datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc),
            initial_sl_distance=5.0,
        )
        account.open_position = pos

        # Bar low is 2489.80. Raw low is below 2490.0, BUT Ask price with $0.30 spread
        # is 2489.80 + 0.30 = 2490.10, which has NOT reached 2490.0!
        bar = {
            "time": datetime(2026, 9, 14, 10, 15, tzinfo=timezone.utc),
            "open": 2495.0,
            "high": 2495.0,
            "low": 2489.80,
            "close": 2492.0,
        }
        orch.on_bar(bar, account)

        # Under ADR-024, position should NOT exit because Ask price did not reach 2490.0!
        self.assertIsNotNone(
            account.open_position,
            "Sell position falsely closed because Ask spread was ignored in orchestrator!",
        )

    def test_repro_orchestrator_breakeven_buffer(self):
        """
        Fail Path 4: When be_enabled, orchestrator must move SL to entry + be_buffer
        (ADR-018 / ADR-024). Foundation BaselinePlay keeps be_enabled=False by default.
        """
        orch = StrategyOrchestrator(be_enabled=True)
        account = AccountState(balance=10000.0, equity=10000.0)
        pos = Position(
            direction=Direction.BUY,
            entry_price=2500.0,
            sl_price=2495.0,
            tp_price=2512.5,
            lot_size=0.10,
            open_time=datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc),
            initial_sl_distance=5.0,
        )
        account.open_position = pos

        # Bar reaches 1.0R (2505.0) to trigger BE
        bar = {
            "time": datetime(2026, 9, 14, 10, 15, tzinfo=timezone.utc),
            "open": 2501.0,
            "high": 2505.5,
            "low": 2500.5,
            "close": 2505.0,
        }
        orch.on_bar(bar, account)

        self.assertTrue(account.open_position.be_moved)
        # Under ADR-018/ADR-024, BE SL should be entry (2500.0) + be_buffer (0.10) = 2500.10
        self.assertEqual(account.open_position.sl_price, 2500.10)


if __name__ == "__main__":
    unittest.main()
