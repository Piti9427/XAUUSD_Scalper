"""Executable quote-side helpers for foundation replay/Demo."""

from __future__ import annotations

from typing import Iterable, Optional, Sequence, Union


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


def ohlc_dual_touch_flag(
    *,
    sl_touched: bool,
    tp_touched: bool,
    has_tick_order: bool,
    tick_first_exit: Optional[str] = None,
) -> str:
    if sl_touched and tp_touched and not has_tick_order:
        return "AMBIGUOUS"
    if sl_touched and tp_touched and has_tick_order:
        if tick_first_exit in ("SL", "TP"):
            return tick_first_exit
        # Tick order claimed but first-exit missing → still ambiguous.
        return "AMBIGUOUS"
    if sl_touched:
        return "SL"
    if tp_touched:
        return "TP"
    return "NONE"


TickPrice = Union[float, Sequence[float]]


def first_exit_from_ticks(
    *,
    direction: str,
    sl_price: float,
    tp_price: float,
    ticks: Iterable[TickPrice],
) -> str:
    """
    Walk ordered ticks and return which protective level is hit first.

    Each tick may be a mid float or an (bid, ask) pair. BUY exits use bid;
    SELL exits use ask (marketable close side). Missing sides skip the tick.
    """
    d = direction.upper()
    for tick in ticks:
        bid: Optional[float]
        ask: Optional[float]
        if isinstance(tick, (int, float)):
            bid = ask = float(tick)
        else:
            if len(tick) < 2:
                continue
            bid = float(tick[0]) if tick[0] is not None else None
            ask = float(tick[1]) if tick[1] is not None else None

        if d == "BUY":
            if bid is None:
                continue
            if bid <= sl_price:
                return "SL"
            if bid >= tp_price:
                return "TP"
        elif d == "SELL":
            if ask is None:
                continue
            if ask >= sl_price:
                return "SL"
            if ask <= tp_price:
                return "TP"
        else:
            return "NONE"
    return "NONE"
