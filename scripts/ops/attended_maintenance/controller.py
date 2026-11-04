"""Reviewed local orchestrator; production host adapters are deliberately absent.

Host methods are closed effects, not caller-authored callbacks or shell steps.
Every method must be bounded by its plan and preserve the recorded operation
identity. A timeout is uncertainty. Only observations can resolve it.
"""

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .actions import action_adapter
from .model import (
    APMeasurement, Approval, CostInstallation, Handle, Observation, Reboot,
    digest, plan_document, read_plan, utc, validate_observation,
)
from .proof import classify, continuity, read_journal, require_flat
from .store import Store


class Host(Protocol):
    """Private host seam; observe is passive and never acquires an SDK reader.

    Broker proof owns one exclusive reader only after sender inactivity; it
    returns fresh same-account evidence and cleans up its reader. Probe cleanup
    requires exact operation/boot/PID/start ownership. Review restoration must
    recheck the exact held artifact/destination. Cost restoration must use the
    persisted acceptance marker. No method may send broker orders/notifications.
    """

    def observe(self, handle: Handle) -> Observation: ...
    def hold_review(self, handle: Handle) -> None: ...
    def stop_sender(self, handle: Handle) -> None: ...
    def prove_broker_flat(self, handle: Handle) -> dict: ...
    def measure_ap(self, handle: Handle, action: APMeasurement) -> None: ...
    def cleanup_probe(self, handle: Handle, identity) -> None: ...
    def install_cost(self, handle: Handle, action: CostInstallation) -> None: ...
    def restore_cost(self, handle: Handle, generation: str) -> None: ...
    def reboot(self, handle: Handle, action: Reboot) -> None: ...
    def restore_review(self, handle: Handle, cohort) -> None: ...
    def start_sender(self, handle: Handle) -> None: ...


SAFE_CODES = frozenset("""
unknown_outbox_schema audit_prefix_gap duplicate_event_lineage
notification_delivery_uncertain invalid_outbox_row unknown_notification_kind_or_schema
notification_identity_invalid notification_cohort_drift notification_lineage_unverified
sender_outbox_defer critical_review_required owned_unknown_halt_defer flat_cycle_missing
cycle_not_fresh post_hold_cycle_required outbox_schema_changed audit_prefix_changed
protected_values_continuity_unverified outbox_row_changed approved_outbox_set_changed
outbox_identity_reused aware_utc_required source_or_cohort_drift backup_unverified
cost_acceptance_unknown broker_flat_unverified reader_ownership_unverified
review_destination_unverified clock_regressed work_budget_exhausted approval_expired
sender_ownership_unverified
journal_account_or_strategy_drift
invalid_journal_json
invalid_host_observation invalid_clock_observation invalid_outside_clock
owned_probe_identity_changed
""".split())


def failure(error, stage, category):
    # Host exceptions are untrusted; only module-owned refusal strings escape.
    code = str(error) if type(error) is ValueError and str(error) in SAFE_CODES else "observation_failed"
    return {"stage": stage, "category": category, "code": code,
            "exception_type": type(error).__name__ if type(error).__name__ in (
                "ValueError", "TypeError", "KeyError", "TimeoutError", "OSError",
                "OperationalError", "JSONDecodeError", "FileNotFoundError") else "Exception"}


class Maintenance:
    def __init__(self, financial_journal):
        self.journal = Path(financial_journal).resolve()
        self.store = Store(self.journal.with_name(self.journal.name + ".maintenance.sqlite3"))
        if self.store.path.exists() and self.store.path.samefile(self.journal):
            raise ValueError("separate_operation_store_required")

    def prepare(self, plan, host: Host):
        """Freeze exact private evidence for review; grants no execution authority."""
        document = plan_document(plan)
        provisional = Handle(plan.operation, "")
        observed = host.observe(provisional)
        validate_observation(observed)
        self._context(plan, observed)
        baseline = read_journal(self.journal)
        observed = host.observe(provisional)
        validate_observation(observed)
        self._context(plan, observed)
        if observed.cohort != plan.cohort:
            raise ValueError("source_or_cohort_drift")
        require_flat(baseline, observed.captured_utc, plan.freshness_seconds)
        classify(baseline, plan, observed)
        frozen = {"plan": document, "baseline": baseline, "journal": str(self.journal),
                  "prepared_utc": utc(observed.captured_utc)}
        handle = Handle(plan.operation, digest(frozen))
        with self.store.locked() as db:
            prior = db.execute("SELECT document FROM operations WHERE id=?", (plan.operation,)).fetchone()
            if prior is not None:
                existing = self.store.load(db, handle)
                self._frozen(existing, handle)
                return handle
            self.store.save(db, dict(frozen, operation=plan.operation, digest=handle.digest,
                                    phase="NEW", status="PREPARED", effects={}, failures=[],
                                    approval=None, hold=None, manual_fallback=False, timing=None))
        return handle

    def inspect(self, handle):
        """Read existing receipt only. No host, SDK, recovery, lock or schema write."""
        document = self.store.read(handle)
        self._frozen(document, handle)
        return self._receipt(document)

    def run(self, handle, approval: Approval, host: Host):
        """Start/continue this exact approved operation; never substitute a new one."""
        with self.store.locked() as db:
            state = self.store.load(db, handle)
            self._frozen(state, handle)
            plan = read_plan(state["plan"])
            grant = self._approval(approval, state)
            if state["approval"] is not None and state["approval"] != grant:
                raise ValueError("approval_drift")
            if state["status"] in ("COMPLETE", "FAILED_RECOVERED", "DEFERRED") or state["phase"] == "END":
                # Reconcile a stranded same-operation claim from an older local
                # receipt; this is operational metadata, never financial state.
                with db:
                    db.execute("DELETE FROM accounts WHERE account=? AND operation=?",
                               (plan.cohort.account, plan.operation))
                return self._receipt(state)
            owner = db.execute("SELECT operation FROM accounts WHERE account=?", (plan.cohort.account,)).fetchone()
            if owner is not None and owner[0] != handle.operation:
                raise ValueError("account_operation_incomplete")
            with db:
                db.execute("INSERT OR IGNORE INTO accounts VALUES (?,?)", (plan.cohort.account, handle.operation))
            state["approval"] = grant
            self.store.save(db, state)
            for _ in range(12):
                phase = state["phase"]
                try:
                    observed = host.observe(handle)
                    validate_observation(observed)
                    if observed.captured_utc < approval.approved_utc:
                        raise ValueError("approval_expired")
                    expected = self._context(plan, observed)
                    current = read_journal(self.journal, original_highwater=state["baseline"]["highwater"])
                    observed = host.observe(handle)
                    validate_observation(observed)
                    expected = self._context(plan, observed)
                    if phase in ("NEW", "HELD", "STOPPED"):
                        self._work_budget(plan, state, approval, observed)
                    continuity(state["baseline"], current, allow_append=phase in ("RECOVERING", "RESTORED", "VERIFY"))
                    classify(current, plan, observed)
                    if phase in ("NEW", "HELD", "STOPPED"):
                        require_flat(current, observed.captured_utc, plan.freshness_seconds,
                                     after=state["hold"]["utc"] if phase == "HELD" else None)
                    if phase == "NEW":
                        if state["hold"] is None:
                            state["hold"] = {"utc": utc(observed.captured_utc), "boot": observed.boot,
                                             "monotonic": observed.monotonic}
                        self._effect(db, state, host, handle, "hold_review", "PRIMARY", retry=True)
                        state["phase"] = "HELD"
                    elif phase == "HELD":
                        if not observed.review_held or not observed.post_hold_cycle:
                            return self._wait(db, state, "WAITING_QUIESCENCE")
                        if observed.sender_running:
                            self._effect(db, state, host, handle, "stop_sender", "PRIMARY", retry=True)
                            after = host.observe(handle)
                            validate_observation(after)
                            self._context(plan, after)
                            if after.sender_running:
                                return self._wait(db, state, "WAITING_STOP")
                        state["phase"] = "STOPPED"
                    elif phase == "STOPPED":
                        if observed.sender_running or observed.readers or observed.owned_probe:
                            raise ValueError("reader_ownership_unverified")
                        if "prove_broker_flat" in state["effects"]:
                            raise ValueError("broker_flat_unverified")
                        packet = self._effect(db, state, host, handle, "prove_broker_flat", "PRIMARY")
                        # Recheck journal/source/budget after the exclusive reader returns.
                        after = host.observe(handle)
                        validate_observation(after)
                        self._broker(packet, after, plan)
                        self._context(plan, after)
                        if after.sender_running or after.readers or after.owned_probe:
                            raise ValueError("reader_ownership_unverified")
                        snapshot = read_journal(self.journal, original_highwater=state["baseline"]["highwater"])
                        after = host.observe(handle)
                        validate_observation(after)
                        self._context(plan, after)
                        self._broker(packet, after, plan)
                        if after.sender_running or after.readers or after.owned_probe:
                            raise ValueError("reader_ownership_unverified")
                        continuity(state["baseline"], snapshot)
                        require_flat(snapshot, after.captured_utc, plan.freshness_seconds)
                        classify(snapshot, plan, after)
                        self._work_budget(plan, state, approval, after)
                        state["action_boot"] = after.boot
                        name = action_adapter(plan).effect
                        # Persist next phase before the irreversible dispatch; a crash resumes observation.
                        state["phase"] = "ACTED"
                        self.store.save(db, state)
                        self._effect(db, state, host, handle, name, "PRIMARY", plan.action)
                    elif phase == "ACTED":
                        adapter = action_adapter(plan)
                        name = adapter.effect
                        if state["effects"].get(name, {}).get("state") != "ACKED" and not any(
                            f["stage"] == name for f in state["failures"]
                        ):
                            state["failures"].append({"stage": name, "category": "PRIMARY",
                                                      "code": "effect_outcome_uncertain", "exception_type": None})
                        wait = adapter.after_action(plan, state, observed)
                        if wait:
                            return self._wait(db, state, wait)
                        state["phase"] = "RECOVERING"
                    elif phase == "RECOVERING":
                        step = action_adapter(plan).recovery(plan, state, observed, approval)
                        if step is not None:
                            name, args = step
                            self._effect(db, state, host, handle, name,
                                         "CLEANUP" if name == "cleanup_probe" else "RECOVERY", *args, retry=True)
                            observed = host.observe(handle)
                            validate_observation(observed)
                            expected = self._context(plan, observed)
                        if observed.readers or observed.owned_probe:
                            return self._wait(db, state, "OPERATOR_REQUIRED")
                        if observed.review_held:
                            if not observed.review_restore_safe:
                                raise ValueError("review_destination_unverified")
                            state["restore_utc"] = utc(observed.captured_utc)
                            self._effect(db, state, host, handle, "restore_review", "RECOVERY", expected, retry=True)
                            after = host.observe(handle)
                            validate_observation(after)
                            self._context(plan, after)
                            if after.review_held:
                                return self._wait(db, state, "OPERATOR_REQUIRED")
                        state["phase"] = "RESTORED"
                    elif phase == "RESTORED":
                        if observed.review_held:
                            # A conditional restore may have failed before its
                            # mutation. Reobserve and continue the same recovery.
                            state["phase"] = "RECOVERING"
                            self.store.save(db, state)
                            continue
                        if observed.readers or observed.owned_probe:
                            raise ValueError("reader_ownership_unverified")
                        if not observed.sender_running:
                            if not approval.allow_manager_recovery:
                                return self._wait(db, state, "WAITING_AUTOMATIC_RECOVERY")
                            if type(plan.action) is Reboot:
                                state["manual_fallback"] = True
                            self._effect(db, state, host, handle, "start_sender", "RECOVERY", retry=True)
                        state["phase"] = "VERIFY"
                    elif phase == "VERIFY":
                        if observed.readers or observed.owned_probe:
                            raise ValueError("reader_ownership_unverified")
                        if not observed.sender_running or not observed.recovered_cycle:
                            if not observed.sender_running:
                                state["phase"] = "RESTORED"
                            return self._wait(db, state, "WAITING_RECOVERY_PROOF")
                        last = current["values"].get("last_result") or {}
                        stamp = datetime.fromisoformat(last["captured_utc"])
                        utc(stamp)
                        if not 0 <= (observed.captured_utc - stamp).total_seconds() < plan.freshness_seconds:
                            raise ValueError("cycle_not_fresh")
                        if state.get("restore_utc") and stamp <= datetime.fromisoformat(state["restore_utc"]):
                            return self._wait(db, state, "WAITING_RECOVERY_PROOF")
                        elapsed = self._elapsed(state, observed)
                        state["timing"] = {"seconds": elapsed,
                                           "status": "TIMING_UNVERIFIED" if elapsed is None else "VERIFIED",
                                           "overrun": elapsed is not None and elapsed > plan.pause_seconds}
                        state["status"] = "FAILED_RECOVERED" if state["failures"] else "COMPLETE"
                        if elapsed is None or elapsed > plan.pause_seconds:
                            state["status"] = "STATE_REVIEW_REQUIRED"
                        state["phase"] = "END"
                        self._finish(db, state, plan)
                        return self._receipt(state)
                    else:
                        raise ValueError("invalid_operation_phase")
                    state["status"] = "RUNNING"
                    self.store.save(db, state)
                except Exception as error:
                    state["failures"].append(failure(error, phase, "PRIMARY" if phase in ("NEW", "HELD", "STOPPED", "ACTED") else "RECOVERY"))
                    if phase == "NEW":
                        state["status"], state["phase"] = "DEFERRED", "END"
                        self._finish(db, state, plan)
                        return self._receipt(state)
                    if phase in ("HELD", "STOPPED"):
                        state["phase"] = "RECOVERING"
                        self.store.save(db, state)
                        continue
                    # Never stop a restored owned manager to force proof equality.
                    return self._wait(db, state, "STATE_REVIEW_REQUIRED")
            return self._wait(db, state, "OPERATOR_REQUIRED")

    def _effect(self, db, state, host, handle, name, category, *args, retry=False):
        conditional = {"hold_review", "stop_sender", "cleanup_probe", "restore_cost", "restore_review", "start_sender"}
        if retry and name not in conditional:
            raise ValueError("nonrepeatable_effect")
        previous = state["effects"].get(name)
        arguments = [asdict(arg) if hasattr(type(arg), "__dataclass_fields__") else arg for arg in args]
        argument_hash = digest(arguments)
        if previous is not None:
            if not retry or previous["state"] == "ACKED":
                return None
            if name == "cleanup_probe" and previous.get("target_sha256") != argument_hash:
                raise ValueError("owned_probe_identity_changed")
            # Only fresh safe-state guards above can reach a conditional retry.
            # Preserve original attempts and their failure evidence.
            previous.setdefault("attempts", [{"state": previous["state"]}])
        else:
            previous = {"state": "ATTEMPTED", "attempts": []}
            state["effects"][name] = previous
            if name == "cleanup_probe":
                previous["target_sha256"] = argument_hash
        previous["state"] = "ATTEMPTED"
        previous["attempts"].append({"state": "ATTEMPTED", "arguments": arguments,
                                     "arguments_sha256": argument_hash})
        self.store.save(db, state)
        try:
            result = getattr(host, name)(handle, *args)
        except Exception as error:
            state["effects"][name]["state"] = "UNCERTAIN"
            previous["attempts"][-1]["state"] = "UNCERTAIN"
            state["failures"].append({"stage": name, "category": category,
                                      "code": "effect_outcome_uncertain",
                                      "exception_type": failure(error, name, category)["exception_type"]})
            result = None
        else:
            state["effects"][name]["state"] = "ACKED"
            previous["attempts"][-1]["state"] = "ACKED"
        self.store.save(db, state)
        return result

    @staticmethod
    def _approval(approval, state):
        if type(approval) is not Approval or approval.plan_digest != state["digest"] or not approval.owner_ref:
            raise ValueError("exact_owner_approval_required")
        if type(approval.allow_manager_recovery) is not bool or type(approval.allow_probe_cleanup) is not bool:
            raise ValueError("invalid_recovery_authority")
        stamp = utc(approval.approved_utc)
        if approval.approved_utc < datetime.fromisoformat(state["prepared_utc"]):
            raise ValueError("approval_predates_plan")
        if approval.valid_until is not None and approval.valid_until <= approval.approved_utc:
            raise ValueError("invalid_approval_interval")
        result = asdict(approval)
        result["approved_utc"] = stamp
        result["valid_until"] = utc(approval.valid_until) if approval.valid_until is not None else None
        return result

    @staticmethod
    def _frozen(state, handle):
        frozen = {key: state[key] for key in ("plan", "baseline", "journal", "prepared_utc")}
        if digest(frozen) != handle.digest:
            raise ValueError("prepared_evidence_drift")

    @staticmethod
    def _context(plan, observed):
        if type(observed.sender_count) is not int or observed.sender_count not in (0, 1) or observed.sender_count != int(observed.sender_running):
            raise ValueError("sender_ownership_unverified")
        expected = action_adapter(plan).cohort(plan, observed)
        if observed.cohort != expected:
            raise ValueError("source_or_cohort_drift")
        if observed.backup_sha256 != plan.backup_sha256 or not observed.backup_restore_verified:
            raise ValueError("backup_unverified")
        return expected

    @staticmethod
    def _broker(packet, observed, plan):
        if (not isinstance(packet, dict) or packet.get("account") != plan.cohort.account
                or any(type(packet.get(key)) is not int or packet[key] != 0 for key in ("positions", "orders"))):
            raise ValueError("broker_flat_unverified")
        stamp = datetime.fromisoformat(packet["captured_utc"])
        utc(stamp)
        if not 0 <= (observed.captured_utc - stamp).total_seconds() < plan.freshness_seconds:
            raise ValueError("broker_flat_unverified")

    @staticmethod
    def _work_budget(plan, state, approval, observed):
        if observed.captured_utc < approval.approved_utc or (
            approval.valid_until is not None and observed.captured_utc >= approval.valid_until
        ):
            raise ValueError("approval_expired")
        elapsed = Maintenance._elapsed(state, observed)
        if elapsed is None or elapsed + plan.action_seconds + plan.recovery_seconds > plan.pause_seconds:
            raise ValueError("work_budget_exhausted")

    @staticmethod
    def _elapsed(state, observed):
        hold = state["hold"]
        if hold is None:
            return 0
        if hold["boot"] != observed.boot:
            return observed.outside_pause_seconds
        elapsed = observed.monotonic - hold["monotonic"]
        if elapsed < 0:
            raise ValueError("clock_regressed")
        return elapsed

    def _wait(self, db, state, status):
        state["status"] = status
        self.store.save(db, state)
        return self._receipt(state)

    def _finish(self, db, state, plan):
        with db:
            self.store.save(db, state, commit=False)
            db.execute("DELETE FROM accounts WHERE account=? AND operation=?", (plan.cohort.account, plan.operation))

    @staticmethod
    def _receipt(state):
        result = {key: state[key] for key in ("operation", "digest", "status", "phase",
                                            "failures", "manual_fallback", "timing")}
        # Raw argument evidence stays private in the operational database.
        result["effects"] = {
            name: dict(effect, attempts=[{k: v for k, v in attempt.items() if k != "arguments"}
                                         for attempt in effect.get("attempts", [])])
            for name, effect in state["effects"].items()
        }
        return result
