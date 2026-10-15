import unittest

from scripts.smc.account_sync import apply_broker_capital
from scripts.smc.types import AccountState


class AccountSyncTests(unittest.TestCase):
    def test_updates_balance_and_equity(self):
        account = AccountState(balance=200.0, equity=200.0)
        apply_broker_capital(account, balance=500.0, equity=480.0)
        self.assertEqual(account.balance, 500.0)
        self.assertEqual(account.equity, 480.0)

    def test_partial_update_leaves_other_field(self):
        account = AccountState(balance=200.0, equity=200.0)
        apply_broker_capital(account, equity=9000.0)
        self.assertEqual(account.balance, 200.0)
        self.assertEqual(account.equity, 9000.0)


if __name__ == "__main__":
    unittest.main()
