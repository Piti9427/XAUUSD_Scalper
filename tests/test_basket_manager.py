"""
tests/test_basket_manager.py — Unit tests for BasketManager

Covers:
  1.  test_open_basket_creates_entry_leg
  2.  test_second_entry_blocked_when_basket_open
  3.  test_recovery_leg_opens_on_mss_repeat
  4.  test_recovery_blocked_at_max_legs
  5.  test_recovery_blocked_when_profitable
  6.  test_recovery_blocked_wrong_direction
  7.  test_basket_tp_closes_all_legs
  8.  test_basket_sl_force_close
  9.  test_state_flat_after_all_legs_closed
  10. test_daily_basket_quota
  11. test_hwm_halt_blocks_new_basket
  12. test_manual_hwm_reset_unhalts

All timestamps are timezone-aware UTC.
"""

import unittest
from datetime import datetime, timezone

from scripts.smc.basket_manager import BasketConfig, BasketManager, BasketState
from scripts.smc.types import Direction, OrderIntentType

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

CFG = BasketConfig(
    basket_fraction=0.15,
    basket_absolute_cap_usd=30.0,
    day_loss_fraction=0.15,
    max_new_baskets_per_utc_day=2,
    recovery_lots=[0.01, 0.02],
    max_recovery_legs=2,
    hwm_halt_fraction=0.20,
    reset_hwm_automatically=False,
)

# Generic signal parameters reused across tests
BUY = Direction.BUY
SELL = Direction.SELL
ENTRY = 2000.0
SL = 1990.0
TP = 2020.0
EQUITY = 200.0  # budget = min(0.15*200, 30) = 30 USD
NOW = datetime(2026, 9, 28, 8, 0, 0, tzinfo=timezone.utc)
NOW_DAY2 = datetime(2026, 9, 29, 8, 0, 0, tzinfo=timezone.utc)


def _make_manager() -> BasketManager:
    """Fresh BasketManager with the shared CFG."""
    return BasketManager(config=CFG)


def _open_basket(mgr: BasketManager, direction: Direction = BUY, now: datetime = NOW) -> list:
    """Helper: fire on_new_signal and return intents."""
    return mgr.on_new_signal(direction, ENTRY, SL, TP, EQUITY, now)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestBasketManager(unittest.TestCase):

    # 1. New signal → PLACE_LIMIT with lot=0.01
    def test_open_basket_creates_entry_leg(self):
        mgr = _make_manager()
        intents = _open_basket(mgr)

        self.assertEqual(len(intents), 1)
        intent = intents[0]
        self.assertEqual(intent.intent_type, OrderIntentType.PLACE_LIMIT)
        self.assertAlmostEqual(intent.lot_size, 0.01)
        self.assertEqual(mgr.state, BasketState.OPEN)
        self.assertAlmostEqual(mgr.basket.frozen_budget_usd, 30.0)

    # 2. Second on_new_signal while OPEN → []
    def test_second_entry_blocked_when_basket_open(self):
        mgr = _make_manager()
        _open_basket(mgr)  # first basket

        intents = _open_basket(mgr)  # should be blocked
        self.assertEqual(intents, [])
        self.assertEqual(mgr.state, BasketState.OPEN)

    # 3. Recovery leg opens when floating_pnl < 0
    def test_recovery_leg_opens_on_mss_repeat(self):
        mgr = _make_manager()
        _open_basket(mgr)

        intents = mgr.on_recovery_signal(BUY, ENTRY, SL, TP, EQUITY, -5.0, NOW)

        self.assertEqual(len(intents), 1)
        intent = intents[0]
        self.assertEqual(intent.intent_type, OrderIntentType.PLACE_LIMIT)
        self.assertAlmostEqual(intent.lot_size, 0.02)

    # 4. 3rd on_recovery_signal → [] (max_recovery_legs=2 already hit after 2 legs total)
    def test_recovery_blocked_at_max_legs(self):
        mgr = _make_manager()
        _open_basket(mgr)                                                     # leg 0
        mgr.on_recovery_signal(BUY, ENTRY, SL, TP, EQUITY, -5.0, NOW)       # leg 1
        # basket now has 2 legs (leg_count == max_recovery_legs == 2)
        intents = mgr.on_recovery_signal(BUY, ENTRY, SL, TP, EQUITY, -10.0, NOW)

        self.assertEqual(intents, [])

    # 5. Recovery blocked when basket profitable
    def test_recovery_blocked_when_profitable(self):
        mgr = _make_manager()
        _open_basket(mgr)

        intents = mgr.on_recovery_signal(BUY, ENTRY, SL, TP, EQUITY, 1.0, NOW)
        self.assertEqual(intents, [])

    # 6. Recovery blocked when direction is opposite
    def test_recovery_blocked_wrong_direction(self):
        mgr = _make_manager()
        _open_basket(mgr, direction=BUY)

        # Opposite direction
        intents = mgr.on_recovery_signal(SELL, ENTRY, SL, TP, EQUITY, -5.0, NOW)
        self.assertEqual(intents, [])

    # 7. on_bar with floating_pnl=+1.0 → CLOSE_MARKET for all open legs
    def test_basket_tp_closes_all_legs(self):
        mgr = _make_manager()
        _open_basket(mgr)
        mgr.on_recovery_signal(BUY, ENTRY, SL, TP, EQUITY, -5.0, NOW)  # add recovery leg

        # Both legs are open, floating PnL turns positive → basket TP
        intents = mgr.on_bar(floating_pnl=1.0, equity=EQUITY, now=NOW)

        close_intents = [i for i in intents if i.intent_type == OrderIntentType.CLOSE_MARKET]
        self.assertEqual(len(close_intents), 2)
        self.assertEqual(mgr.state, BasketState.CLOSE_PENDING)

    # 8. on_bar with floating_pnl=-31.0 (budget=$30) → CLOSE_MARKET (SL breached)
    def test_basket_sl_force_close(self):
        mgr = _make_manager()
        _open_basket(mgr)  # budget = $30 (min(0.15*200, 30))

        # net_pnl = 0 + (-31) = -31 <= -30 → SL breached
        intents = mgr.on_bar(floating_pnl=-31.0, equity=EQUITY, now=NOW)

        close_intents = [i for i in intents if i.intent_type == OrderIntentType.CLOSE_MARKET]
        self.assertGreater(len(close_intents), 0)
        self.assertEqual(mgr.state, BasketState.CLOSE_PENDING)

    # 9. After on_leg_closed for all legs → state == FLAT
    def test_state_flat_after_all_legs_closed(self):
        mgr = _make_manager()
        _open_basket(mgr)  # leg 0

        mgr.on_bar(floating_pnl=1.0, equity=EQUITY, now=NOW)  # triggers CLOSE_PENDING

        # Simulate broker confirming all open legs closed
        mgr.on_leg_closed(leg_index=0, realized_pnl=1.0)

        self.assertEqual(mgr.state, BasketState.FLAT)
        self.assertIsNone(mgr.basket)

    # 10. Daily basket quota — 3rd basket on same UTC day → []
    def test_daily_basket_quota(self):
        mgr = _make_manager()

        # First basket
        intents1 = _open_basket(mgr, now=NOW)
        self.assertEqual(len(intents1), 1)
        # Close it so state returns to FLAT for the next open
        mgr.on_bar(floating_pnl=1.0, equity=EQUITY, now=NOW)
        mgr.on_leg_closed(0, 1.0)

        # Second basket — same day
        intents2 = _open_basket(mgr, now=NOW)
        self.assertEqual(len(intents2), 1)
        mgr.on_bar(floating_pnl=1.0, equity=EQUITY, now=NOW)
        mgr.on_leg_closed(0, 1.0)

        # Third basket — same day → quota exceeded
        intents3 = _open_basket(mgr, now=NOW)
        self.assertEqual(intents3, [])

    # 11. HWM halt blocks new basket
    def test_hwm_halt_blocks_new_basket(self):
        mgr = _make_manager()
        # Day 1: open and close a basket — this seeds HWM = 200
        _open_basket(mgr, now=NOW)
        mgr.on_bar(floating_pnl=1.0, equity=EQUITY, now=NOW)
        mgr.on_leg_closed(0, 1.0)
        # Day 2: equity collapses to 158 → drawdown = 21% > hwm_halt_fraction(20%).
        # Using NOW_DAY2 avoids the daily-loss guard from day 1 blocking us first.
        low_equity = 158.0
        intents = mgr.on_new_signal(BUY, ENTRY, SL, TP, low_equity, NOW_DAY2)
        self.assertEqual(intents, [])
        self.assertEqual(mgr.state, BasketState.HALTED)

    # 12. reset_hwm() restores FLAT from HALTED
    def test_manual_hwm_reset_unhalts(self):
        mgr = _make_manager()
        # Seed HWM on day 1
        _open_basket(mgr, now=NOW)
        mgr.on_bar(floating_pnl=1.0, equity=EQUITY, now=NOW)
        mgr.on_leg_closed(0, 1.0)
        # Day 2: trigger HWM halt
        low_equity = 158.0
        mgr.on_new_signal(BUY, ENTRY, SL, TP, low_equity, NOW_DAY2)
        self.assertEqual(mgr.state, BasketState.HALTED)

        mgr.reset_hwm(low_equity)
        self.assertEqual(mgr.state, BasketState.FLAT)
        self.assertFalse(mgr.is_halted)

    # 13. Basket TP strictly requires > 0.0, never fires at 0.0
    def test_basket_tp_does_not_fire_at_zero_pnl(self):
        mgr = _make_manager()
        _open_basket(mgr)
        # floating_pnl=0.0 must NOT trigger basket TP
        intents = mgr.on_bar(floating_pnl=0.0, equity=EQUITY, now=NOW)
        self.assertEqual(intents, [])
        self.assertEqual(mgr.state, BasketState.OPEN)

    # 14. CLOSE_PENDING auto-clears to FLAT on next bar
    def test_close_pending_auto_clears_to_flat_on_next_bar(self):
        mgr = _make_manager()
        _open_basket(mgr)
        # Trigger SL -> state becomes CLOSE_PENDING
        intents = mgr.on_bar(floating_pnl=-31.0, equity=EQUITY, now=NOW)
        self.assertEqual(mgr.state, BasketState.CLOSE_PENDING)
        # Next bar -> optimistic close clears state to FLAT automatically
        next_bar = datetime(2026, 9, 28, 8, 15, 0, tzinfo=timezone.utc)
        intents2 = mgr.on_bar(floating_pnl=0.0, equity=EQUITY, now=next_bar)
        self.assertEqual(intents2, [])
        self.assertEqual(mgr.state, BasketState.FLAT)
        self.assertIsNone(mgr.basket)


if __name__ == "__main__":
    unittest.main()
