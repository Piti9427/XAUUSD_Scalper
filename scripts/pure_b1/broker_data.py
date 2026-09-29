"""Validate MT5 completed M15 Bid bars for the shared Pure B1 detector."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from scripts.smc.broker_rates import drop_forming_bars, rates_to_frame


def completed_m15(rates, *, now: datetime) -> pd.DataFrame:
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("now must be timezone-aware UTC")
    raw = pd.DataFrame(rates)
    if raw.empty or "time" not in raw:
        raise ValueError("missing M15 bars")
    timestamps = pd.to_datetime(raw["time"], unit="s", utc=True)
    if timestamps.duplicated().any():
        raise ValueError("duplicate M15 bar")
    if not timestamps.is_monotonic_increasing:
        raise ValueError("unordered M15 bars")
    frame = rates_to_frame(rates)
    if frame is None:
        raise ValueError("invalid M15 bars")
    closed = drop_forming_bars(frame, now=now, bar_minutes=15)
    if closed.empty:
        raise ValueError("no completed M15 bars")
    bars = closed.set_index("time")[["open", "high", "low", "close"]]
    if bars.index.tz is None or bars.index.has_duplicates:
        raise ValueError("invalid M15 UTC index")
    if (bars.index.as_unit("ns").asi8 % (900 * 10**9)).any():
        raise ValueError("misaligned M15 bars")
    return bars


def completed_m15_from_m1(rates, *, now: datetime) -> pd.DataFrame:
    """Match archived reference: keep only M15 intervals with all 15 Bid M1 bars."""
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("now must be timezone-aware UTC")
    raw = pd.DataFrame(rates)
    if raw.empty or "time" not in raw:
        raise ValueError("missing M1 bars")
    timestamps = pd.to_datetime(raw["time"], unit="s", utc=True)
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise ValueError("duplicate or unordered M1 bars")
    if (timestamps.dt.as_unit("ns").astype("int64") % (60 * 10**9)).any():
        raise ValueError("misaligned M1 bars")
    frame = rates_to_frame(rates)
    closed = drop_forming_bars(frame, now=now, bar_minutes=1)
    if closed.empty:
        raise ValueError("no completed M1 bars")
    minute_bars = closed.set_index("time")
    grouped = minute_bars.resample("15min", label="left", closed="left")
    result = grouped.agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    counts = grouped.close.count()
    result = result.loc[counts == 15].dropna()
    result = result[result.index + pd.Timedelta(minutes=15) <= now]
    if result.empty:
        raise ValueError("no complete M15 bars from M1")
    return result
