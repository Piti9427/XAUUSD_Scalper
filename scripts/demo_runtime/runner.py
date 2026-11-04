"""Shared Demo orchestration; strategy injected by C22 or rollback adapter."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import time
import json
import uuid
from pathlib import Path
from typing import Any, Callable

from scripts.demo_runtime.market_data import completed_m15_from_m1
from scripts.demo_runtime.journal import Journal
from scripts.demo_runtime.broker import BrokerView

from scripts.demo_runtime.admission import Admission
from scripts.demo_runtime.lifecycle import Lifecycle
from scripts.demo_runtime.status import entry_availability
from scripts.demo_runtime.diagnostics import failure_record, fallback, public_reason


class DemoRunner:
    def __init__(
        self,
        *,
        mt5: Any,
        expected_login: int,
        expected_server: str,
        journal_path: Path,
        cost_policy: dict,
        execute: bool = False,
        notify: Callable[[dict], None] | None = None,
        health_notify: Callable[[dict], None] | None = None,
        alert_notify: Callable[[dict], None] | None = None,
        symbol: str = "XAUUSDm",
        strategy,
        account_guard_dir: Path | None = None,
    ):
        if expected_login <= 0 or not expected_server or symbol != "XAUUSDm":
            raise ValueError("explicit target Demo identity and XAUUSDm required")
        self.strategy = strategy
        self.mt5 = mt5
        self.login = expected_login
        self.server = expected_server
        self.symbol = symbol
        self.execute = execute
        self.policy = cost_policy
        self.notify = notify
        self.health_notify = health_notify
        self.alert_notify = alert_notify
        self.journal = Journal(journal_path)
        self.fingerprint = hashlib.sha256(
            f"{expected_server}:{expected_login}".encode()
        ).hexdigest()[:16]

        self.release_hash = hashlib.sha256(
            b"".join(
                path.read_bytes()
                for folder in ("demo_runtime", "c22h4", "trial30")
                for path in sorted((Path(__file__).parent.parent / folder).glob("*.py"))
            )
        ).hexdigest()
        self.journal.audit_context = dict(
            account_fingerprint=self.fingerprint,
            release_hash=self.release_hash,
            config_hash=hashlib.sha256(
                json.dumps(
                    getattr(strategy, "config", {"snapshot": strategy.snapshot}), sort_keys=True
                ).encode()
            ).hexdigest(),
        )
        self.cohort_id = self.release_hash + ":" + self.journal.audit_context["config_hash"]
        self.journal.audit_context["correlation_id"] = uuid.uuid4().hex

        # Same-account runners share a local single-writer guard, even with
        # separate strategy journals. SQLite guard is local to this host.
        try:
            recorded = self.journal.get("strategy_snapshot")
            active = self.journal.get("active")
            if recorded not in (None, self.strategy.snapshot) or (
                active and int(active["request"]["magic"]) != self.strategy.magic
            ):
                raise ValueError("journal_strategy_mismatch")
            self.account_guard = Journal(
                (account_guard_dir or journal_path.parent)
                / f"demo-account-{self.fingerprint}.sqlite3"
            )
            self.journal.put("strategy_snapshot", self.strategy.snapshot)
        except Exception:
            guard = getattr(self, "account_guard", None)
            if guard is not None:
                guard.close()
            self.journal.close()
            raise

        self.broker = BrokerView(
            mt5, expected_login, expected_server, symbol, self.fingerprint, self.journal
        )

        self._admission = Admission(self)
        self._lifecycle = Lifecycle(self)

    def close(self):
        self.journal.close()
        self.account_guard.close()

    def record_operational_failure(self, result, *, now, stage, error, code):
        """Supplemental evidence only; never mutate financial state or outbox.

        This boundary is for optional outputs after financial processing. A
        failure writing its diagnostics uses stderr; financial writes elsewhere
        keep their existing fail-closed/exception behavior.
        """
        record = failure_record(error, stage=stage, code=code, now=now,
            correlation_id=self.journal.audit_context.get("correlation_id"),
            details=getattr(error, "diagnostics", None))
        record["classification"] = "FAULT"
        result.setdefault("operational_errors", []).append(record)
        try:
            self.journal.audit("OPERATIONAL_FAILURE", diagnostic=record,
                               financial_status=result.get("status"))
            self.journal.put("last_result", result)
        except Exception as persistence_error:
            fallback(record, persistence_error=persistence_error)
        return record

    def cycle(self, *, now: datetime) -> dict:
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("cycle clock must be aware UTC")
        self._started = time.monotonic()
        self._cycle_send_attempted = False
        self.broker.position_count = None
        self.broker.last_equity = None
        self.broker.quote_diagnostics = {}
        self.broker.identity_diagnostics = {}
        self._baseline_diagnostics = {}
        self.journal.audit_context["correlation_id"] = uuid.uuid4().hex
        self._diagnostic_stage = "cycle.financial"
        try:
            result = self._cycle(now)
        except Exception as exc:
            result = {"status": "BLOCKED", "reason": public_reason(exc),
                "failure": failure_record(exc, stage=self._diagnostic_stage,
                    now=now, correlation_id=self.journal.audit_context["correlation_id"],
                    details=getattr(exc, "diagnostics", None))}
        if result.get("reason") in ("quote_stale", "quote_invalid", "quote_unknown", "quote_clock_invalid"):
            result.update(self.broker.quote_diagnostics)
        if result.get("reason") in (
            "demo_identity_required", "algo_permissions_required", "invalid_capital",
            "journal_account_mismatch",
        ) or self._diagnostic_stage in ("broker.identity", "broker.boundary"):
            # Preserve actual timing metadata on identity/capture failure.
            # This creates no mark and cannot supply a later/restart baseline.
            result.update(self.broker.identity_diagnostics)
        # Supplemental evidence from the initial account read/baseline check.
        # Later mutation identity checks may clear broker timing. A closed
        # lifecycle's exit-day validity still takes precedence over this cycle.
        for key, value in self._baseline_diagnostics.items():
            if key not in ("day_start_valid", "day_start_reason"):
                result.setdefault(key, value)
        if "day_start_valid" not in result:
            for key in ("day_start_valid", "day_start_reason"):
                if key in self._baseline_diagnostics:
                    result[key] = self._baseline_diagnostics[key]
        result.update(
            snapshot=self.strategy.snapshot, execute=self.execute, captured_utc=now.isoformat()
        )
        try:
            result.update(self.strategy.diagnostics())
        except Exception as exc:
            self.record_operational_failure(result, now=now, stage="strategy.diagnostics",
                error=exc, code="strategy_diagnostics_failed")
        self._diagnostic_stage = "journal.protection"
        active = self.journal.get("active")
        protected = result["status"] in ("FILLED", "MANAGING", "BE_MOVED", "SHADOW_BE")
        since = self.journal.get("protection_unknown_since")
        exposure = self.broker.position_count
        known_flat = active is None and exposure == 0
        owned_protected = bool(active and protected and exposure == 1)
        uncertain = not (known_flat or owned_protected)
        if uncertain:
            since = since or now.isoformat()
        else:
            since = None
        self.journal.put("protection_unknown_since", since)
        critical = bool(since and now - datetime.fromisoformat(since) >= timedelta(seconds=180))
        result.update(
            process_alive=True,
            entry_ready=result["status"] == "SHADOW_ADMIT",
            position_protection="unknown"
            if uncertain
            else "confirmed"
            if owned_protected
            else "flat",
            owned_position_protection="confirmed"
            if active and protected
            else "unknown"
            if active
            else "absent",
            observed_positions=exposure,
            critical=critical,
        )
        # Independent read-only review inspection explains blockers hidden by an
        # earlier quote/identity return. It neither grants entry nor stops an
        # owned position's already completed reconciliation/protection cycle.
        review = getattr(self._admission, "review", None)
        if review is not None:
            try:
                result["execution_review"] = review.inspect(self, now)
            except Exception as exc:
                result["execution_review"] = dict(status="BLOCKED",
                    code="review_inspection_unavailable", observational=True)
                self.record_operational_failure(result, now=now, stage="review.inspect",
                    error=exc, code="review_inspection_unavailable")
        try:
            result["entry_availability"] = entry_availability(
                result=result, now=now, review=result.get("execution_review"),
                cooldown_minutes=15 * self.strategy.cooldown_bars
                    if hasattr(self.strategy, "cooldown_bars") else None,
                values=dict(active=active, safety_halt=self.journal.get("safety_halt"),
                    selected_last_loss_ms=self.journal.get("selected_last_loss_ms"),
                    last_result=self.journal.get("last_result") or {}))
        except Exception as exc:
            result["entry_availability"] = dict(status="UNVERIFIED",
                coverage="KNOWN_BLOCKERS_ONLY", known_blockers=[],
                downstream_admission="NOT_PROVEN", requires_operator=True)
            self.record_operational_failure(result, now=now, stage="status.availability",
                error=exc, code="entry_availability_failed")
        self._diagnostic_stage = "journal.cycle"
        if critical and not self.journal.get("protection_alerted"):
            self.journal.event(
                dict(
                    kind="CRITICAL",
                    reason="position_unreconciled_180s",
                    captured_utc=now.isoformat(),
                    snapshot=self.strategy.snapshot,
                )
            )
            self.journal.put("protection_alerted", True)
        elif not critical:
            self.journal.put("protection_alerted", False)
        if result["status"] == "BLOCKED":
            block_key = now.date().isoformat() + "|" + str(result.get("reason"))
            if self.journal.get("last_alert_block") != block_key:
                self.journal.audit("BLOCKER", reason=result.get("reason"), result=result)
                self.journal.put("last_alert_block", block_key)
        self.journal.put("last_result", result)
        self.journal.audit("CYCLE", result=result, equity=getattr(self.broker, "last_equity", None))
        last_health = self.journal.get("last_health_event")
        if last_health is None or now - datetime.fromisoformat(last_health) >= timedelta(
            seconds=60
        ):
            self.journal.audit("HEALTH", result=result)
            self.journal.put("last_health_event", now.isoformat())
        if self.health_notify is not None:
            try:
                self.journal.consume(
                    "health_v1",
                    lambda event: self.health_notify(dict(event, result=result)),
                    kinds=("HEALTH",),
                    latest=True,
                )
            except Exception as exc:
                result["health_delivery"] = "pending_retry"
                self.record_operational_failure(result, now=now, stage="delivery.health",
                    error=exc, code="health_delivery_failed")
        if self.alert_notify is not None:
            try:
                self.journal.consume("alerts_v1", self.alert_notify, kinds=("BLOCKER",), limit=1)
            except Exception as exc:
                result["alerts"] = "pending_retry"
                self.record_operational_failure(result, now=now, stage="delivery.alert",
                    error=exc, code="alert_delivery_failed")
        try:
            self.journal.flush(self.notify)
        except Exception as exc:
            result["notification"] = "pending_retry"
            self.record_operational_failure(result, now=now, stage="delivery.lifecycle",
                error=exc, code="notification_failed")
        return result

    def _cycle(self, now):
        # A complete owned exit can be read even when trading is disabled.
        # Mutation checks retain strict identity at the send/modify/close boundary.
        active = self.journal.get("active")
        self._diagnostic_stage = "broker.identity"
        account = self.broker.identity(
            require_trade_permissions=self.execute and not active,
            observation_clock=lambda: self._send_clock(now),
        )
        self._baseline_diagnostics = {
            key: self.broker.identity_diagnostics[key]
            for key in ("account_read_request_started_utc", "account_read_observed_utc")
            if key in self.broker.identity_diagnostics
        }
        self._diagnostic_stage = "broker.boundary"
        try:
            observation = self.broker.account_observation
            if observation is not None:
                self.broker.capture_boundary(
                    observation["account"], request_started=observation["request_started"],
                    observed=observation["observed"],
                )
        except ValueError as exc:
            # Invalid entry-baseline evidence must not stop an owned close/BE
            # manager. Admission still validates proof before using it.
            self.journal.audit("BOUNDARY_CAPTURE_BLOCKED", reason=public_reason(exc),
                failure=failure_record(exc, stage=self._diagnostic_stage, now=now,
                    correlation_id=self.journal.audit_context.get("correlation_id")))
        self._diagnostic_stage = "broker.exposure"
        # Conservative observation time: a slow exposure/history/spec call must
        # not turn an earlier flat read into fresh installation permission.
        self._exposure_read_utc = self._send_clock(now) if getattr(self, "renewal_runtime", None) is not None else now
        positions, orders = self.broker._exposure()
        self._diagnostic_stage = "broker.history"
        deals = self.broker._history(now)
        if active:
            try:
                self.broker._baseline(account, positions, deals, now)
            except ValueError as exc:
                self._baseline_diagnostics.update(
                    day_start_valid=False, day_start_reason=public_reason(exc)
                )
            else:
                self._baseline_diagnostics["day_start_valid"] = True
            result = self._lifecycle.reconcile_closed(positions, deals)
            if result is not None:
                return result
            if self.execute:
                self._diagnostic_stage = "broker.identity"
                account = self.broker.identity()
        self._diagnostic_stage = "broker.spec"
        info = self.broker._spec()
        self.observe_broker_reads(account, positions, orders, deals, info, now)
        self._diagnostic_stage = "broker.quote"
        tick = self.broker._quote(self._send_clock(now))
        if active:
            # Source/cache warmup gates apply only to admission. Reconcile on restart
            # even if detector/history bootstrap fails; retain last BE bar then.
            active = self.journal.get("active")
            closed = datetime.fromisoformat(active["last_be_bar"])
            try:
                bars = completed_m15_from_m1(
                    self.mt5.copy_rates_from_pos(self.symbol, self.mt5.TIMEFRAME_M1, 0, 5000),
                    now=now,
                )
                closed = bars.index[-1].to_pydatetime() + timedelta(minutes=15)
            except ValueError:
                pass
            self._diagnostic_stage = "lifecycle.reconcile"
            return self._reconcile(positions, deals, tick, info, closed, now)
        self._diagnostic_stage = "market.completed_m15"
        bars = completed_m15_from_m1(
            self.mt5.copy_rates_from_pos(self.symbol, self.mt5.TIMEFRAME_M1, 0, 5000), now=now
        )
        self._diagnostic_stage = "admission.check"
        return self._admission.admit(account, positions, orders, deals, info, tick, bars, now)

    def send(self, request, now):
        """Persistence failure blocks mutation; ambiguous responses remain pending."""
        request_id = uuid.uuid4().hex
        started = time.monotonic()
        self.journal.audit(
            "REQUEST", request=request, request_id=request_id, expected=self.journal.get("active")
        )
        self.broker.identity()
        self._cycle_send_attempted = True
        try:
            response = self.mt5.order_send(request)
        except Exception as exc:
            self.journal.audit(
                "RESPONSE",
                request=request,
                response=None,
                reason=type(exc).__name__,
                failure=failure_record(exc, stage="broker.order_send", code="order_send_exception",
                    now=now, correlation_id=self.journal.audit_context.get("correlation_id")),
                request_id=request_id,
                elapsed_ms=(time.monotonic() - started) * 1000,
            )
            return None
        self.journal.audit(
            "RESPONSE",
            request=request,
            response=response,
            request_id=request_id,
            elapsed_ms=(time.monotonic() - started) * 1000,
        )
        return response

    def _send_clock(self, now):
        return now + timedelta(seconds=time.monotonic() - self._started)

    def observe_broker_reads(self, account, positions, orders, deals, info, now):
        """Optional adapter observation of existing reads; no extra broker call."""

    def _daily_losses(self, deals, now):
        return self._admission._daily_losses(deals, now)

    def _first_quote(self, closed, now):
        return self._admission._first_quote(closed, now)

    def _reconcile(self, positions, deals, tick, info, closed, now):
        return self._lifecycle._reconcile(positions, deals, tick, info, closed, now)

    def _record_closed(self, active, ledger, ident, *, safety_reason=None):
        return self._lifecycle._record_closed(active, ledger, ident, safety_reason=safety_reason)

    def _safety_close(self, position, active, info, now, reason):
        return self._lifecycle._safety_close(position, active, info, now, reason)
