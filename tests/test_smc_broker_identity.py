import unittest
from types import SimpleNamespace

from scripts.smc.account_mode import MARGIN_MODE_RETAIL_HEDGING, MARGIN_MODE_RETAIL_NETTING
from scripts.smc.broker_identity import verify_broker_identity


class BrokerIdentityTests(unittest.TestCase):
    def test_accepts_exness_demo_xauusd_hedging(self):
        account = SimpleNamespace(
            server="Exness-MT5Trial",
            login=123,
            currency="USD",
            trade_mode=0,
            margin_mode=MARGIN_MODE_RETAIL_HEDGING,
        )
        symbol = SimpleNamespace(name="XAUUSD")
        report = verify_broker_identity(account_info=account, symbol_info=symbol)
        self.assertTrue(report.ok)
        self.assertEqual(report.reasons, ())
        self.assertEqual(report.margin_mode, str(MARGIN_MODE_RETAIL_HEDGING))

    def test_rejects_missing_or_live_or_wrong_symbol(self):
        self.assertFalse(verify_broker_identity().ok)
        account = SimpleNamespace(
            server="Exness-MT5",
            login=1,
            currency="USD",
            trade_mode=2,
            margin_mode=MARGIN_MODE_RETAIL_HEDGING,
        )
        symbol = SimpleNamespace(name="EURUSD")
        report = verify_broker_identity(account_info=account, symbol_info=symbol)
        self.assertFalse(report.ok)
        self.assertIn("demo_required", report.reasons)
        self.assertIn("symbol_mismatch", report.reasons)

    def test_rejects_netting_even_when_demo_xauusd(self):
        account = SimpleNamespace(
            server="Exness-MT5Trial",
            login=123,
            currency="USD",
            trade_mode=0,
            margin_mode=MARGIN_MODE_RETAIL_NETTING,
        )
        symbol = SimpleNamespace(name="XAUUSD")
        report = verify_broker_identity(account_info=account, symbol_info=symbol)
        self.assertFalse(report.ok)
        self.assertIn("netting_mode_blocks_ownership", report.reasons)


if __name__ == "__main__":
    unittest.main()
