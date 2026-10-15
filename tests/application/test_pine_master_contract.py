import unittest
from pathlib import Path


SOURCE = Path("tradingview/xauusd_master_pro_strategy.pine")


class PineMasterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text()

    def test_canonical_script_is_strategy_with_confirmed_htf_data(self):
        self.assertIn('strategy("XAUUSD Master Pro Strategy', self.source)
        self.assertNotIn("barmerge.lookahead_off", self.source)
        self.assertGreaterEqual(self.source.count("barmerge.lookahead_on"), 4)

    def test_confluence_risk_and_rollover_fail_closed(self):
        self.assertIn('input.string("Confluence (2+)"', self.source)
        self.assertIn("longContributors >= 2", self.source)
        self.assertIn("shortContributors >= 2", self.source)
        self.assertIn("math.floor(rawLot / requiredSplitLot)", self.source)
        self.assertIn("capitalViable = candidateQty >= requiredSplitLot", self.source)
        self.assertIn("20 * 60 + 45", self.source)

    def test_smc_stop_uses_extremum_frozen_at_mss(self):
        self.assertIn("lastMssSweepExtremum := trueSweepExtremum", self.source)
        self.assertIn("rawSl = lastMssSweepExtremum - slBuffer", self.source)
        self.assertIn("rawSl = lastMssSweepExtremum + slBuffer", self.source)


if __name__ == "__main__":
    unittest.main()
