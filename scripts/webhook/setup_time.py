"""Parse TradingView / webhook setup timestamps as timezone-aware UTC."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def parse_setup_event_time(
    event_time_raw: Any,
    *,
    fallback_now: Optional[datetime] = None,
) -> datetime:
    """
    Normalize payload time to aware UTC.

    Accepts ISO strings, epoch seconds, or epoch milliseconds. Invalid / missing
    values fall back to ``fallback_now`` or ``datetime.now(timezone.utc)``.
    """
    now = fallback_now if fallback_now is not None else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    if event_time_raw is None:
        return now
    try:
        if isinstance(event_time_raw, (int, float)):
            if event_time_raw > 1e11:
                return datetime.fromtimestamp(event_time_raw / 1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(float(event_time_raw), tz=timezone.utc)
        raw = str(event_time_raw).replace(" ", "T")
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return now
