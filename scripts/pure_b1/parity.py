"""Read-only comparisons for broker M15, Bid ticks, and saved reference bars."""

from __future__ import annotations

import math

import pandas as pd

from scripts.strategy import pure_b1_bars


OHLC = ("open", "high", "low", "close")


def ticks_to_m15(ticks: pd.DataFrame) -> pd.DataFrame:
    if ticks.empty or not {"time_msc", "bid", "ask"}.issubset(ticks):
        raise ValueError("Bid/Ask ticks required")
    if not ticks["time_msc"].is_monotonic_increasing:
        raise ValueError("tick time invalid")
    if (
        not ticks[["bid", "ask"]].apply(pd.to_numeric, errors="coerce").notna().all().all()
        or (ticks["bid"] <= 0).any()
        or (ticks["ask"] < ticks["bid"]).any()
    ):
        raise ValueError("invalid Bid/Ask ticks")
    frame = ticks[["time_msc", "bid"]].copy()
    frame["bar_open_utc"] = pd.to_datetime(frame.time_msc, unit="ms", utc=True).dt.floor("15min")
    bars = frame.groupby("bar_open_utc", sort=True).bid.agg(
        open="first", high="max", low="min", close="last"
    )
    return bars[list(OHLC)]


def _validate_bars(frame: pd.DataFrame) -> None:
    if not set(OHLC).issubset(frame):
        raise ValueError("OHLC columns required")
    index = frame.index
    if (
        not isinstance(index, pd.DatetimeIndex)
        or index.tz is None
        or index.has_duplicates
        or not index.is_monotonic_increasing
        or any(stamp.utcoffset().total_seconds() != 0 for stamp in index)
    ):
        raise ValueError("ordered UTC DatetimeIndex required")


def compare_bars(
    broker_bars: pd.DataFrame, reference_bars: pd.DataFrame, *, tolerance: float
) -> dict:
    _validate_bars(broker_bars)
    _validate_bars(reference_bars)
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("invalid price tolerance")
    overlap = broker_bars.index.intersection(reference_bars.index)
    if broker_bars.empty or reference_bars.empty:
        raise ValueError("nonempty bar sets required")
    start = max(broker_bars.index[0], reference_bars.index[0])
    end = min(broker_bars.index[-1], reference_bars.index[-1])
    broker_window = broker_bars.loc[start:end].index if start <= end else broker_bars.index[:0]
    reference_window = (
        reference_bars.loc[start:end].index if start <= end else reference_bars.index[:0]
    )
    broker_only = broker_window.difference(reference_window)
    reference_only = reference_window.difference(broker_window)
    mismatches = []
    mismatch_bars = set()
    maximum = 0.0
    for ts in overlap:
        for field in OHLC:
            left = float(broker_bars.at[ts, field])
            right = float(reference_bars.at[ts, field])
            difference = abs(left - right)
            if not math.isfinite(difference):
                raise ValueError("nonfinite OHLC comparison")
            maximum = max(maximum, difference)
            if difference > tolerance:
                mismatch_bars.add(ts)
                mismatches.append(
                    {
                        "bar_open_utc": ts.isoformat(),
                        "field": field,
                        "broker": left,
                        "reference": right,
                        "abs_diff": difference,
                    }
                )
    return {
        "status": (
            "INCONCLUSIVE"
            if not len(overlap)
            else "FAIL"
            if mismatches or len(broker_only) or len(reference_only)
            else "PASS"
        ),
        "overlap_bars": len(overlap),
        "broker_only_bars": len(broker_only),
        "reference_only_bars": len(reference_only),
        "broker_only_examples": [ts.isoformat() for ts in broker_only[:30]],
        "reference_only_examples": [ts.isoformat() for ts in reference_only[:30]],
        "mismatch_bars": len(mismatch_bars),
        "max_abs_diff": maximum,
        "mismatches": mismatches,
    }


def compare_signals(broker_bars: pd.DataFrame, reference_bars: pd.DataFrame) -> dict:
    bar_parity = compare_bars(broker_bars, reference_bars, tolerance=0.001)
    broker = pure_b1_bars(broker_bars)
    reference = pure_b1_bars(reference_bars)
    # EWM needs a long matching history; exclude captured startup from this comparison.
    overlap = broker.index[500:].intersection(reference.index)
    mismatches = []
    max_delta = {field: 0.0 for field in ("rsi", "ema50", "atr")}
    for ts in overlap:
        left, right = broker.loc[ts], reference.loc[ts]
        if not bool(left.ready and right.ready):
            continue
        for field in max_delta:
            max_delta[field] = max(max_delta[field], abs(float(left[field]) - float(right[field])))
        if int(left.direction) != int(right.direction):
            mismatches.append(
                {
                    "bar_open_utc": ts.isoformat(),
                    "broker_direction": int(left.direction),
                    "reference_direction": int(right.direction),
                }
            )
    ready = int(sum(bool(broker.at[ts, "ready"] and reference.at[ts, "ready"]) for ts in overlap))
    drift = any(delta > 1e-6 for delta in max_delta.values())
    return {
        "status": (
            "INCONCLUSIVE"
            if not ready
            else "FAIL"
            if bar_parity["status"] != "PASS" or mismatches or drift
            else "PASS"
        ),
        "comparable_bars": ready,
        "warmup_excluded_broker_bars": min(500, len(broker)),
        "indicator_tolerance": 1e-6,
        "signal_mismatches": mismatches,
        "max_indicator_abs_diff": max_delta,
    }
