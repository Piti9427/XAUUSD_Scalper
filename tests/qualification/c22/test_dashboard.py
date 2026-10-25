"""Evidence cohorts remain distinct in the read-only dashboard."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.qualification.c22.dashboard import build_dashboard


class DashboardTests(unittest.TestCase):
    def test_observed_cost_sample_is_not_forward_profit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "costs.json"
            path.write_text(json.dumps({
                "schema_version": 1, "artifact_type": "observed_cost_reconciliation",
                "status": "COST_INCONCLUSIVE", "candidate_id": None, "cohort_id": None,
                "coverage": {"complete_positions": 19}, "reasons": ["historical_calendar_missing"],
                "data": {"net_pnl": -20.0}, "execution_authorized": False,
            }))
            report = build_dashboard([path])
            self.assertEqual(report["status"], "PREPARATION_ONLY")
            panel = report["data"]["panels"][0]
            self.assertEqual(panel["evidence"]["data"]["net_pnl"], -20.0)
            self.assertEqual(panel["cohort_class"], "observed_broker_cost_sample")
            self.assertFalse(report["execution_authorized"])
            self.assertNotIn("forward_net_profit", report["data"])
