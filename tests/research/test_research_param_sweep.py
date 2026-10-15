"""Declared parameter experiments fail closed on malformed or untraceable specs."""

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.research.param_sweep import audit_outputs, load_candidates


class ParameterCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).resolve().parents[2] / "docs/research/handoff-parameter-candidates.json"
        self.source = json.loads(self.path.read_text())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.edited = Path(self.temp.name) / "candidates.json"

    def load_edit(self, change):
        source = copy.deepcopy(self.source)
        change(source)
        self.edited.write_text(json.dumps(source))
        return load_candidates(self.edited)

    def test_declared_handoff_candidates_keep_provenance_and_risk_parameters(self):
        declaration, specs = load_candidates(self.path)
        self.assertEqual(len(specs), 5)
        self.assertEqual(declaration["status"], "reconstructed_execution_partial_rule_match")
        self.assertEqual(specs[0].name, "Legacy_Donchian30_plain_2p5_2p5")
        self.assertEqual((specs[0].lookback, specs[0].sl, specs[0].tp), (30, 2.5, 2.5))
        self.assertTrue(
            all(
                row["handoff_reference"] and row["known_mismatch"]
                for row in declaration["candidates"]
            )
        )

    def test_duplicate_and_unsupported_candidate_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.load_edit(
                lambda src: src["candidates"].append(copy.deepcopy(src["candidates"][0]))
            )
        with self.assertRaisesRegex(ValueError, "Invalid candidate fields"):
            self.load_edit(lambda src: src["candidates"][0].update(entry="limit"))

    def test_invalid_risk_and_missing_mismatch_disclosure_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Invalid sl"):
            self.load_edit(lambda src: src["candidates"][0].update(sl=-1))
        with self.assertRaisesRegex(ValueError, "Missing provenance"):
            self.load_edit(lambda src: src["candidates"][0].update(known_mismatch=""))

    def test_trade_and_summary_reconciliation_blocks_corrupt_output(self):
        root = Path(self.temp.name)
        (root / "trades").mkdir()
        path = root / "trades" / "Legacy_Test__native__2010.csv"
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=("signal_time", "entry_time", "exit_time", "net", "r")
            )
            writer.writeheader()
            writer.writerow(
                {
                    "signal_time": "2010-01-01 00:00:00+00:00",
                    "entry_time": "2010-01-01 00:01:00+00:00",
                    "exit_time": "2010-01-01 00:02:00+00:00",
                    "net": 10,
                    "r": 1,
                }
            )
        annual = [
            {
                "strategy": "Legacy_Test",
                "year": 2010,
                "trades": 1,
                "net": 10.0,
                "total_r": 1.0,
                "pf": None,
            }
        ]
        summary = [
            {
                "strategy": "Legacy_Test",
                "trades": 1,
                "net": 10.0,
                "total_r": 1.0,
                "positive_years": 1,
                "pf": None,
            }
        ]
        audit_outputs(root, annual, summary, ["Legacy_Test"], [2010])
        summary[0]["net"] = 11.0
        with self.assertRaisesRegex(ValueError, "Summary reconciliation failed"):
            audit_outputs(root, annual, summary, ["Legacy_Test"], [2010])
        summary[0]["net"] = 10.0
        with self.assertRaisesRegex(ValueError, "coverage"):
            audit_outputs(root, annual, summary, ["Legacy_Test"], [2010, 2011])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit_outputs(root, annual + annual, summary, ["Legacy_Test"], [2010])


if __name__ == "__main__":
    unittest.main()
