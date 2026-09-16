import unittest

from scripts.smc.cost_accounting import (
    expectancy_hides_operating_loss,
    summarize_profit_layers,
)


class CostAccountingTests(unittest.TestCase):
    def test_separates_trading_and_operating_layers(self):
        report = summarize_profit_layers(
            bot_realized_pnl=120.0,
            fees_and_swap=5.0,
            operating_costs=40.0,
        )
        self.assertEqual(report.net_trading_profit, 115.0)
        self.assertEqual(report.net_operating_profit, 75.0)
        self.assertIn("spread embedded", report.note)

    def test_flags_expectancy_hiding_ops_loss(self):
        report = summarize_profit_layers(
            bot_realized_pnl=20.0,
            fees_and_swap=0.0,
            operating_costs=50.0,
        )
        self.assertTrue(
            expectancy_hides_operating_loss(
                positive_trade_expectancy=True,
                net_operating_profit=report.net_operating_profit,
            )
        )


if __name__ == "__main__":
    unittest.main()
