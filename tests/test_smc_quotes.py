import unittest

from scripts.smc.quotes import executable_price, ohlc_dual_touch_flag


class QuoteSideTests(unittest.TestCase):
    def test_buy_ask_sell_bid_without_invention(self):
        px, side = executable_price(direction="BUY", bid=10.0, ask=10.2)
        self.assertEqual((px, side), (10.2, "ask"))
        px, side = executable_price(direction="SELL", bid=10.0, ask=10.2)
        self.assertEqual((px, side), (10.0, "bid"))
        px, side = executable_price(direction="BUY", bid=10.0, ask=None)
        self.assertIsNone(px)
        self.assertEqual(side, "missing_ask")

    def test_dual_touch_without_ticks_is_ambiguous(self):
        self.assertEqual(
            ohlc_dual_touch_flag(sl_touched=True, tp_touched=True, has_tick_order=False),
            "AMBIGUOUS",
        )
        self.assertEqual(
            ohlc_dual_touch_flag(sl_touched=True, tp_touched=True, has_tick_order=True),
            "SL",
        )


if __name__ == "__main__":
    unittest.main()
