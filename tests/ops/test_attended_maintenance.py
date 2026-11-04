"""Exercise the reviewed maintenance interface with real disposable journals."""

from dataclasses import replace
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.demo_runtime.journal import Journal
from scripts.ops.attended_maintenance import (
    APMeasurement, Approval, Cohort, CostInstallation, Maintenance,
    NotificationMode, Observation, OwnedProbe, Plan, Reboot,
)


NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)
COHORT = Cohort(*("a" * 16, "b" * 64, "c" * 64, "d" * 64,
                  "e" * 64, "f" * 64, "fixture26b8"))


class RecordingHost:
    """Closed effect adapter. Never opens SSH, SDK, transport or systemd."""

    def __init__(self, journal):
        self.journal = journal
        self.state = Observation(NOW, 100.0, "boot-1", COHORT, "4" * 64, True)
        self.calls = []
        self.fail = {}
        self.hooks = {}
        self.auto_boot = True

    def observe(self, handle):
        return self.state

    def effect(self, name):
        self.calls.append(name)
        self.state = replace(self.state, monotonic=self.state.monotonic + 1,
                             captured_utc=self.state.captured_utc + timedelta(seconds=1))
        if name in self.hooks:
            self.hooks[name]()
        if name in self.fail:
            raise self.fail[name]

    def hold_review(self, handle):
        self.effect("hold")
        self.state = replace(self.state, review_held=True, post_hold_cycle=True)
        self.cycle()

    def cycle(self):
        self.journal.put("last_result", dict(captured_utc=self.state.captured_utc.isoformat(),
                                            execute=True, observed_positions=0, position_protection="flat"))

    def stop_sender(self, handle):
        self.effect("stop")
        self.state = replace(self.state, sender_running=False, sender_count=0)

    def prove_broker_flat(self, handle):
        self.effect("broker")
        return {"account": self.state.cohort.account, "captured_utc": self.state.captured_utc.isoformat(),
                "positions": 0, "orders": 0}

    def measure_ap(self, handle, action):
        self.effect("ap")

    def cleanup_probe(self, handle, identity):
        self.effect("cleanup")
        self.state = replace(self.state, owned_probe=None)

    def install_cost(self, handle, action):
        self.effect("cost")
        self.state = replace(self.state, cost_marker=action.generation,
                             cohort=replace(COHORT, policy=action.policy, review=action.review))

    def restore_cost(self, handle, generation):
        self.effect("recover_cost")

    def reboot(self, handle, action):
        self.effect("reboot")
        if self.auto_boot:
            self.state = replace(self.state, boot="boot-2", monotonic=10,
                                 startup_verified=True, outside_pause_seconds=7)

    def restore_review(self, handle, cohort):
        self.effect("restore")
        self.state = replace(self.state, review_held=False, cohort=cohort)

    def start_sender(self, handle):
        self.effect("start")
        self.state = replace(self.state, sender_running=True, sender_count=1, recovered_cycle=True)
        self.cycle()


class AttendedMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "financial.sqlite3"
        self.journal = Journal(self.path)
        self.addCleanup(self.journal.close)
        self.journal.audit_context = {
            "account_fingerprint": COHORT.account,
            "release_hash": COHORT.source, "config_hash": COHORT.config,
        }
        self.journal.put("identity", COHORT.account)
        self.journal.put("strategy_snapshot", "fixture26b8")
        self.journal.put("last_result", dict(captured_utc=NOW.isoformat(), execute=True,
                                            observed_positions=0, position_protection="flat"))
        self.host = RecordingHost(self.journal)
        self.module = Maintenance(self.path)

    def plan(self, action=None, **changes):
        return Plan("op-1", COHORT, "4" * 64, action or APMeasurement("1" * 64),
                    mode=NotificationMode.OFF_NOTIFICATION_HANDOFF, **changes)

    def approve(self, handle):
        return Approval(handle.digest, "owner-local-fixture", self.host.state.captured_utc,
                        allow_manager_recovery=True, allow_probe_cleanup=True)

    def add_event(self, kind="FILLED"):
        self.journal.transition("active", None, {"kind": kind, "fixture": "original"})

    def rows(self):
        return self.journal.conn.execute("SELECT id,payload,sent FROM events ORDER BY id").fetchall()

    def test_handoff_preserves_exact_rows_across_all_three_action_families(self):
        self.add_event()
        original = self.rows()
        for index, action in enumerate((APMeasurement("1" * 64), Reboot(),
                                       CostInstallation("generation-2", "2" * 64, "3" * 64))):
            with self.subTest(action=action):
                self.host = RecordingHost(self.journal)
                self.host.cycle()
                handle = self.module.prepare(replace(self.plan(action), operation=f"op-{index}"), self.host)
                result = self.module.run(handle, self.approve(handle), self.host)
                self.assertEqual(result["status"], "COMPLETE")
                self.assertEqual(self.rows(), original)
                self.assertEqual(self.host.calls.count("broker"), 1)
                self.assertEqual(self.module.inspect(handle), result)

    def test_strict_zero_defers_without_any_host_effect(self):
        self.add_event()
        with self.assertRaisesRegex(ValueError, "sender_outbox_defer"):
            self.module.prepare(replace(self.plan(), mode=NotificationMode.STRICT_ZERO), self.host)
        self.assertEqual(self.host.calls, [])

    def test_payload_change_with_same_count_is_detected_and_manager_preserved(self):
        self.add_event()
        handle = self.module.prepare(self.plan(), self.host)
        def alter():
            with self.journal.conn:
                self.journal.conn.execute("UPDATE events SET payload=?", ('{"kind":"CLOSED"}',))
        self.host.hooks["start"] = alter
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "STATE_REVIEW_REQUIRED")
        self.assertTrue(self.host.state.sender_running)
        self.assertEqual(self.host.calls.count("stop"), 1)
        self.assertIn("outbox_row_changed", json.dumps(result))

    def test_row_delete_renumber_sent_and_schema_changes_are_rejected(self):
        for sql in ("DELETE FROM events", "UPDATE events SET id=id+10", "UPDATE events SET sent=1",
                    "ALTER TABLE events ADD COLUMN extra TEXT"):
            with self.subTest(sql=sql), TemporaryDirectory() as tmp:
                # Independent fixtures avoid repairing or rewinding a financial journal.
                path = Path(tmp) / "copy.sqlite3"
                with closing(sqlite3.connect(path)) as db:
                    self.journal.conn.backup(db)
                journal = Journal(path)
                journal.audit_context = self.journal.audit_context
                journal.transition("active", None, {"kind": "FILLED"})
                self.addCleanup(journal.close)
                module = Maintenance(path)
                host = RecordingHost(journal)
                handle = module.prepare(self.plan(), host)
                host.hooks["start"] = lambda: journal.conn.execute(sql)
                result = module.run(handle, self.approve(handle), host)
                self.assertEqual(result["status"], "STATE_REVIEW_REQUIRED")
                self.assertTrue(host.state.sender_running)

    def test_unknown_notification_foreign_cohort_and_unreviewed_critical_defer(self):
        for kind in ("UNRECOGNIZED", "CRITICAL"):
            with self.subTest(kind=kind):
                self.add_event(kind)
                with self.assertRaisesRegex(ValueError, "unknown_notification|critical_review"):
                    self.module.prepare(self.plan(), self.host)
                self.assertEqual(self.host.calls, [])
                # Each subcase uses only disposable fixture rows.
                with self.journal.conn:
                    self.journal.conn.execute("DELETE FROM events")
        self.journal.audit_context["account_fingerprint"] = "9" * 64
        self.add_event()
        with self.assertRaisesRegex(ValueError, "notification_cohort_drift"):
            self.module.prepare(self.plan(), self.host)

    def test_reviewed_critical_requires_exact_payload_and_resolved_condition(self):
        self.add_event("CRITICAL")
        ident, raw, _ = self.rows()[0]
        plan = self.plan(reviewed_critical=((ident, hashlib.sha256(raw.encode()).hexdigest(), "owner-review"),))
        self.host.state = replace(self.host.state, unresolved_critical=(ident,))
        with self.assertRaisesRegex(ValueError, "critical_review_required"):
            self.module.prepare(plan, self.host)
        self.host.state = replace(self.host.state, unresolved_critical=())
        handle = self.module.prepare(plan, self.host)
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(self.rows()[0], (ident, raw, 0))

    def test_delivery_enabled_or_uncertain_blocks_handoff_without_effects(self):
        self.add_event()
        for values in ({"delivery_off": False}, {"delivery_inflight": True}):
            with self.subTest(values=values):
                self.host.state = replace(self.host.state, delivery_off=True, delivery_inflight=False, **{})
                self.host.state = replace(self.host.state, **values)
                with self.assertRaisesRegex(ValueError, "notification_delivery_uncertain"):
                    self.module.prepare(self.plan(), self.host)
                self.assertEqual(self.host.calls, [])

    def test_missing_wrong_or_drifted_approval_cannot_start_effect(self):
        handle = self.module.prepare(self.plan(), self.host)
        for approval in (None, replace(self.approve(handle), plan_digest="0" * 64),
                         replace(self.approve(handle), owner_ref="")):
            with self.subTest(approval=approval), self.assertRaises(ValueError):
                self.module.run(handle, approval, self.host)
        self.assertEqual(self.host.calls, [])

    def test_freshness_source_backup_active_unknown_and_halt_block_before_hold(self):
        cases = ("stale", "source", "backup", "active", "halt")
        for index, case in enumerate(cases):
            with self.subTest(case=case):
                plan = replace(self.plan(), operation=f"guard-{index}")
                handle = self.module.prepare(plan, self.host)
                state = self.host.state
                if case == "stale":
                    self.host.state = replace(state, captured_utc=NOW + timedelta(seconds=20))
                elif case == "source":
                    self.host.state = replace(state, cohort=replace(COHORT, source="0" * 64))
                elif case == "backup":
                    self.host.state = replace(state, backup_restore_verified=False)
                else:
                    self.journal.put("active" if case == "active" else "safety_halt", {"state": "UNKNOWN"})
                result = self.module.run(handle, self.approve(handle), self.host)
                self.assertEqual(result["status"], "DEFERRED")
                self.assertEqual(self.host.calls, [])
                self.host.state = state
                if case in ("active", "halt"):
                    self.journal.put("active" if case == "active" else "safety_halt", None)

    def test_stop_timeout_never_overlaps_broker_and_same_handle_resumes(self):
        self.add_event()
        handle = self.module.prepare(self.plan(), self.host)
        approval = self.approve(handle)
        self.host.fail["stop"] = TimeoutError("PRIVATE")
        first = self.module.run(handle, approval, self.host)
        self.assertEqual(first["status"], "WAITING_STOP")
        self.assertNotIn("broker", self.host.calls)
        self.assertNotIn("PRIVATE", json.dumps(first))
        self.host.state = replace(self.host.state, sender_running=False, sender_count=0)
        restarted = Maintenance(self.path)
        result = restarted.run(handle, approval, self.host)
        self.assertEqual(result["status"], "FAILED_RECOVERED")
        self.assertEqual(self.host.calls.count("stop"), 1)
        self.assertEqual(self.host.calls.count("broker"), 1)

    def test_lingering_reader_prevents_sdk_and_start_but_preserves_primary_failure(self):
        handle = self.module.prepare(self.plan(), self.host)
        self.host.hooks["stop"] = lambda: setattr(self.host, "state", replace(self.host.state, readers=("foreign-reader",)))
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "OPERATOR_REQUIRED")
        self.assertNotIn("broker", self.host.calls)
        self.assertNotIn("start", self.host.calls)
        self.assertIn("reader_ownership_unverified", json.dumps(result))

    def test_broker_foreign_exposure_stale_and_unknown_proofs_never_dispatch_action(self):
        packets = ({"positions": 1}, {"orders": 1}, {"account": "foreign"},
                   {"captured_utc": (NOW - timedelta(seconds=30)).isoformat()})
        for index, change in enumerate(packets):
            with self.subTest(change=change):
                self.host = RecordingHost(self.journal)
                self.host.cycle()
                handle = self.module.prepare(replace(self.plan(), operation=f"broker-{index}"), self.host)
                original = self.host.prove_broker_flat
                self.host.prove_broker_flat = lambda h, original=original, change=change: dict(original(h), **change)
                result = self.module.run(handle, self.approve(handle), self.host)
                self.assertEqual(result["status"], "FAILED_RECOVERED")
                self.assertNotIn("ap", self.host.calls)
                self.assertEqual(self.host.calls.count("restore"), 1)

    def test_ap_primary_and_cleanup_failures_are_both_retained(self):
        handle = self.module.prepare(self.plan(), self.host)
        self.host.hooks["ap"] = lambda: setattr(self.host, "state", replace(
            self.host.state, owned_probe=OwnedProbe("op-1", "boot-1", 123, "start-identity", "1" * 64)))
        self.host.fail = {"ap": TimeoutError("PRIVATE"), "cleanup": OSError("PRIVATE")}
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "OPERATOR_REQUIRED")
        self.assertEqual([f["category"] for f in result["failures"]], ["PRIMARY", "CLEANUP"])
        self.assertNotIn("start", self.host.calls)
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_reboot_lost_ack_and_controller_restart_never_redispatch_or_preboot_start(self):
        self.add_event()
        handle = self.module.prepare(self.plan(Reboot()), self.host)
        approval = self.approve(handle)
        self.host.auto_boot = False
        self.host.fail["reboot"] = TimeoutError("lost ack")
        result = self.module.run(handle, approval, self.host)
        self.assertEqual(result["status"], "WAITING_REBOOT")
        self.assertNotIn("restore", self.host.calls)
        module = Maintenance(self.path)
        module.run(handle, approval, self.host)
        self.assertEqual(self.host.calls.count("reboot"), 1)
        self.host.state = replace(self.host.state, boot="boot-2", monotonic=5,
                                  startup_verified=True, outside_pause_seconds=10)
        result = module.run(handle, approval, self.host)
        self.assertEqual(result["status"], "FAILED_RECOVERED")
        self.assertTrue(result["manual_fallback"])
        self.assertEqual(self.host.calls.count("reboot"), 1)
        self.assertEqual(self.host.calls.count("start"), 1)

    def test_missing_outside_clock_never_claims_crossboot_budget_pass(self):
        handle = self.module.prepare(self.plan(Reboot()), self.host)
        self.host.hooks["restore"] = lambda: setattr(self.host, "state", replace(self.host.state, outside_pause_seconds=None))
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "STATE_REVIEW_REQUIRED")
        self.assertEqual(result["timing"]["status"], "TIMING_UNVERIFIED")
        self.assertTrue(self.host.state.sender_running)

    def test_cost_accepted_marker_preserves_new_pair_after_lost_ack(self):
        action = CostInstallation("generation-2", "2" * 64, "3" * 64)
        handle = self.module.prepare(self.plan(action), self.host)
        def accepted():
            self.host.state = replace(self.host.state, cost_marker=action.generation,
                                      cohort=replace(COHORT, policy=action.policy, review=action.review))
        self.host.hooks["cost"] = accepted
        self.host.fail["cost"] = TimeoutError("PRIVATE")
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "FAILED_RECOVERED")
        self.assertEqual(self.host.state.cohort.policy, action.policy)
        self.assertEqual(self.host.state.cohort.review, action.review)
        self.assertEqual(self.host.calls.count("cost"), 1)

    def test_cost_unknown_marker_cannot_restore_guessed_generation(self):
        handle = self.module.prepare(self.plan(CostInstallation("next", "2" * 64, "3" * 64)), self.host)
        self.host.hooks["cost"] = lambda: setattr(self.host, "state", replace(self.host.state, cost_marker=None))
        self.host.fail["cost"] = TimeoutError("PRIVATE")
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "STATE_REVIEW_REQUIRED")
        self.assertNotIn("recover_cost", self.host.calls)
        self.assertNotIn("restore", self.host.calls)
        self.assertNotIn("start", self.host.calls)

    def test_reserve_exhaustion_stops_work_and_recovers_review_without_action(self):
        handle = self.module.prepare(self.plan(), self.host)
        self.host.hooks["stop"] = lambda: setattr(self.host, "state", replace(self.host.state, monotonic=800))
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "FAILED_RECOVERED")
        self.assertNotIn("ap", self.host.calls)
        self.assertIn("restore", self.host.calls)
        self.assertIn("work_budget_exhausted", json.dumps(result))

    def test_legitimate_append_after_restoration_preserves_every_prior_row(self):
        self.add_event()
        original = self.rows()
        handle = self.module.prepare(self.plan(), self.host)
        self.host.hooks["start"] = lambda: self.add_event("CLOSED")
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(self.rows()[:len(original)], original)
        self.assertEqual(len(self.rows()), len(original) + 1)

    def test_held_midnight_protected_key_change_keeps_owned_manager_and_reports_unverified(self):
        handle = self.module.prepare(self.plan(), self.host)
        self.host.hooks["start"] = lambda: self.journal.put("day", {"utc_day": "next"})
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "STATE_REVIEW_REQUIRED")
        self.assertTrue(self.host.state.sender_running)
        self.assertEqual(self.journal.get("day"), {"utc_day": "next"})
        self.assertIn("protected_values_continuity_unverified", json.dumps(result))

    def test_durable_account_claim_rejects_another_operation_and_inspect_is_readonly(self):
        first = self.module.prepare(self.plan(Reboot()), self.host)
        second = self.module.prepare(replace(self.plan(), operation="other"), self.host)
        self.host.auto_boot = False
        self.module.run(first, self.approve(first), self.host)
        before = self.module.store.path.read_bytes()
        self.module.inspect(first)
        self.assertEqual(self.module.store.path.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "account_operation_incomplete"):
            self.module.run(second, self.approve(second), self.host)
        self.assertEqual(self.host.calls.count("reboot"), 1)

    def test_controller_crash_during_hold_preserves_original_pause_origin(self):
        handle = self.module.prepare(self.plan(), self.host)
        approval = self.approve(handle)
        self.host.fail["hold"] = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.module.run(handle, approval, self.host)
        self.host.state = replace(self.host.state, review_held=True, post_hold_cycle=True,
                                  monotonic=800, captured_utc=NOW + timedelta(seconds=1))
        self.host.cycle()
        result = Maintenance(self.path).run(handle, approval, self.host)
        self.assertNotIn("ap", self.host.calls)
        self.assertEqual(self.host.calls.count("hold"), 1)
        self.assertIn("work_budget_exhausted", json.dumps(result))

    def test_crash_during_action_cannot_become_unqualified_complete(self):
        handle = self.module.prepare(self.plan(), self.host)
        approval = self.approve(handle)
        self.host.fail["ap"] = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.module.run(handle, approval, self.host)
        result = Maintenance(self.path).run(handle, approval, self.host)
        self.assertEqual(result["status"], "FAILED_RECOVERED")
        self.assertEqual(self.host.calls.count("ap"), 1)
        self.assertIn("effect_outcome_uncertain", json.dumps(result))

    def test_cost_ack_without_acceptance_marker_cannot_report_success(self):
        handle = self.module.prepare(self.plan(CostInstallation("next", "2" * 64, "3" * 64)), self.host)
        def ineffective(handle, action):
            self.host.effect("cost")
        self.host.install_cost = ineffective
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "FAILED_RECOVERED")
        self.assertEqual(self.host.state.cohort, COHORT)
        self.assertIn("cost_installation_unverified", json.dumps(result))

    def test_running_owned_manager_after_hold_is_never_stopped_for_maintenance(self):
        handle = self.module.prepare(self.plan(), self.host)
        self.host.hooks["hold"] = lambda: self.journal.put("active", {"state": "FILLED", "fixture": "owned"})
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertNotIn("stop", self.host.calls)
        self.assertNotIn("broker", self.host.calls)
        self.assertNotIn("ap", self.host.calls)
        self.assertTrue(self.host.state.sender_running)
        self.assertFalse(self.host.state.review_held)
        self.assertEqual(self.journal.get("active")["state"], "FILLED")
        self.assertNotEqual(result["status"], "COMPLETE")

    def test_automatic_reboot_recovery_is_not_labelled_manual_fallback(self):
        handle = self.module.prepare(self.plan(Reboot()), self.host)
        def automatic():
            self.host.state = replace(self.host.state, sender_running=True, sender_count=1, recovered_cycle=True)
            self.host.cycle()
        self.host.hooks["restore"] = automatic
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertFalse(result["manual_fallback"])
        self.assertNotIn("start", self.host.calls)

    def test_approval_expiry_prevents_new_action_without_preventing_approved_recovery(self):
        handle = self.module.prepare(self.plan(), self.host)
        approval = replace(self.approve(handle), valid_until=NOW + timedelta(seconds=2))
        result = self.module.run(handle, approval, self.host)
        self.assertEqual(result["status"], "FAILED_RECOVERED")
        self.assertNotIn("ap", self.host.calls)
        self.assertIn("restore", self.host.calls)

    def test_approved_pending_set_cannot_silently_expand_before_quiescence(self):
        self.add_event()
        handle = self.module.prepare(self.plan(), self.host)
        self.add_event("CLOSED")
        before = self.rows()
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "DEFERRED")
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.host.calls, [])

    def test_financial_database_is_byte_identical_when_only_operation_is_prepared_and_inspected(self):
        self.add_event()
        before = self.path.read_bytes()
        handle = self.module.prepare(self.plan(), self.host)
        self.module.inspect(handle)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.host.calls, [])

    def test_empty_strict_zero_and_exact_effect_order_remain_supported(self):
        handle = self.module.prepare(replace(self.plan(), mode=NotificationMode.STRICT_ZERO), self.host)
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(self.host.calls, ["hold", "stop", "broker", "ap", "restore", "start"])
        self.assertEqual(self.rows(), [])

    def test_foreign_probe_identity_cannot_be_signalled(self):
        handle = self.module.prepare(self.plan(), self.host)
        self.host.hooks["ap"] = lambda: setattr(self.host, "state", replace(
            self.host.state, owned_probe=OwnedProbe("foreign-op", "boot-1", 123, "start", "1" * 64)))
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "STATE_REVIEW_REQUIRED")
        self.assertNotIn("cleanup", self.host.calls)
        self.assertNotIn("start", self.host.calls)

    def test_journal_account_and_snapshot_are_independently_bound(self):
        for key, value in (("identity", "foreign-account"), ("strategy_snapshot", "foreign-strategy")):
            with self.subTest(key=key):
                old = self.journal.get(key)
                self.journal.put(key, value)
                with self.assertRaisesRegex(ValueError, "journal_account_or_strategy_drift"):
                    self.module.prepare(self.plan(), self.host)
                self.assertEqual(self.host.calls, [])
                self.journal.put(key, old)

    def test_budget_source_time_and_typed_action_validation_precede_host_effects(self):
        for changes in ({"pause_seconds": 901}, {"recovery_seconds": 800},
                        {"action_seconds": True}, {"action": "arbitrary-command"},
                        {"backup_sha256": "not-a-hash"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.module.prepare(replace(self.plan(), **changes), self.host)
        self.host.state = replace(self.host.state, captured_utc=NOW.replace(tzinfo=None))
        with self.assertRaisesRegex(ValueError, "aware_utc_required"):
            self.module.prepare(self.plan(), self.host)
        self.assertEqual(self.host.calls, [])

    def test_competing_sender_and_nonboolean_recovery_authority_are_refused(self):
        handle = self.module.prepare(self.plan(), self.host)
        with self.assertRaisesRegex(ValueError, "invalid_recovery_authority"):
            self.module.run(handle, replace(self.approve(handle), allow_manager_recovery="yes"), self.host)
        self.host.state = replace(self.host.state, sender_count=2)
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "DEFERRED")
        self.assertEqual(self.host.calls, [])

    def test_operation_store_private_and_same_journal_serializes_controller_instances(self):
        handle = self.module.prepare(self.plan(), self.host)
        other = Maintenance(self.path)
        self.assertEqual(self.module.store.path, other.store.path)
        self.assertEqual(self.module.store.path.stat().st_mode & 0o077, 0)
        with self.module.store.locked(), self.assertRaisesRegex(ValueError, "controller_busy"):
            other.run(handle, self.approve(handle), self.host)
        self.assertEqual(self.host.calls, [])

    def test_operation_store_hardlink_to_financial_database_is_refused(self):
        canonical = self.path.with_name(self.path.name + ".maintenance.sqlite3")
        canonical.hardlink_to(self.path)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "separate_operation_store_required"):
            Maintenance(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_resolved_evidence_continues_same_handle_without_repeating_cost_install(self):
        action = CostInstallation("next", "2" * 64, "3" * 64)
        handle = self.module.prepare(self.plan(action), self.host)
        approval = self.approve(handle)
        self.host.hooks["cost"] = lambda: setattr(self.host, "state", replace(self.host.state, cost_marker=None))
        self.host.fail["cost"] = TimeoutError("PRIVATE")
        first = self.module.run(handle, approval, self.host)
        self.assertEqual(first["status"], "STATE_REVIEW_REQUIRED")
        self.host.state = replace(self.host.state, cost_marker=action.generation,
                                  cohort=replace(COHORT, policy=action.policy, review=action.review))
        result = Maintenance(self.path).run(handle, approval, self.host)
        self.assertEqual(result["status"], "FAILED_RECOVERED")
        self.assertEqual(self.host.calls.count("cost"), 1)
        self.assertTrue(self.host.state.sender_running)

    def test_slow_proof_read_revalidates_freshness_before_hold(self):
        from scripts.ops.attended_maintenance import controller
        handle = self.module.prepare(self.plan(), self.host)
        approval = self.approve(handle)
        original = controller.read_journal
        def slow(*args, **kwargs):
            result = original(*args, **kwargs)
            self.host.state = replace(self.host.state, captured_utc=self.host.state.captured_utc + timedelta(seconds=21))
            return result
        with patch.object(controller, "read_journal", side_effect=slow):
            result = self.module.run(handle, approval, self.host)
        self.assertEqual(result["status"], "DEFERRED")
        self.assertEqual(self.host.calls, [])

    def test_original_audit_payload_tamper_is_detected_independently_of_outbox_count(self):
        self.add_event()
        handle = self.module.prepare(self.plan(), self.host)
        before = self.rows()
        def corrupt_fixture():
            with self.journal.conn:
                self.journal.conn.execute("DROP TRIGGER audit_no_update")
                self.journal.conn.execute("UPDATE audit_events SET payload=? WHERE id=1", ('{"kind":"changed"}',))
        self.host.hooks["start"] = corrupt_fixture
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertEqual(result["status"], "STATE_REVIEW_REQUIRED")
        self.assertEqual(self.rows(), before)
        self.assertTrue(self.host.state.sender_running)
        self.assertIn("audit_prefix_changed", json.dumps(result))

    def test_real_selected_runtime_identity_is_accepted_without_journal_rewrite(self):
        from scripts.c22_selected.runner import SelectedDemoRunner
        from tests.demo.test_c22_selected_runner import SelectedBroker, selected_config
        from tests.demo.test_trial30_demo import policy

        broker = SelectedBroker()
        path = self.root / "real-contract.sqlite3"
        runner = SelectedDemoRunner(mt5=broker, expected_login=123, expected_server="Exness-Demo",
                                   journal_path=path, config=selected_config(), cost_policy=policy())
        self.addCleanup(runner.close)
        runner.broker.identity()  # Real BrokerView identity path; SDK boundary is fake.
        context = runner.journal.audit_context
        self.assertEqual(len(runner.fingerprint), 16)
        self.assertEqual(runner.journal.get("identity"), runner.fingerprint)
        cohort = replace(COHORT, account=runner.fingerprint, source=runner.release_hash,
                         config=context["config_hash"], snapshot=runner.strategy.snapshot)
        host = RecordingHost(runner.journal)
        host.state = replace(host.state, cohort=cohort)
        host.cycle()  # Synthetic flat cycle, not claimed as actual native execution.
        module = Maintenance(path)
        before = path.read_bytes()
        handle = module.prepare(replace(self.plan(), cohort=cohort), host)
        self.assertEqual(path.read_bytes(), before)
        result = module.run(handle, self.approve(handle), host)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(runner.journal.get("identity"), runner.fingerprint)
        broker.order_send.assert_not_called()

    def test_terminal_receipt_and_account_release_are_one_atomic_operation(self):
        from scripts.ops.attended_maintenance.store import Store
        handle = self.module.prepare(self.plan(), self.host)
        approval = self.approve(handle)
        original = Store.save
        def interrupt_after_save(db, document, **kwargs):
            original(db, document, **kwargs)
            if document["phase"] == "END":
                raise KeyboardInterrupt()
        with patch.object(Store, "save", side_effect=interrupt_after_save), self.assertRaises(KeyboardInterrupt):
            self.module.run(handle, approval, self.host)
        result = Maintenance(self.path).run(handle, approval, self.host)
        self.assertEqual(result["status"], "COMPLETE")
        next_handle = self.module.prepare(replace(self.plan(), operation="op-after-complete"), self.host)
        result = self.module.run(next_handle, self.approve(next_handle), self.host)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(self.host.calls.count("ap"), 2)

    def test_transient_review_restore_failure_can_retry_same_conditional_recovery(self):
        handle = self.module.prepare(self.plan(), self.host)
        approval = self.approve(handle)
        self.host.fail["restore"] = TimeoutError("PRIVATE")
        first = self.module.run(handle, approval, self.host)
        self.assertEqual(first["status"], "OPERATOR_REQUIRED")
        self.assertTrue(self.host.state.review_held)
        self.assertFalse(self.host.state.sender_running)
        self.host.fail.clear()
        result = Maintenance(self.path).run(handle, approval, self.host)
        self.assertEqual(result["status"], "FAILED_RECOVERED")
        self.assertEqual(self.host.calls.count("ap"), 1)
        self.assertEqual(self.host.calls.count("restore"), 2)
        self.assertTrue(self.host.state.sender_running)

    def test_transient_cleanup_retries_only_same_owned_probe_without_repeating_ap(self):
        handle = self.module.prepare(self.plan(), self.host)
        approval = self.approve(handle)
        self.host.hooks["ap"] = lambda: setattr(self.host, "state", replace(
            self.host.state, owned_probe=OwnedProbe("op-1", "boot-1", 123, "same-start", "1" * 64)))
        self.host.fail["cleanup"] = TimeoutError("PRIVATE")
        self.module.run(handle, approval, self.host)
        self.host.fail.clear()
        result = Maintenance(self.path).run(handle, approval, self.host)
        self.assertEqual(result["status"], "FAILED_RECOVERED")
        self.assertEqual(self.host.calls.count("ap"), 1)
        self.assertEqual(self.host.calls.count("cleanup"), 2)
        self.assertIsNone(self.host.state.owned_probe)
        self.assertTrue(self.host.state.sender_running)

    def test_truthy_unknown_host_flags_are_not_evidence(self):
        for field in ("backup_restore_verified", "delivery_off", "delivery_inflight",
                      "review_restore_safe", "sender_running", "post_hold_cycle"):
            with self.subTest(field=field):
                state = self.host.state
                try:
                    self.host.state = replace(state, **{field: "UNKNOWN"})
                    with self.assertRaisesRegex(ValueError, "invalid_host_observation"):
                        self.module.prepare(self.plan(), self.host)
                    self.assertEqual(self.host.calls, [])
                finally:
                    self.host.state = state

    def test_probe_left_after_broker_proof_prevents_work_dispatch(self):
        handle = self.module.prepare(self.plan(), self.host)
        self.host.hooks["broker"] = lambda: setattr(self.host, "state", replace(
            self.host.state, owned_probe=OwnedProbe("op-1", "boot-1", 123, "same-start", "1" * 64)))
        result = self.module.run(handle, self.approve(handle), self.host)
        self.assertNotEqual(result["status"], "COMPLETE")
        self.assertNotIn("ap", self.host.calls)
        self.assertIn("reader_ownership_unverified", json.dumps(result))

    def test_late_reader_before_manager_start_prevents_overlapping_sdk_ownership(self):
        handle = self.module.prepare(self.plan(), self.host)
        approval = self.approve(handle)
        self.host.hooks["restore"] = lambda: setattr(self.host, "state", replace(
            self.host.state, readers=("late-reader",)))
        result = self.module.run(handle, approval, self.host)
        self.assertNotIn("start", self.host.calls)
        self.assertFalse(self.host.state.sender_running)
        self.assertNotEqual(result["status"], "COMPLETE")
        self.host.state = replace(self.host.state, readers=())
        result = Maintenance(self.path).run(handle, approval, self.host)
        self.assertEqual(result["status"], "FAILED_RECOVERED")
        self.assertEqual(self.host.calls.count("ap"), 1)
        self.assertTrue(self.host.state.sender_running)

    def test_conditional_stop_and_start_retry_only_after_fresh_safe_observation(self):
        for index, stage in enumerate(("stop", "start")):
            with self.subTest(stage=stage):
                self.host = RecordingHost(self.journal)
                self.host.cycle()
                handle = self.module.prepare(replace(self.plan(), operation=f"retry-{index}"), self.host)
                approval = self.approve(handle)
                self.host.fail[stage] = TimeoutError("PRIVATE")
                first = self.module.run(handle, approval, self.host)
                self.assertNotEqual(first["status"], "COMPLETE")
                self.host.fail.clear()
                result = Maintenance(self.path).run(handle, approval, self.host)
                self.assertEqual(result["status"], "FAILED_RECOVERED")
                self.assertEqual(self.host.calls.count(stage), 2)
                self.assertEqual(self.host.calls.count("ap"), 1)
                effect = result["effects"]["stop_sender" if stage == "stop" else "start_sender"]
                self.assertEqual([item["state"] for item in effect["attempts"]], ["UNCERTAIN", "ACKED"])
                self.assertTrue(self.host.state.sender_running)

    def test_terminal_reinspection_releases_only_a_stranded_same_operation_claim(self):
        handle = self.module.prepare(self.plan(), self.host)
        approval = self.approve(handle)
        self.module.run(handle, approval, self.host)
        with closing(sqlite3.connect(self.module.store.path)) as db, db:
            db.execute("INSERT INTO accounts VALUES (?,?)", (COHORT.account, handle.operation))
        result = Maintenance(self.path).run(handle, approval, self.host)
        self.assertEqual(result["status"], "COMPLETE")
        with closing(sqlite3.connect(self.module.store.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 0)
            with db:
                db.execute("INSERT INTO accounts VALUES (?,?)", (COHORT.account, "foreign-op"))
        self.module.run(handle, approval, self.host)
        with closing(sqlite3.connect(self.module.store.path)) as db:
            self.assertEqual(db.execute("SELECT operation FROM accounts").fetchone()[0], "foreign-op")
        self.assertEqual(self.host.calls.count("ap"), 1)

    def test_cleanup_retry_never_signals_reused_pid_with_a_different_start_identity(self):
        handle = self.module.prepare(self.plan(), self.host)
        approval = self.approve(handle)
        original = OwnedProbe("op-1", "boot-1", 123, "original-start", "1" * 64)
        self.host.hooks["ap"] = lambda: setattr(self.host, "state", replace(self.host.state, owned_probe=original))
        self.host.fail["cleanup"] = TimeoutError("PRIVATE")
        self.module.run(handle, approval, self.host)
        self.host.fail.clear()
        self.host.state = replace(self.host.state, owned_probe=replace(original, started="replacement-start"))
        result = Maintenance(self.path).run(handle, approval, self.host)
        self.assertEqual(result["status"], "STATE_REVIEW_REQUIRED")
        self.assertEqual(self.host.calls.count("cleanup"), 1)
        self.assertEqual(self.host.calls.count("ap"), 1)
        self.assertNotIn("start", self.host.calls)
        self.assertIn("owned_probe_identity_changed", json.dumps(result))

    def test_boolean_zero_position_count_is_not_flat_evidence(self):
        # Inject malformed raw evidence: Journal.put's equality shortcut treats
        # Python False as equal to the existing numeric zero.
        with self.journal.conn:
            self.journal.conn.execute("UPDATE kv SET value=? WHERE key='last_result'", (
                json.dumps(dict(captured_utc=NOW.isoformat(), execute=True,
                                observed_positions=False, position_protection="flat")),))
        with self.assertRaisesRegex(ValueError, "flat_cycle_missing"):
            self.module.prepare(self.plan(), self.host)
        self.assertEqual(self.host.calls, [])


if __name__ == "__main__":
    unittest.main()
