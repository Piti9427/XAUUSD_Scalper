"""Pure TRADE_CLOSED PnL resolution — no invent live cash."""

import unittest

from scripts.smc.trade_closed_pnl import resolve_trade_closed_pnl, parse_optional_float


class TradeClosedPnlTests(unittest.TestCase):
    def test_parse_optional_float(self):
        self.assertEqual(parse_optional_float("1.5"), 1.5)
        self.assertIsNone(parse_optional_float("x"))
        self.assertIsNone(parse_optional_float(None))

    def test_live_missing_broker_pnl_does_not_invent(self):
        pnl_r, pnl_dollar, status = resolve_trade_closed_pnl(
            dry_run=False,
            payload_pnl_r=2.0,
            payload_pnl_dollar=50.0,
            broker_pnl=None,
            entry=2000.0,
            sl=1990.0,
            lot=0.01,
            exit_price=2020.0,
            direction="BUY",
        )
        self.assertIsNone(pnl_r)
        self.assertIsNone(pnl_dollar)
        self.assertEqual(status, "live_broker_pnl_missing")

    def test_live_broker_pnl_drives_frozen_r(self):
        # $10 on 10pt SL * 0.01 lot * 100 contract → depends on frozen_initial_r
        pnl_r, pnl_dollar, status = resolve_trade_closed_pnl(
            dry_run=False,
            payload_pnl_r=None,
            payload_pnl_dollar=999.0,  # ignored when broker_pnl present
            broker_pnl=10.0,
            entry=2000.0,
            sl=1990.0,
            lot=0.01,
            exit_price=2010.0,
            direction="BUY",
        )
        self.assertEqual(status, "ok")
        self.assertEqual(pnl_dollar, 10.0)
        self.assertIsNotNone(pnl_r)

    def test_dry_run_geometric_r_without_dollars(self):
        pnl_r, pnl_dollar, status = resolve_trade_closed_pnl(
            dry_run=True,
            payload_pnl_r=None,
            payload_pnl_dollar=None,
            broker_pnl=None,
            entry=2000.0,
            sl=1990.0,
            lot=0.01,
            exit_price=2020.0,
            direction="BUY",
        )
        self.assertEqual(status, "ok")
        self.assertIsNone(pnl_dollar)
        self.assertEqual(pnl_r, 2.0)

    def test_dry_run_payload_dollars_to_frozen_r(self):
        pnl_r, pnl_dollar, status = resolve_trade_closed_pnl(
            dry_run=True,
            payload_pnl_r=None,
            payload_pnl_dollar=10.0,
            entry=2000.0,
            sl=1990.0,
            lot=0.01,
            exit_price=0.0,
            direction="BUY",
        )
        self.assertEqual(status, "ok")
        self.assertEqual(pnl_dollar, 10.0)
        self.assertIsNotNone(pnl_r)


if __name__ == "__main__":
    unittest.main()
