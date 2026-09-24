import unittest
from pathlib import Path


MECHANICAL = Path("docs/specs/xauusd-s1-s4-mechanical-v1.md")
NARRATIVE = Path("docs/specs/xauusd-setup-experiment-v1.md")
HANDOFF = Path("docs/specs/xauusd-s1-s4-research-handoff-v1.md")


class S1S4MechanicalSpecContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mechanical = MECHANICAL.read_text()
        cls.narrative = NARRATIVE.read_text()

    def test_mechanical_spec_exists_and_classifies_decisions(self):
        self.assertTrue(MECHANICAL.is_file())
        for marker in (
            "## 1. Decision classification",
            "### 1.1 Individually confirmed choices",
            "### 1.2 Proposed v1 numerical defaults",
            "### 1.3 Unresolved material gates",
            "C9",
            "U1",
        ):
            self.assertIn(marker, self.mechanical)

    def test_if_then_invalid_tables_cover_core_rules(self):
        for marker in (
            "### 3.3 Pools & Sweep",
            "### 3.4 MSS (S1 only)",
            "### 3.5 Structure state",
            "### 3.6 FVG / OB / overlap",
            "### 3.7 Entry / SL / TP / pending / session",
            "AMBIGUOUS",
        ):
            self.assertIn(marker, self.mechanical)

    def test_worked_buy_sell_examples_exist_for_each_candidate(self):
        for marker in (
            "### 5.1 S1 BUY",
            "### 5.2 S1 SELL",
            "### 5.3 S2 BUY",
            "### 5.4 S2 SELL",
            "### 5.5 S3 BUY",
            "### 5.6 S3 SELL",
            "### 5.7 S4 BUY",
            "### 5.8 S4 SELL",
            "Lifecycle ledger",
        ):
            self.assertIn(marker, self.mechanical)

    def test_parent_scenario_matrix_covers_examples_1_to_21(self):
        self.assertIn("## 8. Parent scenario coverage matrix", self.mechanical)
        self.assertIn("| 1 Valid BUY/SELL each candidate |", self.mechanical)
        self.assertIn("| 17–21 Ambiguity/costs/risk/data/Legacy |", self.mechanical)
        for boundary_id in ("B6", "B11", "B13", "B19", "B21"):
            self.assertIn(boundary_id, self.mechanical)

    def test_no_implementation_authorization_claim(self):
        self.assertIn("Documentation artifact only", self.mechanical)
        self.assertIn("Not claimed:", self.mechanical)
        self.assertIn("xauusd-s1-s4-mechanical-v1.md", self.narrative)

    def test_handoff_package_present_when_written(self):
        if not HANDOFF.is_file():
            self.skipTest("handoff package not written yet")
        text = HANDOFF.read_text()
        for marker in (
            "Evidence-to-readiness",
            "run-manifest",
            "Handoff verdict",
            "Documentation completion",
            "Experiment readiness",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
