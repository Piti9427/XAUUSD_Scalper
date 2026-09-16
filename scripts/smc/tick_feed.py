"""Attach ordered ticks to OHLC bars for foundation replay."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd

from scripts.smc.quotes import first_exit_from_ticks


def load_tick_frame(path: str) -> pd.DataFrame:
    """
    Load tick CSV with columns: time, bid, ask (mid optional).

    time must be UTC-parseable. Rows missing both bid and ask are dropped.
    """
    df = pd.read_csv(path)
    required = {"time"}
    if not required.issubset(df.columns):
        raise ValueError("tick CSV requires a time column")
    if "bid" not in df.columns and "ask" not in df.columns and "mid" not in df.columns:
        raise ValueError("tick CSV requires bid/ask or mid")
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    if "bid" not in df.columns:
        df["bid"] = df.get("mid")
    if "ask" not in df.columns:
        df["ask"] = df.get("mid")
    df = df.dropna(subset=["time"])
    df = df[df["bid"].notna() | df["ask"].notna()]
    return df.sort_values("time").reset_index(drop=True)


def ticks_for_bar(
    ticks: pd.DataFrame,
    *,
    bar_open: datetime,
    bar_close: datetime,
) -> List[tuple[Optional[float], Optional[float]]]:
    """Return ordered (bid, ask) pairs whose time is in [bar_open, bar_close)."""
    if bar_open.tzinfo is None:
        bar_open = bar_open.replace(tzinfo=timezone.utc)
    else:
        bar_open = bar_open.astimezone(timezone.utc)
    if bar_close.tzinfo is None:
        bar_close = bar_close.replace(tzinfo=timezone.utc)
    else:
        bar_close = bar_close.astimezone(timezone.utc)

    mask = (ticks["time"] >= bar_open) & (ticks["time"] < bar_close)
    out: List[tuple[Optional[float], Optional[float]]] = []
    for _, row in ticks.loc[mask].iterrows():
        bid = None if pd.isna(row.get("bid")) else float(row["bid"])
        ask = None if pd.isna(row.get("ask")) else float(row["ask"])
        out.append((bid, ask))
    return out


def annotate_bar_with_ticks(
    bar: Dict[str, Any],
    ticks: Sequence[tuple[Optional[float], Optional[float]]],
    *,
    direction: Optional[str] = None,
    sl_price: Optional[float] = None,
    tp_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Copy bar and attach tick order evidence when ticks exist.

    When direction/SL/TP provided, also precompute tick_first_exit.
    """
    out = dict(bar)
    if not ticks:
        out["has_tick_order"] = False
        out.pop("ticks", None)
        out.pop("tick_first_exit", None)
        return out
    out["has_tick_order"] = True
    out["ticks"] = list(ticks)
    if direction is not None and sl_price is not None and tp_price is not None:
        out["tick_first_exit"] = first_exit_from_ticks(
            direction=direction,
            sl_price=float(sl_price),
            tp_price=float(tp_price),
            ticks=ticks,
        )
    return out
