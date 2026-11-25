"""Selected C22 hooks reuse shared broker-confirmed Demo execution lifecycle."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.c22_selected.strategy import CONFIG_PATH, MAGIC, SelectedStrategy
from scripts.c22_selected.evidence import capture_current_reads, export_requested
from scripts.demo_runtime.admission import Admission
from scripts.demo_runtime.broker import _cash
from scripts.demo_runtime.diagnostics import public_reason
from scripts.demo_runtime.runner import DemoRunner


class SelectedAdmission(Admission):
    """Apply elapsed-time cooldown at the existing first-quote admission seam."""

    def __init__(self, context):
        super().__init__(context)
        self._candidate_deals = None

    def admit(self, account, positions, orders, deals, info, tick, bars, now):
        self._candidate_deals = deals
        try:
            renewal = getattr(self.context, "renewal_runtime", None)
            if renewal is not None and renewal.ensure_tracking(now):
                receipt = renewal.audit_existing_reads(account, positions, deals, now)
                if receipt["status"] != "CLEAR":
                    raise ValueError("renewal_runtime_unresolved_cost_incident")
            return super().admit(account, positions, orders, deals, info, tick, bars, now)
        finally:
            self._candidate_deals = None

    def _first_quote(self, closed, now):
        first = super()._first_quote(closed, now)
        ctx = self.context
        deals = self._candidate_deals
        if deals is None:
            # The shared lifecycle also asks for the first closed-bar quote
            # when managing BE. A new-entry cooldown must not block protection.
            if ctx.journal.get("active") is not None:
                return first
            raise ValueError("cooldown_history_missing")
        owned = {
            int(d.position_id) for d in deals
            if int(d.entry) == 0 and int(d.type) in (0, 1)
            and int(d.magic) == MAGIC and str(d.comment).startswith(ctx.strategy.prefix)
        }
        last_loss = 0
        for ident in owned:
            ledger = [d for d in deals if int(d.position_id) == ident and int(d.type) in (0, 1)]
            exits = [d for d in ledger if int(d.entry) in (1, 3)]
            volume = sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in ledger)
            if exits and abs(volume) < 1e-8 and sum(_cash(d) for d in ledger) < 0:
                last_loss = max(last_loss, max(int(d.time_msc) for d in exits))
        recorded = ctx.journal.get("selected_last_loss_ms") or 0
        if last_loss < recorded:
            raise ValueError("cooldown_history_drift")
        if last_loss:
            ctx.journal.put("selected_last_loss_ms", last_loss)
        cooldown_ms = ctx.strategy.cooldown_bars * 15 * 60 * 1000
        if last_loss and int(first.time_msc) < last_loss + cooldown_ms:
            ctx.journal.put("last_bar", closed.isoformat())
            raise ValueError("cooldown")
        return first


class SelectedDemoRunner(DemoRunner):
    def __init__(self, *, config=None, cache_output=None, broker_evidence_dir=None, **kwargs):
        config = json.loads(CONFIG_PATH.read_text()) if config is None else config
        self.cache_output = cache_output
        self.broker_evidence_dir = broker_evidence_dir
        self._evidence_snapshot = None
        self._evidence_exposure_utc = None
        self.renewal_runtime = None
        self.renewal_sources_path = None
        super().__init__(strategy=SelectedStrategy(config), **kwargs)
        self.strategy.cache_path = cache_output
        self.strategy.cache_fingerprint = self.fingerprint
        self.strategy.history_seed_status = "disabled" if cache_output is None else "not_loaded"
        self._admission = SelectedAdmission(self)
        # Shared release hashing predates this adapter. Include every new module
        # so two adapter versions cannot share a forward cohort accidentally.
        digest = hashlib.sha256(self.release_hash.encode())
        for path in sorted(Path(__file__).parent.glob("*.py")):
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
        self.release_hash = digest.hexdigest()
        self.journal.audit_context["release_hash"] = self.release_hash
        self.cohort_id = self.release_hash + ":" + self.journal.audit_context["config_hash"]

    def export_cache(self, path, *, only_if_changed=False):
        """Persist the exact completed causal prefix, not a bootstrap count claim."""
        bars = self.strategy.cache.bars
        if bars is None:
            return
        path = Path(path)
        previous = getattr(self, "_cache_export", None)
        # SelectedBarCache replaces its DataFrame when a prefix grows or resets.
        # A normal no-new-bar poll retains the same immutable prefix object.
        def signature():
            value = path.stat()
            return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns

        if only_if_changed and previous is not None and previous[0] == path.resolve() and previous[1] is bars:
            try:
                if signature() == previous[2]:
                    return
            except FileNotFoundError:
                pass
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        bars.to_csv(temporary, index_label="bar_open_utc")
        temporary.replace(path)
        self._cache_export = path.resolve(), bars, signature()

    def cycle(self, *, now):
        self._evidence_snapshot = None
        self._evidence_exposure_utc = None
        restore_error = None
        if self.renewal_runtime is not None:
            started = time.monotonic()
            try:
                self.policy = self.renewal_runtime.policy_for_reload(self.policy, now)
                self.renewal_runtime.restore(now)
            except Exception as error:
                # A corrupt/revoked generation blocks the review adapter, not
                # the existing owned-position reconciliation/protection path.
                restore_error = error
            now += timedelta(seconds=max(0, time.monotonic() - started))
        self._cycle_utc = now
        result = super().cycle(now=now)
        if restore_error is not None:
            self.record_operational_failure(result, now=now, stage="renewal.restore",
                error=restore_error, code="renewal_runtime_installed_generation_invalid")
        result["research_rules_id"] = self.strategy.config["contract_id"]
        result["cooldown_minutes"] = int(timedelta(minutes=15 * self.strategy.cooldown_bars).total_seconds() / 60)
        if self.cache_output is not None:
            # Financial reconciliation/protection has already completed above.
            # A cache is a restart aid, so its failure must not stop that manager.
            try:
                self.export_cache(self.cache_output, only_if_changed=True)
            except Exception as error:
                self.record_operational_failure(
                    result, now=now, stage="cache.export", error=error,
                    code="cache_export_failed")
            else:
                try:
                    error = self.strategy.checkpoint(now=now)
                except Exception as failure:
                    # Keep unexpected adapter failures inside the optional seam.
                    if self.strategy.history_seed_status != "checkpoint_failed":
                        self.strategy._checkpoint_seed_status = self.strategy.history_seed_status
                    self.strategy.history_seed_status = "checkpoint_failed"
                    error = failure
                result["history_seed_status"] = self.strategy.history_seed_status
                if error is not None:
                    self.record_operational_failure(
                        result, now=now, stage="cache.checkpoint", error=error,
                        code="cache_checkpoint_failed")
        if self.broker_evidence_dir is not None:
            try:
                receipt = export_requested(self, self.broker_evidence_dir, self._evidence_snapshot,
                    now=self._send_clock(now))
                if receipt is not None:
                    result["broker_evidence"] = receipt
                    if getattr(self, "_last_evidence_receipt", None) != receipt:
                        self.journal.audit("BROKER_EVIDENCE", receipt=receipt)
                        self._last_evidence_receipt = receipt
                    self.journal.put("last_result", result)
            except Exception as error:
                reason = public_reason(error)
                code = reason if reason != type(error).__name__ else "broker_evidence_export_failed"
                result["broker_evidence"] = dict(status="FAULT", reason=code,
                                                execution_authorized=False)
                self.record_operational_failure(result, now=now, stage="evidence.export",
                    error=error, code=code)
        if self.renewal_runtime is not None and self.renewal_sources_path is not None:
            try:
                reviewed = datetime.fromisoformat(self.policy["reviewed_utc"])
                if now >= reviewed + timedelta(hours=96):
                    self._automatic_renewal(result, now)
            except Exception as error:
                result["renewal"] = dict(status="DEFERRED", reason=public_reason(error), execution_authorized=False)
                self.record_operational_failure(result, now=now, stage="renewal.prepare",
                    error=error, code="renewal_runtime_preparation_failed")
        return result

    def observe_broker_reads(self, account, positions, orders, deals, info, now):
        if self.broker_evidence_dir is not None or self.renewal_runtime is not None:
            self._evidence_snapshot = (account, positions, orders, deals, info, now,
                self._send_clock(now), dict(self.broker.identity_diagnostics))
            self._evidence_exposure_utc = self._exposure_read_utc

    def configure_renewal(self, *, grant_path, trusted_grant_sha256, generation_root,
                          original_review_path, now, sources_path=None):
        """Explicit opt-in only; a file path does not create an owner grant."""
        from scripts.c22_selected.renewal_runtime import RenewalRuntime
        from scripts.c22_selected.execution import ReviewedAdmission
        runtime = RenewalRuntime(self, grant_path=grant_path, trusted_grant_sha256=trusted_grant_sha256,
            generation_root=generation_root, original_review_path=original_review_path)
        self.renewal_runtime = runtime
        self.renewal_sources_path = sources_path
        self._admission = ReviewedAdmission(self, runtime)
        try:
            runtime.restore(now)
        except Exception:
            # cycle/check preserve this failure for entries. Do not prevent an
            # already-owned manager starting because renewal evidence failed.
            pass
        return runtime

    def reload_cost_policy(self, policy, *, now):
        if self.renewal_runtime is None:
            self.policy = policy
        else:
            self.policy = self.renewal_runtime.policy_for_reload(policy, now)

    def prepare_renewal(self, source_packet, captures, *, now, clock):
        """Use only the completed current read seam and actual journal state."""
        from scripts.c22_selected.generations import FreshState
        from scripts.c22_selected.renewal import RenewalState
        if self.renewal_runtime is None:
            raise ValueError("renewal_runtime_not_configured")
        if (self._evidence_snapshot is None or self.journal.get("active") is not None
                or self.journal.get("safety_halt") or self._cycle_send_attempted
                or self._evidence_snapshot[1] or self._evidence_snapshot[2]):
            return dict(status="DEFERRED", reason="flat_no_orders_no_active_no_unknown_required",
                        execution_authorized=False)
        if (self._evidence_exposure_utc is None
                or not timedelta(0) <= clock() - self._evidence_exposure_utc <= timedelta(seconds=5)):
            return dict(status="DEFERRED", reason="generation_fresh_flat_window_required",
                        execution_authorized=False)
        broker = capture_current_reads(self, self._evidence_snapshot, now=clock())

        def state():
            snapshot = self._evidence_snapshot
            if snapshot is None:
                return FreshState(RenewalState(None, None, None, None), now)
            active = self.journal.get("active")
            return FreshState(RenewalState(len(snapshot[1]), len(snapshot[2]), active is not None,
                bool(self.journal.get("safety_halt")) or self._cycle_send_attempted
                or bool(active and active.get("status") in {"UNKNOWN", "SENDING"})), self._evidence_exposure_utc)

        return self.renewal_runtime.prepare(broker, source_packet, captures, now=now,
            observe_state=state, clock=clock)

    def _automatic_renewal(self, result, now):
        """Consume local source evidence; never do HTTP/SDK work in the sender."""
        import base64
        if (self._evidence_snapshot is None or self.journal.get("active") is not None
                or self.journal.get("safety_halt") or self._cycle_send_attempted
                or self._evidence_snapshot[1] or self._evidence_snapshot[2]):
            result["renewal"] = dict(status="DEFERRED",
                reason="flat_no_orders_no_active_no_unknown_required", execution_authorized=False)
            return
        path = Path(self.renewal_sources_path)
        if path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("renewal_runtime_source_binding_invalid")
        stamp = (path.stat().st_mtime_ns, path.stat().st_size)
        previous = getattr(self, "_renewal_source_cache", None)
        if previous is None or previous[0] != stamp:
            document = json.loads(path.read_bytes())
            captures = {role: dict(item, body=base64.b64decode(item["body_base64"], validate=True))
                        for role, item in document["captures"].items()}
            self._renewal_source_cache = (stamp, document["packet"], captures)
        _, packet, captures = self._renewal_source_cache
        result["renewal"] = self.prepare_renewal(packet, captures,
            now=self._send_clock(now), clock=lambda: self._send_clock(now))
        self.journal.put("last_result", result)

    def _record_closed(self, active, ledger, ident, *, safety_reason=None):
        failure = None
        if self.renewal_runtime is not None:
            try:
                self.renewal_runtime.bind_active(active, ident,
                    self._send_clock(getattr(self, "_cycle_utc", datetime.now(timezone.utc))))
            except Exception as error:
                failure = error
        result = super()._record_closed(active, ledger, ident, safety_reason=safety_reason)
        if failure is not None:
            self.record_operational_failure(result, now=getattr(self, "_cycle_utc", datetime.now(timezone.utc)),
                stage="renewal.closed_provenance", error=failure, code="renewal_runtime_position_provenance_missing")
        return result
