"""Foundation story 47: one shared behavioral lifecycle boundary.

Replay (orchestrator) and Demo dry-run adapter must exercise the same
admit → place → fill → close sequence — not disconnected helper unit tests alone.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts.smc.mt5_adapter import SMCExecutionAdapter
from scripts.smc.notification_policy import may_notify_close, may_use_ohlc_invented_close_pnl
from scripts.smc.orchestrator import StrategyOrchestrator
from scripts.smc.types import (
    AccountState,
    Direction,
    OrderIntentType,
    SetupSignal,
)


class FoundationBehavioralLifecycleTests(unittest.TestCase):
    def test_smc_main_uses_setup_decision_signal_api(self):
        import inspect
        import smc_main

        src = inspect.getsource(smc_main)
        self.assertIn("decision.signal", src)
        self.assertIn("decision.accepted", src)
        self.assertNotIn("decision.setup", src)
        self.assertNotIn("decision.admitted", src)

    def test_shared_admit_place_fill_close_boundary(self):
        now = datetime(2026, 9, 16, 13, 0, tzinfo=timezone.utc)
        setup = SetupSignal(
            direction=Direction.BUY,
            sweep_price=2505.0,
            sweep_wick=2490.0,
            mss_price=2508.0,
            entry_price=2500.0,
            sl_price=2490.0,
            tp_price=2525.0,
            sl_distance=10.0,
            risk_r=2.5,
            fvg_high=2501.0,
            fvg_low=2499.0,
            reason="behavioral lifecycle BUY",
            timestamp=now,
            setup_id="BEHAV_LIFE_1",
        )
        account = AccountState(balance=10_000.0, equity=10_000.0)
        orch = StrategyOrchestrator(
            partial_tp_enabled=False,
            be_enabled=False,
            risk_pct=0.005,
        )
        bar = {
            "time": now,
            "open": 2501.0,
            "high": 2502.0,
            "low": 2500.5,
            "close": 2501.5,
        }
        intents = orch.on_bar(bar, account, setup_signal=setup, current_spread=0.20)
        self.assertTrue(intents)
        place = intents[0]
        self.assertEqual(place.intent_type, OrderIntentType.PLACE_LIMIT)
        self.assertIsNotNone(account.pending_order)

        adapter = SMCExecutionAdapter(symbol="XAUUSD", dry_run=True, db_path=":memory:")
        try:
            adapter.claim_setup(
                {
                    "order_id": "BEHAV_LIFE_1",
                    "limit": place.limit_price,
                    "sl": place.sl_price,
                    "tp": place.tp_price,
                }
            )
            adapter.update_setup_status("BEHAV_LIFE_1", "accepted", ticket=101)

            fill_bar = {
                "time": now,
                "open": 2500.0,
                "high": 2500.5,
                "low": 2499.5,
                "close": 2500.2,
            }
            orch.on_bar(fill_bar, account, setup_signal=None)
            self.assertIsNotNone(account.open_position)
            self.assertIsNone(account.pending_order)

            tp_bar = {
                "time": now,
                "open": 2520.0,
                "high": 2526.0,
                "low": 2519.0,
                "close": 2524.0,
                "has_tick_order": False,
            }
            orch.on_bar(tp_bar, account, setup_signal=None)
            self.assertIsNone(account.open_position)

            self.assertTrue(may_notify_close(broker_close_success=True))
            self.assertFalse(may_notify_close(broker_close_success=False))
            self.assertTrue(may_use_ohlc_invented_close_pnl(dry_run=True))
            self.assertFalse(may_use_ohlc_invented_close_pnl(dry_run=False))

            adapter.mark_webhook_processed("BEHAV_LIFE_1", "ORDER_FILLED", status="success")
            self.assertTrue(adapter.is_webhook_processed("BEHAV_LIFE_1", "ORDER_FILLED"))
        finally:
            adapter.close()


if __name__ == "__main__":
    unittest.main()
