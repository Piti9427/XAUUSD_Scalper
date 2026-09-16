import unittest

from scripts.smc.quotes import executable_price, first_exit_from_ticks, ohlc_dual_touch_flag


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
            ohlc_dual_touch_flag(
                sl_touched=True,
                tp_touched=True,
                has_tick_order=True,
                tick_first_exit="SL",
            ),
            "SL",
        )
        self.assertEqual(
            ohlc_dual_touch_flag(
                sl_touched=True,
                tp_touched=True,
                has_tick_order=True,
                tick_first_exit="TP",
            ),
            "TP",
        )
        self.assertEqual(
            ohlc_dual_touch_flag(sl_touched=True, tp_touched=True, has_tick_order=True),
            "AMBIGUOUS",
        )

    def test_first_exit_from_ticks_respects_order(self):
        self.assertEqual(
            first_exit_from_ticks(
                direction="BUY",
                sl_price=1995.0,
                tp_price=2010.0,
                ticks=[2000.0, 2011.0, 1994.0],
            ),
            "TP",
        )
        self.assertEqual(
            first_exit_from_ticks(
                direction="BUY",
                sl_price=1995.0,
                tp_price=2010.0,
                ticks=[2000.0, 1994.0, 2011.0],
            ),
            "SL",
        )
        self.assertEqual(
            first_exit_from_ticks(
                direction="SELL",
                sl_price=2010.0,
                tp_price=1990.0,
                ticks=[(2000.0, 2000.2), (1989.0, 1989.2), (2011.0, 2011.2)],
            ),
            "TP",
        )


if __name__ == "__main__":
    unittest.main()
