"""Liquidity pool computation with incomplete-session unavailability."""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from scripts.smc.types import LiquidityLevels

# M5 bars expected in Asian 00:00–07:00 UTC (7h * 12).
ASIAN_SESSION_M5_BARS = 84
# Prior calendar day completeness floor (full day = 288 M5 bars).
PREV_DAY_MIN_M5_BARS = 200


def _ensure_utc_time(df: pd.DataFrame) -> pd.DataFrame:
    out = df
    if not pd.api.types.is_datetime64_any_dtype(out["time"]):
        out = out.copy()
        out["time"] = pd.to_datetime(out["time"], utc=True)
    elif out["time"].dt.tz is None:
        out = out.copy()
        out["time"] = out["time"].dt.tz_localize("UTC")
    else:
        out = out.copy()
        out["time"] = out["time"].dt.tz_convert("UTC")
    return out


def _asian_session_complete(asian_df: pd.DataFrame, start_hour: int, end_hour: int) -> bool:
    if asian_df.empty:
        return False
    hours = set(int(h) for h in asian_df["time"].dt.hour.unique())
    required = set(range(start_hour, end_hour))
    if not required.issubset(hours):
        return False
    return len(asian_df) >= ASIAN_SESSION_M5_BARS


def _prev_day_complete(prev_df: pd.DataFrame) -> bool:
    if prev_df.empty:
        return False
    return len(prev_df) >= PREV_DAY_MIN_M5_BARS


def compute_liquidity_levels(
    m5_df: pd.DataFrame,
    target_date: date,
    asian_start_hour: int = 0,
    asian_end_hour: int = 7,
) -> Optional[LiquidityLevels]:
    """
    Computes Asian Range High/Low (00:00–07:00 UTC) for target_date and
    Previous Day High/Low (PDH/PDL) from the immediately preceding trading day.

    Incomplete Asian session or incomplete prior day makes that pool unavailable
    (None). Never fabricate PDH/PDL from Asian levels.
    """
    if m5_df is None or m5_df.empty:
        return None

    df = _ensure_utc_time(m5_df)

    target_mask = df["time"].dt.date == target_date
    asian_mask = (
        target_mask
        & (df["time"].dt.hour >= asian_start_hour)
        & (df["time"].dt.hour < asian_end_hour)
    )
    asian_df = df[asian_mask]
    if not _asian_session_complete(asian_df, asian_start_hour, asian_end_hour):
        return None

    asian_high = float(asian_df["high"].max())
    asian_low = float(asian_df["low"].min())

    pdh: Optional[float] = None
    pdl: Optional[float] = None
    prev_dates = df[df["time"].dt.date < target_date]["time"].dt.date.unique()
    if len(prev_dates) > 0:
        prev_date = max(prev_dates)
        prev_df = df[df["time"].dt.date == prev_date]
        if _prev_day_complete(prev_df):
            pdh = float(prev_df["high"].max())
            pdl = float(prev_df["low"].min())

    london_mask = (
        target_mask
        & (df["time"].dt.hour >= 7)
        & (df["time"].dt.hour < 12)
    )
    london_df = df[london_mask]
    london_high = float(london_df["high"].max()) if not london_df.empty else None
    london_low = float(london_df["low"].min()) if not london_df.empty else None

    return LiquidityLevels(
        asian_high=asian_high,
        asian_low=asian_low,
        pdh=pdh,
        pdl=pdl,
        date_str=target_date.isoformat(),
        london_high=london_high,
        london_low=london_low,
    )


def select_nearest_opposing_pool_tp(
    direction,
    entry_price: float,
    sl_distance: float,
    liquidity: LiquidityLevels,
    min_r: float = 1.5,
    consumed_levels: Optional[set] = None,
):
    """
    Foundation BaselinePlay TP: nearest untouched opposing liquidity pool.

    BUY targets pools strictly above entry; SELL targets pools strictly below.
    Skip when nearest eligible planned R < min_r (do not stretch to a farther pool).
    """
    from scripts.smc.types import Direction

    consumed = consumed_levels or set()
    if direction == Direction.BUY:
        candidates = [
            ("asian_high", liquidity.asian_high),
            ("pdh", liquidity.pdh),
            ("london_high", liquidity.london_high),
        ]
        candidates = [
            (name, float(level))
            for name, level in candidates
            if level is not None and float(level) > entry_price and float(level) not in consumed
        ]
        candidates.sort(key=lambda item: item[1])
    else:
        candidates = [
            ("asian_low", liquidity.asian_low),
            ("pdl", liquidity.pdl),
            ("london_low", liquidity.london_low),
        ]
        candidates = [
            (name, float(level))
            for name, level in candidates
            if level is not None and float(level) < entry_price and float(level) not in consumed
        ]
        candidates.sort(key=lambda item: item[1], reverse=True)

    if not candidates:
        return None, "no opposing pool beyond entry"

    name, tp = candidates[0]
    if sl_distance <= 0:
        return None, "nonpositive SL distance"
    planned_r = abs(tp - entry_price) / sl_distance
    if planned_r < min_r:
        return None, f"nearest {name} R {planned_r:.2f} < {min_r}"
    return round(tp, 2), name
