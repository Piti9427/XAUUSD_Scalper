import unittest
from types import SimpleNamespace

from scripts.smc.account_pnl_sync import (
    classify_deal_source,
    classify_deals,
    apply_classified_deals,
    DEAL_TYPE_BALANCE,
    DEAL_TYPE_BUY,
)
from scripts.smc.types import AccountState, apply_account_pnl_event


class AccountPnlSeparationTests(unittest.TestCase):
    def test_manual_loss_moves_equity_but_not_bot_expectancy(self):
        account = AccountState(balance=500.0, equity=500.0)
        apply_account_pnl_event(account, amount=-10.0, source="manual")
        self.assertEqual(account.equity, 490.0)
        self.assertEqual(account.manual_realized_pnl, -10.0)
        self.assertEqual(account.bot_realized_pnl, 0.0)

    def test_bot_win_counts_only_in_bot_pnl(self):
        account = AccountState(balance=500.0, equity=500.0)
        apply_account_pnl_event(account, amount=7.5, source="bot")
        self.assertEqual(account.bot_realized_pnl, 7.5)
        self.assertEqual(account.manual_realized_pnl, 0.0)

    def test_cash_flow_disclosed_separately(self):
        account = AccountState(balance=500.0, equity=500.0)
        apply_account_pnl_event(account, amount=100.0, source="cash_flow")
        self.assertEqual(account.cash_flow_total, 100.0)
        self.assertEqual(account.bot_realized_pnl, 0.0)
        self.assertEqual(account.equity, 600.0)

    def test_classify_bot_manual_and_cash_flow_deals(self):
        bot = SimpleNamespace(
            ticket=1, type=DEAL_TYPE_BUY, comment="SMC_ORDER_A",
            profit=12.0, commission=-0.5, swap=0.0, fee=0.0,
        )
        manual = SimpleNamespace(
            ticket=2, type=DEAL_TYPE_BUY, comment="manual scalp",
            profit=-8.0, commission=0.0, swap=0.0, fee=0.0,
        )
        deposit = SimpleNamespace(
            ticket=3, type=DEAL_TYPE_BALANCE, comment="",
            profit=200.0, commission=0.0, swap=0.0, fee=0.0,
        )
        self.assertEqual(classify_deal_source(bot), "bot")
        self.assertEqual(classify_deal_source(manual), "manual")
        self.assertEqual(classify_deal_source(deposit), "cash_flow")

        account = AccountState(balance=500.0, equity=500.0)
        n = apply_classified_deals(account, classify_deals([bot, manual, deposit]))
        self.assertEqual(n, 3)
        self.assertAlmostEqual(account.bot_realized_pnl, 11.5)
        self.assertAlmostEqual(account.manual_realized_pnl, -8.0)
        self.assertAlmostEqual(account.cash_flow_total, 200.0)
        self.assertAlmostEqual(account.equity, 500.0 + 11.5 - 8.0 + 200.0)


if __name__ == "__main__":
    unittest.main()
