"""Validate closed runtime M1 inputs before frozen aggregation."""

from datetime import timedelta

import numpy as np
import pandas as pd

from scripts.pure_b1.broker_data import completed_m15_from_m1 as aggregate


def completed_m15_from_m1(rates, *, now):
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("now must be timezone-aware UTC")
    raw = pd.DataFrame(rates)
    required = {"time", "open", "high", "low", "close"}
    if raw.empty or not required.issubset(raw.columns):
        raise ValueError("missing M1 bars")
    stamps = pd.to_datetime(raw.time, unit="s", utc=True, errors="coerce")
    if stamps.isna().any():
        raise ValueError("invalid M1 timestamps")
    closed = raw.loc[stamps + pd.Timedelta(minutes=1) <= pd.Timestamp(now)]
    values = closed[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    if (
        not np.isfinite(values.to_numpy()).all()
        or (values <= 0).any().any()
        or (values.high < values[["open", "close", "low"]].max(axis=1)).any()
        or (values.low > values[["open", "close", "high"]].min(axis=1)).any()
    ):
        raise ValueError("invalid_closed_M1_OHLC")
    return aggregate(rates, now=now)
