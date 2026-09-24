"""Frozen development / holdout window labels for Gate D (foundation proposal).

Does not invent PASS criteria. Mixing windows in one sample is forbidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional, Union


# Foundation proposal: 2025-09-01 inclusive through day before 2026-09-01.
# Development = first 9 calendar months; holdout = final 3 months.
FOUNDATION_DATASET_START = date(2025, 9, 1)
FOUNDATION_DATASET_END_EXCLUSIVE = date(2026, 9, 1)
FOUNDATION_HOLDOUT_START = date(2026, 6, 1)


TimeLike = Union[date, datetime]


def _as_utc_date(value: TimeLike) -> date:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.date()
    return value


@dataclass(frozen=True)
class WindowLabel:
    name: str  # "development" | "holdout" | "out_of_range" | "invalid_range"
    ok_for_tuning: bool
    ok_for_holdout_eval: bool
    detail: str


def label_foundation_window(ts: TimeLike) -> WindowLabel:
    """
    Label a bar/event timestamp against the proposed foundation dataset windows.

    Holdout must not be used for rule selection. Out-of-range is not silently
    treated as development.
    """
    d = _as_utc_date(ts)
    if d < FOUNDATION_DATASET_START or d >= FOUNDATION_DATASET_END_EXCLUSIVE:
        return WindowLabel(
            name="out_of_range",
            ok_for_tuning=False,
            ok_for_holdout_eval=False,
            detail=f"{d.isoformat()} outside [{FOUNDATION_DATASET_START},{FOUNDATION_DATASET_END_EXCLUSIVE})",
        )
    if d >= FOUNDATION_HOLDOUT_START:
        return WindowLabel(
            name="holdout",
            ok_for_tuning=False,
            ok_for_holdout_eval=True,
            detail="holdout window — no tuning / no merge with development sample",
        )
    return WindowLabel(
        name="development",
        ok_for_tuning=True,
        ok_for_holdout_eval=False,
        detail="development window — may select rules before holdout freeze",
    )


def samples_may_merge(
    *,
    left_window: str,
    right_window: str,
) -> tuple[bool, str]:
    """Refuse merging development with holdout into one Gate D sample."""
    if left_window != right_window:
        return False, f"refuse_merge:{left_window}+{right_window}"
    if left_window not in {"development", "holdout"}:
        return False, f"refuse_merge_unknown:{left_window}"
    return True, "ok"


def assert_single_window_or_reason(
    timestamps: list[TimeLike],
) -> tuple[Optional[str], str]:
    """
    Return (window_name, reason). Mixed windows → (None, refuse reason).
    Empty → (None, empty_sample).
    """
    if not timestamps:
        return None, "empty_sample"
    labels = {label_foundation_window(ts).name for ts in timestamps}
    if len(labels) != 1:
        return None, "refuse_merge:" + "+".join(sorted(labels))
    name = next(iter(labels))
    if name == "out_of_range":
        return None, "out_of_range_only"
    return name, "ok"
