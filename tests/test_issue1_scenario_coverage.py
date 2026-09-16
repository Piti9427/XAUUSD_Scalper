"""Issue #1 scenario coverage matrix CLI tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.ops.issue1_scenario_coverage import SCENARIOS, build_report


class Issue1ScenarioCoverageTests(unittest.TestCase):
    def test_all_foundation_scenarios_1_to_24_registered(self):
        ids = [s["id"] for s in SCENARIOS]
        self.assertEqual(ids, list(range(1, 25)))

    def test_software_scenarios_have_existing_evidence(self):
        report = build_report()
        self.assertTrue(report["summary"]["software_evidence_complete"])
        self.assertFalse(report["summary"]["issue1_closable_from_software_alone"])
        live = [c for c in report["scenarios"] if c["status"] == "live_ops_required"]
        self.assertEqual(len(live), 1)
        self.assertEqual(live[0]["id"], 24)

    def test_writes_ops_artifact_shape(self):
        report = build_report()
        # Ensure JSON-serializable and includes required keys.
        payload = json.loads(json.dumps(report))
        self.assertIn("scenarios", payload)
        self.assertEqual(len(payload["scenarios"]), 24)


if __name__ == "__main__":
    unittest.main()
