"""Causal completed M15 setups and complete Bid M5 trigger bars, research only."""

from pathlib import Path
import json
import numpy as np
import pandas as pd
from scripts.research.data import bars
from scripts.research.tune_breakout_logic import sha256


def build_m5(ticks, output, dataset_sha256):
    """Aggregate actual minute quotes; exclude any M5 missing one minute."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cache, marker = output / "bars.csv", output / "manifest.json"
    if marker.exists():
        meta = json.loads(marker.read_text())
        if (
            meta["dataset_sha256"] != dataset_sha256
            or meta["builder_sha256"] != sha256(__file__)
            or meta["bars_sha256"] != sha256(cache)
        ):
            raise ValueError("M5 cache provenance mismatch")
        frame = pd.read_csv(cache, float_precision="round_trip")
        frame.index = pd.to_datetime(frame.pop("bar_open_utc"), utc=True)
        return frame
    times, bid, _ = ticks
    first_month = pd.Timestamp(int(times[0]), unit="ms", tz="UTC").normalize().replace(day=1)
    last = pd.Timestamp(int(times[-1]), unit="ms", tz="UTC")
    frames = []
    for month in pd.date_range(first_month, last, freq="MS"):
        following = month + pd.offsets.MonthBegin(1)
        left, right = np.asarray(
            np.searchsorted(
                times, np.asarray([month.value // 10**6, following.value // 10**6], dtype=np.int64)
            )
        )
        t, b = times[left:right], bid[left:right]
        if not len(t):
            continue
        minute = t // 60000
        first = np.r_[0, np.flatnonzero(np.diff(minute)) + 1]
        end = np.r_[first[1:] - 1, len(t) - 1]
        m1 = pd.DataFrame(
            dict(
                bid_open=b[first],
                bid_high=np.maximum.reduceat(b, first),
                bid_low=np.minimum.reduceat(b, first),
                bid_close=b[end],
            ),
            index=pd.to_datetime(minute[first] * 60000, unit="ms", utc=True),
        )
        frames.append(bars(m1, minutes=5))
    frame = pd.concat(frames)
    frame.to_csv(cache, index_label="bar_open_utc", float_format="%.17g")
    marker.write_text(
        json.dumps(
            dict(
                dataset_sha256=dataset_sha256,
                builder_sha256=sha256(__file__),
                bars_sha256=sha256(cache),
                complete_m5_bars=len(frame),
            ),
            indent=2,
        )
        + "\n"
    )
    return frame


def retest_frame(setups, m5, ttl, *, buy_only=False):
    """A pending setup consumes at most ttl complete M5 bars after availability."""
    if ttl not in (2, 4):
        raise ValueError("unsupported M5 TTL")
    for frame in (setups, m5):
        if (
            frame.index.tz is None
            or str(frame.index.tz) != "UTC"
            or frame.index.has_duplicates
            or not frame.index.is_monotonic_increasing
        ):
            raise ValueError("M5/M15 bars require ordered unique UTC timestamps")
    available = setups.index + pd.Timedelta(minutes=15)
    cursor, latest, pending = 0, None, None
    records = []
    management_times = set(available)
    for candle in m5.itertuples():
        stamp = candle.Index + pd.Timedelta(minutes=5)
        while cursor < len(setups) and available[cursor] <= stamp:
            setup = setups.iloc[cursor]
            latest = setup
            if setup.direction:
                direction = int(setup.direction)
                if buy_only and direction == -1:
                    pending = None
                elif pending is None or pending[0] != direction:
                    pending = (direction, setup, available[cursor], 0)
            cursor += 1
        if latest is None:
            continue
        row = dict(
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            hh=latest.hh,
            ll=latest.ll,
            atr=latest.atr,
            direction=0,
            management_bar=stamp in management_times,
        )
        if buy_only and row["management_bar"] and latest.direction == -1:
            row["direction"] = -1
        if pending is not None and candle.Index >= pending[2]:
            direction, setup, born, count = pending
            boundary = setup.hh if direction == 1 else setup.ll
            beyond = direction * (candle.close - boundary) > 0
            touched = candle.low <= boundary if direction == 1 else candle.high >= boundary
            if beyond and touched:
                row.update(direction=direction, hh=setup.hh, ll=setup.ll, atr=setup.atr)
                pending = None
            elif direction * (candle.close - boundary) < 0 or count + 1 >= ttl:
                pending = None
            else:
                pending = (direction, setup, born, count + 1)
        records.append((candle.Index, row))
    if not records:
        raise ValueError("no overlapping completed M15/M5 bars")
    return pd.DataFrame([r for _, r in records], index=pd.DatetimeIndex([t for t, _ in records]))
