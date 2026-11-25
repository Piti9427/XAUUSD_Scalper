"""Causal completed-bar challenger signal preparation, research only."""

import numpy as np
import pandas as pd


def candidate_frame(
    frame,
    buy_filter,
    depth,
    buy_signal="breakout",
    signal_spec=None,
    oscillator_spec=None,
    entry_session="all",
    sell_filter="off",
):
    """Causal completed-bar signals; default D48 or explicit directional horizons."""
    if sell_filter not in ("off", "body_dominant"):
        raise ValueError("unsupported SELL candle filter")
    utc_sessions = {"utc_00_07": (0, 7), "utc_07_13": (7, 13), "utc_13_20": (13, 20)}
    if entry_session not in ("all", "avoid_rollover", *utc_sessions):
        raise ValueError("unsupported entry session")
    if entry_session != "all" and (frame.index.tz is None or str(frame.index.tz) != "UTC"):
        raise ValueError("session filters require aware UTC")
    if buy_filter not in ("off", "ema50", "prior_day", "body", "extreme", "ema_prior"):
        raise ValueError("unknown BUY filter")
    if depth not in (0.0, 0.15):
        raise ValueError("unknown depth")
    if buy_signal not in ("breakout", "lower_wick", "trend_pullback"):
        raise ValueError("unknown BUY setup")
    if oscillator_spec is not None:
        if signal_spec is not None or buy_signal != "breakout" or buy_filter != "off" or depth:
            raise ValueError("oscillator contract cannot combine breakout transforms")
        if set(oscillator_spec) - {"side", "parent_lookback", "parent_trend_span"} != {
            "period",
            "threshold",
            "trend_span",
        }:
            raise ValueError("unknown oscillator contract")
        period, threshold, trend_span = (
            oscillator_spec[k] for k in ("period", "threshold", "trend_span")
        )
        if period not in (7, 14, 21) or threshold not in (25, 30, 35) or trend_span not in (0, 50):
            raise ValueError("unsupported oscillator contract")
        side = oscillator_spec.get("side", "both")
        if side not in ("both", "buy", "sell"):
            raise ValueError("unsupported oscillator side")
        parent_lookback = oscillator_spec.get("parent_lookback")
        if parent_lookback is not None and (side != "buy" or parent_lookback not in (24, 48, 96)):
            raise ValueError("unsupported SELL parent horizon")
        parent_trend_span = oscillator_spec.get("parent_trend_span", 0)
        if parent_trend_span not in (0, 50, 200) or (
            "parent_trend_span" in oscillator_spec and parent_lookback is None
        ):
            raise ValueError("unsupported SELL parent trend")
        frame = frame.copy()
        if parent_lookback is not None:
            # Both range anchors must share parent warmup; replay validates both.
            frame["hh"] = frame.high.rolling(parent_lookback).max().shift(1)
            frame["ll"] = frame.low.rolling(parent_lookback).min().shift(1)
            parent_direction = pd.Series(np.where(frame.close < frame.ll, -1, 0), index=frame.index)
            if parent_trend_span:
                parent_average = frame.close.ewm(
                    span=parent_trend_span, adjust=False, min_periods=parent_trend_span
                ).mean()
                bearish = (frame.close < parent_average) & (
                    parent_average < parent_average.shift(4)
                )
                parent_direction.loc[~bearish.fillna(False)] = 0
        else:
            parent_direction = frame.direction.copy()
        delta = frame.close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rsi = 100 - 100 / (1 + gain / loss)
        rsi = rsi.mask((gain == 0) & (loss == 0), 50.0)
        frame["direction"] = np.select(
            [
                (rsi.shift(1) < threshold) & (rsi >= threshold) & (delta > 0),
                (rsi.shift(1) > 100 - threshold) & (rsi <= 100 - threshold) & (delta < 0),
            ],
            [1, -1],
            0,
        )
        if trend_span:
            average = frame.close.ewm(span=trend_span, adjust=False, min_periods=trend_span).mean()
            aligned = (frame.direction * (frame.close - average) > 0) & (
                frame.direction * (average - average.shift(4)) > 0
            )
            frame.loc[~aligned.fillna(False), "direction"] = 0
        oscillator = frame.direction != 0
        if side != "both":
            selected = 1 if side == "buy" else -1
            # Preserve the other breakout leg, including its priority on a conflict.
            parent = parent_direction == -selected
            oscillator = (frame.direction == selected) & ~parent
            frame["direction"] = np.select([parent, oscillator], [-selected, selected], 0)
        # Only oscillator setups use trigger close as recorded ATR-trade anchor.
        frame.loc[oscillator, "hh"] = frame.close[oscillator]
        frame.loc[oscillator, "ll"] = frame.close[oscillator]
    if signal_spec is not None:
        if buy_signal != "breakout":
            raise ValueError("horizon contract requires breakout setup")
        if set(signal_spec) - {"max_range_atr"} != {"buy_lookback", "sell_lookback", "trend_span"}:
            raise ValueError("unknown signal contract")
        if any(signal_spec[k] not in (12, 24, 48, 96) for k in ("buy_lookback", "sell_lookback")):
            raise ValueError("unsupported horizon")
        if signal_spec["trend_span"] not in (0, 50, 200):
            raise ValueError("unsupported trend span")
        maximum = signal_spec.get("max_range_atr", 0.0)
        if maximum not in (0.0, 6.0, 9.0, 12.0):
            raise ValueError("unsupported range compression")
        frame = frame.copy()
        frame["hh"] = frame.high.rolling(signal_spec["buy_lookback"]).max().shift(1)
        frame["ll"] = frame.low.rolling(signal_spec["sell_lookback"]).min().shift(1)
        frame["direction"] = np.select([frame.close > frame.hh, frame.close < frame.ll], [1, -1], 0)
        if maximum:
            buy_low = frame.low.rolling(signal_spec["buy_lookback"]).min().shift(1)
            sell_high = frame.high.rolling(signal_spec["sell_lookback"]).max().shift(1)
            width = pd.Series(
                np.where(frame.direction == 1, frame.hh - buy_low, sell_high - frame.ll),
                index=frame.index,
            )
            prior_atr = frame.atr.shift(1)
            compressed = (prior_atr > 0) & (width / prior_atr <= maximum)
            frame.loc[~compressed.fillna(False), "direction"] = 0
        if signal_spec["trend_span"]:
            span = signal_spec["trend_span"]
            average = frame.close.ewm(span=span, adjust=False, min_periods=span).mean()
            aligned = (frame.direction * (frame.close - average) > 0) & (
                frame.direction * (average - average.shift(4)) > 0
            )
            frame.loc[~aligned.fillna(False), "direction"] = 0
    result = frame.copy()
    ema = frame.close.ewm(span=50, adjust=False, min_periods=50).mean()
    trend = (frame.close > ema) & (ema > ema.shift(4))
    if buy_signal != "breakout":
        result.loc[result.direction == 1, "direction"] = 0
        trigger = (
            (frame.low < frame.ll) & (frame.close > frame.ll) & (frame.high <= frame.hh)
            if buy_signal == "lower_wick"
            else trend
            & (frame.close.shift(1) < frame.open.shift(1))
            & (frame.close > frame.high.shift(1))
        )
        admitted = trigger.fillna(False) & (frame.direction != -1)
        result.loc[admitted, "direction"] = 1
        result.loc[admitted, "hh"] = (
            frame.ll if buy_signal == "lower_wick" else frame.high.shift(1)
        )[admitted]
    daily = frame.resample("1D").agg({"open": "first", "close": "last"})
    prior = np.sign(daily.close - daily.open).shift(1)
    prior_up = prior.reindex((frame.index + pd.Timedelta(minutes=15)).normalize())
    prior_up.index = frame.index
    span = frame.high - frame.low
    allowed = {
        "off": result.direction == 1,
        "ema50": trend,
        "prior_day": prior_up == 1,
        "body": (span > 0) & (frame.close - frame.open >= span / 2),
        "extreme": (span > 0) & (frame.close >= frame.high - span * 0.2),
        "ema_prior": trend & (prior_up == 1),
    }[buy_filter]
    result.loc[(result.direction == 1) & ~allowed.fillna(False), "direction"] = 0
    if depth:
        boundary = np.where(result.direction == 1, result.hh, result.ll)
        distance = result.direction * (result.close - boundary) / result.atr
        result.loc[distance < depth, "direction"] = 0
    if entry_session == "avoid_rollover":
        result.loc[(result.index + pd.Timedelta(minutes=15)).hour >= 21, "direction"] = 0
    elif entry_session in utc_sessions:
        lower, upper = utc_sessions[entry_session]
        hour = (result.index + pd.Timedelta(minutes=15)).hour
        result.loc[(hour < lower) | (hour >= upper), "direction"] = 0
    if sell_filter == "body_dominant":
        strong = (result.high > result.low) & (
            (result.open - result.close) >= (result.high - result.low) / 2
        )
        result.loc[(result.direction == -1) & ~strong, "direction"] = 0
    return result
