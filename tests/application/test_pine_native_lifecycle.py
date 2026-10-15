import unittest
from pathlib import Path


class PineNativeLifecycleTests(unittest.TestCase):
    def test_broker_emulator_owns_position_and_exit_lifecycle(self):
        source = Path("tradingview/xauusd_master_pro_strategy.pine").read_text()

        self.assertIn("strategy.position_size", source)
        self.assertIn("strategy.position_avg_price", source)
        self.assertIn("strategy.exit", source)
        self.assertNotIn("var bool   tradeActive", source)
        self.assertNotIn("if filled", source)


if __name__ == "__main__":
    unittest.main()
