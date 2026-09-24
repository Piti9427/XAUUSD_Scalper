"""Broker OHLC helpers: forming-bar drop and clock skew check (ADR-022)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def drop_forming_bars(
    df: pd.DataFrame,
    *,
    now: datetime,
    bar_minutes: int = 5,
) -> pd.DataFrame:
    """Drop the in-progress bar whose close time is still in the future."""
    if df.empty:
        return df.copy()
    now_utc = _as_utc(now)
    bar_delta = timedelta(minutes=bar_minutes)
    times = pd.to_datetime(df["time"], utc=True)
    close_at = times + bar_delta
    keep = close_at <= now_utc
    return df.loc[keep].reset_index(drop=True)


def classify_bar_clock(
    *,
    bar_open: datetime,
    tick_time: datetime,
    bar_minutes: int = 5,
    max_skew_seconds: int = 180,
) -> str:
    """
    Last closed M5 open should be the floor of tick time to bar size, minus one bar.

    Hour-scale skew means the series was treated as the wrong timezone.
    """
    bar_open_utc = _as_utc(bar_open)
    tick_utc = _as_utc(tick_time)
    bar_delta = timedelta(minutes=bar_minutes)
    tick_floor = tick_utc.replace(second=0, microsecond=0)
    remainder = tick_floor.minute % bar_minutes
    tick_floor = tick_floor - timedelta(minutes=remainder)
    expected_closed_open = tick_floor - bar_delta
    skew = abs((bar_open_utc - expected_closed_open).total_seconds())
    if skew > max_skew_seconds:
        return "DATA_BAD_TIMEZONE"
    return "ok"


def rates_to_frame(rates, *, source_tz: str = "UTC") -> Optional[pd.DataFrame]:
    """Convert MetaTrader5 copy_rates rows to UTC OHLCV."""
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    if "time" not in df.columns:
        return None
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    if source_tz.upper() != "UTC":
        df["time"] = df["time"].dt.tz_convert(None).dt.tz_localize(source_tz).dt.tz_convert("UTC")
    rename = {}
    if "tick_volume" in df.columns and "volume" not in df.columns:
        rename["tick_volume"] = "volume"
    df = df.rename(columns=rename)
    keep = [c for c in ("time", "open", "high", "low", "close", "volume") if c in df.columns]
    return df[keep].sort_values("time").reset_index(drop=True)
