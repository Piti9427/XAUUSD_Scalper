"""Notification admission for execution outcomes (foundation scenario 20)."""

from __future__ import annotations

from typing import Optional


# Statuses that may produce a user-visible trade card.
NOTIFY_OK_STATUSES = frozenset({"OK", "ACCEPTED", "FILLED"})


def may_notify_execution(
    *,
    success: bool,
    status: Optional[str] = None,
) -> bool:
    """
    Rejected/UNKNOWN intents must not emit phantom trade notifications.

    Accepted/fill cards are separate call sites; this only answers "may we notify".
    """
    if not success:
        return False
    normalized = (status or "OK").upper()
    if normalized in {"REJECTED", "UNKNOWN", "UNCERTAIN"}:
        return False
    return normalized in NOTIFY_OK_STATUSES


def classify_exec_outcome(*, success: bool, status: Optional[str] = None) -> str:
    """Map adapter result to bridge response: success | rejected | uncertain."""
    normalized = (status or ("OK" if success else "REJECTED")).upper()
    if normalized == "UNKNOWN":
        return "uncertain"
    if success and normalized in NOTIFY_OK_STATUSES:
        return "success"
    if not success or normalized == "REJECTED":
        return "rejected"
    return "uncertain"


def may_notify_close(
    *,
    broker_close_success: bool,
    already_flat_on_broker: bool = False,
) -> bool:
    """
    Scenario 19: never announce TRADE CLOSED without broker evidence.

    already_flat_on_broker covers 'position not found' after a successful broker flat.
    """
    return bool(broker_close_success or already_flat_on_broker)
