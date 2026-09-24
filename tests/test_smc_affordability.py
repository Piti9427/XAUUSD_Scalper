import unittest

from scripts.smc.affordability import build_affordability_report


class AffordabilityReportTests(unittest.TestCase):
    def test_usd500_demo_min_lot_distance(self):
        # $500 * 0.5% = $2.50; 0.01 lot * 100 oz => $2.50 covers $2.50 of SL distance
        report = build_affordability_report(
            balance=500.0, risk_pct=0.005, min_lot=0.01, contract_size=100.0
        )
        self.assertAlmostEqual(report.risk_budget, 2.5)
        self.assertAlmostEqual(report.max_sl_distance_at_min_lot, 2.5)
        self.assertIn("min lot", report.note)


if __name__ == "__main__":
    unittest.main()
