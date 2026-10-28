"""Independent gate reconstruction rejects self-consistent reported decisions."""

from copy import deepcopy
import unittest

from scripts.research.c22_recovery_be_verify import audit_recovery_gate
from tests.research import test_c22_recovery_be_replay as fixtures
from tests.research.test_c22_risk_replay import BROKER


class RecoveryGateAuditTests(unittest.TestCase):
    def example(self):
        helper = fixtures.RecoveryNetBeReplayTests()
        frame, ticks = helper.recovery_fixture()
        return helper.run_case(frame, ticks)

    def test_realized_cash_peak_and_entry_gate_reconstruct_without_reported_boolean(self):
        result = self.example()
        proof = audit_recovery_gate(result, BROKER)
        self.assertEqual(proof["entries"], 3)
        self.assertEqual(proof["eligible_entries"], 1)
        self.assertAlmostEqual(proof["closing_peak"], 203.9)

    def test_reported_future_peak_and_commission_based_gate_are_rejected(self):
        result = self.example()
        for field, value in [("closing_peak", 1000), ("balance", 199.9), ("eligible", True)]:
            bad = deepcopy(result)
            bad["recovery_be"]["entry_decisions"][0][field] = value
            if field == "eligible":
                bad["ledger"][0]["recovery_be_eligible"] = True
            with self.subTest(field=field), self.assertRaises(AssertionError):
                audit_recovery_gate(bad, BROKER)

    def test_missing_decision_or_unbound_adjustment_cannot_pass(self):
        result = self.example()
        bad = deepcopy(result)
        bad["recovery_be"]["entry_decisions"].pop()
        with self.assertRaises(AssertionError):
            audit_recovery_gate(bad, BROKER)
        bad = deepcopy(result)
        bad["recovery_be"]["be_adjustments"][0]["entry_ms"] = bad["ledger"][0]["entry_ms"]
        with self.assertRaises(AssertionError):
            audit_recovery_gate(bad, BROKER)


if __name__ == "__main__":
    unittest.main()
