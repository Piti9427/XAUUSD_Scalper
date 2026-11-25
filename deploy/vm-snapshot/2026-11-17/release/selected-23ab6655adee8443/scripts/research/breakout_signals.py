"""Completed-bar features and causal entry transforms."""

import numpy as np
import pandas as pd


def features(bars: pd.DataFrame) -> pd.DataFrame:
    frame = bars[["open", "high", "low", "close"]].astype(float).copy()
    frame["hh"] = frame.high.rolling(48).max().shift(1)
    frame["ll"] = frame.low.rolling(48).min().shift(1)
    previous = frame.close.shift()
    frame["atr"] = (
        pd.concat(
            [frame.high - frame.low, (frame.high - previous).abs(), (frame.low - previous).abs()],
            axis=1,
        )
        .max(axis=1)
        .rolling(14)
        .mean()
    )
    frame["direction"] = np.select([frame.close > frame.hh, frame.close < frame.ll], [1, -1], 0)
    return frame


def _entry_signals(frame, mode):
    output = frame.copy()
    output["stop_low"] = frame.low
    output["stop_high"] = frame.high
    output["entry_boundary"] = np.where(frame.direction == 1, frame.hh, frame.ll)
    if mode == "immediate":
        return output
    output["direction"] = 0
    pending = None
    for index, row in enumerate(frame.itertuples()):
        if pending is not None:
            direction, high, low, born, candle_low, candle_high = pending
            boundary = high if direction == 1 else low
            beyond = direction * (row.close - boundary) > 0
            touched = row.low <= boundary if direction == 1 else row.high >= boundary
            reverse = mode == "failed_reverse" and index - born <= 2 and low <= row.close <= high
            if reverse or (mode != "failed_reverse" and beyond and (mode == "confirm" or touched)):
                if reverse:
                    direction = -direction
                output.loc[row.Index, ["direction", "hh", "ll"]] = [direction, high, low]
                output.loc[row.Index, "entry_boundary"] = boundary
                output.loc[row.Index, ["stop_low", "stop_high"]] = [
                    min(candle_low, row.low),
                    max(candle_high, row.high),
                ]
                pending = None
                continue
            expired = index - born >= (2 if mode == "failed_reverse" else 4)
            if (mode != "failed_reverse" and not beyond) or mode == "confirm" or expired:
                pending = None
        if pending is None and row.direction:
            pending = (int(row.direction), row.hh, row.ll, index, row.low, row.high)
    return output
