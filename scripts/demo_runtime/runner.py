"""Shared Demo orchestration; strategy injected by C22 or rollback adapter."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import time
from pathlib import Path
from typing import Any, Callable

from scripts.pure_b1.broker_data import completed_m15_from_m1
from scripts.demo_runtime.journal import Journal
from scripts.demo_runtime.broker import BrokerView

from scripts.demo_runtime.admission import Admission
from scripts.demo_runtime.lifecycle import Lifecycle


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
        self.journal = Journal(journal_path)
        self.fingerprint = hashlib.sha256(
            f"{expected_server}:{expected_login}".encode()
        ).hexdigest()[:16]

        # Same-account runners share a local single-writer guard, even with
        # separate strategy journals. Journal implementation stays unchanged.
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

    def cycle(self, *, now: datetime) -> dict:
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("cycle clock must be aware UTC")
        self._started = time.monotonic()
        try:
            result = self._cycle(now)
        except ValueError as exc:
            result = {"status": "BLOCKED", "reason": str(exc)}
        except Exception as exc:
            result = {"status": "BLOCKED", "reason": type(exc).__name__}
        result.update(
            snapshot=self.strategy.snapshot, execute=self.execute, captured_utc=now.isoformat()
        )
        result.update(self.strategy.diagnostics())
        self.journal.put("last_result", result)
        try:
            self.journal.flush(self.notify)
        except Exception:
            result["notification"] = "pending_retry"
        return result

    def _cycle(self, now):
        account = self.broker.identity()
        positions, orders = self.broker._exposure()
        deals = self.broker._history(now)
        info = self.broker._spec()
        tick = self.broker._quote(now)
        if self.journal.get("active"):
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
            try:
                self.broker._baseline(account, positions, deals, now)
            except ValueError:
                pass
            return self._reconcile(positions, deals, tick, info, closed, now)
        bars = completed_m15_from_m1(
            self.mt5.copy_rates_from_pos(self.symbol, self.mt5.TIMEFRAME_M1, 0, 5000), now=now
        )
        return self._admission.admit(account, positions, orders, deals, info, tick, bars, now)

    def _send_clock(self, now):
        return now + timedelta(seconds=time.monotonic() - self._started)

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
