"""Fibonacci research features for foundation BaselinePlay (log only; no filter)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


OTE_LOW = 0.62
OTE_HIGH = 0.79


@dataclass(frozen=True)
class FibonacciFeatures:
    swing_high: float
    swing_low: float
    entry: float
    retracement: Optional[float]
    in_ote: bool
    available: bool
    reason: str


def compute_fibonacci_features(
    *,
    direction: str,
    swing_high: float,
    swing_low: float,
    entry: float,
) -> FibonacciFeatures:
    """
    Record Fib retracement of entry within the decision-time swing range.

    Does not admit/reject trades. Zero-width or inverted ranges are unavailable.
    """
    width = swing_high - swing_low
    if width <= 0:
        return FibonacciFeatures(
            swing_high=swing_high,
            swing_low=swing_low,
            entry=entry,
            retracement=None,
            in_ote=False,
            available=False,
            reason="zero_or_inverted_swing_range",
        )

    if direction.upper() == "BUY":
        # 0 at high, 1 at low for bullish pullback into discount
        retracement = (swing_high - entry) / width
    else:
        retracement = (entry - swing_low) / width

    in_ote = OTE_LOW <= retracement <= OTE_HIGH
    return FibonacciFeatures(
        swing_high=swing_high,
        swing_low=swing_low,
        entry=entry,
        retracement=round(retracement, 6),
        in_ote=in_ote,
        available=True,
        reason="ok",
    )
