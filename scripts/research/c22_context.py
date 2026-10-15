"""Open context proxies. Offline, causal, and independent of outcome labels."""

from collections import Counter
import math

import numpy as np
import pandas as pd

SCHEMA = 1
STEP = pd.Timedelta(minutes=15)


def utc(value):
    value = pd.Timestamp(value)
    if value.tzinfo is None or value.utcoffset().total_seconds() != 0:
        raise ValueError("aware UTC required")
    return value


class Context:
    """Coverage is explicit provenance, never inferred from candle counts.

    coverage days/weeks list fully covered period starts; provenance identifies
    evidence establishing session closures and missing-data checks. Absent
    evidence leaves period-dependent values unavailable.
    """

    def __init__(self, bars, coverage=None):
        if not isinstance(bars.index, pd.DatetimeIndex):
            raise ValueError("aware UTC index required")
        if bars.index.tz is None or any(t.utcoffset().total_seconds() for t in bars.index):
            raise ValueError("aware UTC index required")
        if bars.index.has_duplicates or not bars.index.is_monotonic_increasing:
            raise ValueError("ordered unique bars required")
        self.bars = bars
        coverage = coverage or {}
        if coverage and not coverage.get("provenance"):
            raise ValueError("coverage provenance required")
        self.days = set(coverage.get("days", []))
        self.weeks = set(coverage.get("weeks", []))
        self.daily = bars.resample("1D").agg({"high": "max", "low": "min", "close": "last"})
        self.weekly = bars.resample("W-MON", closed="left", label="left").agg(
            {"high": "max", "low": "min"}
        )
        # Reject partly invalid periods, even if an external assertion says complete.
        valid = np.isfinite(bars[["open", "high", "low", "close"]]).all(axis=1)
        self.bad_days = set(bars.index[~valid].strftime("%Y-%m-%d"))
        self.bad_weeks = set(
            (t.normalize() - pd.Timedelta(days=t.weekday())).strftime("%Y-%m-%d")
            for t in bars.index[~valid]
        )

    def at(self, close_time, direction):
        stamp = utc(close_time)
        if direction not in (-1, 1):
            raise ValueError("direction must be BUY/+1 or SELL/-1")
        day = stamp.normalize()
        week = day - pd.Timedelta(days=day.weekday() + 7)
        eligible = self.daily.loc[self.daily.index < day]
        eligible = eligible.loc[eligible.index.strftime("%Y-%m-%d").isin(self.days - self.bad_days)]
        eligible = eligible.dropna()
        sr = dict(status="coverage_unavailable", levels=[], published_utc=None)
        if (
            len(eligible)
            and week.strftime("%Y-%m-%d") in self.weeks - self.bad_weeks
            and week in self.weekly.index
        ):
            prior = eligible.iloc[-1]
            weekly = self.weekly.loc[week]
            if np.isfinite(weekly).all():
                sr = dict(
                    status="available",
                    levels=[
                        float(prior.high),
                        float(prior.low),
                        float(weekly.high),
                        float(weekly.low),
                    ],
                    published_utc=max(
                        eligible.index[-1] + pd.Timedelta(days=1), week + pd.Timedelta(days=7)
                    ).isoformat(),
                )
        past = self.bars.loc[self.bars.index + STEP <= stamp]
        daily = dict(
            status="coverage_unavailable" if not self.days else "warmup",
            published_utc=day.isoformat(),
            anchor=None,
            median_range=None,
            lower=None,
            upper=None,
            signed=None,
            adjusted=None,
        )
        if len(eligible) >= 20:
            recent = eligible.iloc[-20:]
            spread = float((recent.high - recent.low).median())
            anchor = float(recent.close.iloc[-1])
            if spread > 0 and math.isfinite(spread):
                daily.update(
                    status="available",
                    anchor=anchor,
                    median_range=spread,
                    lower=anchor - spread,
                    upper=anchor + spread,
                )
            else:
                daily["status"] = "invalid_range"
        sd = dict(
            status="warmup",
            published_utc=stamp.isoformat(),
            mean=None,
            sigma=None,
            z=None,
            adjusted=None,
        )
        if len(past) and past.index[-1] + STEP == stamp:
            close = float(past.close.iloc[-1])
            if daily["status"] == "available":
                if math.isfinite(close):
                    daily.update(signed=(close - daily["anchor"]) / daily["median_range"])
                    daily["adjusted"] = direction * daily["signed"]
                else:
                    daily["status"] = "invalid_close"
            values = past.close.iloc[-20:].to_numpy(dtype=float)
            if len(values) == 20:
                if np.isfinite(values).all():
                    mean, sigma = float(values.mean()), float(values.std(ddof=0))
                    if sigma > 0:
                        z = (close - mean) / sigma
                        sd.update(
                            status="available", mean=mean, sigma=sigma, z=z, adjusted=direction * z
                        )
                    else:
                        sd["status"] = "zero_variance"
                else:
                    sd["status"] = "nonfinite"
        else:
            daily["status"] = sd["status"] = "signal_bar_unavailable"
        return dict(sr=sr, daily=daily, sd=sd)


def features(bars, close_time, direction, coverage=None):
    return Context(bars, coverage).at(close_time, direction)


def room(sr, direction, entry=None, stop=None):
    result = dict(status=sr["status"], value=None, level=None)
    if sr["status"] != "available":
        return result
    if entry is None or stop is None:
        result["status"] = "entry_geometry_unavailable"
        return result
    risk = abs(entry - stop)
    if not risk or not math.isfinite(risk):
        raise ValueError("invalid authoritative initial stop")
    ahead = [
        (direction * (level - entry), i, level)
        for i, level in enumerate(sr["levels"])
        if direction * (level - entry) > 0
    ]
    if not ahead:
        result["status"] = "no_opposing_level"
        return result
    distance, _, level = min(ahead)
    result.update(status="available", value=distance / risk, level=level)
    return result


def annotate(frame, result, *, run, scenario, start, end, coverage=None, symbol="XAUUSD"):
    """Build immutable decision context first; join authoritative outcomes last."""
    context = Context(frame, coverage)
    events = {}
    for event in result.get("context_events", []):
        key = (event["signal_close_utc"], event["direction"])
        if key in events:
            raise ValueError("duplicate signal event")
        events[key] = event
    trades = {}
    for i, trade in enumerate(result["ledger"]):
        key = (trade["entry_time_utc"], trade["direction"])
        if key in trades:
            raise ValueError("duplicate ledger entry")
        trades[key] = (i, trade)
    rows, linked = [], set()
    for bar in frame.itertuples():
        stamp = bar.Index + STEP
        raw = int(getattr(bar, "raw_direction", bar.direction))
        if not raw or not utc(start) <= stamp < utc(end):
            continue
        event = events.get((stamp.isoformat(), raw))
        reason = (
            event["reason"] if event else ("macro_blocked" if not bar.direction else "unvisited")
        )
        row = dict(
            schema=SCHEMA,
            run=run,
            scenario=scenario,
            symbol=symbol,
            signal_close_utc=stamp.isoformat(),
            direction=raw,
            raw_direction=raw,
            post_macro_direction=int(bar.direction),
            visited=event is not None,
            admission_reason=reason,
            features=context.at(stamp, raw),
            ledger_id=None,
            entry_time_utc=None,
            entry=None,
            initial_stop=None,
            outcome=None,
        )
        trade = None
        if reason == "admitted":
            key = (event["time_utc"], raw)
            if key not in trades:
                raise ValueError("admitted event has no ledger trade")
            i, trade = trades[key]
            if i in linked:
                raise ValueError("ledger trade linked twice")
            linked.add(i)
            row.update(
                ledger_id=i,
                entry_time_utc=trade["entry_time_utc"],
                entry=trade["entry"],
                initial_stop=trade["initial_stop"],
            )
        row["features"]["room"] = room(
            row["features"]["sr"], raw, row["entry"], row["initial_stop"]
        )
        if trade is not None:
            row["outcome"] = {
                k: trade[k]
                for k in ("net", "reason", "held_bars", "mae_usd", "mfe_usd", "exit_time_utc")
            }
        rows.append(row)
    if len(linked) != len(trades):
        raise ValueError("ledger coverage mismatch")
    return rows


def report(rows):
    """Frozen descriptive bins, separate denominators; no counterfactual equity."""
    output = dict(
        signals=len(rows),
        visited=sum(r["visited"] for r in rows),
        executed=sum(r["ledger_id"] is not None for r in rows),
        reasons=dict(Counter(r["admission_reason"] for r in rows)),
        groups=[],
    )
    bins = {
        "room": ([1, 2], ["<1", "[1,2)", ">=2"]),
        "daily": ([0, 1], ["<0", "[0,1)", ">=1"]),
        "sd": ([-2, 0, 2], ["<-2", "[-2,0)", "[0,2)", ">=2"]),
    }
    for direction in (1, -1):
        selected = [r for r in rows if r["direction"] == direction]
        for name, (bounds, labels) in bins.items():
            groups = {label: [] for label in labels}
            for row in selected:
                feature = row["features"][name]
                value = feature.get("value" if name == "room" else "adjusted")
                label = (
                    feature["status"] if value is None else labels[sum(value >= b for b in bounds)]
                )
                groups.setdefault(label, []).append(row)
            for label, members in groups.items():
                nets = [r["outcome"]["net"] for r in members if r["outcome"] is not None]
                output["groups"].append(
                    dict(
                        direction=direction,
                        feature=name,
                        bin=label,
                        signal_denominator=len(selected),
                        signals=len(members),
                        trades=len(nets),
                        wins=sum(n > 0 for n in nets),
                        losses=sum(n < 0 for n in nets),
                        flats=sum(n == 0 for n in nets),
                        net_total=sum(nets) if nets else None,
                        net_mean=sum(nets) / len(nets) if nets else None,
                    )
                )
    return output
