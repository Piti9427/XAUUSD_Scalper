"""Wall-clock TIME_EXIT planning when the bar feed stalls (foundation scenario 19)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class OpenFill:
    order_id: str
    open_time: datetime
    direction: Optional[str] = None


@dataclass(frozen=True)
class ClockExitPlan:
    order_id: str
    reason: str
    direction: Optional[str] = None


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def plan_clock_time_exits(
    fills: Iterable[OpenFill],
    *,
    now: datetime,
    max_hold_bars: int,
    bar_minutes: int = 5,
) -> List[ClockExitPlan]:
    """
    Emit TIME_EXIT close plans for fills held past max_hold without requiring a new bar.

    Pure planner — callers must execute CLOSE_MARKET and wait for broker evidence
    before notifying TRADE CLOSED.
    """
    if max_hold_bars <= 0:
        return []
    now_utc = _as_utc(now)
    max_hold = timedelta(minutes=max_hold_bars * bar_minutes)
    plans: List[ClockExitPlan] = []
    for fill in fills:
        open_time = _as_utc(fill.open_time)
        if now_utc - open_time < max_hold:
            continue
        plans.append(
            ClockExitPlan(
                order_id=fill.order_id,
                direction=fill.direction,
                reason=(
                    f"TIME_EXIT wall-clock after {max_hold_bars}*{bar_minutes}m "
                    f"without requiring a new bar"
                ),
            )
        )
    return plans
