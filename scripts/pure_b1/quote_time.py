"""One quote-time rule for Shadow admission and labeled Pure B1 replay.

The fresh rule accepts the first quote at or after bar close when that quote is
not after the decision clock, is at most 60 seconds old, and is at most 90
seconds after bar close. Exact 60s and exact 90s are inside the window.

The archival rule reproduces the previous replay window: the first tick is
rejected when it is 900 seconds or later. It is a labeled historical scenario,
not the Shadow rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np


@dataclass(frozen=True)
class QuoteRule:
    name: str
    max_age_seconds: float | None
    max_lateness_seconds: float
    reject_lateness_at_limit: bool


FRESH_QUOTE = QuoteRule(
    name="first_fresh_quote_age_60s_lateness_90s",
    max_age_seconds=60,
    max_lateness_seconds=90,
    reject_lateness_at_limit=False,
)
ARCHIVAL_QUOTE = QuoteRule(
    name="archival_first_tick_within_900s",
    max_age_seconds=None,
    max_lateness_seconds=900,
    reject_lateness_at_limit=True,
)


def _utc(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == timedelta(0)


def classify_quote(
    *,
    bar_close: datetime,
    quote_time: datetime,
    now: datetime,
    rule: QuoteRule = FRESH_QUOTE,
) -> str | None:
    """Return None when the quote is accepted, otherwise invalid_quote or stale_quote."""
    if not _utc(bar_close) or not _utc(quote_time) or not _utc(now):
        return "invalid_quote"
    if quote_time < bar_close or quote_time > now:
        return "invalid_quote"
    lateness = (quote_time - bar_close).total_seconds()
    if rule.reject_lateness_at_limit:
        late = lateness >= rule.max_lateness_seconds
    else:
        late = lateness > rule.max_lateness_seconds
    aged = (
        rule.max_age_seconds is not None
        and (now - quote_time).total_seconds() > rule.max_age_seconds
    )
    if late or aged:
        return "stale_quote"
    return None


def first_tick(times, bar_close_ms: int, rule: QuoteRule) -> tuple[int | None, str]:
    """Return the first tick index accepted by `rule`, or a fail-closed reason.

    Replay observes the tick at its own timestamp, so quote age is zero and the
    lateness limit is the binding constraint. No fill is invented when the tick
    is missing or late.
    """
    index = int(np.searchsorted(times, bar_close_ms, side="left"))
    if index >= len(times):
        return None, "missing_quote"
    delta_ms = int(times[index]) - int(bar_close_ms)
    if delta_ms < 0:
        return None, "quote_before_close"
    limit_ms = int(round(rule.max_lateness_seconds * 1000))
    if rule.reject_lateness_at_limit:
        late = delta_ms >= limit_ms
    else:
        late = delta_ms > limit_ms
    if late:
        return None, "late_quote"
    return index, "accepted"
