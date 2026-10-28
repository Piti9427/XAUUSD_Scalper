"""Incident-specific operator resolution; never broker orders or blind unhalt."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.demo_runtime.journal import Journal
from scripts.ops.c22_unknown_resolution import plan_resolution, apply_resolution, main

NOW = datetime(2026, 10, 28, 15, tzinfo=timezone.utc)
FP = "a" * 16
REL = "b" * 64
CFG = "c" * 64


class UnknownResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "execution.sqlite3"
        self.guard = Journal(self.path.parent / f"demo-account-{FP}.sqlite3")
        self.guard.close()
        j = Journal(self.path)
        j.audit_context = dict(account_fingerprint=FP, release_hash=REL, config_hash=CFG)
        j.put("identity", FP)
        j.put("strategy_snapshot", "RESEARCH-C22-SELECTED-20261025-26B8")
        j.put("day", {"day": "2026-10-28", "equity": 200})
        j.put("selected_last_loss_ms", 1)
        request = dict(comment="C22S:fixture", magic=22261025, type=0, volume=0.01)
        active = dict(
            position_id=7,
            comment=request["comment"],
            entry_ms=int((NOW - timedelta(minutes=2)).timestamp() * 1000),
            request=request,
            cohort_id=REL + ":" + CFG,
        )
        j.put("active", active)
        j.put("safety_halt", "position_identity_unresolved")
        j.transition(
            "active",
            None,
            dict(
                kind="CLOSED",
                position_id=7,
                net=-1.0,
                profit=-1.0,
                commission=0.0,
                swap=0.0,
                fee=0.0,
            ),
        )
        j.conn.execute("update events set sent=1")
        j.conn.commit()
        j.close()
        opened = int((NOW - timedelta(minutes=2)).timestamp() * 1000)
        closed = int((NOW - timedelta(minutes=1)).timestamp() * 1000)
        self.packet = dict(
            source="existing_sender_reads",
            account_fingerprint=FP,
            release_hash=REL,
            config_hash=CFG,
            captured_utc=(NOW - timedelta(seconds=1)).isoformat(),
            read_observed_utc=NOW.isoformat(),
            demo_verified=True,
            hedging_verified=True,
            symbol="XAUUSDm",
            positions=0,
            orders=0,
            terminal={"connected": True},
            account={"currency": "USD", "balance": 199.0, "equity": 199.0},
            history_start_utc="1970-01-01T00:00:00+00:00",
            history_end_utc=NOW.isoformat(),
            history_complete=True,
            history_deals_total=3,
            execution_authorized=False,
            order_send_called=False,
            history_deals=[
                dict(
                    ticket=1,
                    type=2,
                    entry=0,
                    position_id=0,
                    magic=0,
                    time_msc=1,
                    volume=0,
                    profit=200.0,
                    commission=0.0,
                    swap=0.0,
                    fee=0.0,
                    comment="deposit",
                ),
                dict(
                    ticket=2,
                    type=0,
                    entry=0,
                    position_id=7,
                    magic=22261025,
                    time_msc=opened,
                    volume=0.01,
                    profit=0.0,
                    commission=0.0,
                    swap=0.0,
                    fee=0.0,
                    comment="C22S:fixture",
                ),
                dict(
                    ticket=3,
                    type=1,
                    entry=1,
                    position_id=7,
                    magic=22261025,
                    time_msc=closed,
                    volume=0.01,
                    profit=-1.0,
                    commission=0.0,
                    swap=0.0,
                    fee=0.0,
                    comment="exit",
                ),
            ],
        )

    def raw(self, packet=None):
        return json.dumps(packet or self.packet, sort_keys=True).encode()

    def plan(self):
        return plan_resolution(self.path, self.raw(), now=NOW)

    def review(self, plan):
        raw = json.dumps(
            dict(
                schema=1,
                decision="RESOLVE_PROVED_CLOSED",
                scope_sha256=plan["scope_sha256"],
                approved_utc=NOW.isoformat(),
                expires_utc=(NOW + timedelta(minutes=5)).isoformat(),
                owner_decision_ref="fixture-explicit-incident-approval",
            ),
            sort_keys=True,
        ).encode()
        return raw, hashlib.sha256(raw).hexdigest()

    def values(self):
        j = Journal(self.path)
        try:
            return {k: json.loads(v) for k, v in j.conn.execute("select key,value from kv")}
        finally:
            j.close()

    def test_proved_closed_resolution_changes_only_halt_and_retains_append_only_review_after_restart(
        self,
    ):
        before = self.values()
        plan = self.plan()
        review, pin = self.review(plan)
        applied = apply_resolution(
            self.path, plan, self.raw(), review_bytes=review, trusted_review_sha256=pin, now=NOW
        )
        self.assertEqual(applied["status"], "RESOLVED_PROVED_CLOSED")
        after = self.values()
        self.assertIsNone(after["safety_halt"])
        self.assertEqual(
            {k: v for k, v in before.items() if k != "safety_halt"},
            {k: v for k, v in after.items() if k != "safety_halt"},
        )
        j = Journal(self.path)
        try:
            record = json.loads(
                j.conn.execute(
                    "select payload from audit_events where json_extract(payload,'$.kind')='OPERATOR_UNKNOWN_RESOLUTION'"
                ).fetchone()[0]
            )
            self.assertEqual(record["review_sha256"], pin)
            self.assertEqual(record["incident_id"], plan["incident_id"])
            self.assertEqual(record["position_id"], 7)
        finally:
            j.close()
        with self.assertRaises(ValueError):
            apply_resolution(
                self.path, plan, self.raw(), review_bytes=review, trusted_review_sha256=pin, now=NOW
            )

    def test_no_owner_review_wrong_incident_or_unpinned_review_keeps_halt(self):
        plan = self.plan()
        review, pin = self.review(plan)
        for raw, trusted in [(None, None), (review, "f" * 64)]:
            with self.subTest(trusted=trusted), self.assertRaises(ValueError):
                apply_resolution(
                    self.path,
                    plan,
                    self.raw(),
                    review_bytes=raw,
                    trusted_review_sha256=trusted,
                    now=NOW,
                )
        other = deepcopy(plan)
        other["scope"]["incident_id"] = "wrong"
        with self.assertRaises(ValueError):
            apply_resolution(
                self.path,
                other,
                self.raw(),
                review_bytes=review,
                trusted_review_sha256=pin,
                now=NOW,
            )
        self.assertEqual(self.values()["safety_halt"], "position_identity_unresolved")

    def test_stale_foreign_missing_history_or_changed_costs_cannot_prove_outcome(self):
        for key, value in [
            ("positions", 1),
            ("orders", 1),
            ("account_fingerprint", "f" * 16),
            ("history_complete", False),
            ("history_deals_total", 2),
        ]:
            bad = deepcopy(self.packet)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                plan_resolution(self.path, self.raw(bad), now=NOW)
        bad = deepcopy(self.packet)
        bad["captured_utc"] = (NOW - timedelta(minutes=6)).isoformat()
        with self.assertRaises(ValueError):
            plan_resolution(self.path, self.raw(bad), now=NOW)
        bad = deepcopy(self.packet)
        bad["history_deals"][-1]["swap"] = -0.1
        with self.assertRaises(ValueError):
            plan_resolution(self.path, self.raw(bad), now=NOW)

    def test_live_writer_and_new_active_intent_refuse_resolution(self):
        plan = self.plan()
        review, pin = self.review(plan)
        j = Journal(self.path)
        try:
            with self.assertRaises(ValueError):
                apply_resolution(
                    self.path,
                    plan,
                    self.raw(),
                    review_bytes=review,
                    trusted_review_sha256=pin,
                    now=NOW,
                )
            j.put("active", {"status": "UNKNOWN"})
        finally:
            j.close()
        with self.assertRaises(ValueError):
            plan_resolution(self.path, self.raw(), now=NOW)

    def test_new_observation_time_only_can_refresh_flat_proof_without_new_authority(self):
        plan = self.plan()
        review, pin = self.review(plan)
        fresh = deepcopy(self.packet)
        later = NOW + timedelta(seconds=2)
        for key in ("captured_utc", "read_observed_utc", "history_end_utc"):
            fresh[key] = later.isoformat()
        result = apply_resolution(
            self.path,
            plan,
            self.raw(fresh),
            review_bytes=review,
            trusted_review_sha256=pin,
            now=later,
        )
        self.assertEqual(result["status"], "RESOLVED_PROVED_CLOSED")

    def test_final_stale_proof_and_new_cashflow_scope_keep_halt(self):
        plan = self.plan()
        review, pin = self.review(plan)
        with self.assertRaisesRegex(ValueError, "final_flat_proof"):
            apply_resolution(
                self.path,
                plan,
                self.raw(),
                review_bytes=review,
                trusted_review_sha256=pin,
                now=NOW + timedelta(seconds=6),
            )
        changed = deepcopy(self.packet)
        changed["history_deals"].append(
            dict(
                changed["history_deals"][0],
                ticket=4,
                time_msc=int(NOW.timestamp() * 1000),
                profit=10.0,
            )
        )
        changed["history_deals_total"] = 4
        changed["account"]["balance"] = changed["account"]["equity"] = 209.0
        with self.assertRaisesRegex(ValueError, "state_changed"):
            apply_resolution(
                self.path,
                plan,
                self.raw(changed),
                review_bytes=review,
                trusted_review_sha256=pin,
                now=NOW,
            )
        self.assertEqual(self.values()["safety_halt"], "position_identity_unresolved")

    def test_audit_failure_rolls_back_halt_resolution_atomically(self):
        plan = self.plan()
        review, pin = self.review(plan)
        original = Journal._audit

        def fail_after_insert(store, *args, **kwargs):
            original(store, *args, **kwargs)
            raise RuntimeError("fixture_storage_fault")

        with (
            patch.object(Journal, "_audit", new=fail_after_insert),
            self.assertRaises(RuntimeError),
        ):
            apply_resolution(
                self.path, plan, self.raw(), review_bytes=review, trusted_review_sha256=pin, now=NOW
            )
        self.assertEqual(self.values()["safety_halt"], "position_identity_unresolved")
        store = Journal(self.path)
        try:
            self.assertEqual(
                store.conn.execute(
                    "select count(*) from audit_events where json_extract(payload,'$.kind')='OPERATOR_UNKNOWN_RESOLUTION'"
                ).fetchone()[0],
                0,
            )
        finally:
            store.close()

    def test_plan_alias_tamper_and_non_unknown_financial_halt_never_resolve(self):
        plan = self.plan()
        review, pin = self.review(plan)
        bad = deepcopy(plan)
        bad["incident_id"] = "another-incident"
        with self.assertRaisesRegex(ValueError, "plan"):
            apply_resolution(
                self.path, bad, self.raw(), review_bytes=review, trusted_review_sha256=pin, now=NOW
            )
        store = Journal(self.path)
        try:
            prior = json.loads(
                store.conn.execute(
                    "select payload from audit_events where json_extract(payload,'$.kind')='LIFECYCLE' order by id desc limit 1"
                ).fetchone()[0]
            )
            store.audit_context = dict(account_fingerprint=FP, release_hash=REL, config_hash=CFG)
            store.put("active", prior["active"])
            store.put("safety_halt", "filled_risk_violation")
            repeated = {k: v for k, v in prior["event"].items() if k != "event_id"}
            store.transition("active", None, repeated)
            store.conn.execute("update events set sent=1")
            store.conn.commit()
        finally:
            store.close()
        with self.assertRaisesRegex(ValueError, "scope"):
            plan_resolution(self.path, self.raw(), now=NOW)

    def test_disabled_notification_outbox_is_preserved_without_blocking_proved_close(self):
        store = Journal(self.path)
        store.conn.execute("update events set sent=0")
        store.conn.commit()
        store.close()
        plan = self.plan()
        review, pin = self.review(plan)
        self.assertEqual(plan["pending_notification_events"], 1)
        apply_resolution(
            self.path, plan, self.raw(), review_bytes=review, trusted_review_sha256=pin, now=NOW
        )
        store = Journal(self.path)
        try:
            self.assertEqual(
                store.conn.execute("select count(*) from events where sent=0").fetchone()[0], 1
            )
        finally:
            store.close()

    def test_cli_reserves_receipt_before_any_resolution_mutation(self):
        plan = self.plan()
        review, pin = self.review(plan)
        root = self.path.parent
        for name, raw in [
            ("plan.json", json.dumps(plan).encode()),
            ("review.json", review),
            ("broker.json", self.raw()),
        ]:
            (root / name).write_bytes(raw)
        args = [
            "--journal",
            str(self.path),
            "--broker",
            str(root / "broker.json"),
            "--plan",
            str(root / "plan.json"),
            "--review",
            str(root / "review.json"),
            "--review-sha256",
            pin,
            "--out",
            str(root / "receipt.json"),
        ]
        with (
            patch("scripts.ops.c22_unknown_resolution.os.open", side_effect=FileExistsError),
            self.assertRaises(FileExistsError),
        ):
            main(args, now=NOW)
        self.assertEqual(self.values()["safety_halt"], "position_identity_unresolved")


if __name__ == "__main__":
    unittest.main()
