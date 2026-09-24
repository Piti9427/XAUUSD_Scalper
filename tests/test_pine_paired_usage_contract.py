import unittest
from pathlib import Path


INDICATOR = Path("tradingview/xauusd_master_pro_v6.pine")
STRATEGY = Path("tradingview/xauusd_master_pro_strategy.pine")


class PinePairedUsageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.indicator = INDICATOR.read_text()
        cls.strategy = STRATEGY.read_text()

    def test_pair_uses_same_signal_and_timing_contract(self):
        signal_contract = (
            'input.string("Confluence (2+)", "Signal Engine Mode", '
            'options=["Confluence (2+)", "SMC Prime Only", '
            '"TSS (Turtle Soup) Only", "GSS (Golden Zone OTE) Only"]'
        )
        for source in (self.indicator, self.strategy):
            self.assertIn(signal_contract, source)
            self.assertIn("20 * 60 + 45", source)
            self.assertNotIn("20 * 60 + 55", source)
            self.assertNotIn("barmerge.lookahead_off", source)

    def test_indicator_separates_human_card_from_machine_json(self):
        self.assertRegex(self.indicator, r'alertOutput\s*=\s*input\.string\("Manual Card"')
        self.assertIn('options=["Manual Card", "Bot JSON", "Off"]', self.indicator)
        self.assertIn('alert(alertOutput == "Bot JSON" ? pendingJson : pendingCard', self.indicator)
        setup_alert_block = self.indicator.split("if eventSetupPending", 1)[1].split(
            "if eventOrderFilled", 1
        )[0]
        self.assertNotIn("+ pendingJson", setup_alert_block)
        self.assertNotIn("--- JSON WEBHOOK ---", self.indicator)

    def test_strategy_exposes_manual_operator_overlay(self):
        self.assertRegex(self.strategy, r'visualPreset\s*=\s*input\.string\("Balanced \(Clean\)"')
        self.assertIn("var table operatorHud = table.new(", self.strategy)
        self.assertIn("plot(activeEntry", self.strategy)
        self.assertIn("plot(activeSl", self.strategy)
        self.assertIn("plot(activeTp1", self.strategy)
        self.assertIn("plot(activeTp2", self.strategy)


if __name__ == "__main__":
    unittest.main()
