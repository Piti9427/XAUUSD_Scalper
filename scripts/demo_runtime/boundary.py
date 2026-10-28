"""Persist actual account equity observed inside the existing UTC boundary window."""
from __future__ import annotations

from datetime import datetime, timedelta
import math

SOURCE = "verified_account_info_at_utc_boundary_v1"


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("boundary clock must be aware UTC")
    return value


def _positive(value):
    try:
        return not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _inside_window(started, observed):
    midnight = started.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight <= started <= observed < midnight + timedelta(seconds=1)


def read_mark(journal, *, fingerprint, day):
    """Return a same-day proof; reject malformed evidence rather than renewing it."""
    mark = journal.get("utc_boundary_mark")
    if mark is None:
        return None
    try:
        started = _utc(datetime.fromisoformat(mark["request_started_utc"]))
        observed = _utc(datetime.fromisoformat(mark["observed_utc"]))
        valid = (
            type(mark["version"]) is int and mark["version"] == 1
            and mark["source"] == SOURCE
            and mark["account_fingerprint"] == fingerprint
            and mark["day"] == started.date().isoformat()
            and _inside_window(started, observed)
            and _positive(mark["equity"]) and _positive(mark["balance"])
        )
    except (KeyError, TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        raise ValueError("invalid_boundary_mark")
    return mark if mark["day"] == day else None


def capture(journal, account, *, fingerprint, request_started, observed):
    """Caller verifies Demo identity; start and response must both be inside1second."""
    started, observed = _utc(request_started), _utc(observed)
    if not _inside_window(started, observed):
        return False
    if not all(_positive(getattr(account, key, None)) for key in ("balance", "equity")):
        return False
    day = started.date().isoformat()
    if read_mark(journal, fingerprint=fingerprint, day=day) is not None:
        return False
    journal.put("utc_boundary_mark", dict(
        version=1, source=SOURCE, day=day, account_fingerprint=fingerprint,
        request_started_utc=started.isoformat(), observed_utc=observed.isoformat(),
        balance=float(account.balance), equity=float(account.equity),
    ))
    return True


def poll_delay(poll, now):
    """Align a normal poll to just after UTC midnight without a second SDK reader."""
    now = _utc(now)
    if not _positive(poll):
        raise ValueError("positive poll required")
    boundary = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return min(float(poll), (boundary-now).total_seconds() + 0.01)
