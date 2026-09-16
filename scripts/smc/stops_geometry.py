"""Broker stops/freeze geometry checks before pending placement (scenario 10)."""

from __future__ import annotations

import math
from typing import Optional, Tuple


def min_stop_distance_price(*, point: float, stops_level: float) -> float:
    """Convert MT5 stops_level (points) into absolute price distance."""
    if not math.isfinite(point) or point <= 0:
        return float("nan")
    if not math.isfinite(stops_level) or stops_level < 0:
        return float("nan")
    return float(stops_level) * float(point)


def pending_stops_geometry_allows(
    *,
    entry_price: float,
    sl_price: float,
    tp_price: Optional[float],
    point: float,
    stops_level: float,
) -> Tuple[bool, str]:
    """
    Fail closed when SL/TP distances violate broker stops_level.

    Does not invent a freeze policy beyond requiring known, finite metadata.
    Missing/invalid point or stops_level blocks new risk.
    """
    for name, value in (
        ("entry_price", entry_price),
        ("sl_price", sl_price),
        ("point", point),
        ("stops_level", stops_level),
    ):
        if value is None or not math.isfinite(float(value)):
            return False, f"invalid_{name}"

    point = float(point)
    stops_level = float(stops_level)
    if point <= 0:
        return False, "invalid_point"
    if stops_level < 0:
        return False, "invalid_stops_level"

    min_dist = min_stop_distance_price(point=point, stops_level=stops_level)
    if not math.isfinite(min_dist):
        return False, "invalid_min_stop_distance"

    entry = float(entry_price)
    sl = float(sl_price)
    sl_dist = abs(entry - sl)
    if sl_dist <= 0:
        return False, "entry_sl_identical"
    if sl_dist + 1e-12 < min_dist:
        return False, f"sl_inside_stops_level:{sl_dist:.5f}<{min_dist:.5f}"

    if tp_price is not None:
        if not math.isfinite(float(tp_price)):
            return False, "invalid_tp_price"
        tp = float(tp_price)
        tp_dist = abs(entry - tp)
        if tp_dist <= 0:
            return False, "entry_tp_identical"
        if tp_dist + 1e-12 < min_dist:
            return False, f"tp_inside_stops_level:{tp_dist:.5f}<{min_dist:.5f}"

    return True, "ok"


def sl_modify_freeze_allows(
    *,
    new_sl: float,
    market_bid: Optional[float],
    market_ask: Optional[float],
    point: float,
    freeze_level: float,
) -> Tuple[bool, str]:
    """
    Fail closed when market is inside freeze distance of the new SL.

    Uses the nearer executable side available; missing both quotes blocks.
    freeze_level=0 means no freeze constraint beyond known metadata.
    """
    if new_sl is None or not math.isfinite(float(new_sl)):
        return False, "invalid_new_sl"
    if point is None or not math.isfinite(float(point)) or float(point) <= 0:
        return False, "invalid_point"
    if freeze_level is None or not math.isfinite(float(freeze_level)) or float(freeze_level) < 0:
        return False, "invalid_freeze_level"

    quotes = [q for q in (market_bid, market_ask) if q is not None and math.isfinite(float(q))]
    if not quotes:
        return False, "missing_market_quote"

    min_dist = float(freeze_level) * float(point)
    nearest = min(abs(float(new_sl) - float(q)) for q in quotes)
    if nearest + 1e-12 < min_dist:
        return False, f"sl_inside_freeze_level:{nearest:.5f}<{min_dist:.5f}"
    return True, "ok"
