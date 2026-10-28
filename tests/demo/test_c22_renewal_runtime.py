"""Coordinator joins actual proof seams without minting another approval."""

from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from scripts.demo_runtime.journal import Journal
from scripts.c22_selected.generations import FreshState
from scripts.c22_selected.renewal import RenewalState, _binding
from scripts.c22_selected.source_packets import review_source_captures
from scripts.c22_selected.trial_costs import build_trial_policy
from tests.demo.test_c22_official_source_packets import captures
from tests.demo.test_c22_selected_execution import review_fixture
from tests.demo.test_c22_selected_trial_costs import broker_fixture, sources_fixture, NOW


def raw(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(raw(value)).hexdigest()


def broker_packet(now):
    value = broker_fixture()
    value["captured_utc"] = value["history_end_utc"] = now.isoformat()
    value["account"]["balance"] = value["account"]["equity"] = 200.
    value["history_deals"] = [dict(ticket=1, position_id=0, magic=0, entry=0, type=2, volume=0.,
        time_msc=int((NOW - timedelta(days=2)).timestamp() * 1000), profit=200., commission=0., swap=0., fee=0.)]
    value["history_deals_total"] = 1
    return value


def source_input(now):
    value = captures()
    for item in value.values():
        item["requested_utc"] = (now - timedelta(seconds=2)).isoformat()
        item["retrieved_utc"] = (now - timedelta(seconds=1)).isoformat()
    return value, review_source_captures(value, now=now)


class RenewalRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.journal = Journal(self.root / "journal.sqlite3")
        self.addCleanup(self.journal.close)
        self.base = build_trial_policy(raw(broker_packet(NOW)), now=NOW, sources=sources_fixture())
        self.runner = NS(policy=deepcopy(self.base), fingerprint=self.base["account_fingerprint"],
            release_hash="a" * 64, journal=self.journal, strategy=NS(magic=22261025), symbol="XAUUSDm")
        self.journal.audit_context = {"config_hash": "b" * 64}
        self.review = review_fixture(self.runner, NOW)
        self.review_path = self.root / "review.json"
        self.review_path.write_bytes(raw(self.review))
        self.original_hash = hashlib.sha256(self.review_path.read_bytes()).hexdigest()
        self.journal.put("selected_execution_review_sha256", self.original_hash)
        self.grant = dict(version=1, scope="SELECTED_DEMO_SAME_ASSUMPTION_RENEWAL",
            owner_authorized=True, owner_instruction="Synthetic test-only standing grant",
            approved_utc=NOW.isoformat(), expires_utc=(NOW + timedelta(days=30)).isoformat(), revoked=False,
            original_review_sha256=self.original_hash, original_policy_sha256=digest(self.base),
            binding=_binding(dict(policy=self.base, source_sha256="a" * 64, config_sha256="b" * 64)),
            limits=dict(policy_hours=168, prepare_hours=72, broker_fresh_seconds=300, official_fresh_seconds=86400))
        self.grant_path = self.root / "grant.json"
        self.grant_path.write_bytes(raw(self.grant))
        self.now = NOW + timedelta(hours=96)

    def runtime(self):
        from scripts.c22_selected.renewal_runtime import RenewalRuntime
        return RenewalRuntime(self.runner, grant_path=self.grant_path,
            trusted_grant_sha256=digest(self.grant), generation_root=self.root / "generations",
            original_review_path=self.review_path)

    def prepare(self, subject, *, now=None, state=None, broker=None):
        now = now or self.now
        value, packet = source_input(now)
        return subject.prepare(raw(broker or broker_packet(now)), packet, value, now=now,
            observe_state=lambda: FreshState(state or RenewalState(0, 0, False, False), now), clock=lambda: now)

    def test_matching_renewal_and_restart_keeps_original_approval_after_base_expiry(self):
        subject = self.runtime()
        before = self.review_path.read_bytes()
        result = self.prepare(subject)
        self.assertEqual(result["status"], "INSTALLED", result)
        self.assertNotEqual(self.runner.policy, self.base)
        self.assertEqual(self.runner.policy["reviewed_utc"], self.now.isoformat())
        self.assertEqual(self.review_path.read_bytes(), before)
        self.assertEqual(self.journal.get("selected_execution_review_sha256"), self.original_hash)
        self.runner.policy = deepcopy(self.base)  # Existing startup input remains the original file.
        restored = self.runtime()
        later = NOW + timedelta(hours=169)
        self.assertEqual(restored.restore(later)["reviewed_utc"], self.now.isoformat())
        accepted = restored.check(self.runner, later)
        self.assertEqual(accepted, self.review)
        self.assertEqual(accepted["approved_utc"], NOW.isoformat())
        self.assertIsNone(self.journal.get("active"))

    def test_no_generation_preserves_legacy_review_when_future_grant_is_invalid(self):
        subject = self.runtime()
        self.grant_path.write_bytes(b"{}")
        accepted = subject.check(self.runner, NOW, record=False)
        self.assertEqual(accepted, self.review)
        self.assertEqual(subject.inspect(self.runner, NOW)["status"], "VALID")
        self.assertEqual(self.runner.policy, self.base)
        self.assertFalse(subject.ensure_tracking(NOW))

    def test_enrolled_factual_close_binding_continues_after_future_grant_revocation(self):
        subject = self.runtime()
        self.assertTrue(subject.ensure_tracking(NOW))
        self.grant_path.write_bytes(b"{}")
        self.assertTrue(subject.ensure_tracking(self.now))
        active = {"cost_policy_hash": digest(self.base), "status": "UNKNOWN"}
        subject.bind_active(active, 7, self.now)
        rows = broker_packet(self.now)["history_deals"]
        rows += [dict(ticket=2, position_id=7, magic=22261025, entry=0, type=0, volume=.01,
            time_msc=int((NOW + timedelta(minutes=1)).timestamp() * 1000), profit=0., commission=0., swap=0., fee=0.),
            dict(ticket=3, position_id=7, magic=0, entry=1, type=1, volume=.01,
            time_msc=int((NOW + timedelta(hours=1)).timestamp() * 1000), profit=1., commission=0., swap=0., fee=0.)]
        observed = subject.audit_existing_reads(NS(balance=201.), [], [NS(**item) for item in rows], self.now)
        self.assertEqual(observed["status"], "CLEAR")
        self.assertEqual(observed["checkpoint"]["audited_exit_deals"], 1)
        self.assertEqual(observed["generation_ids"], [digest(self.base)])
        self.assertEqual(subject.check(self.runner, NOW), self.review)

    def test_before_prepare_window_needs_no_source_refresh_and_keeps_native_policy(self):
        subject = self.runtime()
        result = subject.prepare(None, None, None, now=NOW,
            observe_state=lambda: FreshState(RenewalState(0, 0, False, False), NOW), clock=lambda: NOW)
        self.assertEqual(result["status"], "NOT_DUE")
        self.assertEqual(self.runner.policy, self.base)

    def test_held_order_active_or_unknown_defers_without_switching_or_touching_manager(self):
        for state in (RenewalState(1, 0, False, False), RenewalState(0, 1, False, False),
                      RenewalState(0, 0, True, False), RenewalState(0, 0, False, True)):
            with self.subTest(state=state):
                subject = self.runtime()
                original = self.runner.policy
                self.journal.put("active", {"status": "UNKNOWN", "must_reconcile": True})
                result = self.prepare(subject, state=state)
                self.assertEqual(result["status"], "DEFER", result)
                self.assertIs(self.runner.policy, original)
                self.assertEqual(self.journal.get("active"), {"status": "UNKNOWN", "must_reconcile": True})
                self.assertFalse((self.root / "generations/current.json").exists())
        self.journal.put("active", None)

    def test_revoked_grant_original_review_or_source_change_blocks_installed_generation(self):
        subject = self.runtime()
        self.prepare(subject)
        installed = self.runner.policy
        grant_bytes, review_bytes = self.grant_path.read_bytes(), self.review_path.read_bytes()
        for kind in ("grant", "review", "source"):
            with self.subTest(kind=kind):
                if kind == "grant":
                    value = deepcopy(self.grant)
                    value["revoked"] = True
                    self.grant_path.write_bytes(raw(value))
                elif kind == "review":
                    self.review_path.write_bytes(b"{}")
                else:
                    self.runner.release_hash = "c" * 64
                with self.assertRaises(ValueError):
                    subject.check(self.runner, self.now)
                self.assertEqual(subject.inspect(self.runner, self.now)["status"], "BLOCKED")
                self.assertIs(self.runner.policy, installed)
                self.grant_path.write_bytes(grant_bytes)
                self.review_path.write_bytes(review_bytes)
                self.runner.release_hash = "a" * 64

    def test_inspection_is_read_only_and_missing_pointer_cannot_fall_back_after_adoption(self):
        subject = self.runtime()
        self.prepare(subject)
        rows = self.journal.conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        self.runner.policy = deepcopy(self.base)
        original = self.runner.policy
        result = subject.inspect(self.runner, self.now)
        self.assertEqual(result["status"], "VALID")
        self.assertIs(self.runner.policy, original)
        self.assertEqual(self.journal.conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0], rows)
        (self.root / "generations/current.json").unlink()
        with self.assertRaises(ValueError):
            self.runtime().check(self.runner, NOW)

    def test_changed_candidate_or_incomplete_receipt_retains_old_valid_policy(self):
        subject = self.runtime()
        original = self.runner.policy
        changed = broker_packet(self.now)
        changed["spec"]["swap_long"] += 1
        result = self.prepare(subject, broker=changed)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertIs(self.runner.policy, original)
        self.assertEqual(subject.check(self.runner, NOW), self.review)
        malformed = broker_packet(self.now)
        malformed["history_deals"][0].pop("magic")
        with self.assertRaises(ValueError):
            self.prepare(subject, broker=malformed)
        self.assertIs(self.runner.policy, original)
        self.assertFalse((self.root / "generations/current.json").exists())

    def test_existing_cost_drift_stays_blocked_after_candidate_renewal_attempt(self):
        subject = self.runtime()
        subject.audit_existing_reads(NS(balance=200.), [], [NS(**broker_packet(NOW)["history_deals"][0])], NOW)
        active = {"cost_policy_hash": digest(self.base), "status": "UNKNOWN"}
        subject.bind_active(active, 7, NOW)
        open_at, exit_at = NOW + timedelta(minutes=1), NOW + timedelta(hours=1)
        data = broker_packet(self.now)
        data["history_deals"] += [dict(ticket=2, position_id=7, magic=22261025, entry=0, type=0,
            volume=.01, time_msc=int(open_at.timestamp() * 1000), profit=0., commission=0., swap=0., fee=0.),
            dict(ticket=3, position_id=7, magic=0, entry=1, type=1, volume=.01,
            time_msc=int(exit_at.timestamp() * 1000), profit=1., commission=0., swap=0., fee=-.01)]
        data["history_deals_total"] = 3
        data["account"]["balance"] = data["account"]["equity"] = 200.99
        observed = subject.audit_existing_reads(NS(balance=200.99), [],
            [NS(**item) for item in data["history_deals"]], self.now)
        self.assertEqual(observed["status"], "BLOCKED")
        result = self.prepare(subject, broker=data)
        self.assertEqual(result["status"], "DEFER")  # Native builder also rejects the actual fee.
        self.assertEqual(subject.ledger.status()["status"], "BLOCKED")
        self.assertEqual(subject.ledger.status()["unresolved_incidents"][0]["code"], "cost_broker_deal_drift")
        self.assertEqual(self.runner.policy, self.base)
        self.assertEqual(self.journal.get("selected_execution_review_sha256"), self.original_hash)

    def test_coherent_but_forged_cost_receipt_cannot_restore_an_installed_generation(self):
        subject = self.runtime()
        result = self.prepare(subject)
        original = self.runner.policy
        folder = self.root / "generations/objects" / result["generation_id"]
        manifest = json.loads((folder / "manifest.json").read_bytes())
        documents = {name: (folder / (name + ".json")).read_bytes() for name in manifest["files"]}
        audit = json.loads(documents["cost_audit"])
        audit["checkpoint"]["snapshot_sha256"] = "d" * 64
        audit.pop("receipt_sha256")
        audit["receipt_sha256"] = digest(audit)
        documents["cost_audit"] = raw(audit)
        context = json.loads(documents["context"])
        context["cost_audit_sha256"] = hashlib.sha256(documents["cost_audit"]).hexdigest()
        documents["context"] = raw(context)
        manifest["files"] = {name: hashlib.sha256(value).hexdigest() for name, value in documents.items()}
        ident = digest(manifest)
        fake = self.root / "generations/objects" / ident
        fake.mkdir()
        for name, content in documents.items():
            (fake / (name + ".json")).write_bytes(content)
        (fake / "manifest.json").write_bytes(raw(manifest))
        (self.root / "generations/current.json").write_bytes(raw({"schema": 1, "generation_id": ident}))
        with self.assertRaisesRegex(ValueError, "installed_generation_invalid"):
            subject.restore(self.now)
        self.assertIs(self.runner.policy, original)
        self.assertEqual(subject.inspect(self.runner, self.now)["status"], "BLOCKED")

    def test_observation_aging_during_install_preserves_old_policy_and_authority(self):
        subject = self.runtime()
        value, packet = source_input(self.now)
        original = self.runner.policy
        ticks = []

        def clock():
            ticks.append(None)
            return self.now + timedelta(seconds=6 if len(ticks) >= 3 else 0)

        with self.assertRaisesRegex(ValueError, "fresh_flat_window_required"):
            subject.prepare(raw(broker_packet(self.now)), packet, value, now=self.now,
                observe_state=lambda: FreshState(RenewalState(0, 0, False, False), self.now), clock=clock)
        self.assertIs(self.runner.policy, original)
        self.assertFalse((self.root / "generations/current.json").exists())
        self.assertEqual(self.review["approved_utc"], NOW.isoformat())

    def test_corrupt_tracking_state_does_not_prevent_owned_manager_construction(self):
        subject = self.runtime()
        self.assertTrue(subject.ensure_tracking(NOW))
        state = self.journal.get("selected_cost_generations_v1")
        state["legacy_cutoff_utc"] = (NOW + timedelta(days=1)).isoformat()
        self.journal.put("selected_cost_generations_v1", state)
        self.journal.put("active", {"status": "UNKNOWN", "retain": True})
        restored = self.runtime()  # Construction itself has no cost-state gate.
        with self.assertRaisesRegex(ValueError, "state_audit_mismatch"):
            restored.ensure_tracking(NOW)
        with self.assertRaisesRegex(ValueError, "state_audit_mismatch"):
            restored.bind_active({"cost_policy_hash": digest(self.base)}, 7, NOW)
        self.assertEqual(self.journal.get("active"), {"status": "UNKNOWN", "retain": True})

    def test_fresh_evidence_can_replace_expired_derived_generation_without_erasing_it(self):
        subject = self.runtime()
        first = self.prepare(subject)
        later = self.now + timedelta(hours=168, seconds=1)
        with self.assertRaises(ValueError):
            subject.check(self.runner, later)
        second = self.prepare(subject, now=later)
        self.assertEqual(second["status"], "INSTALLED", second)
        self.assertNotEqual(second["generation_id"], first["generation_id"])
        self.assertEqual(self.runner.policy["reviewed_utc"], later.isoformat())
        self.assertTrue((self.root / "generations/objects" / first["generation_id"]).exists())
        self.assertEqual(subject.check(self.runner, later)["approved_utc"], NOW.isoformat())

    def test_repointing_to_still_valid_ancestor_blocks_instead_of_readopting_it(self):
        subject = self.runtime()
        first = self.prepare(subject)
        pointer = self.root / "generations/current.json"
        first_pointer = pointer.read_bytes()
        later = self.now + timedelta(hours=96)
        second = self.prepare(subject, now=later)
        self.assertEqual(second["status"], "INSTALLED", second)
        self.assertNotEqual(first["generation_id"], second["generation_id"])
        held = {"status": "UNKNOWN", "retain": True}
        self.journal.put("active", held)
        installed = self.runner.policy
        pointer.write_bytes(first_pointer)
        restarted = self.runtime()
        with self.assertRaisesRegex(ValueError, "installed_generation_invalid") as rejected:
            restarted.restore(later)
        self.assertEqual(rejected.exception.diagnostics,
            {"stage": "renewal.generation", "code": "renewal_runtime_generation_lineage_invalid"})
        with self.assertRaisesRegex(ValueError, "installed_generation_invalid"):
            restarted.policy_for_reload({}, later)
        self.assertEqual(restarted.inspect(self.runner, later)["status"], "BLOCKED")
        with self.assertRaisesRegex(ValueError, "installed_generation_invalid"):
            restarted.check(self.runner, later)
        self.assertIs(self.runner.policy, installed)
        self.assertEqual(self.journal.get("active"), held)

    def test_expired_derived_context_recovers_when_legacy_input_reload_failed(self):
        subject = self.runtime()
        first = self.prepare(subject)
        self.assertEqual(first["status"], "INSTALLED")
        later = self.now + timedelta(hours=168, seconds=1)
        self.runner.policy = {}  # Legacy input read failure in the sender CLI.
        second = self.prepare(subject, now=later)
        self.assertEqual(second["status"], "INSTALLED", second)
        self.assertNotEqual(second["generation_id"], first["generation_id"])
        self.assertEqual(self.runner.policy["reviewed_utc"], later.isoformat())
        self.assertEqual(subject.check(self.runner, later), self.review)

    def test_reload_returns_sealed_historical_context_only_and_preserves_default_off(self):
        subject = self.runtime()
        legacy = {}
        self.assertIs(subject.policy_for_reload(legacy, NOW), legacy)
        self.prepare(subject)
        sealed = deepcopy(self.runner.policy)
        later = self.now + timedelta(hours=168, seconds=1)
        self.runner.policy = legacy
        restarted = self.runtime()  # Starts with failed/untrusted legacy input.
        events = self.journal.conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        restored = restarted.policy_for_reload(legacy, later)
        self.assertEqual(restored, sealed)
        self.assertIs(self.runner.policy, legacy)
        self.assertEqual(self.journal.conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0], events)
        with self.assertRaisesRegex(ValueError, "installed_generation_invalid"):
            restarted.check(self.runner, later)
        self.runner.policy = restored
        self.assertEqual(self.prepare(restarted, now=later)["status"], "INSTALLED")
        self.assertEqual(restarted.check(self.runner, later), self.review)

    def test_direct_child_with_durable_final_flat_intent_recovers_after_replace_crash(self):
        from scripts.c22_selected import generations
        subject = self.runtime()
        first = self.prepare(subject)
        original = self.runner.policy
        later = self.now + timedelta(hours=96)
        sync = generations._sync_directory

        def fail_after_replace(path):
            if Path(path) == self.root / "generations":
                raise OSError("Synthetic post-replace sync fault")
            return sync(path)

        with patch("scripts.c22_selected.generations._sync_directory", side_effect=fail_after_replace):
            with self.assertRaisesRegex(RuntimeError, "durability_unknown"):
                self.prepare(subject, now=later)
        pointer = json.loads((self.root / "generations/current.json").read_bytes())
        self.assertNotEqual(pointer["generation_id"], first["generation_id"])
        self.assertIs(self.runner.policy, original)
        held = {"status": "UNKNOWN", "retain": True}
        self.journal.put("active", held)
        restarted = self.runtime()
        self.assertEqual(restarted.inspect(self.runner, later)["status"], "VALID")
        self.assertEqual(restarted.restore(later)["reviewed_utc"], later.isoformat())
        self.assertEqual(restarted.check(self.runner, later), self.review)
        self.assertEqual(self.journal.get("active"), held)

    def test_initial_switch_crash_can_recover_even_if_expired_before_next_prepare(self):
        from scripts.c22_selected import generations
        subject = self.runtime()
        sync = generations._sync_directory

        def fail_after_replace(path):
            if Path(path) == self.root / "generations":
                raise OSError("Synthetic first-switch sync fault")
            return sync(path)

        with patch("scripts.c22_selected.generations._sync_directory", side_effect=fail_after_replace):
            with self.assertRaisesRegex(RuntimeError, "durability_unknown"):
                self.prepare(subject)
        later = self.now + timedelta(hours=168, seconds=1)
        self.runner.policy = {}
        restarted = self.runtime()
        result = self.prepare(restarted, now=later)
        self.assertEqual(result["status"], "INSTALLED", result)
        self.assertEqual(restarted.check(self.runner, later)["approved_utc"], NOW.isoformat())

    def test_known_precommit_failure_cancels_intent_and_cannot_be_manually_installed(self):
        subject = self.runtime()
        first = self.prepare(subject)
        later = self.now + timedelta(hours=96)
        with patch("scripts.c22_selected.generations.os.replace", side_effect=OSError("Synthetic replace fault")):
            with self.assertRaises(OSError):
                self.prepare(subject, now=later)
        self.assertEqual(subject.restore(later)["reviewed_utc"], self.now.isoformat())
        folders = {path.name for path in (self.root / "generations/objects").iterdir()}
        child, = folders - {first["generation_id"]}
        (self.root / "generations/current.json").write_bytes(raw({"schema": 1, "generation_id": child}))
        with self.assertRaisesRegex(ValueError, "installed_generation_invalid"):
            self.runtime().restore(later)

    def test_wrapped_generation_failures_preserve_only_known_finite_cause(self):
        subject = self.runtime()
        self.prepare(subject)
        original = self.runner.policy
        grant_bytes = self.grant_path.read_bytes()
        self.grant_path.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "installed_generation_invalid") as rejected:
            subject.restore(self.now)
        self.assertEqual(rejected.exception.diagnostics,
            {"stage": "renewal.generation", "code": "generation_trusted_binding_required"})
        self.assertIsNotNone(rejected.exception.__cause__)
        self.grant_path.write_bytes(grant_bytes)
        self.review_path.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "installed_generation_invalid") as rejected:
            subject.policy_for_reload({}, self.now)
        self.assertEqual(rejected.exception.diagnostics,
            {"stage": "renewal.generation", "code": "renewal_runtime_original_proof_invalid"})
        self.assertIs(self.runner.policy, original)
        self.review_path.unlink()
        with self.assertRaisesRegex(ValueError, "installed_generation_invalid") as rejected:
            subject.restore(self.now)
        self.assertNotIn("owner_instruction", str(getattr(rejected.exception, "diagnostics", {})))
