"""Selected readiness measures evidence without granting order permission."""

from contextlib import redirect_stdout
from datetime import timedelta
import hashlib
from io import StringIO
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from copy import deepcopy
from typing import Any

from scripts.c22_selected.strategy import CANDIDATE_ID, MAGIC, ROOT, SNAPSHOT
from scripts.ops.c22_selected_readiness import build_selected_report, main
from tests.demo import test_c22h4_readiness as old_tests


class SelectedReadinessTests(unittest.TestCase):
    def setUp(self):
        self.fixture: Any = old_tests.MarketOpenReadinessTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.context["release_hash"] = "b" * 64
        self.fixture.values["strategy_snapshot"] = SNAPSHOT
        self.fixture.last["snapshot"] = SNAPSHOT
        rows = self.fixture.conn.execute("SELECT id,payload FROM audit_events").fetchall()
        for ident, raw in rows:
            event = json.loads(raw)
            event["release_hash"] = self.fixture.context["release_hash"]
            if event["kind"] == "CYCLE":
                event["result"]["snapshot"] = SNAPSHOT
            self.fixture.conn.execute(
                "UPDATE audit_events SET payload=? WHERE id=?", (json.dumps(event), ident)
            )
        self.parity = dict(
            history_gate=True,
            parity_gate=True,
            contract_id=CANDIDATE_ID,
            snapshot=SNAPSHOT,
            **self.fixture.context,
        )

    def report(self, **kwargs):
        fixture = self.fixture
        fixture.conn.execute("DELETE FROM kv")
        fixture.conn.executemany(
            "INSERT INTO kv VALUES (?,?)",
            [(key, json.dumps(value)) for key, value in fixture.values.items()],
        )
        fixture.conn.commit()
        return build_selected_report(
            fixture.conn,
            now=fixture.now,
            since=fixture.since,
            broker=fixture.broker,
            parity=self.parity,
            policy=fixture.policy,
            **kwargs,
        )

    def short_observation(self):
        fixture = self.fixture
        fixture.since = fixture.now - timedelta(minutes=2)
        fixture.conn.execute("DELETE FROM audit_events")
        for minutes in (2, 1, 0):
            stamp = fixture.now - timedelta(minutes=minutes)
            fixture.event("CYCLE", stamp, result=dict(fixture.last, captured_utc=stamp.isoformat()))
        fixture.event(
            "SIGNAL", fixture.now, bar=fixture.now.isoformat(), observed=dict(macro_ema=4000)
        )

    def duration_waiver(self) -> dict[str, Any]:
        return dict(
            version=1,
            scope="SELECTED_DEMO_TRIAL_DURATION_ONLY",
            snapshot=SNAPSHOT,
            contract_id=CANDIDATE_ID,
            magic=MAGIC,
            **self.fixture.context,
            accepted_utc=(self.fixture.now - timedelta(minutes=1)).isoformat(),
            owner_decision="เริ่ม Demo trial เมื่อหลักฐานพร้อม โดยยกเว้นเวลา shadow 48 ชั่วโมง/96 แท่งสำหรับ 26b8",
            waived_gates=[
                "shadow_48h_continuous_observation_missing",
                "shadow_96_new_complete_m15_missing",
            ],
        )

    def test_explicit_selected_duration_waiver_preserves_measured_shortfall(self):
        self.short_observation()
        before = self.report()
        self.assertIn("shadow_48h_continuous_observation_missing", before["blockers"])
        self.assertIn("shadow_96_new_complete_m15_missing", before["blockers"])
        waiver = self.duration_waiver()
        result = self.report(shadow_waiver=waiver)
        self.assertEqual(result["status"], "AWAITING_OPERATOR_REVIEW", result)
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["shadow"]["new_complete_m15_bars"], 1)
        self.assertAlmostEqual(result["shadow"]["observed_hours"], 2 / 60)
        self.assertEqual(result["shadow"]["waived_gates"], waiver["waived_gates"])
        self.assertTrue(result["shadow"]["selected_duration_waiver_applied"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(
            result["input_sha256"]["shadow_waiver"],
            hashlib.sha256(
                json.dumps(waiver, sort_keys=True, allow_nan=False).encode()
            ).hexdigest(),
        )

    def test_invalid_or_broader_waiver_never_removes_waiting_gates(self):
        self.short_observation()
        original = self.duration_waiver()
        for key, value in (
            ("contract_id", "1af968e9ac6a26ea"),
            ("snapshot", "old-snapshot"),
            ("magic", 22261004),
            ("account_fingerprint", "other"),
            ("release_hash", "d" * 64),
            ("config_hash", "e" * 64),
            ("owner_decision", "old decision"),
            ("scope", "LIVE_EXECUTION"),
            ("accepted_utc", (self.fixture.now + timedelta(seconds=1)).isoformat()),
            ("accepted_utc", self.fixture.now.replace(tzinfo=None).isoformat()),
            ("waived_gates", original["waived_gates"] + ["shadow_utc_midnight_missing"]),
        ):
            with self.subTest(key=key, value=value):
                waiver = deepcopy(original)
                waiver[key] = value
                result = self.report(shadow_waiver=waiver)
                self.assertIn("selected_duration_waiver_invalid", result["blockers"])
                self.assertIn("shadow_48h_continuous_observation_missing", result["blockers"])
                self.assertIn("shadow_96_new_complete_m15_missing", result["blockers"])
                self.assertFalse(result["shadow"]["selected_duration_waiver_applied"])

    def test_duration_waiver_keeps_utc_midnight_and_continuity(self):
        self.short_observation()
        self.fixture.conn.execute(
            "DELETE FROM audit_events WHERE json_extract(payload,'$.kind')='CYCLE'"
        )
        self.fixture.event("CYCLE", self.fixture.now, result=dict(self.fixture.last))
        result = self.report(shadow_waiver=self.duration_waiver())
        self.assertIn("shadow_utc_midnight_missing", result["blockers"])
        self.assertNotIn("shadow_48h_continuous_observation_missing", result["blockers"])
        self.fixture.since = self.fixture.now - timedelta(minutes=4)
        stamp = self.fixture.now - timedelta(minutes=3)
        self.fixture.event(
            "CYCLE", stamp, result=dict(self.fixture.last, captured_utc=stamp.isoformat())
        )
        # Persist chronological order, as the actual journal does.
        rows = sorted(
            (
                json.loads(raw)
                for (raw,) in self.fixture.conn.execute("SELECT payload FROM audit_events")
            ),
            key=lambda row: row["utc"],
        )
        self.fixture.conn.execute("DELETE FROM audit_events")
        for row in rows:
            self.fixture.conn.execute(
                "INSERT INTO audit_events(payload) VALUES (?)", (json.dumps(row),)
            )
        result = self.report(shadow_waiver=self.duration_waiver())
        self.assertIn("selected_recent_observation_missing_or_interrupted", result["blockers"])
        self.assertEqual(result["shadow"]["max_cycle_gap_seconds"], 180)

    def test_duration_waiver_requires_fresh_bar_and_finite_current_macro(self):
        self.short_observation()
        self.fixture.conn.execute(
            "DELETE FROM audit_events WHERE json_extract(payload,'$.kind')='SIGNAL'"
        )
        self.assertIn(
            "selected_fresh_prospective_m15_missing",
            self.report(shadow_waiver=self.duration_waiver())["blockers"],
        )
        self.fixture.since = self.fixture.now - timedelta(hours=1)
        stale = self.fixture.now - timedelta(minutes=30)
        self.fixture.event("SIGNAL", stale, bar=stale.isoformat(), observed=dict(macro_ema=4000))
        result = self.report(shadow_waiver=self.duration_waiver())
        self.assertEqual(result["shadow"]["new_complete_m15_bars"], 1)
        self.assertIn("selected_fresh_prospective_m15_missing", result["blockers"])
        self.short_observation()
        for macro in (True, None, float("nan")):
            with self.subTest(macro=macro):
                self.fixture.last["macro_ema"] = macro
                self.assertIn(
                    "selected_current_macro_warmup_not_verified",
                    self.report(shadow_waiver=self.duration_waiver())["blockers"],
                )

    def test_duration_waiver_never_clears_cost_quote_feed_or_exposure_blocks(self):
        self.short_observation()
        self.fixture.policy = {}
        self.fixture.broker["tick"]["time_msc"] -= 3600 * 1000
        self.fixture.broker["positions"] = 1
        self.parity["parity_gate"] = False
        self.fixture.conn.execute("INSERT INTO events(sent) VALUES (0)")
        result = self.report(shadow_waiver=self.duration_waiver())
        for blocker in (
            "cost_v2_evidence_missing_or_invalid",
            "fresh_broker_quote_missing",
            "fresh_demo_identity_or_flat_exposure_missing",
            "broker_parity_not_passed",
            "pending_outbox",
        ):
            self.assertIn(blocker, result["blockers"])
        self.assertNotIn("shadow_96_new_complete_m15_missing", result["blockers"])
        self.assertFalse(result["execution_authorized"])

    def test_selected_identity_and_single_current_cohort_remain_read_only(self):
        result = self.report()
        self.assertEqual(result["status"], "AWAITING_OPERATOR_REVIEW", result)
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["snapshot"], SNAPSHOT)
        self.assertEqual(result["contract_id"], CANDIDATE_ID)
        self.assertEqual(result["magic"], MAGIC)
        self.assertEqual(result["account_fingerprint"], self.fixture.fingerprint)
        self.assertEqual(
            result["cohort"],
            {name: self.fixture.context[name] for name in ("release_hash", "config_hash")},
        )
        self.assertEqual(result["shadow"]["new_complete_m15_bars"], 96)
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["unattended_authorized"])
        self.assertEqual(set(result["input_sha256"]), {"broker", "parity", "policy", "feed_review"})
        self.fixture.conn.execute("PRAGMA query_only=ON")
        read_only = build_selected_report(
            self.fixture.conn,
            now=self.fixture.now,
            since=self.fixture.since,
            broker=self.fixture.broker,
            parity=self.parity,
            policy=self.fixture.policy,
        )
        self.assertEqual(read_only["status"], "AWAITING_OPERATOR_REVIEW")

    def test_old_identity_and_mixed_cohort_cannot_qualify_selected(self):
        original = dict(self.parity)
        for key, value in (
            ("contract_id", "1af968e9ac6a26ea"),
            ("snapshot", "RESEARCH-C22-H4EMA200-20261004"),
            ("account_fingerprint", "other"),
            ("release_hash", "d" * 64),
            ("config_hash", "e" * 64),
        ):
            with self.subTest(key=key):
                self.parity = original | {key: value}
                self.assertIn(
                    "selected_parity_identity_or_cohort_mismatch", self.report()["blockers"]
                )
        self.parity = original
        self.fixture.values["strategy_snapshot"] = "RESEARCH-C22-H4EMA200-20261004"
        self.assertIn("journal_identity_or_strategy_missing", self.report()["blockers"])
        self.fixture.values["strategy_snapshot"] = SNAPSHOT
        self.fixture.conn.execute(
            "UPDATE audit_events SET payload=json_set(payload,'$.release_hash',?) WHERE id=1",
            ("d" * 64,),
        )
        mixed = self.report()
        self.assertEqual(mixed["status"], "BLOCKED")
        self.assertIsNone(mixed["cohort"])
        self.assertIn("selected_single_cohort_missing_or_invalid", mixed["blockers"])

    def test_input_bindings_cover_exact_documents_with_stable_key_order(self):
        baseline = self.report()["input_sha256"]
        for field, document in (
            ("broker", self.fixture.broker),
            ("parity", self.parity),
            ("policy", self.fixture.policy),
        ):
            with self.subTest(field=field):
                document["fixture_evidence_revision"] = "changed"
                changed = self.report()["input_sha256"]
                self.assertNotEqual(changed[field], baseline[field])
                for untouched in set(baseline) - {field}:
                    self.assertEqual(changed[untouched], baseline[untouched])
                del document["fixture_evidence_revision"]
        self.parity = dict(reversed(list(self.parity.items())))
        self.assertEqual(self.report()["input_sha256"], baseline)

    def test_old_feed_review_and_monday_waiver_never_transfer(self):
        review = self.fixture.monday_attended_review()
        self.fixture.values["strategy_snapshot"] = SNAPSHOT
        self.fixture.last["snapshot"] = SNAPSHOT
        for ident, raw in self.fixture.conn.execute(
            "SELECT id,payload FROM audit_events"
        ).fetchall():
            event = json.loads(raw)
            if event["kind"] == "CYCLE":
                event["result"]["snapshot"] = SNAPSHOT
            self.fixture.conn.execute(
                "UPDATE audit_events SET payload=? WHERE id=?", (json.dumps(event), ident)
            )
        result = self.report(feed_review=review)
        self.assertIn("selected_feed_review_identity_or_cohort_mismatch", result["blockers"])
        self.assertIn("selected_shadow_time_waiver_not_authorized", result["blockers"])
        self.assertIn("shadow_48h_continuous_observation_missing", result["blockers"])
        self.assertIn("shadow_96_new_complete_m15_missing", result["blockers"])
        self.assertFalse(result["shadow"]["time_requirement_waived_for_attended_trial"])
        self.assertFalse(result["execution_authorized"])

    def test_selected_magic_observed_cost_drift_is_not_ignored(self):
        stamp = int(self.fixture.now.timestamp() * 1000)
        common = dict(position_id=12, volume=0.01, time_msc=stamp, fee=0.0, swap=0.0)
        self.fixture.broker["history_deals"] = [
            dict(common, entry=0, type=0, magic=MAGIC, commission=-0.05),
            dict(common, entry=1, type=1, magic=0, commission=0.0),
        ]
        result = self.report()
        self.assertIn("cost_deal_or_calendar_unverified", result["blockers"])
        self.assertEqual(result["costs"]["status"], "cost_broker_deal_drift")

    def test_current_heartbeat_must_have_matching_completed_cycle_evidence(self):
        self.fixture.last["captured_utc"] = (self.fixture.now - timedelta(seconds=1)).isoformat()
        result = self.report()
        self.assertIn("selected_latest_cycle_not_bound_to_heartbeat", result["blockers"])
        self.assertEqual(result["status"], "BLOCKED")

    def test_cli_binds_raw_input_bytes_and_never_overwrites_journal_or_report(self):
        self.short_observation()
        waiver = self.duration_waiver()
        self.report(shadow_waiver=waiver)
        with TemporaryDirectory(dir=ROOT / "runs") as folder:
            root = Path(folder)
            journal = root / "financial.sqlite3"
            target = sqlite3.connect(journal)
            self.fixture.conn.backup(target)
            target.close()
            original = journal.read_bytes()
            args = ["--journal", str(journal), "--since", self.fixture.since.isoformat()]
            for flag, document in (
                ("broker", self.fixture.broker),
                ("parity", self.parity),
                ("cost-policy", self.fixture.policy),
                ("shadow-waiver", waiver),
            ):
                path = root / (flag + ".json")
                path.write_text(json.dumps(document, indent=2) + "\n")
                args += ["--" + flag, str(path)]
            output = root / "readiness.json"
            args += ["--out", str(output)]
            with (
                patch("scripts.ops.c22_selected_readiness.datetime") as clock,
                redirect_stdout(StringIO()),
            ):
                clock.now.return_value = self.fixture.now
                self.assertEqual(main(args), 0)
            result = json.loads(output.read_text())
            self.assertFalse(result["execution_authorized"])
            self.assertEqual(
                result["raw_input_sha256"]["broker"],
                hashlib.sha256((root / "broker.json").read_bytes()).hexdigest(),
            )
            self.assertNotEqual(
                result["raw_input_sha256"]["broker"], result["input_sha256"]["broker"]
            )
            self.assertEqual(
                result["raw_input_sha256"]["shadow_waiver"],
                hashlib.sha256((root / "shadow-waiver.json").read_bytes()).hexdigest(),
            )
            self.assertTrue(result["shadow"]["selected_duration_waiver_applied"])
            self.assertEqual(journal.read_bytes(), original)
            preserved = output.read_bytes()
            with self.assertRaises(SystemExit):
                main(args)
            self.assertEqual(output.read_bytes(), preserved)
            self.assertEqual(journal.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
