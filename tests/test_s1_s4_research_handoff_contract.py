import unittest
from pathlib import Path


HANDOFF = Path("docs/specs/xauusd-s1-s4-research-handoff-v1.md")
MECHANICAL = Path("docs/specs/xauusd-s1-s4-mechanical-v1.md")


class S1S4ResearchHandoffContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HANDOFF.is_file():
            raise unittest.SkipTest("research handoff v1 missing")
        cls.text = HANDOFF.read_text()

    def test_handoff_exists_and_routes_parent_scenarios(self):
        self.assertTrue(HANDOFF.is_file())
        self.assertIn("## 1. Mechanical-spec review", self.text)
        self.assertIn("| 1 | Worked example |", self.text)
        self.assertIn("| Empirical PASS/FAIL | **Blocked** |", self.text)

    def test_datasets_separated_from_proxies(self):
        self.assertIn("## 2. Dataset evidence inventory", self.text)
        self.assertIn("certified Exness XAUUSD", self.text)
        self.assertIn("Diagnostic only", self.text)
        self.assertIn("Missing evidence must not become", self.text)

    def test_evidence_to_readiness_and_manifest(self):
        self.assertIn("## 3. Evidence-to-readiness decision table", self.text)
        self.assertIn("## 4. Versioned run-manifest template", self.text)
        self.assertIn("rule_version: s1-s4-mechanical-v1", self.text)
        self.assertIn("UNKNOWN_NEWS", self.text)

    def test_shared_controls_and_legacy_isolation(self):
        self.assertIn("## 5. Shared controls", self.text)
        self.assertIn("Legacy Reference", self.text)
        self.assertIn("never treat Legacy vs S1 as one-variable", self.text)

    def test_verdict_docs_yes_experiment_no(self):
        self.assertIn("## 9. Handoff verdict", self.text)
        self.assertIn("Documentation completion", self.text)
        self.assertIn("**YES**", self.text)
        self.assertIn("Experiment readiness", self.text)
        self.assertIn("**NO**", self.text)
        self.assertIn("U1", self.text)
        self.assertIn("U9", self.text)

    def test_explicit_non_actions_for_issue_four(self):
        self.assertIn("## 10. Explicit non-actions (issue #4)", self.text)
        self.assertIn("No Pine / EA / production Python behavior changes", self.text)
        self.assertIn("No comparative profitability run", self.text)
        self.assertTrue(MECHANICAL.is_file())


if __name__ == "__main__":
    unittest.main()
