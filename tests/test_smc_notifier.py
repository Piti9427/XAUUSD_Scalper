import unittest
from datetime import datetime, timezone
from scripts.smc.types import Direction, SetupSignal, Position
from scripts.smc.notifier import (
    format_smc_trade_card,
    format_order_filled_card,
    format_be_moved_card,
    format_partial_tp_card,
    format_trade_closed_card,
    format_circuit_breaker_card,
)


class TestSMCNotifier(unittest.TestCase):
    def test_format_smc_trade_card_buy(self):
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
            reason="BUY SMC Setup: Swept 2010.0 -> MSS 2014.0",
            timestamp=datetime(2026, 3, 2, 8, 5, tzinfo=timezone.utc)
        )
        card = format_smc_trade_card(signal, lot_size=0.08, risk_amount=50.0)
        
        self.assertIn("XAUUSD SMC SIGNAL: BUY", card)
        self.assertIn("2014.00", card)
        self.assertIn("2008.20", card)
        self.assertIn("2025.60", card)
        self.assertIn("0.08 Lot", card)
        self.assertIn("1:2.0", card)

    def test_format_order_filled_card(self):
        pos = Position(
            direction=Direction.BUY,
            entry_price=2014.0,
            sl_price=2008.2,
            tp_price=2025.6,
            lot_size=0.08,
            open_time=datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc),
            initial_sl_distance=5.8,
        )
        card = format_order_filled_card(pos)
        self.assertIn("ORDER FILLED: BUY", card)
        self.assertIn("2014.00", card)
        self.assertIn("0.08 Lot", card)

    def test_format_be_moved_card(self):
        pos = Position(
            direction=Direction.BUY,
            entry_price=2014.0,
            sl_price=2014.0,
            tp_price=2025.6,
            lot_size=0.08,
            open_time=datetime(2026, 3, 2, 8, 15, tzinfo=timezone.utc),
            initial_sl_distance=5.8,
            be_moved=True,
        )
        card = format_be_moved_card(pos)
        self.assertIn("BREAKEVEN SECURED: BUY", card)
        self.assertIn("2014.00", card)

    def test_format_trade_closed_card(self):
        # Win card
        win_card = format_trade_closed_card(
            direction=Direction.BUY,
            exit_price=2025.6,
            pnl_dollars=100.0,
            pnl_r=2.0,
            reason="TP reached",
        )
        self.assertIn("TRADE CLOSED (BUY)", win_card)
        self.assertIn("WIN", win_card)
        self.assertIn("+100.00", win_card)
        self.assertIn("+2.00R", win_card)

        # Loss card
        loss_card = format_trade_closed_card(
            direction=Direction.SELL,
            exit_price=2010.0,
            pnl_dollars=-50.0,
            pnl_r=-1.0,
            reason="SL hit",
        )
        self.assertIn("TRADE CLOSED (SELL)", loss_card)
        self.assertIn("LOSS", loss_card)
        self.assertIn("-50.00", loss_card)

    def test_format_circuit_breaker_card(self):
        card = format_circuit_breaker_card(losses_today=2, cooldown_mins=30)
        self.assertIn("CIRCUIT BREAKER ACTIVATED", card)
        self.assertIn("2/2", card)
        self.assertIn("30 minutes", card)

    def test_format_partial_tp_card(self):
        card = format_partial_tp_card(
            direction=Direction.BUY,
            closed_lot=0.04,
            remaining_lot=0.04,
            r_multiple=1.0,
            entry_price=2014.0,
        )
        self.assertIn("PARTIAL TAKE PROFIT HIT!", card)
        self.assertIn("+1.0R Profit Locked In", card)
        self.assertIn("0.04 lots", card)
        self.assertIn("2014.00", card)


if __name__ == "__main__":
    unittest.main()
