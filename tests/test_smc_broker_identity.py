import unittest
from types import SimpleNamespace

from scripts.smc.broker_identity import verify_broker_identity


class BrokerIdentityTests(unittest.TestCase):
    def test_accepts_exness_demo_xauusd(self):
        account = SimpleNamespace(server="Exness-MT5Trial", login=123, currency="USD", trade_mode=0)
        symbol = SimpleNamespace(name="XAUUSD")
        report = verify_broker_identity(account_info=account, symbol_info=symbol)
        self.assertTrue(report.ok)
        self.assertEqual(report.reasons, ())

    def test_rejects_missing_or_live_or_wrong_symbol(self):
        self.assertFalse(verify_broker_identity().ok)
        account = SimpleNamespace(server="Exness-MT5", login=1, currency="USD", trade_mode=2)
        symbol = SimpleNamespace(name="EURUSD")
        report = verify_broker_identity(account_info=account, symbol_info=symbol)
        self.assertFalse(report.ok)
        self.assertIn("demo_required", report.reasons)
        self.assertIn("symbol_mismatch", report.reasons)


if __name__ == "__main__":
    unittest.main()
