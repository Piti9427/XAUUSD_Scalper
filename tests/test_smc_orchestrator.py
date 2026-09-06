import unittest
from datetime import datetime, timezone, timedelta, time
import pandas as pd
from scripts.smc.types import (
    Direction,
    OrderIntentType,
    OrderIntent,
    Position,
    AccountState,
    SetupSignal,
    LiquidityLevels
)
from scripts.smc.orchestrator import StrategyOrchestrator


class TestSMCOrchestrator(unittest.TestCase):
    def setUp(self):
        self.orchestrator = StrategyOrchestrator()

    def test_ttl_expiration_after_3_bars(self):
        # Scenario: Limit order is pending. 3 bars pass without price touching limit_price.
        # On 3rd bar, CANCEL_LIMIT must be emitted.
        initial_order = OrderIntent(
            intent_type=OrderIntentType.PLACE_LIMIT,
            direction=Direction.BUY,
            limit_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            lot_size=0.10,
            expire_bars=3
        )
        account = AccountState(
            balance=10000.0,
            equity=10000.0,
            pending_order=initial_order,
            pending_bars_held=0
        )
        
        # Bar 1: Price stays above limit_price (high=2015, low=2012) -> pending_bars_held becomes 1
        bar1 = {"time": datetime(2026, 3, 2, 8, 35, tzinfo=timezone.utc), "open": 2014, "high": 2015, "low": 2012, "close": 2013}
        intents1 = self.orchestrator.on_bar(bar1, account)
        self.assertEqual(intents1, [])
        self.assertEqual(account.pending_bars_held, 1)

        # Bar 2: Price stays above (high=2014, low=2011) -> pending_bars_held becomes 2
        bar2 = {"time": datetime(2026, 3, 2, 8, 40, tzinfo=timezone.utc), "open": 2013, "high": 2014, "low": 2011, "close": 2012}
        intents2 = self.orchestrator.on_bar(bar2, account)
        self.assertEqual(intents2, [])
        self.assertEqual(account.pending_bars_held, 2)

        # Bar 3: Price still doesn't touch (high=2013, low=2010.5) -> TTL reached (3 bars)! CANCEL_LIMIT emitted
        bar3 = {"time": datetime(2026, 3, 2, 8, 45, tzinfo=timezone.utc), "open": 2012, "high": 2013, "low": 2010.5, "close": 2011}
        intents3 = self.orchestrator.on_bar(bar3, account)
        self.assertEqual(len(intents3), 1)
        self.assertEqual(intents3[0].intent_type, OrderIntentType.CANCEL_LIMIT)
        self.assertIsNone(account.pending_order)

    def test_limit_order_fills_and_moves_to_be_at_1r(self):
        # Scenario: Limit order filled on Bar 1, then reaches +1.0R on Bar 2 -> MOVE_SL_TO_BE emitted
        limit_order = OrderIntent(
            intent_type=OrderIntentType.PLACE_LIMIT,
            direction=Direction.BUY,
            limit_price=2010.0,
            sl_price=2005.0, # SL distance = $5.00
            tp_price=2020.0, # +2.0R
            lot_size=0.10,
            expire_bars=3
        )
        account = AccountState(
            balance=10000.0,
            equity=10000.0,
            pending_order=limit_order,
            pending_bars_held=0
        )
        
        # Bar 1: Low dips to 2009.5 (touches 2010.0) -> Limit order fills! Position opened
        bar1 = {"time": datetime(2026, 3, 2, 8, 35, tzinfo=timezone.utc), "open": 2012, "high": 2013, "low": 2009.5, "close": 2011}
        intents1 = self.orchestrator.on_bar(bar1, account)
        self.assertIsNotNone(account.open_position)
        self.assertIsNone(account.pending_order)
        self.assertEqual(account.open_position.entry_price, 2010.0)

        # Bar 2: Price reaches +1.0R (2010.0 + 5.00 = 2015.00) -> High touches 2015.5
        # Must emit MOVE_SL_TO_BE!
        bar2 = {"time": datetime(2026, 3, 2, 8, 40, tzinfo=timezone.utc), "open": 2011, "high": 2015.5, "low": 2010.8, "close": 2015.0}
        intents2 = self.orchestrator.on_bar(bar2, account)
        self.assertEqual(len(intents2), 1)
        self.assertEqual(intents2[0].intent_type, OrderIntentType.MOVE_SL_TO_BE)
        self.assertTrue(account.open_position.be_moved)

    def test_rollover_flat_before_21_utc(self):
        # Scenario: Position is open at 20:55 UTC. Must emit CLOSE_MARKET before 21:00 UTC rollover.
        position = Position(
            direction=Direction.BUY,
            entry_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            lot_size=0.10,
            open_time=datetime(2026, 3, 2, 14, 0, tzinfo=timezone.utc),
            initial_sl_distance=5.0
        )
        account = AccountState(
            balance=10000.0,
            equity=10000.0,
            open_position=position
        )
        
        # Bar at 20:55 UTC
        bar_rollover = {"time": datetime(2026, 3, 2, 20, 55, tzinfo=timezone.utc), "open": 2012, "high": 2013, "low": 2011, "close": 2012}
        intents = self.orchestrator.on_bar(bar_rollover, account)
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].intent_type, OrderIntentType.CLOSE_MARKET)
        self.assertIn("Rollover Flat", intents[0].reason)

    def test_daily_circuit_breaker_halts_trading(self):
        # Scenario: Account already experienced 2 realized losses today.
        account = AccountState(
            balance=9900.0,
            equity=9900.0,
            daily_loss_count=2,
            current_utc_date="2026-03-02"
        )
        bar = {"time": datetime(2026, 3, 2, 13, 0, tzinfo=timezone.utc), "open": 2010, "high": 2012, "low": 2008, "close": 2011}
        intents = self.orchestrator.on_bar(bar, account)
        self.assertEqual(intents, [])

    def test_cooldown_timer_blocks_for_30_minutes(self):
        # Loss occurred 15 minutes ago
        loss_time = datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc)
        account = AccountState(
            balance=9950.0,
            equity=9950.0,
            daily_loss_count=1,
            last_loss_time=loss_time,
            current_utc_date="2026-03-02"
        )
        bar = {"time": datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc), "open": 2010, "high": 2012, "low": 2008, "close": 2011}
        # Under cooldown (15 < 30 min) -> No action
        intents = self.orchestrator.on_bar(bar, account)
        self.assertEqual(intents, [])

    def test_spread_guard_blocks_fill_when_blown_out(self):
        # Scenario: Limit order touched, but live spread is 0.50 (> 0.35 max)
        initial_order = OrderIntent(
            intent_type=OrderIntentType.PLACE_LIMIT,
            direction=Direction.BUY,
            limit_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            lot_size=0.10,
            expire_bars=3,
        )
        account = AccountState(
            balance=10000.0,
            equity=10000.0,
            pending_order=initial_order,
            pending_bars_held=0,
        )
        # Price touches 2009.5 <= 2010.0, but spread is 0.50
        bar = {"time": datetime(2026, 3, 2, 8, 35, tzinfo=timezone.utc), "open": 2012, "high": 2013, "low": 2009.5, "close": 2011}
        intents = self.orchestrator.on_bar(bar, account, current_spread=0.50, max_spread=0.35)
        self.assertEqual(intents, [])
        self.assertIsNone(account.open_position)
        self.assertIsNotNone(account.pending_order)
        self.assertEqual(account.pending_bars_held, 1)

    def test_spread_guard_blocks_new_order_when_blown_out(self):
        account = AccountState(balance=10000.0, equity=10000.0)
        signal = SetupSignal(
            direction=Direction.BUY,
            sweep_price=2010.0,
            sweep_wick=2008.5,
            mss_price=2014.0,
            entry_price=2014.0,
            sl_price=2008.2,
            tp_price=2025.6,
            sl_distance=5.8,
            risk_r=2.0,
            fvg_high=2015.0,
            fvg_low=2013.0,
            reason="BUY SMC Setup",
            timestamp=datetime(2026, 3, 2, 8, 5, tzinfo=timezone.utc),
        )
        bar = {"time": datetime(2026, 3, 2, 8, 35, tzinfo=timezone.utc), "open": 2012, "high": 2013, "low": 2011.0, "close": 2012}
        intents = self.orchestrator.on_bar(bar, account, setup_signal=signal, current_spread=0.45, max_spread=0.35)
        self.assertEqual(intents, [])
        self.assertIsNone(account.pending_order)


if __name__ == "__main__":
    unittest.main()
