"""Pinned public CSV acquisition and strict UTC Bid/Ask validation."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen
import numpy as np
import pandas as pd

SOURCE = "https://raw.githubusercontent.com/kevingtlin/Market-Data-Lab"
REVISION = "922f83a60cc574e7395fb27397077288055a1ef6"
OHLC = ["open", "high", "low", "close"]


def acquire(cache, years, download=True):
    """Download immutable revision; preserve checksums alongside inputs."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    jobs = [
        (y, m, s)
        for y in years
        for m in range(1, 13)
        if (y, m) <= (2026, 8)
        for s in ("bid", "ask")
    ]

    def fetch(job):
        y, m, side = job
        name = f"xauusd_{side}_m1_{y}_{m:02}.csv"
        path = cache / name
        url = f"{SOURCE}/{REVISION}/xauusd/{side}/m1/{name}"
        metadata = path.with_suffix(".source.json")
        if path.exists():
            if not metadata.exists():
                raise ValueError(f"Unverified cache file: {path}")
            old = json.loads(metadata.read_text())
            if (
                old["url"] != url
                or old["sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()
            ):
                raise ValueError(f"Cache integrity failure: {path}")
            return old
        if not download:
            raise FileNotFoundError(f"Missing cached input: {path}; use --download")
        with urlopen(url, timeout=90) as response:
            raw = response.read()
        if not raw.startswith(b"timestamp,open,high,low,close"):
            raise ValueError(f"Unexpected source schema: {url}")
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(raw)
        tmp.replace(path)
        result = {
            "file": name,
            "url": url,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        metadata.write_text(json.dumps(result, indent=2))
        return result

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(fetch, jobs))


def validate_side(df):
    if list(df.columns) != ["timestamp"] + OHLC:
        raise ValueError("Expected timestamp,open,high,low,close")
    idx = pd.to_datetime(df.timestamp, unit="ms", utc=True)
    if idx.isna().any() or idx.duplicated().any() or not idx.is_monotonic_increasing:
        raise ValueError("Invalid, duplicate or unordered timestamps")
    if not (
        idx.dt.second.eq(0) & idx.dt.microsecond.eq(0) & idx.dt.nanosecond.eq(0)
    ).all():
        raise ValueError("Not minute aligned")
    values = df[OHLC].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Nonfinite/nonpositive prices")
    o, h, low_prices, c = values.T
    if (
        (h < np.maximum(o, c)) | (low_prices > np.minimum(o, c)) | (h < low_prices)
    ).any():
        raise ValueError("Invalid OHLC geometry")
    return pd.DataFrame(values, columns=OHLC, index=pd.DatetimeIndex(idx))


def load_year(cache, year):
    sides = {}
    for side in ("bid", "ask"):
        paths = sorted(Path(cache).glob(f"xauusd_{side}_m1_{year}_*.csv"))
        expected = 8 if year == 2026 else 12
        if len(paths) != expected:
            raise ValueError(
                f"{year} {side}: expected {expected} monthly files, got {len(paths)}"
            )
        sides[side] = validate_side(
            pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
        )
    bid, ask = sides["bid"], sides["ask"]
    common = bid.index.intersection(ask.index)
    mismatch = len(bid) + len(ask) - 2 * len(common)
    # Preserve explicit audit of missing-side timestamps; never forward-fill prices.
    paired = bid.loc[common].add_prefix("bid_").join(ask.loc[common].add_prefix("ask_"))
    for field in ("open", "close"):
        if (paired[f"ask_{field}"] < paired[f"bid_{field}"]).any():
            raise ValueError("Crossed contemporaneous Bid/Ask")
    spread = paired.ask_open - paired.bid_open
    audit = {
        "year": year,
        "bid_rows": len(bid),
        "ask_rows": len(ask),
        "matched_rows": len(paired),
        "unmatched_rows": mismatch,
        "start": str(common.min()),
        "end": str(common.max()),
        "flat_bid_minutes": int((paired.bid_high == paired.bid_low).sum()),
        "spread_open_median": float(spread.median()),
        "spread_open_p90": float(spread.quantile(0.9)),
        "spread_open_p99": float(spread.quantile(0.99)),
        "gaps_over_1_minute": int(
            (common.to_series().diff() > pd.Timedelta(minutes=1)).sum()
        ),
    }
    if mismatch / max(len(bid), 1) > 0.001:
        raise ValueError("More than 0.1% timestamps have no paired side")
    return paired, audit


def bars(m1, minutes=15):
    bid = m1[[f"bid_{c}" for c in OHLC]].copy()
    bid.columns = OHLC
    rule = f"{minutes}min"
    result = bid.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    counts = bid.close.resample(rule).count()
    # Incomplete bars are absent, never fabricated; next-open execution requires exact timestamp.
    return result.loc[counts == minutes].dropna()
