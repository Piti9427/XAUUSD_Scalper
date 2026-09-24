"""Locked warmup / seed conventions for replay vs Demo parity."""

from __future__ import annotations

from typing import Sequence

# Foundation proposal locked until a measured coverage review changes it.
H1_WARMUP_BARS = 1000
M5_WARMUP_BARS = 500


def warmup_coverage_ok(
    bar_count: int,
    *,
    required: int,
) -> bool:
    """True when history length meets the locked warmup floor."""
    return int(bar_count) >= int(required)


def assert_warmup_coverage(
    bars: Sequence,
    *,
    required: int,
    label: str = "bars",
) -> None:
    if not warmup_coverage_ok(len(bars), required=required):
        raise ValueError(f"{label} warmup insufficient: have={len(bars)} need>={required}")


def h1_warmup_ok(h1_bar_count: int) -> bool:
    return warmup_coverage_ok(h1_bar_count, required=H1_WARMUP_BARS)


def recommended_h1_request_count(extra: int = 0) -> int:
    """Bars to request from broker/export including locked warmup."""
    return H1_WARMUP_BARS + max(0, int(extra))
