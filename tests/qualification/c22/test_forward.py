"""Fixed-version prospective cohort behavior at the public file seam."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.qualification.c22.artifacts import make_report, source_ref
from scripts.qualification.c22.forward import (
    draft_protocol, freeze_cohort, record_evidence, review_cohort,
)


class ForwardTests(unittest.TestCase):
    def freeze_fixture(self, root):
        source = root / "adapter.py"
        source.write_text("# fixture adapter version1\n")
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps(make_report(
            "candidate_manifest", "RESEARCH_BOUND", candidate_id="fixture-candidate",
            sources=[source_ref(source)], coverage={}, reasons=[],
            manifest={"data_cutoff_utc": "2020-01-01T00:00:00Z"},
        )))
        parity = root / "parity.json"
        parity.write_text(json.dumps(make_report(
            "event_parity", "PARITY_PASS", candidate_id="fixture-candidate",
            sources=[source_ref(source)], coverage={"events_compared": 1}, reasons=[],
        )))
        criteria = root / "criteria.json"
        criteria.write_text(json.dumps({
            "schema_version": 1, "criteria_confirmed": True,
            "freeze_utc": "2020-01-02T00:00:00Z", "exposed_through_utc": "2020-01-01T00:00:00Z",
            "review_end_utc": "2020-03-01T00:00:00Z", "minimum_closed_positions": 10,
            "operational_stop_reasons": ["unresolved_broker_state"],
        }))
        with patch("scripts.qualification.c22.forward.datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime(2020, 1, 2, tzinfo=timezone.utc)
            return freeze_cohort(manifest, parity, criteria, root / "cohort")

    def test_provisional_candidate_cannot_freeze_a_cohort(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"status": "PROVISIONAL", "candidate_id": "abc"}))
            draft = draft_protocol(manifest)
            self.assertEqual(draft["status"], "DRAFT_NOT_FROZEN")
            self.assertFalse(draft["data"]["criteria"]["criteria_confirmed"])
            with self.assertRaisesRegex(ValueError, "RESEARCH_BOUND"):
                freeze_cohort(manifest, root / "parity.json", root / "criteria.json", root / "cohort")
            self.assertFalse((root / "cohort").exists())

    def test_negative_evidence_retained_and_candidate_change_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cohort = self.freeze_fixture(root)
            evidence = root / "loss.json"
            payload = {
                "schema_version": 1, "candidate_id": "fixture-candidate", "cohort_id": cohort["cohort_id"],
                "coverage": {"from_utc": "2020-01-02T00:00:00Z", "until_utc": "2020-01-03T00:00:00Z"},
                "data": {"net_pnl": -20.0},
            }
            evidence.write_text(json.dumps(payload))
            record_evidence(root / "cohort", evidence, kind="broker_demo", observed_utc="2020-01-03T00:01:00Z")
            review = review_cohort(root / "cohort")
            self.assertEqual(review["data"]["observations"][0]["evidence"]["data"]["net_pnl"], -20.0)
            self.assertEqual(review["data"]["profitability"], "INCONCLUSIVE")
            payload["candidate_id"] = "changed-strategy"
            changed = root / "changed.json"
            changed.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "candidate/cohort"):
                record_evidence(root / "cohort", changed, kind="broker_demo", observed_utc="2020-01-03T00:02:00Z")
            with self.assertRaises(FileExistsError):
                self.freeze_fixture(root)

    def test_shadow_cannot_be_recorded_as_broker_profit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cohort = self.freeze_fixture(root)
            evidence = root / "phantom-fill.json"
            evidence.write_text(json.dumps({
                "schema_version": 1, "candidate_id": "fixture-candidate", "cohort_id": cohort["cohort_id"],
                "coverage": {"from_utc": "2020-01-02T00:00:00Z", "until_utc": "2020-01-03T00:00:00Z"},
                "data": {"net_pnl": 100.0, "trades": 1},
            }))
            with self.assertRaisesRegex(ValueError, "Shadow"):
                record_evidence(root / "cohort", evidence, kind="shadow", observed_utc="2020-01-03T00:01:00Z")

    def test_duplicate_and_modified_evidence_are_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cohort = self.freeze_fixture(root)
            evidence = root / "shadow.json"
            payload = {
                "schema_version": 1, "candidate_id": "fixture-candidate", "cohort_id": cohort["cohort_id"],
                "coverage": {"from_utc": "2020-01-02T00:00:00Z", "until_utc": "2020-01-03T00:00:00Z"},
                "data": {"signals": 1},
            }
            evidence.write_text(json.dumps(payload))
            record_evidence(root / "cohort", evidence, kind="shadow", observed_utc="2020-01-03T00:01:00Z")
            with self.assertRaisesRegex(ValueError, "already recorded"):
                record_evidence(root / "cohort", evidence, kind="shadow", observed_utc="2020-01-03T00:02:00Z")
            payload["data"]["signals"] = 100
            evidence.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "source drift"):
                review_cohort(root / "cohort")

    def test_operational_stop_requires_declared_reason_and_remains_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cohort = self.freeze_fixture(root)
            evidence = root / "stop.json"
            payload = {
                "schema_version": 1, "candidate_id": "fixture-candidate", "cohort_id": cohort["cohort_id"],
                "coverage": {"from_utc": "2020-01-03T00:00:00Z", "until_utc": "2020-01-03T00:00:00Z"},
                "data": {"reason": "unresolved_broker_state"},
            }
            evidence.write_text(json.dumps(payload))
            record_evidence(root / "cohort", evidence, kind="operational_stop", observed_utc="2020-01-03T00:01:00Z")
            review = review_cohort(root / "cohort")
            self.assertEqual(review["status"], "OPERATIONALLY_STOPPED")
            self.assertFalse(review["execution_authorized"])
            payload["data"]["reason"] = "dislike_loss"
            unknown = root / "unknown.json"
            unknown.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "not declared"):
                record_evidence(root / "cohort", unknown, kind="operational_stop", observed_utc="2020-01-03T00:02:00Z")

    def test_candidate_envelope_drift_cannot_override_frozen_definition(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.freeze_fixture(root)
            path = root / "cohort" / "cohort.json"
            changed = json.loads(path.read_text())
            changed["candidate_id"] = "changed-strategy"
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "identity"):
                review_cohort(root / "cohort")

    def test_backdated_freeze_cannot_claim_prospective_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.freeze_fixture(root)
            with self.assertRaisesRegex(ValueError, "creation"):
                freeze_cohort(root / "manifest.json", root / "parity.json", root / "criteria.json", root / "backdated")
            self.assertFalse((root / "backdated").exists())

    def test_changed_adapter_invalidates_freeze_append_and_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.freeze_fixture(root)
            (root / "adapter.py").write_text("# fixture adapter version2\n")
            with self.assertRaisesRegex(ValueError, "source drift"):
                freeze_cohort(root / "manifest.json", root / "parity.json", root / "criteria.json", root / "other")
            with self.assertRaisesRegex(ValueError, "source drift"):
                review_cohort(root / "cohort")
            with self.assertRaisesRegex(ValueError, "source drift"):
                record_evidence(root / "cohort", root / "missing.json", kind="shadow", observed_utc="2020-01-03T00:00:00Z")

    def test_bare_status_report_cannot_freeze(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.freeze_fixture(root)
            (root / "manifest.json").write_text(json.dumps({"status": "RESEARCH_BOUND", "candidate_id": "fixture-candidate"}))
            with self.assertRaisesRegex(ValueError, "report envelope"):
                freeze_cohort(root / "manifest.json", root / "parity.json", root / "criteria.json", root / "other")
