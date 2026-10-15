import unittest
from types import SimpleNamespace

from scripts.smc.account_mode import (
    MARGIN_MODE_RETAIL_HEDGING,
    MARGIN_MODE_RETAIL_NETTING,
    verify_account_mode,
)


class AccountModeTests(unittest.TestCase):
    def test_hedging_ok(self):
        account = SimpleNamespace(margin_mode=MARGIN_MODE_RETAIL_HEDGING)
        report = verify_account_mode(account_info=account)
        self.assertTrue(report.ok)
        self.assertEqual(report.reasons, ())

    def test_netting_blocks_demo_gate(self):
        account = SimpleNamespace(margin_mode=MARGIN_MODE_RETAIL_NETTING)
        report = verify_account_mode(account_info=account)
        self.assertFalse(report.ok)
        self.assertIn("netting_mode_blocks_ownership", report.reasons)

    def test_missing_fails_closed(self):
        self.assertFalse(verify_account_mode().ok)
        account = SimpleNamespace()  # no margin_mode attr
        report = verify_account_mode(account_info=account)
        self.assertFalse(report.ok)
        self.assertIn("margin_mode_unknown", report.reasons)


if __name__ == "__main__":
    unittest.main()
