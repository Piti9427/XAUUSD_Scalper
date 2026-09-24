"""Executable quote-side helpers for foundation replay/Demo."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Union


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


def pending_sl_touched_before_fill(
    *,
    direction: str,
    limit_price: float,
    sl_price: float,
    bar_high: float,
    bar_low: float,
) -> bool:
    """
    S1–S4 / experiment: SL reached while pending → end pending (no fill).

    OCO-style: a bar that pierces the planned SL cancels the limit instead of
    inventing a fill-then-stop path. For valid BUY geometry (sl < limit),
    touching SL implies the limit was also in range; cancel still wins.
    """
    d = direction.upper()
    if d == "BUY":
        return float(bar_low) <= float(sl_price)
    if d == "SELL":
        return float(bar_high) >= float(sl_price)
    return False


def disclose_missing_quote_for_pending_sl(
    *,
    pending_order_ids: Sequence[str],
    have_ohlc: bool,
    have_live_quotes: bool,
) -> List[Dict[str, Any]]:
    """
    B15 / S1–S4: missing quote at SL-before-fill check → disclose, never invent OHLC.

    When unfilled pendings exist and neither clock OHLC nor live bid/ask is
    available, return one disclosure row per order_id. Empty when quotes exist
    or there is nothing pending to evaluate.
    """
    if have_ohlc or have_live_quotes:
        return []
    rows: List[Dict[str, Any]] = []
    for oid in pending_order_ids:
        if not oid:
            continue
        rows.append(
            {
                "order_id": str(oid),
                "status": "disclosed",
                "reason": "missing_quote",
                "context": "sl_before_fill_check",
            }
        )
    return rows


def disclose_missing_quote_at_exit_deadline(
    *,
    open_order_ids: Sequence[str],
    have_live_quotes: bool,
) -> List[Dict[str, Any]]:
    """
    S1–S4 / experiment: session flat or TIME_EXIT with missing quote → disclose.

    Does not invent an executable exit price. Callers still may request broker
    CLOSE_MARKET; PnL must wait for broker deal evidence.
    """
    if have_live_quotes:
        return []
    rows: List[Dict[str, Any]] = []
    for oid in open_order_ids:
        if not oid:
            continue
        rows.append(
            {
                "order_id": str(oid),
                "status": "disclosed",
                "reason": "missing_quote",
                "context": "session_flat_exit",
            }
        )
    return rows


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
