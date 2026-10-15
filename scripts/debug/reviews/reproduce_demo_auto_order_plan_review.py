#!/usr/bin/env python3
"""Deterministic review checks for demo auto-order remediation plan."""

from pathlib import Path


PLAN = Path("docs/archive/plans/2026-09-15-demo-auto-order-remediation-plan.md")


def main() -> int:
    text = PLAN.read_text(encoding="utf-8")
    checks = {
        "durable_lifecycle_worker": all(
            marker in text
            for marker in (
                "BrokerLifecycleWorker",
                "startup reconciliation",
                "durable outbox",
                "TP1_DONE",
            )
        ),
        "cancellation_owner": all(
            marker in text
            for marker in (
                "SETUP_CANCEL_REQUESTED",
                "Pine owns confirmed strategy setup detection and structural invalidation",
            )
        ),
        "identifier_contract": all(
            marker in text for marker in ("event_id", "setup_id", "broker_ref", "MT5 ticket")
        ),
        "runtime_execution_policy": all(
            marker in text
            for marker in ("ExecutionPolicy", "expected account fingerprint", "maximum tick age")
        ),
        "runtime_calendar_contract": all(
            marker in text
            for marker in (
                "runtime JSON calendar artifact",
                "coverage_start_utc",
                "coverage_end_utc",
            )
        ),
        "staged_validation": all(
            marker in text
            for marker in ("Offline contract", "Read-only broker policy", "Demo canary")
        ),
    }
    print(checks)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
