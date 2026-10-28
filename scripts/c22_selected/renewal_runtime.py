"""Opt-in same-sender renewal coordination, separate from human approval.

No SDK/network call or grant creation occurs here. Callers supply existing sender
reads and fresh exposure observations. Missing candidate evidence preserves the
old context; invalid installed evidence blocks new entry, never owned management.
"""

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from scripts.c22_selected.cost_generations import CostGenerationLedger
from scripts.c22_selected.execution import ExecutionReview
from scripts.c22_selected.generations import GenerationStore, FreshState, _object
from scripts.c22_selected.renewal import RenewalState, _binding, _grant_error, _utc, plan_renewal
from scripts.c22_selected.source_packets import sources_for_policy
from scripts.demo_runtime.costs import validate_policy
from scripts.demo_runtime.diagnostics import RESUME, public_reason

_FIELDS = ("ticket", "position_id", "magic", "entry", "type", "volume", "time_msc",
           "profit", "commission", "swap", "fee")


def _raw(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def _hash(value):
    return hashlib.sha256(_raw(value)).hexdigest()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class RenewalRuntime:
    """Join accepted review, source proof, cost audit and atomic generation.

    Construction is not activation or approval. The independently configured pin
    must identify an actual owner-issued grant. Original review acceptance must
    already be present in the journal; renewal never creates that acceptance.
    Legacy review behavior remains available while no generation is installed.
    """

    def __init__(self, runner, *, grant_path, trusted_grant_sha256, generation_root, original_review_path):
        self.runner = runner
        self.grant_path = Path(grant_path)
        self.pin = trusted_grant_sha256
        self.root = Path(generation_root)
        self.original_path = Path(original_review_path)
        self.original = ExecutionReview(original_review_path)
        self.base_policy = deepcopy(runner.policy)
        self.snapshot = None
        self.fault = None
        self.last_diagnostics = {}
        # Invalid observational cost state must not prevent construction of an
        # owned financial manager. Entry/tracking methods validate it lazily.
        self._ledger = None

    @property
    def ledger(self):
        if self._ledger is None:
            self._ledger = CostGenerationLedger(self.runner.journal, fingerprint=self.runner.fingerprint,
                                                magic=self.runner.strategy.magic)
        return self._ledger

    def _pointer_exists(self):
        exists = (self.root / "current.json").exists() or (self.root / "current.json").is_symlink()
        if not exists and self._adopted_id() is not None:
            raise ValueError("renewal_runtime_generation_pointer_missing")
        return exists

    def _adopted_id(self):
        event = self._latest_event("RENEWAL_GENERATION_ADOPTED")
        return None if event is None else event[1]["generation_id"]

    def _latest_event(self, kind):
        row = self.runner.journal.conn.execute(
            "SELECT id,payload FROM audit_events WHERE json_extract(payload, '$.kind')=? ORDER BY id DESC LIMIT 1",
            (kind,)).fetchone()
        return None if row is None else (row[0], json.loads(row[1]))

    def _lineage(self, snapshot):
        """Reject rollback; recover only an exactly authorized direct child.

        The journal and filesystem cannot commit atomically. A crash may leave
        an intent without a switch, or a complete switched child without its
        adoption event. Only the latter pointer is recovered here; an intent
        never changes the pointer or grants new financial authority by itself.
        """
        adopted = self._latest_event("RENEWAL_GENERATION_ADOPTED")
        parent = None if adopted is None else adopted[1]["generation_id"]
        if snapshot.generation_id == parent:
            return None
        context = _object(snapshot.documents["context"])
        intent = self._latest_event("RENEWAL_INSTALL_INTENT")
        cancelled = self._latest_event("RENEWAL_INSTALL_CANCELLED")
        if (context["parent_generation_id"] != parent or intent is None
                or (adopted is not None and intent[0] <= adopted[0])
                or (cancelled is not None and cancelled[0] > intent[0]
                    and cancelled[1].get("install_intent_event_id") == intent[1]["event_id"])):
            raise ValueError("renewal_runtime_generation_lineage_invalid")
        facts = intent[1]
        state = RenewalState(**facts["state"])
        if (facts["generation_id"] != snapshot.generation_id
                or facts["parent_generation_id"] != parent
                or facts["prior_adoption_event_id"] != (None if adopted is None else adopted[1]["event_id"])
                or facts["grant_sha256"] != self.pin
                or facts["cost_audit_sha256"] != _sha(snapshot.documents["cost_audit"])
                or not state.install_window()
                or not timedelta(0) <= _utc(facts["authorized_utc"]) - _utc(facts["observed_utc"]) <= timedelta(seconds=5)):
            raise ValueError("renewal_runtime_generation_lineage_invalid")
        return facts

    def _install_intent(self, snapshot, now, observation):
        self._lineage_parent(snapshot)
        grant = self._grant(self.base_policy, now)
        self._proof(grant, self.base_policy, now, expected_review=snapshot.documents["review"])
        if self.ledger.status() != _object(snapshot.documents["cost_audit"]):
            raise ValueError("renewal_runtime_unresolved_cost_incident")
        adopted = self._latest_event("RENEWAL_GENERATION_ADOPTED")
        return self.runner.journal.audit("RENEWAL_INSTALL_INTENT",
            generation_id=snapshot.generation_id,
            parent_generation_id=_object(snapshot.documents["context"])["parent_generation_id"],
            prior_adoption_event_id=None if adopted is None else adopted[1]["event_id"],
            grant_sha256=self.pin, cost_audit_sha256=_sha(snapshot.documents["cost_audit"]),
            observed_utc=_utc(observation.observed_utc).isoformat(), authorized_utc=now.isoformat(),
            state=vars(observation.state))

    def _lineage_parent(self, snapshot):
        if _object(snapshot.documents["context"])["parent_generation_id"] != self._adopted_id():
            raise ValueError("renewal_runtime_generation_lineage_invalid")

    def _record_adoption(self, snapshot, intent, *, historical=False):
        if self._adopted_id() != snapshot.generation_id:
            self.runner.journal.audit("RENEWAL_GENERATION_ADOPTED", generation_id=snapshot.generation_id,
                parent_generation_id=_object(snapshot.documents["context"])["parent_generation_id"],
                install_intent_event_id=intent["event_id"], historical_context=historical,
                execution_authorized=False)

    def _adopt(self, snapshot, base, policy, now):
        intent = self._lineage(snapshot)
        self.ledger.register_generation(policy, evidence_sha256=policy["account_evidence_sha256"], now=now)
        self._record_adoption(snapshot, intent)
        self.base_policy = deepcopy(base)
        self.snapshot = snapshot
        self.runner.policy = policy
        self.fault = None

    def _grant(self, base, now):
        try:
            if self.grant_path.is_symlink() or self.grant_path.stat().st_size > 65536:
                raise ValueError("renewal_runtime_grant_invalid")
            grant = _object(self.grant_path.read_bytes(), limit=65536)
            binding = _binding(dict(policy=base, source_sha256=self.runner.release_hash,
                config_sha256=self.runner.journal.audit_context["config_hash"]))
            if _grant_error(grant, self.pin, binding, now) is not None:
                raise ValueError("renewal_runtime_grant_invalid")
            if grant.get("original_policy_sha256") != _hash(base):
                raise ValueError("renewal_runtime_original_proof_invalid")
            return grant
        except (OSError, KeyError, TypeError, AttributeError, OverflowError) as error:
            raise ValueError("renewal_runtime_grant_invalid") from error

    def _proof(self, grant, base, now, *, expected_review=None):
        try:
            if self.original_path.is_symlink() or self.original_path.stat().st_size > 1024 * 1024:
                raise ValueError("renewal_runtime_original_proof_invalid")
            content = self.original_path.read_bytes()
            digest = _sha(content)
            if (digest != grant.get("original_review_sha256")
                    or self.runner.journal.get("selected_execution_review_sha256") != digest
                    or (expected_review is not None and content != expected_review)):
                raise ValueError("renewal_runtime_original_proof_invalid")
            review = _object(content)
            approved = _utc(review["approved_utc"])
            if approved > now:
                raise ValueError("renewal_runtime_original_proof_invalid")
            # Checking the historical immutable approval is additional proof,
            # not a refresh of its time or acceptance. inspect cannot persist it.
            context = SimpleNamespace(policy=base, fingerprint=self.runner.fingerprint,
                release_hash=self.runner.release_hash, journal=self.runner.journal)
            if self.original.inspect(context, approved).get("status") != "VALID":
                raise ValueError("renewal_runtime_original_proof_invalid")
            return review, content
        except (OSError, KeyError, TypeError, AttributeError, OverflowError) as error:
            raise ValueError("renewal_runtime_original_proof_invalid") from error

    def _enroll(self, base, grant, now):
        self._proof(grant, base, now)
        self.ledger.register_generation(base, evidence_sha256=base["account_evidence_sha256"],
            now=now, original_review_sha256=grant["original_review_sha256"])

    def ensure_tracking(self, now):
        """Enroll once with authority; factual reconciliation then persists.

        A missing future renewal grant cannot invalidate a still-valid legacy
        approval. After enrollment, a revoked grant does not erase cost facts or
        prevent recording an owned exit. Derived entry still needs live authority.
        Integrity/storage failures are not downgraded to unenrolled.
        """
        now = _utc(now)
        if self.ledger.status()["legacy_cutoff_utc"] is not None:
            return True
        try:
            grant = self._grant(self.base_policy, now)
            self._enroll(self.base_policy, grant, now)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
            if self._pointer_exists():
                raise
            return False
        return True

    def bind_active(self, active, ident, now):
        """Bind actual intent provenance before a complete close clears it."""
        now = _utc(now)
        if not self.ensure_tracking(now):
            raise ValueError("renewal_runtime_position_provenance_missing")
        generation = active.get("cost_policy_hash")
        if isinstance(active.get("cost"), dict):
            if generation is not None and generation != _hash(active["cost"]):
                raise ValueError("renewal_runtime_position_provenance_missing")
            generation = self.ledger.register_generation(active["cost"],
                evidence_sha256=active["cost"]["account_evidence_sha256"], now=now)
        if generation not in self.ledger.status()["generation_ids"]:
            raise ValueError("renewal_runtime_position_provenance_missing")
        self.ledger.bind_position(int(ident), generation, evidence_sha256=_hash(active), now=now)

    def audit_existing_reads(self, account, positions, deals, now):
        """Consume already verified epoch reads; no SDK access or new flat claim."""
        now = _utc(now)
        if not self.ensure_tracking(now):
            return dict(status="UNVERIFIED", reason="renewal_tracking_not_enrolled", execution_authorized=False)
        active = self.runner.journal.get("active")
        if active is not None and active.get("position_id") is not None:
            self.bind_active(active, active["position_id"], now)
        return self.ledger.audit_history(deals, total=len(deals),
            history_start=datetime(1970, 1, 1, tzinfo=timezone.utc), history_end=now,
            balance=float(account.balance), positions=positions, now=now)

    @staticmethod
    def _captures(document):
        result = {}
        for role, item in document["_captures"].items():
            result[role] = dict(item)
            result[role]["body"] = base64.b64decode(result[role].pop("body_base64"), validate=True)
        return result

    def _semantic(self, snapshot, now):
        docs = {key: _object(value) for key, value in snapshot.documents.items()}
        base = docs["context"]["base_policy"]
        grant = self._grant(base, now)
        if docs["grant"] != grant:
            raise ValueError("renewal_runtime_grant_invalid")
        self._proof(grant, base, now, expected_review=snapshot.documents["review"])
        sources = docs["sources"]
        verified = sources_for_policy(sources["_packet"], self._captures(sources),
                                       now=_utc(docs["policy"]["reviewed_utc"]))
        if any(sources.get(role) != value for role, value in verified.items()):
            raise ValueError("renewal_runtime_source_binding_invalid")
        receipt, broker = docs["cost_audit"], docs["broker"]
        rows = {}
        for deal in broker["history_deals"]:
            row = {key: deal[key] for key in _FIELDS}
            for key in ("volume", "profit", "commission", "swap", "fee"):
                row[key] = float(row[key])
            key = str(row["ticket"])
            if key in rows:
                raise ValueError("renewal_runtime_cost_coverage_invalid")
            rows[key] = row
        point = receipt["checkpoint"]
        if (receipt["status"] != "CLEAR" or point["snapshot_sha256"] != _hash(rows)
                or point["history_count"] != broker["history_deals_total"]
                or point["history_count"] != len(rows)
                or point["history_start_utc"] != broker["history_start_utc"]
                or point["history_end_utc"] != broker["history_end_utc"]
                or point["balance"] != float(broker["account"]["balance"])
                or abs(point["cash_total"] - float(broker["account"]["balance"])) > .02):
            raise ValueError("renewal_runtime_cost_coverage_invalid")
        return True

    def _store(self, grant):
        return GenerationStore(self.root, binding=grant.get("binding"), trusted_grant_sha256=self.pin)

    def _renewal_parent(self, store, now):
        """Prove historical parent integrity without granting expired entry.

        An expired but complete generation may be superseded by genuinely fresh
        evidence. Its pointer is only a CAS parent; historical validation never
        adopts it or declares it valid at the current clock. Corruption still
        refuses replacement instead of concealing the damaged prior context.
        """
        previous = store.load_current_historical(now=now, validate=self._semantic)
        if previous is None:
            if self._adopted_id() is not None:
                raise ValueError("renewal_runtime_installed_generation_invalid")
            return None
        intent = self._lineage(previous)
        if intent is not None:
            # Recover identity bookkeeping of an already authorized complete
            # switch, even if its entry policy has since expired. This neither
            # adopts the expired running policy nor refreshes any authority.
            policy = _object(previous.documents["policy"])
            self.ledger.register_generation(policy, evidence_sha256=policy["account_evidence_sha256"], now=now)
            self._record_adoption(previous, intent, historical=True)
        return previous.generation_id

    def _invalid_installed(self, error):
        self.fault = "renewal_runtime_installed_generation_invalid"
        failure = ValueError(self.fault)
        reason = public_reason(error)
        if reason in RESUME:
            failure.diagnostics = dict(stage="renewal.generation", code=reason)
        return failure

    def policy_for_reload(self, legacy, now):
        """Retain coherent installed context despite a failed legacy-file read.

        No installed generation preserves the legacy opt-in/default-off behavior.
        Historical loading proves integrity and current renewal authority only;
        an expired returned policy remains ineligible under current entry checks.
        The caller adopts this complete value, never individual legacy fields.
        """
        now = _utc(now)
        try:
            if not self._pointer_exists():
                return legacy
            grant = _object(self.grant_path.read_bytes(), limit=65536)
            snapshot = self._store(grant).load_current_historical(now=now, validate=self._semantic)
            self._lineage(snapshot)
            base = _object(snapshot.documents["context"])["base_policy"]
            grant = self._grant(base, now)
            self._proof(grant, base, now, expected_review=snapshot.documents["review"])
            self.base_policy = deepcopy(base)
            return _object(snapshot.documents["policy"])
        except Exception as error:
            raise self._invalid_installed(error) from error

    def restore(self, now):
        """Adopt one validated snapshot; failures block entry without erasing it."""
        now = _utc(now)
        if not self._pointer_exists():
            return None
        try:
            # The grant's independent pin and current source/config binding are
            # checked again by _semantic against the sealed original policy.
            grant = _object(self.grant_path.read_bytes(), limit=65536)
            snapshot = self._store(grant).load_current(now=now, validate=self._semantic)
            self._lineage(snapshot)
            base = _object(snapshot.documents["context"])["base_policy"]
            policy = _object(snapshot.documents["policy"])
            self._enroll(base, grant, now)
            self._adopt(snapshot, base, policy, now)
            return deepcopy(policy)
        except Exception as error:
            raise self._invalid_installed(error) from error

    def check(self, ctx, now, *, record=False):
        if ctx is not self.runner:
            raise ValueError("renewal_runtime_context_mismatch")
        if not self._pointer_exists():
            result = self.original.check(ctx, now, record=record)
            self.last_diagnostics = dict(self.original.last_diagnostics)
            return result
        self.restore(now)
        grant = self._grant(self.base_policy, _utc(now))
        review, _ = self._proof(grant, self.base_policy, _utc(now))
        valid, _ = validate_policy(ctx.policy, fingerprint=ctx.fingerprint, now=now, strategy="c22h4")
        if not valid:
            raise ValueError("renewal_runtime_installed_generation_invalid")
        self.last_diagnostics = dict(status="VALID", code="renewal_generation_valid", observational=True,
            coverage="review_and_policy_only", approval_accepted=True,
            approved_utc=review["approved_utc"], arm_not_before_utc=review.get("arm_not_before_utc"),
            generation_id=self.snapshot.generation_id, policy_reviewed_utc=ctx.policy["reviewed_utc"])
        return review

    def inspect(self, ctx, now):
        try:
            if not self._pointer_exists():
                return self.original.inspect(ctx, now)
            grant = _object(self.grant_path.read_bytes(), limit=65536)
            snapshot = self._store(grant).load_current(now=now, validate=self._semantic)
            self._lineage(snapshot)
            review = _object(snapshot.documents["review"])
            policy = _object(snapshot.documents["policy"])
            self.last_diagnostics = dict(status="VALID", code="renewal_generation_valid", observational=True,
                coverage="review_and_policy_only", approval_accepted=True,
                approved_utc=review["approved_utc"], arm_not_before_utc=review.get("arm_not_before_utc"),
                generation_id=snapshot.generation_id, policy_reviewed_utc=policy["reviewed_utc"])
        except Exception:
            self.last_diagnostics = dict(status="BLOCKED", code="renewal_runtime_installed_generation_invalid",
                observational=True, coverage="review_and_policy_only")
        return dict(self.last_diagnostics)

    def prepare(self, broker_bytes, source_packet, captures, *, now, observe_state, clock):
        """Prepare/install only under current independent grant and fresh proof.

        Errors before a successful pointer switch retain the existing running
        policy. A post-replace ambiguity requires restore and blocks new entry.
        Neither a candidate nor a returned receipt authorizes an order.
        """
        now = _utc(now)
        retained = self.policy_for_reload(self.runner.policy, now)
        if retained != self.runner.policy:
            self.runner.policy = retained
        old_policy = self.runner.policy
        switched = False
        intent = None
        try:
            grant = self._grant(self.base_policy, now)
            _, review_bytes = self._proof(grant, self.base_policy, now)
            self._enroll(self.base_policy, grant, now)
            observation = observe_state()
            state = observation.state if isinstance(observation, FreshState) else RenewalState(None, None, None, None)
            current = dict(policy=old_policy, source_sha256=self.runner.release_hash,
                config_sha256=self.runner.journal.audit_context["config_hash"], context=self.runner.journal)
            due = plan_renewal(current=current, grant=grant, trusted_grant_sha256=self.pin,
                now=now, state=state, enabled=True)
            if due.action != "PREPARE":
                return dict(status=due.action, reason=due.reason, execution_authorized=False)
            sources = sources_for_policy(source_packet, captures, now=now)
            plan = plan_renewal(current=current, grant=grant, trusted_grant_sha256=self.pin,
                now=now, state=state, enabled=True, broker_bytes=broker_bytes, sources=sources)
            if plan.action != "REVIEW_CANDIDATE":
                return dict(status=plan.action, reason=plan.reason, execution_authorized=False)
            store = self._store(grant)
            parent = self._renewal_parent(store, now)
            broker = _object(broker_bytes)
            deals = [SimpleNamespace(**item) for item in broker["history_deals"]]
            receipt = self.ledger.audit_history(deals, total=broker["history_deals_total"],
                history_start=_utc(broker["history_start_utc"]), history_end=_utc(broker["history_end_utc"]),
                balance=broker["account"]["balance"], positions=[], now=now)
            if receipt["status"] != "CLEAR":
                raise ValueError("renewal_runtime_unresolved_cost_incident")
            source_document = dict(sources, _packet=source_packet,
                _captures={role: dict({key: value for key, value in item.items() if key != "body"},
                    body_base64=base64.b64encode(item["body"]).decode()) for role, item in captures.items()})
            audit_raw = _raw(receipt)
            context = dict(binding=grant["binding"], grant_sha256=self.pin,
                original_review_sha256=_sha(review_bytes), cost_audit_sha256=_sha(audit_raw),
                parent_generation_id=parent, base_policy=self.base_policy)
            documents = dict(policy=_raw(plan.candidate_policy), broker=broker_bytes, sources=_raw(source_document),
                review=review_bytes, grant=_raw(grant), context=_raw(context), cost_audit=audit_raw)
            staged = store.stage(plan, documents, now=now, validate=self._semantic)

            def authorize(snapshot, at):
                self._grant(self.base_policy, at)
                self._proof(grant, self.base_policy, at)
                return self.ledger.status() == _object(snapshot.documents["cost_audit"])

            def before_replace(snapshot, at, observation):
                nonlocal intent
                intent = self._install_intent(snapshot, at, observation)

            installed = store.install(staged.generation_id, expected_current=parent, clock=clock,
                observe_state=observe_state, validate=self._semantic, authorize=authorize,
                before_replace=before_replace)
            switched = True
            self._adopt(installed, self.base_policy, _object(installed.documents["policy"]), _utc(clock()))
            return dict(status="INSTALLED", generation_id=installed.generation_id,
                        policy=deepcopy(self.runner.policy), execution_authorized=False)
        except Exception as error:
            if switched or isinstance(error, RuntimeError):
                self.fault = "renewal_runtime_switch_unknown"
            else:
                self.runner.policy = old_policy
                if intent is not None:
                    self.runner.journal.audit("RENEWAL_INSTALL_CANCELLED", install_intent_event_id=intent["event_id"])
            raise
