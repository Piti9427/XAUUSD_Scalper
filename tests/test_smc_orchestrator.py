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
        # Opt-in BE path (foundation BaselinePlay keeps be_enabled=False)
        orch = StrategyOrchestrator(be_enabled=True, be_trigger_r=1.0)
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
        intents1 = orch.on_bar(bar1, account)
        self.assertIsNotNone(account.open_position)
        self.assertIsNone(account.pending_order)
        self.assertEqual(account.open_position.entry_price, 2010.0)

        # Bar 2: Price reaches +1.0R (2010.0 + 5.00 = 2015.00) -> High touches 2015.5
        # Must emit MOVE_SL_TO_BE!
        bar2 = {"time": datetime(2026, 3, 2, 8, 40, tzinfo=timezone.utc), "open": 2011, "high": 2015.5, "low": 2010.8, "close": 2015.0}
        intents2 = orch.on_bar(bar2, account)
        self.assertEqual(len(intents2), 1)
        self.assertEqual(intents2[0].intent_type, OrderIntentType.MOVE_SL_TO_BE)
        self.assertTrue(account.open_position.be_moved)

    def test_foundation_baseline_does_not_move_be(self):
        limit_order = OrderIntent(
            intent_type=OrderIntentType.PLACE_LIMIT,
            direction=Direction.BUY,
            limit_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            lot_size=0.10,
            expire_bars=4,
        )
        account = AccountState(
            balance=10000.0,
            equity=10000.0,
            pending_order=limit_order,
            pending_bars_held=0,
        )
        bar1 = {"time": datetime(2026, 3, 2, 8, 35, tzinfo=timezone.utc), "open": 2012, "high": 2013, "low": 2009.5, "close": 2011}
        self.orchestrator.on_bar(bar1, account)
        bar2 = {"time": datetime(2026, 3, 2, 8, 40, tzinfo=timezone.utc), "open": 2011, "high": 2015.5, "low": 2010.8, "close": 2015.0}
        intents2 = self.orchestrator.on_bar(bar2, account)
        self.assertEqual(intents2, [])
        self.assertFalse(account.open_position.be_moved)
        self.assertEqual(account.open_position.sl_price, 2005.0)

    def test_lot_size_uses_min_balance_equity(self):
        signal = SetupSignal(
            direction=Direction.BUY,
            sweep_price=2010.0,
            sweep_wick=2000.0,
            mss_price=2014.0,
            entry_price=2010.0,
            sl_price=2000.0,
            tp_price=2030.0,
            sl_distance=10.0,
            risk_r=2.0,
            fvg_high=2011.0,
            fvg_low=2009.0,
            reason="BUY SMC Setup",
            timestamp=datetime(2026, 3, 2, 8, 5, tzinfo=timezone.utc),
        )
        bar = {"time": datetime(2026, 3, 2, 8, 35, tzinfo=timezone.utc), "open": 2012, "high": 2013, "low": 2011.0, "close": 2012}
        orch = StrategyOrchestrator(risk_pct=0.005)
        rich = AccountState(balance=10000.0, equity=10000.0)
        poor_equity = AccountState(balance=10000.0, equity=5000.0)
        orch.on_bar(bar, rich, setup_signal=signal, current_spread=0.15, max_spread=0.35)
        orch.on_bar(bar, poor_equity, setup_signal=signal, current_spread=0.15, max_spread=0.35)
        self.assertIsNotNone(rich.pending_order)
        self.assertIsNotNone(poor_equity.pending_order)
        self.assertGreater(rich.pending_order.lot_size, poor_equity.pending_order.lot_size)

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

    def test_pending_fill_survives_spread_blowout(self):
        # Foundation scenario 15: high spread after pending accepted must not erase fill.
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
        # Price touches 2009.5 <= 2010.0 even with spread 0.50 > max 0.35
        bar = {"time": datetime(2026, 3, 2, 8, 35, tzinfo=timezone.utc), "open": 2012, "high": 2013, "low": 2009.5, "close": 2011}
        self.orchestrator.on_bar(bar, account, current_spread=0.50, max_spread=0.35)
        self.assertIsNotNone(account.open_position)
        self.assertIsNone(account.pending_order)
        self.assertEqual(account.open_position.entry_price, 2010.0)

    def test_new_setup_uses_configured_risk_pct(self):
        signal = SetupSignal(
            direction=Direction.BUY,
            sweep_price=2010.0,
            sweep_wick=2000.0,
            mss_price=2014.0,
            entry_price=2010.0,
            sl_price=2000.0,
            tp_price=2030.0,
            sl_distance=10.0,
            risk_r=2.0,
            fvg_high=2011.0,
            fvg_low=2009.0,
            reason="BUY SMC Setup",
            timestamp=datetime(2026, 3, 2, 8, 5, tzinfo=timezone.utc),
        )
        bar = {"time": datetime(2026, 3, 2, 8, 35, tzinfo=timezone.utc), "open": 2012, "high": 2013, "low": 2011.0, "close": 2012}
        half = StrategyOrchestrator(risk_pct=0.005)
        full = StrategyOrchestrator(risk_pct=0.01)
        acct_half = AccountState(balance=10000.0, equity=10000.0)
        acct_full = AccountState(balance=10000.0, equity=10000.0)
        half.on_bar(bar, acct_half, setup_signal=signal, current_spread=0.15, max_spread=0.35)
        full.on_bar(bar, acct_full, setup_signal=signal, current_spread=0.15, max_spread=0.35)
        self.assertIsNotNone(acct_half.pending_order)
        self.assertIsNotNone(acct_full.pending_order)
        self.assertGreater(acct_full.pending_order.lot_size, acct_half.pending_order.lot_size)

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

    def test_partial_take_profit_triggers_and_moves_sl_to_be(self):
        orch = StrategyOrchestrator(partial_tp_enabled=True, partial_tp_r=1.0, partial_tp_ratio=0.5)
        pos = Position(
            direction=Direction.BUY,
            entry_price=2000.0,
            sl_price=1995.0,
            tp_price=2010.0,
            lot_size=0.10,
            open_time=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            initial_sl_distance=5.0,
        )
        account = AccountState(balance=10000.0, equity=10000.0, open_position=pos)

        # Bar reaches 2005.0 (+1.0R): triggers Partial TP and BE move
        bar = {"time": datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc), "open": 2002, "high": 2005.5, "low": 2001, "close": 2005}
        intents = orch.on_bar(bar, account)

        intent_types = [i.intent_type for i in intents]
        self.assertIn(OrderIntentType.PARTIAL_CLOSE, intent_types)
        self.assertIn(OrderIntentType.MOVE_SL_TO_BE, intent_types)
        self.assertTrue(pos.partial_closed)
        self.assertTrue(pos.be_moved)
        self.assertEqual(pos.sl_price, 2000.0 + orch.be_buffer)
        self.assertAlmostEqual(pos.lot_size, 0.05)

    def test_partial_skips_when_residual_would_floor_up_past_min_lot(self):
        """Risk invariant: never invent residual lot via max(0.01, remaining)."""
        orch = StrategyOrchestrator(partial_tp_enabled=True, partial_tp_r=1.0, partial_tp_ratio=0.5)
        pos = Position(
            direction=Direction.BUY,
            entry_price=2000.0,
            sl_price=1995.0,
            tp_price=2010.0,
            lot_size=0.01,  # half rounds below broker min lot
            open_time=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            initial_sl_distance=5.0,
        )
        account = AccountState(balance=10000.0, equity=10000.0, open_position=pos)
        bar = {
            "time": datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc),
            "open": 2002,
            "high": 2005.5,
            "low": 2001,
            "close": 2005,
        }
        intents = orch.on_bar(bar, account)
        intent_types = [i.intent_type for i in intents]
        self.assertNotIn(OrderIntentType.PARTIAL_CLOSE, intent_types)
        self.assertFalse(pos.partial_closed)
        self.assertAlmostEqual(pos.lot_size, 0.01)

    def test_fill_bar_immediate_stop_out(self):
        # Pending BUY limit at 2010.0, SL at 2005.0, TP at 2020.0
        limit_order = OrderIntent(
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
            pending_order=limit_order,
            pending_bars_held=0,
        )
        # Bar opens at 2012.0, plunges to 2003.0 (fills at 2010.0 and breaches SL at 2005.0!)
        bar = {
            "time": datetime(2026, 3, 2, 8, 35, tzinfo=timezone.utc),
            "open": 2012.0,
            "high": 2012.0,
            "low": 2003.0,
            "close": 2004.0,
        }
        intents = self.orchestrator.on_bar(bar, account)
        self.assertIsNone(account.pending_order)
        self.assertIsNone(account.open_position)
        self.assertEqual(account.daily_loss_count, 1)
        self.assertIsNotNone(account.last_loss_time)

    def test_ohlc_dual_touch_without_ticks_is_ambiguous(self):
        pos = Position(
            direction=Direction.BUY,
            entry_price=2000.0,
            sl_price=1995.0,
            tp_price=2010.0,
            lot_size=0.10,
            open_time=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            initial_sl_distance=5.0,
        )
        account = AccountState(balance=10000.0, equity=10000.0, open_position=pos)
        bar = {
            "time": datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc),
            "open": 2000.0,
            "high": 2011.0,
            "low": 1994.0,
            "close": 2002.0,
        }
        intents = self.orchestrator.on_bar(bar, account)
        self.assertIsNone(account.open_position)
        self.assertEqual(account.daily_loss_count, 0)
        self.assertIsNone(account.last_loss_time)
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].intent_type, OrderIntentType.CLOSE_MARKET)
        self.assertIn("AMBIGUOUS", intents[0].reason)
        self.assertIn("SL", intents[0].reason)
        self.assertIn("TP", intents[0].reason)

    def test_dual_touch_with_tick_order_keeps_sl_path(self):
        pos = Position(
            direction=Direction.BUY,
            entry_price=2000.0,
            sl_price=1995.0,
            tp_price=2010.0,
            lot_size=0.10,
            open_time=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            initial_sl_distance=5.0,
        )
        account = AccountState(balance=10000.0, equity=10000.0, open_position=pos)
        bar = {
            "time": datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc),
            "open": 2000.0,
            "high": 2011.0,
            "low": 1994.0,
            "close": 2002.0,
            "has_tick_order": True,
            "ticks": [2000.0, 1994.0, 2011.0],
        }
        intents = self.orchestrator.on_bar(bar, account)
        self.assertIsNone(account.open_position)
        self.assertEqual(account.daily_loss_count, 1)
        self.assertEqual(intents, [])

    def test_dual_touch_tick_order_can_take_tp_first(self):
        pos = Position(
            direction=Direction.BUY,
            entry_price=2000.0,
            sl_price=1995.0,
            tp_price=2010.0,
            lot_size=0.10,
            open_time=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            initial_sl_distance=5.0,
        )
        account = AccountState(balance=10000.0, equity=10000.0, open_position=pos)
        bar = {
            "time": datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc),
            "open": 2000.0,
            "high": 2011.0,
            "low": 1994.0,
            "close": 2002.0,
            "has_tick_order": True,
            "ticks": [2000.0, 2011.0, 1994.0],
        }
        intents = self.orchestrator.on_bar(bar, account)
        self.assertIsNone(account.open_position)
        self.assertEqual(account.daily_loss_count, 0)
        self.assertEqual(intents, [])

    def test_time_exit_after_max_hold_bars_profit_loss_flat(self):
        orch = StrategyOrchestrator(max_hold_bars=2, be_trigger_r=99.0)

        def run_case(close_px: float):
            pos = Position(
                direction=Direction.BUY,
                entry_price=2000.0,
                sl_price=1990.0,
                tp_price=2030.0,
                lot_size=0.10,
                open_time=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
                initial_sl_distance=10.0,
            )
            account = AccountState(balance=10000.0, equity=10000.0, open_position=pos)
            bar1 = {
                "time": datetime(2026, 3, 2, 8, 5, tzinfo=timezone.utc),
                "open": 2000.0,
                "high": 2001.0,
                "low": 1999.0,
                "close": 2000.5,
            }
            bar2 = {
                "time": datetime(2026, 3, 2, 8, 10, tzinfo=timezone.utc),
                "open": 2000.5,
                "high": max(close_px, 2000.5),
                "low": min(close_px, 1999.0),
                "close": close_px,
            }
            self.assertEqual(orch.on_bar(bar1, account), [])
            self.assertIsNotNone(account.open_position)
            intents = orch.on_bar(bar2, account)
            self.assertIsNone(account.open_position)
            self.assertEqual(len(intents), 1)
            self.assertIn("TIME_EXIT", intents[0].reason)
            return close_px - 2000.0

        self.assertGreater(run_case(2005.0), 0)  # profit path counted
        self.assertLess(run_case(1995.0), 0)  # loss path counted
        self.assertEqual(run_case(2000.0), 0)  # flat path counted

    def test_time_exit_on_clock_without_new_bar(self):
        orch = StrategyOrchestrator(max_hold_bars=2, bar_minutes=5, partial_tp_enabled=False)
        pos = Position(
            direction=Direction.BUY,
            entry_price=2000.0,
            sl_price=1990.0,
            tp_price=2030.0,
            lot_size=0.10,
            open_time=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            initial_sl_distance=10.0,
        )
        account = AccountState(balance=10000.0, equity=10000.0, open_position=pos)
        early = orch.on_clock(account, datetime(2026, 3, 2, 8, 5, tzinfo=timezone.utc))
        self.assertEqual(early, [])
        self.assertIsNotNone(account.open_position)
        late = orch.on_clock(account, datetime(2026, 3, 2, 8, 10, tzinfo=timezone.utc))
        self.assertEqual(len(late), 1)
        self.assertEqual(late[0].intent_type, OrderIntentType.CLOSE_MARKET)
        self.assertIn("TIME_EXIT", late[0].reason)
        # Local state stays open until broker evidence arrives.
        self.assertIsNotNone(account.open_position)

    def test_news_blackout_cancels_pending_but_fill_wins_same_bar(self):
        pending = OrderIntent(
            intent_type=OrderIntentType.PLACE_LIMIT,
            direction=Direction.BUY,
            limit_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            lot_size=0.10,
            expire_bars=3,
            order_id="NEWS1",
        )
        # No touch -> cancel
        account = AccountState(
            balance=10000.0, equity=10000.0, pending_order=pending, pending_bars_held=0
        )
        bar = {
            "time": datetime(2026, 3, 2, 8, 35, tzinfo=timezone.utc),
            "open": 2014, "high": 2015, "low": 2012, "close": 2013,
        }
        intents = self.orchestrator.on_bar(
            bar, account, news_cancel_pending=True, news_cancel_reason="news_blackout:NFP"
        )
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].intent_type, OrderIntentType.CANCEL_LIMIT)
        self.assertIsNone(account.pending_order)

        # Touch + news cancel flag -> fill wins (hold through news)
        pending2 = OrderIntent(
            intent_type=OrderIntentType.PLACE_LIMIT,
            direction=Direction.BUY,
            limit_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            lot_size=0.10,
            expire_bars=3,
            order_id="NEWS2",
        )
        account2 = AccountState(
            balance=10000.0, equity=10000.0, pending_order=pending2, pending_bars_held=0
        )
        fill_bar = {
            "time": datetime(2026, 3, 2, 8, 40, tzinfo=timezone.utc),
            "open": 2012, "high": 2013, "low": 2009.5, "close": 2011,
        }
        self.orchestrator.on_bar(
            fill_bar, account2, news_cancel_pending=True, news_cancel_reason="news_blackout:NFP"
        )
        self.assertIsNotNone(account2.open_position)
        self.assertIsNone(account2.pending_order)


if __name__ == "__main__":
    unittest.main()
