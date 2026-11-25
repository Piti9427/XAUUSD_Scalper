"""Verified restart seed for complete Bid M15; never an order/data-gap bypass."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
from io import StringIO
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = ["open", "high", "low", "close"]
AGGREGATION = "UTC_BID_M15_FROM_15_COMPLETE_M1_V1"


def _utc(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("UTC clock required")
    return value


def _binding(fingerprint, config):
    if not isinstance(fingerprint, str) or len(fingerprint) != 16:
        raise ValueError("account fingerprint required")
    return dict(version=1, aggregation=AGGREGATION, account_fingerprint=fingerprint,
                symbol=config["symbol"], contract_id=config["contract_id"],
                config_sha256=hashlib.sha256(json.dumps(config, sort_keys=True, allow_nan=False).encode()).hexdigest())


def _validate(bars, now):
    now = _utc(now)
    if not isinstance(bars.index, pd.DatetimeIndex) or str(bars.index.tz) != "UTC":
        raise ValueError("UTC index required")
    if bars.empty or bars.index.has_duplicates or not bars.index.is_monotonic_increasing:
        raise ValueError("invalid chronology")
    if not bars.index.equals(bars.index.floor("15min")):
        raise ValueError("unaligned M15")
    frame = bars[COLUMNS].astype(float)
    if not np.isfinite(frame.to_numpy()).all() or (frame <= 0).any().any():
        raise ValueError("invalid prices")
    if ((frame.high < frame[["open", "close", "low"]].max(axis=1)) |
            (frame.low > frame[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("invalid OHLC geometry")
    if frame.index[-1] + pd.Timedelta(minutes=15) > now:
        raise ValueError("unclosed or future bar")
    return frame


def _read(raw, now):
    bars = pd.read_csv(StringIO(raw.decode("utf-8")), index_col=0, float_precision="round_trip")
    bars.index = pd.to_datetime(bars.index)
    return _validate(bars, now)


def _same(left, right):
    return left.index.equals(right.index) and np.array_equal(left[COLUMNS].to_numpy(), right[COLUMNS].to_numpy())


def merge_history(saved, fresh):
    """Backfill only outside the validated prefix; preserve every known bar."""
    start = max(saved.index[0], fresh.index[0])
    end = min(saved.index[-1], fresh.index[-1])
    if start > end or not _same(saved.loc[start:end], fresh.loc[start:end]):
        raise ValueError("bar_cache_divergence")
    return pd.concat([fresh.loc[fresh.index < saved.index[0]], saved,
                      fresh.loc[fresh.index > saved.index[-1]]])


def save_manifest(path, *, bars, fingerprint, config, now):
    """Bind an already atomically exported CSV. A torn pair is rejected on load."""
    path = Path(path)
    expected = _validate(bars, now)
    raw = path.read_bytes()
    if not _same(_read(raw, now), expected):
        raise ValueError("export differs from validated prefix")
    metadata = dict(_binding(fingerprint, config), created_utc=_utc(now).isoformat(),
                    sha256=hashlib.sha256(raw).hexdigest(), rows=len(expected),
                    first_bar_utc=expected.index[0].isoformat(),
                    last_bar_utc=expected.index[-1].isoformat())
    target = path.with_suffix(path.suffix + ".meta.json")
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, sort_keys=True, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(target)


def load_seed(path, *, recent, fingerprint, config, now):
    """Trust neither an old CSV alone nor cached prices without fresh overlap."""
    path = Path(path)
    try:
        meta = json.loads(path.with_suffix(path.suffix + ".meta.json").read_text())
        if not isinstance(meta, dict):
            return None, "invalid"
        if any(meta.get(k) != v for k, v in _binding(fingerprint, config).items()):
            return None, "binding_mismatch"
        if _utc(meta["created_utc"]) > _utc(now):
            return None, "future_metadata"
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
            return None, "content_hash_mismatch"
        saved = _read(raw, now)
        recent = _validate(recent, now)
        saved.index = saved.index.as_unit(recent.index.unit)
        saved.index.name = recent.index.name
        if (len(saved) != meta["rows"] or saved.index[0].isoformat() != meta["first_bar_utc"]
                or saved.index[-1].isoformat() != meta["last_bar_utc"]):
            return None, "range_mismatch"
        if recent.index[-1] < saved.index[-1]:
            return None, "broker_tail_behind_cache"
        overlap = saved.index.intersection(recent.index)
        if overlap.empty:
            return None, "no_broker_overlap"
        left = saved.loc[saved.index >= recent.index[0]]
        right = recent.loc[recent.index <= saved.index[-1]]
        if not _same(left, right):
            return None, "broker_overlap_divergence"
        tail = recent.loc[recent.index > saved.index[-1]]
        return pd.concat([saved, tail]) if not tail.empty else saved, "restored"
    except FileNotFoundError:
        return None, "missing"
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        return None, "invalid"
