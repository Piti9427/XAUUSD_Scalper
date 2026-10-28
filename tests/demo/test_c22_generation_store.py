"""Atomic generation snapshots convey no broker or owner authority themselves."""

from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.c22_selected.generations import GenerationStore, FreshState
from scripts.c22_selected.renewal import RenewalState, plan_renewal
from tests.demo.test_c22_selected_renewal import fixture, inputs, digest, NOW


def raw(document):
    return json.dumps(document, sort_keys=True, allow_nan=False).encode()


def candidate(now=None, *, marker="first", parent=None):
    now = now or NOW + timedelta(hours=96)
    current, grant = fixture()
    broker, sources = inputs(now)
    plan = plan_renewal(current=current, grant=grant, trusted_grant_sha256=digest(grant),
        now=now, state=RenewalState(0, 0, False, False), enabled=True,
        old_entry_gates_pass=True, broker_bytes=broker, sources=sources)
    review = raw({"approved_utc": grant["approved_utc"], "owner_instruction": "Test-only original review"})
    audit = {"schema_version": 1, "account_fingerprint": grant["binding"]["account_fingerprint"],
        "status": "CLEAR", "magic": 22261025, "execution_authorized": False, "unresolved_incidents": [],
        "original_review_sha256": hashlib.sha256(review).hexdigest(),
        "checkpoint": {"observed_utc": now.isoformat(), "history_end_utc": now.isoformat()},
        "marker": marker}
    audit["receipt_sha256"] = digest(audit)
    audit_bytes = raw(audit)
    context = {"binding": grant["binding"], "grant_sha256": digest(grant),
        "original_review_sha256": hashlib.sha256(review).hexdigest(),
        "cost_audit_sha256": hashlib.sha256(audit_bytes).hexdigest(),
        "parent_generation_id": parent}
    documents = {"policy": raw(plan.candidate_policy), "broker": broker, "sources": raw(sources),
        "review": review, "grant": raw(grant), "context": raw(context), "cost_audit": audit_bytes}
    return plan, documents, deepcopy(grant["binding"]), digest(grant), current


class GenerationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "generations"
        self.now = NOW + timedelta(hours=96)
        self.plan, self.documents, self.binding, self.pin, self.current = candidate(self.now)
        self.store = GenerationStore(self.root, binding=self.binding, trusted_grant_sha256=self.pin)

    def valid(self, snapshot, now):
        self.assertEqual(snapshot.binding, self.binding)
        self.assertEqual(json.loads(snapshot.documents["grant"])["approved_utc"],
                         (NOW - timedelta(hours=1)).isoformat())
        return True

    def flat(self):
        return FreshState(RenewalState(0, 0, False, False), self.now)

    def test_stage_seals_complete_snapshot_without_installing_or_mutating_context(self):
        prior = deepcopy(self.current["policy"])
        staged = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        self.assertEqual(len(staged.generation_id), 64)
        self.assertIsNone(self.store.load_current(now=self.now, validate=self.valid))
        self.assertFalse((self.root / "current.json").exists())
        self.assertEqual(self.current["policy"], prior)
        self.assertEqual(set(staged.documents), set(self.documents))
        self.assertEqual(staged.documents["review"], self.documents["review"])
        with self.assertRaises(TypeError):
            staged.documents["policy"] = b"tamper"
        repeated = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        self.assertEqual(repeated.generation_id, staged.generation_id)

    def test_install_requires_separate_authorizer_and_adopts_one_complete_snapshot(self):
        staged = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        with self.assertRaisesRegex(ValueError, "authorization"):
            self.store.install(staged.generation_id, expected_current=None, clock=lambda: self.now,
                observe_state=self.flat, validate=self.valid, authorize=lambda _snapshot, _now: False)
        self.assertFalse((self.root / "current.json").exists())
        installed = self.store.install(staged.generation_id, expected_current=None, clock=lambda: self.now,
            observe_state=self.flat, validate=self.valid, authorize=lambda _snapshot, _now: True)
        restored = GenerationStore(self.root, binding=self.binding, trusted_grant_sha256=self.pin)
        loaded = restored.load_current(now=self.now, validate=self.valid)
        self.assertEqual(loaded.generation_id, installed.generation_id)
        self.assertEqual(dict(loaded.documents), self.documents)
        self.assertEqual(json.loads(loaded.documents["context"])["parent_generation_id"], None)
        self.assertEqual(self.current["context"]["cost_incidents"], ["must-retain"])

    def test_tamper_or_missing_document_blocks_restart_instead_of_mixing_generations(self):
        staged = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        self.store.install(staged.generation_id, expected_current=None, clock=lambda: self.now,
            observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
        target = self.root / "objects" / staged.generation_id / "policy.json"
        target.write_bytes(self.documents["policy"] + b" ")
        with self.assertRaisesRegex(ValueError, "hash_mismatch"):
            self.store.load_current(now=self.now, validate=self.valid)
        self.assertEqual(json.loads((self.root / "current.json").read_bytes())["generation_id"], staged.generation_id)

    def test_stale_candidate_cannot_install_even_while_policy_still_within_168_hours(self):
        staged = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        self.now += timedelta(minutes=5, microseconds=1)
        with self.assertRaisesRegex(ValueError, "fresh_evidence"):
            self.store.install(staged.generation_id, expected_current=None, clock=lambda: self.now,
                observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
        self.assertFalse((self.root / "current.json").exists())

    def test_slow_validation_or_pointer_write_does_not_reuse_old_flat_observation(self):
        staged = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        calls = []
        def observation():
            return FreshState(RenewalState(0, 0, False, False), self.now)

        def validator(snapshot, now):
            calls.append(now)
            if len(calls) == 2:
                self.now += timedelta(seconds=6)
            return self.valid(snapshot, now)

        with self.assertRaisesRegex(ValueError, "fresh_flat"):
            self.store.install(staged.generation_id, expected_current=None, clock=lambda: self.now,
                observe_state=observation, validate=validator, authorize=lambda *_: True)
        self.assertTrue(calls)
        self.assertFalse((self.root / "current.json").exists())

    def installed_pair(self):
        first = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        self.store.install(first.generation_id, expected_current=None, clock=lambda: self.now,
            observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
        self.now += timedelta(seconds=1)
        plan, documents, _binding, _pin, _current = candidate(self.now, marker="second", parent=first.generation_id)
        second = self.store.stage(plan, documents, now=self.now, validate=self.valid)
        return first, second, documents

    def test_pending_held_active_unknown_and_missing_state_keep_whole_old_snapshot(self):
        first, second, _ = self.installed_pair()
        states = [RenewalState(1, 0, False, False), RenewalState(0, 1, False, False),
            RenewalState(0, 0, True, False), RenewalState(0, 0, False, True),
            RenewalState(None, 0, False, False)]
        for state in states:
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "fresh_flat"):
                    self.store.install(second.generation_id, expected_current=first.generation_id,
                        clock=lambda: self.now, observe_state=lambda: FreshState(state, self.now),
                        validate=self.valid, authorize=lambda *_: True)
                loaded = self.store.load_current(now=self.now, validate=self.valid)
                self.assertEqual(loaded.generation_id, first.generation_id)
                self.assertEqual(dict(loaded.documents), self.documents)
        self.assertEqual(self.current["context"]["loss_count"], 2)

    def test_precommit_io_failure_preserves_old_pointer_and_retry_reuses_sealed_candidate(self):
        first, second, documents = self.installed_pair()
        pointer = (self.root / "current.json").read_bytes()
        with patch("scripts.c22_selected.generations.os.replace", side_effect=OSError("fixture replace failure")):
            with self.assertRaises(OSError):
                self.store.install(second.generation_id, expected_current=first.generation_id,
                    clock=lambda: self.now, observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
        self.assertEqual((self.root / "current.json").read_bytes(), pointer)
        self.assertEqual(self.store.load_current(now=self.now, validate=self.valid).generation_id, first.generation_id)
        installed = self.store.install(second.generation_id, expected_current=first.generation_id,
            clock=lambda: self.now, observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
        self.assertEqual(dict(installed.documents), documents)
        self.assertTrue((self.root / "objects" / first.generation_id).is_dir())

    def test_crash_during_stage_never_exposes_partial_candidate_to_restart(self):
        from scripts.c22_selected import generations
        first = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        self.store.install(first.generation_id, expected_current=None, clock=lambda: self.now,
            observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
        self.now += timedelta(seconds=1)
        plan, documents, _binding, _pin, _current = candidate(self.now, marker="second", parent=first.generation_id)
        calls = []
        original = generations._write

        def partial(path, content):
            calls.append(path.name)
            if len(calls) == 3:
                raise OSError("fixture stage crash")
            return original(path, content)

        with patch("scripts.c22_selected.generations._write", side_effect=partial):
            with self.assertRaises(OSError):
                self.store.stage(plan, documents, now=self.now, validate=self.valid)
        self.assertEqual(len(calls), 3)
        self.assertTrue(list(self.root.glob(".stage-*")))
        restored = GenerationStore(self.root, binding=self.binding, trusted_grant_sha256=self.pin)
        self.assertEqual(dict(restored.load_current(now=self.now, validate=self.valid).documents), self.documents)
        completed = restored.stage(plan, documents, now=self.now, validate=self.valid)
        self.assertEqual(dict(completed.documents), documents)
        self.assertEqual(restored.load_current(now=self.now, validate=self.valid).generation_id, first.generation_id)

    def test_changed_pointer_parent_or_revoked_external_authority_never_switches(self):
        first, second, _ = self.installed_pair()
        for kind in ("cas", "parent", "revoked"):
            with self.subTest(kind=kind):
                expected = None if kind == "cas" else first.generation_id
                chosen = first if kind == "parent" else second
                with self.assertRaises(ValueError):
                    self.store.install(chosen.generation_id, expected_current=expected,
                        clock=lambda: self.now, observe_state=self.flat, validate=self.valid,
                        authorize=lambda *_: kind != "revoked")
                self.assertEqual(self.store.load_current(now=self.now, validate=self.valid).generation_id, first.generation_id)

    def test_postcommit_sync_failure_is_explicit_and_restart_loads_only_complete_new_generation(self):
        first, second, documents = self.installed_pair()
        with patch("scripts.c22_selected.generations._sync_directory", side_effect=OSError("fixture postcommit sync")):
            with self.assertRaisesRegex(RuntimeError, "durability_unknown"):
                self.store.install(second.generation_id, expected_current=first.generation_id,
                    clock=lambda: self.now, observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
        restored = GenerationStore(self.root, binding=self.binding, trusted_grant_sha256=self.pin)
        loaded = restored.load_current(now=self.now, validate=self.valid)
        self.assertEqual(loaded.generation_id, second.generation_id)
        self.assertEqual(dict(loaded.documents), documents)
        self.assertTrue((self.root / "objects" / first.generation_id).is_dir())

    def test_loader_expiry_and_missing_calendar_never_invent_a_valid_restart(self):
        from dataclasses import replace
        staged = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        self.store.install(staged.generation_id, expected_current=None, clock=lambda: self.now,
            observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
        exact = self.now + timedelta(hours=168)
        self.assertEqual(self.store.load_current(now=exact, validate=self.valid).generation_id, staged.generation_id)
        with self.assertRaisesRegex(ValueError, "policy_invalid"):
            self.store.load_current(now=exact + timedelta(microseconds=1), validate=self.valid)
        broken = dict(self.documents)
        policy = json.loads(broken["policy"])
        del policy["evidence"]["swap_calendar"]
        broken["policy"] = raw(policy)
        with self.assertRaisesRegex(ValueError, "policy_invalid"):
            self.store.stage(replace(self.plan, candidate_policy=policy), broken, now=self.now, validate=self.valid)
        self.assertEqual(self.store.load_current(now=self.now, validate=self.valid).generation_id, staged.generation_id)

    def test_historical_context_retains_complete_expired_parent_without_current_validity(self):
        staged = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        self.store.install(staged.generation_id, expected_current=None, clock=lambda: self.now,
            observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
        expired = self.now + timedelta(hours=168, seconds=1)
        with self.assertRaisesRegex(ValueError, "policy_invalid"):
            self.store.load_current(now=expired, validate=self.valid)
        historical = self.store.load_current_historical(now=expired, validate=self.valid)
        self.assertEqual(historical.generation_id, staged.generation_id)
        self.assertEqual(dict(historical.documents), self.documents)
        with self.assertRaisesRegex(ValueError, "historical_clock_invalid"):
            self.store.load_current_historical(now=self.now - timedelta(seconds=1), validate=self.valid)
        folder = self.root / "objects" / staged.generation_id
        (folder / "policy.json").write_bytes(self.documents["policy"] + b" ")
        with self.assertRaisesRegex(ValueError, "hash_mismatch"):
            self.store.load_current_historical(now=expired, validate=self.valid)

    def test_durable_transition_callback_cannot_age_past_final_flat_window(self):
        staged = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        observed = self.flat()
        callbacks = []

        def slow_receipt(snapshot, now, proof):
            callbacks.append((snapshot.generation_id, now, proof))
            self.now += timedelta(seconds=6)

        with self.assertRaisesRegex(ValueError, "fresh_flat"):
            self.store.install(staged.generation_id, expected_current=None, clock=lambda: self.now,
                observe_state=lambda: observed, validate=self.valid, authorize=lambda *_: True,
                before_replace=slow_receipt)
        self.assertEqual(callbacks, [(staged.generation_id, observed.observed_utc, observed)])
        self.assertIsNone(self.store.load_current(now=self.now, validate=self.valid))

    def test_grant_limits_version_and_owner_fields_are_not_relaxed_by_storage(self):
        for kind in ("lifetime", "version", "owner_instruction"):
            with self.subTest(kind=kind):
                docs = dict(self.documents)
                grant, context = json.loads(docs["grant"]), json.loads(docs["context"])
                if kind == "lifetime":
                    grant["limits"]["policy_hours"] = 999
                elif kind == "version":
                    grant["version"] = True
                else:
                    grant["owner_instruction"] = ""
                docs["grant"] = raw(grant)
                context["grant_sha256"] = digest(grant)
                docs["context"] = raw(context)
                store = GenerationStore(self.root, binding=self.binding, trusted_grant_sha256=digest(grant))
                with self.assertRaisesRegex(ValueError, "authority_invalid"):
                    store.stage(self.plan, docs, now=self.now, validate=self.valid)
        self.assertFalse((self.root / "current.json").exists())

    def test_cost_incident_or_failed_semantic_validation_cannot_be_installed(self):
        first, second, _ = self.installed_pair()
        with self.assertRaisesRegex(ValueError, "semantic_validation"):
            self.store.install(second.generation_id, expected_current=first.generation_id,
                clock=lambda: self.now, observe_state=self.flat, validate=lambda *_: False, authorize=lambda *_: True)
        docs = dict(self.documents)
        audit, context = json.loads(docs["cost_audit"]), json.loads(docs["context"])
        audit["status"] = "BLOCKED"
        audit["unresolved_incidents"] = [{"code": "cost_broker_deal_drift"}]
        audit["receipt_sha256"] = digest({k: v for k, v in audit.items() if k != "receipt_sha256"})
        docs["cost_audit"] = raw(audit)
        context["cost_audit_sha256"] = hashlib.sha256(docs["cost_audit"]).hexdigest()
        docs["context"] = raw(context)
        with self.assertRaisesRegex(ValueError, "cost_audit_invalid"):
            self.store.stage(self.plan, docs, now=self.now, validate=self.valid)
        self.assertEqual(self.store.load_current(now=self.now, validate=self.valid).generation_id, first.generation_id)

    def test_rebinding_source_or_missing_grant_pin_blocks_load_without_touching_original(self):
        staged = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        self.store.install(staged.generation_id, expected_current=None, clock=lambda: self.now,
            observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
        changed = dict(self.binding, source_sha256="c" * 64)
        wrong = GenerationStore(self.root, binding=changed, trusted_grant_sha256=self.pin)
        with self.assertRaisesRegex(ValueError, "manifest_invalid"):
            wrong.load_current(now=self.now, validate=lambda *_: True)
        with self.assertRaisesRegex(ValueError, "trusted_binding"):
            GenerationStore(self.root, binding=self.binding, trusted_grant_sha256=None)
        self.assertEqual(self.store.load_current(now=self.now, validate=self.valid).generation_id, staged.generation_id)

    def test_concurrent_reader_always_gets_one_whole_retained_generation(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        staged = self.store.stage(self.plan, self.documents, now=self.now, validate=self.valid)
        self.store.install(staged.generation_id, expected_current=None, clock=lambda: self.now,
            observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
        known = {staged.generation_id: dict(staged.documents)}
        first_read, first_switch = Event(), Event()

        def read_many():
            found = []
            for number in range(40):
                item = self.store.load_current(now=self.now, validate=self.valid)
                found.append((item.generation_id, dict(item.documents)))
                if number == 0:
                    first_read.set()
                    self.assertTrue(first_switch.wait(5))
            return found

        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(read_many)
            self.assertTrue(first_read.wait(5))
            previous = staged.generation_id
            for number in range(3):
                plan, docs, _binding, _pin, _current = candidate(self.now, marker=str(number), parent=previous)
                item = self.store.stage(plan, docs, now=self.now, validate=self.valid)
                known[item.generation_id] = docs
                self.store.install(item.generation_id, expected_current=previous, clock=lambda: self.now,
                    observe_state=self.flat, validate=self.valid, authorize=lambda *_: True)
                previous = item.generation_id
                first_switch.set()
            observed = pending.result()
        self.assertEqual(len(observed), 40)
        self.assertGreaterEqual(len({ident for ident, _ in observed}), 2)
        for ident, docs in observed:
            self.assertEqual(docs, known[ident])
        self.assertEqual(self.store.load_current(now=self.now, validate=self.valid).generation_id, previous)
        self.assertEqual(len(list((self.root / "objects").iterdir())), 4)


if __name__ == "__main__":
    unittest.main()
