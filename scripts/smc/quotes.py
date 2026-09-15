"""Executable quote-side helpers for foundation replay/Demo."""

from __future__ import annotations

from typing import Optional


def executable_price(
    *,
    direction: str,
    bid: Optional[float],
    ask: Optional[float],
    mid: Optional[float] = None,
) -> tuple[Optional[float], str]:
    """
    Return the executable side for a marketable action.

    BUY uses ask; SELL uses bid. Missing sides do not invent a favorable fill.
    """
    d = direction.upper()
    if d == "BUY":
        if ask is not None:
            return float(ask), "ask"
        return None, "missing_ask"
    if d == "SELL":
        if bid is not None:
            return float(bid), "bid"
        return None, "missing_bid"
    if mid is not None:
        return float(mid), "mid_fallback_unknown_side"
    return None, "unknown_direction"


def ohlc_dual_touch_flag(*, sl_touched: bool, tp_touched: bool, has_tick_order: bool) -> str:
    if sl_touched and tp_touched and not has_tick_order:
        return "AMBIGUOUS"
    if sl_touched:
        return "SL"
    if tp_touched:
        return "TP"
    return "NONE"
