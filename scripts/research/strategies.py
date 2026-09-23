"""Versioned deterministic research definitions, including explicitly reconstructed variants."""

from dataclasses import dataclass, replace
import numpy as np
import pandas as pd
from .data import bars


@dataclass(frozen=True)
class Spec:
    name: str
    family: str
    lookback: int = 20
    expansion: float = 1.5
    fast: int = 20
    slow: int = 50
    filters: tuple = ()
    sl: float = 2.0
    tp: float = 2.0
    timeframe: int = 15
    entry: str = "market"
    reconstruction: bool = True


def registry():
    specs = [Spec(f"Donchian{n}", "donchian", lookback=n) for n in (20, 30, 40)]
    specs += [Spec(f"State{n}", "state", lookback=n) for n in (15, 20, 25)]
    specs += [Spec(f"ATR{v}", "expansion", expansion=v) for v in (1.25, 1.5)]
    specs += [
        Spec(f"EMA{a}x{b}", "ema", fast=a, slow=b) for a, b in ((10, 30), (20, 50))
    ]
    specs += [
        Spec("ORB30", "orb", lookback=30),
        Spec("ORB60", "orb", lookback=60),
        Spec("AsianBreak", "asian"),
        Spec("AsianRetest", "asian_retest"),
        Spec("SweepReversal", "sweep"),
        Spec("SweepMSS", "mss"),
        Spec("GSS_OTE", "ote"),
    ]
    bases = specs.copy()
    # Controlled one-filter-at-a-time ablation; avoid an unrestricted parameter search.
    specs += [
        replace(s, name=f"{s.name}__{f}", filters=(f,))
        for s in bases
        for f in ("rsi", "body", "fvg", "h1ema", "h1structure")
    ]
    specs += [
        Spec(
            "A_TrendStructure",
            "donchian",
            filters=("body", "h1structure"),
            reconstruction=False,
        ),
        Spec(
            "B_Donchian30_RSI",
            "donchian",
            lookback=30,
            filters=("rsi",),
            sl=2.5,
            tp=2.5,
            reconstruction=False,
        ),
        Spec(
            "C_State25_RSI_FVG",
            "state",
            lookback=25,
            filters=("rsi", "fvg"),
            sl=3,
            tp=3,
        ),
        Spec("D_ATR1.5_RSI_FVG", "expansion", filters=("rsi", "fvg"), tp=3),
        Spec("Asian_RSI_H1EMA", "asian", filters=("rsi", "h1ema")),
        Spec("SweepCHOCH", "choch"),
        Spec("SweepMSS_FVG", "mss_fvg"),
        Spec("SweepMSS_FVG_CE50", "mss_fvg", entry="ce50"),
        Spec("Structure_OB", "ob", entry="ob"),
        Spec("TurtleSweep20", "sweep"),
    ]
    specs += [
        replace(s, name=s.name + "_H4", timeframe=240)
        for s in [specs[0], bases[5], bases[7], bases[9], bases[16], specs[-3]]
    ]
    specs += [
        Spec(
            f"TrendStructure{n}",
            "donchian",
            lookback=n,
            filters=("body", "h1structure"),
        )
        for n in (25, 30)
    ]
    assert len({s.name for s in specs}) == len(specs)
    return specs


def wilder(series, period=14):
    """Arithmetic seed, then Wilder recursion; no pandas EWM seed ambiguity."""
    a = series.to_numpy(float)
    out = np.full(len(a), np.nan)
    if len(a) >= period:
        out[period - 1] = np.mean(a[:period])
        for i in range(period, len(a)):
            out[i] = (out[i - 1] * (period - 1) + a[i]) / period
    return pd.Series(out, index=series.index)


def structure(frame):
    """Strict 2-left/2-right pivots become available only at confirming bar close."""
    high, low = frame.high.to_numpy(), frame.low.to_numpy()
    direction = np.zeros(len(frame), dtype=int)
    sh = np.full(len(frame), np.nan)
    sl = sh.copy()
    highs, lows = [], []
    for i in range(4, len(frame)):
        p = i - 2
        if high[p] > max(high[p - 2 : p]) and high[p] > max(high[p + 1 : i + 1]):
            highs.append(high[p])
        if low[p] < min(low[p - 2 : p]) and low[p] < min(low[p + 1 : i + 1]):
            lows.append(low[p])
        if highs:
            sh[i] = highs[-1]
        if lows:
            sl[i] = lows[-1]
        if len(highs) >= 2 and len(lows) >= 2:
            if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
                direction[i] = 1
            elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
                direction[i] = -1
    return direction, sh, sl


def features(m1, minutes):
    f = bars(m1, minutes)
    prior = f.close.shift()
    tr = pd.concat(
        [f.high - f.low, (f.high - prior).abs(), (f.low - prior).abs()], axis=1
    ).max(axis=1)
    f["atr"] = wilder(tr)
    delta = f.close.diff().fillna(0)
    gain, loss = wilder(delta.clip(lower=0)), wilder(-delta.clip(upper=0))
    f["rsi"] = 100 - 100 / (1 + gain / loss)
    f.loc[(loss == 0) & (gain > 0), "rsi"] = 100
    f.loc[(loss == 0) & (gain == 0), "rsi"] = 50
    f["body"] = (f.close - f.open).abs() / (f.high - f.low).replace(0, np.nan)
    f["fvg_up"] = f.low - f.high.shift(2)
    f["fvg_down"] = f.low.shift(2) - f.high
    consecutive = f.index.to_series().diff(2) == pd.Timedelta(minutes=2 * minutes)
    f.loc[~consecutive, ["fvg_up", "fvg_down"]] = np.nan
    f["structure"], f["swing_high"], f["swing_low"] = structure(f)
    h = bars(m1, 60)
    h["h1structure"] = structure(h)[0]
    ema = h.close.ewm(span=200, adjust=False, min_periods=200).mean()
    h["h1ema"] = np.sign(h.close - ema).fillna(0)
    # Both frames' indices now denote availability (bar CLOSE), not bar open.
    h.index = h.index + pd.Timedelta(hours=1)
    for col in ("h1structure", "h1ema"):
        f[col] = (
            h[col]
            .reindex(f.index + pd.Timedelta(minutes=minutes), method="ffill")
            .fillna(0)
            .to_numpy()
        )
    efficiency = (f.close - f.close.shift(20)).abs() / f.close.diff().abs().rolling(
        20
    ).sum()
    f["regime"] = np.where(
        (f.high - f.low) >= 1.5 * f.atr,
        "expansion",
        np.where(efficiency >= 0.3, "trend", "sideway"),
    )
    return f


def continuation(f, seed):
    o, h, low_prices, c = (f[k].to_numpy() for k in ("open", "high", "low", "close"))
    out = np.zeros(len(f), dtype=int)
    active = None
    for i in range(len(f)):
        if active:
            start, d, level, invalid, count = active
            if (
                i - start > 6
                or (d == 1 and low_prices[i] < invalid)
                or (d == -1 and h[i] > invalid)
            ):
                active = None
            else:
                opposing = d * (c[i] - o[i]) < 0
                if opposing:
                    count += 1
                    active = (start, d, level, invalid, count) if count <= 2 else None
                elif count and d * (c[i] - level) > 0:
                    out[i] = d
                    active = None
        if active is None and not out[i] and seed[i]:
            d = seed[i]
            active = (
                i,
                d,
                h[i] if d == 1 else low_prices[i],
                low_prices[i] if d == 1 else h[i],
                0,
            )
    return out


def session_signal(f, spec):
    out = np.zeros(len(f), dtype=int)
    # Reconstructed UTC schedule: Asian 00:00–07:00, ORB starts 07:00.
    for _, positions in pd.Series(np.arange(len(f)), index=f.index).groupby(
        f.index.date
    ):
        ids = positions.to_numpy()
        mins = f.index[ids].hour * 60 + f.index[ids].minute
        start, end = (420, 420 + spec.lookback) if spec.family == "orb" else (0, 420)
        range_ids = ids[(mins >= start) & (mins < end)]
        expected = (end - start) // spec.timeframe
        if not expected or len(range_ids) != expected:
            continue
        upper, lower = f.high.iloc[range_ids].max(), f.low.iloc[range_ids].min()
        armed = 0
        # Signal is known only when its bar closes. Range membership uses bar open.
        close_mins = mins + spec.timeframe
        for i in ids[(mins >= end) & (close_mins < 1020)]:
            c, lo, hi = f.close.iloc[i], f.low.iloc[i], f.high.iloc[i]
            if spec.family == "asian_retest":
                if armed == 1 and lo <= upper and c > upper:
                    out[i] = 1
                    break
                if armed == -1 and hi >= lower and c < lower:
                    out[i] = -1
                    break
                if not armed:
                    armed = 1 if c > upper else (-1 if c < lower else 0)
            else:
                if c > upper or c < lower:
                    out[i] = 1 if c > upper else -1
                    break
    return out


def signals(f, spec):
    n = len(f)
    out = np.zeros(n, dtype=int)
    limit = np.full(n, np.nan)
    upper = f.high.shift().rolling(spec.lookback).max().to_numpy()
    lower = f.low.shift().rolling(spec.lookback).min().to_numpy()
    o, h, low_prices, c = (f[k].to_numpy() for k in ("open", "high", "low", "close"))
    breakout = np.where(c > upper, 1, np.where(c < lower, -1, 0))
    if spec.family == "donchian":
        out = breakout
    elif spec.family == "state":
        out = continuation(f, breakout)
    elif spec.family == "expansion":
        seed = np.where(
            ((h - low_prices) >= spec.expansion * f.atr) & (f.body >= 0.5),
            np.sign(c - o),
            0,
        ).astype(int)
        out = continuation(f, seed)
    elif spec.family == "ema":
        a = f.close.ewm(span=spec.fast, adjust=False, min_periods=spec.fast).mean()
        b = f.close.ewm(span=spec.slow, adjust=False, min_periods=spec.slow).mean()
        out = np.where(
            (a > b) & (a.shift() <= b.shift()),
            1,
            np.where((a < b) & (a.shift() >= b.shift()), -1, 0),
        )
    elif spec.family in ("asian", "asian_retest", "orb"):
        out = session_signal(f, spec)
    elif spec.family == "sweep":
        out = np.where(
            (low_prices < lower) & (np.minimum(o, c) > lower),
            1,
            np.where((h > upper) & (np.maximum(o, c) < upper), -1, 0),
        )
    elif spec.family in ("mss", "choch", "mss_fvg", "ob"):
        active = None
        sh, sl = f.swing_high.to_numpy(), f.swing_low.to_numpy()
        trend = f.structure.to_numpy()
        for i in range(1, n):
            if active:
                start, d, level, phase = active
                if i - start > (12 if phase else 8):
                    active = None
                elif phase or (
                    np.isfinite(level)
                    and d * (c[i] - level) > 0
                    and d * (c[i] - o[i]) > 0
                ):
                    if spec.family == "mss_fvg":
                        gap = f.fvg_up.iloc[i] if d == 1 else f.fvg_down.iloc[i]
                        if gap >= 0.05 * f.atr.iloc[i]:
                            out[i] = d
                            limit[i] = (
                                (low_prices[i] + h[i - 2]) / 2
                                if d == 1
                                else (h[i] + low_prices[i - 2]) / 2
                            )
                            active = None
                        else:
                            active = (start, d, level, 1)
                    else:
                        out[i] = d
                        active = None
            if not out[i] and active is None:
                d = (
                    1
                    if low_prices[i] < lower[i] and min(o[i], c[i]) > lower[i]
                    else (-1 if h[i] > upper[i] and max(o[i], c[i]) < upper[i] else 0)
                )
                if spec.family == "ob":
                    d = (
                        1
                        if c[i] > sh[i - 1] and c[i - 1] <= sh[i - 1]
                        else (-1 if c[i] < sl[i - 1] and c[i - 1] >= sl[i - 1] else 0)
                    )
                    if d:
                        opp = [
                            j for j in range(max(0, i - 10), i) if d * (c[j] - o[j]) < 0
                        ]
                        if opp:
                            out[i] = d
                            j = opp[-1]
                            limit[i] = (o[j] + c[j]) / 2
                elif d and (spec.family != "choch" or trend[i - 1] == -d):
                    active = (i, d, sh[i - 1] if d == 1 else sl[i - 1], 0)
    elif spec.family == "ote":
        active = None
        for i in range(n):
            available = f.index[i] + pd.Timedelta(minutes=spec.timeframe)
            minute = available.hour * 60 + available.minute
            session = 420 <= minute < 630 or 750 <= minute < 990
            if active:
                start, d, lo, hi = active
                if i - start > 8 or low_prices[i] < lo or h[i] > hi:
                    active = None
                elif session:
                    a, b = (
                        (hi - 0.786 * (hi - lo), hi - 0.618 * (hi - lo))
                        if d == 1
                        else (lo + 0.618 * (hi - lo), lo + 0.786 * (hi - lo))
                    )
                    if low_prices[i] <= b and h[i] >= a and d * (c[i] - o[i]) > 0:
                        out[i] = d
                        active = None
            if (
                active is None
                and not out[i]
                and session
                and h[i] - low_prices[i] >= 1.5 * f.atr.iloc[i]
                and f.body.iloc[i] >= 0.5
            ):
                active = (i, int(np.sign(c[i] - o[i])), low_prices[i], h[i])
    else:
        raise ValueError(spec.family)
    raw = pd.DataFrame({"direction": out, "limit": limit}, index=f.index)
    return apply_filters(f, raw, spec)


def apply_filters(f, raw, spec):
    out = raw.direction.to_numpy().copy()
    limit = raw.limit.to_numpy()
    for filt in spec.filters:
        if filt == "rsi":
            valid = ((out == 1) & (f.rsi <= 75)) | ((out == -1) & (f.rsi >= 25))
        elif filt == "body":
            valid = f.body >= 0.6
        elif filt == "fvg":
            valid = ((out == 1) & (f.fvg_up >= 0.05 * f.atr)) | (
                (out == -1) & (f.fvg_down >= 0.05 * f.atr)
            )
        else:
            valid = f[filt] == out
        out = np.where(valid, out, 0)
    out = np.where((f.atr > 0) & f.atr.notna() & (f.high > f.low), out, 0)
    return pd.DataFrame({"direction": out, "limit": limit}, index=f.index)
