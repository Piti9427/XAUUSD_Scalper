import unittest
from datetime import datetime, timedelta, timezone

from scripts.profitability_qualification import (
    QualificationPolicy,
    assess_capital_viability,
    qualify_candidate,
)


class ProfitabilityQualificationTests(unittest.TestCase):
    def test_qualifies_only_when_base_stress_bootstrap_and_slices_pass(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        trades = []
        for index in range(120):
            trades.append({
                "pnl_r": 1.0 if index % 3 else -1.0,
                "direction": "long" if index % 2 else "short",
                "session": "london" if index % 4 < 2 else "new_york",
                "closed_at": start + timedelta(days=index),
            })
        result = qualify_candidate(trades, trades, QualificationPolicy(bootstrap_samples=500, seed=7))
        self.assertEqual("HISTORICAL_QUALIFIED", result.status)
        self.assertGreaterEqual(result.base.profit_factor, 1.5)
        self.assertGreater(result.bootstrap_lower_95_expectancy_r, 0)

    def test_insufficient_sample_is_inconclusive(self):
        result = qualify_candidate([], [], QualificationPolicy(bootstrap_samples=20))
        self.assertEqual("INCONCLUSIVE", result.status)
        self.assertIn("trade_count<100", result.failures)

    def test_capital_viability_never_rounds_up_to_split_minimum(self):
        result = assess_capital_viability(
            balance=100, equity=100, risk_pct=0.005, entry=4300, stop=4290,
            contract_size=100, min_lot=0.01, lot_step=0.01,
        )
        self.assertFalse(result.viable)
        self.assertEqual(0.0, result.allowed_lot)
        self.assertEqual(0.02, result.required_split_lot)
        self.assertAlmostEqual(4000.0, result.minimum_capital, places=2)

    def test_invalid_bootstrap_policy_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "policy"):
            qualify_candidate([], [], QualificationPolicy(bootstrap_samples=0))


if __name__ == "__main__":
    unittest.main()
