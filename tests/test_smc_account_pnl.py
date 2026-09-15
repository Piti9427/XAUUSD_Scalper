import unittest

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


if __name__ == "__main__":
    unittest.main()
