"""Frozen statistical protocol helpers (foundation scenario 23).

These fixtures are deterministic. Do not retune thresholds after seeing outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Literal


Side = Literal["one_sided", "two_sided"]


@dataclass(frozen=True)
class WilsonInterval:
    n: int
    wins: int
    z: float
    side: Side
    lower: float
    upper: float
    note: str


# Frozen before evaluation — do not change after seeing live results.
DEFAULT_Z_95 = 1.959963984540054


def wilson_interval(
    *,
    wins: int,
    n: int,
    z: float = DEFAULT_Z_95,
    side: Side = "two_sided",
) -> WilsonInterval:
    """Wilson score interval for binomial win-rate under IID assumption."""
    if n <= 0:
        return WilsonInterval(0, 0, z, side, 0.0, 1.0, "empty_sample_INCONCLUSIVE")
    if wins < 0 or wins > n:
        raise ValueError("wins must be in [0, n]")
    p = wins / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    half = (z * sqrt((p * (1.0 - p) / n) + (z * z) / (4.0 * n * n))) / denom
    lower = max(0.0, center - half)
    upper = min(1.0, center + half)
    if side == "one_sided":
        # Lower bound only; upper reported as 1.0 for transparency.
        return WilsonInterval(n, wins, z, side, round(lower, 6), 1.0, "one_sided_lower_bound")
    return WilsonInterval(n, wins, z, side, round(lower, 6), round(upper, 6), "two_sided")


def sample_verdict(*, n: int, min_trades: int = 100) -> str:
    """Few trades stay INCONCLUSIVE — never retune rules to invent PASS."""
    if n < min_trades:
        return "INCONCLUSIVE"
    return "EVALUABLE"
