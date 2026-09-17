import unittest

from scripts.smc.quotes import (
    executable_price,
    first_exit_from_ticks,
    ohlc_dual_touch_flag,
    pending_sl_touched_before_fill,
)


class QuoteSideTests(unittest.TestCase):
    def test_buy_ask_sell_bid_without_invention(self):
        px, side = executable_price(direction="BUY", bid=10.0, ask=10.2)
        self.assertEqual((px, side), (10.2, "ask"))
        px, side = executable_price(direction="SELL", bid=10.0, ask=10.2)
        self.assertEqual((px, side), (10.0, "bid"))
        px, side = executable_price(direction="BUY", bid=10.0, ask=None)
        self.assertIsNone(px)
        self.assertEqual(side, "missing_ask")

    def test_pending_sl_touched_before_fill_buy_and_sell(self):
        self.assertTrue(
            pending_sl_touched_before_fill(
                direction="BUY",
                limit_price=2010.0,
                sl_price=2005.0,
                bar_high=2012.0,
                bar_low=2004.0,
            )
        )
        self.assertFalse(
            pending_sl_touched_before_fill(
                direction="BUY",
                limit_price=2010.0,
                sl_price=2005.0,
                bar_high=2012.0,
                bar_low=2009.5,
            )
        )
        self.assertTrue(
            pending_sl_touched_before_fill(
                direction="SELL",
                limit_price=2010.0,
                sl_price=2015.0,
                bar_high=2016.0,
                bar_low=2008.0,
            )
        )
        self.assertFalse(
            pending_sl_touched_before_fill(
                direction="SELL",
                limit_price=2010.0,
                sl_price=2015.0,
                bar_high=2011.0,
                bar_low=2008.0,
            )
        )

    def test_disclose_missing_quote_for_pending_sl(self):
        from scripts.smc.quotes import disclose_missing_quote_for_pending_sl

        self.assertEqual(
            disclose_missing_quote_for_pending_sl(
                pending_order_ids=["A"],
                have_ohlc=True,
                have_live_quotes=False,
            ),
            [],
        )
        self.assertEqual(
            disclose_missing_quote_for_pending_sl(
                pending_order_ids=["A"],
                have_ohlc=False,
                have_live_quotes=True,
            ),
            [],
        )
        self.assertEqual(
            disclose_missing_quote_for_pending_sl(
                pending_order_ids=[],
                have_ohlc=False,
                have_live_quotes=False,
            ),
            [],
        )
        rows = disclose_missing_quote_for_pending_sl(
            pending_order_ids=["P1", ""],
            have_ohlc=False,
            have_live_quotes=False,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["order_id"], "P1")
        self.assertEqual(rows[0]["reason"], "missing_quote")
        self.assertEqual(rows[0]["context"], "sl_before_fill_check")

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
