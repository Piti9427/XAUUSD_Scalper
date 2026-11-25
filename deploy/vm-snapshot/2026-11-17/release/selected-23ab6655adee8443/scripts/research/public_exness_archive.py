"""Acquire public Exness Bid/Ask archives, seal holdout, audit discovery only.

Public archive feed is indicative, not proof of target Demo execution parity.
No broker credentials, order API, inferred Ask or forward-filled bars.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import urlopen
import zipfile

import numpy as np
import pandas as pd

from scripts.research.data import bars as aggregate_bars
from scripts.research.tune_breakout_logic import sha256

BASE = "https://ticks.ex2archive.com/ticks/XAUUSDm"


def months(start, end):
    current = pd.Timestamp(start + "-01", tz="UTC")
    finish = pd.Timestamp(end + "-01", tz="UTC")
    while current < finish:
        yield current.strftime("%Y-%m")
        current += pd.DateOffset(months=1)


def acquire(root, month):
    year, number = month.split("-")
    name = f"Exness_XAUUSDm_{year}_{number}.zip"
    path = root / name
    url = f"{BASE}/{year}/{number}/{name}"
    if not path.exists():
        pending = path.with_suffix(".part")
        with urlopen(url, timeout=60) as response, pending.open("wb") as output:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                output.write(chunk)
        pending.replace(path)
    expected = name[:-4] + ".csv"
    with zipfile.ZipFile(path) as archive:
        if archive.namelist() != [expected] or archive.getinfo(expected).file_size > 2 * 1024**3:
            raise ValueError("unexpected archive layout/size")
    print(f"Archive {month} bytes={path.stat().st_size}", flush=True)
    return dict(month=month, url=url, file=name, sha256=sha256(path), bytes=path.stat().st_size)


def import_month(root, item):
    """Stream full discovery CSV and preserve every quoted tick in source order."""
    path = root / item["file"]
    if sha256(path) != item["sha256"]:
        raise ValueError("archive hash changed")
    start = pd.Timestamp(item["month"] + "-01", tz="UTC")
    end = start + pd.DateOffset(months=1)
    begin_ms, end_ms = start.value // 10**6, end.value // 10**6
    segments = []
    previous = None
    with zipfile.ZipFile(path) as archive, archive.open(item["file"][:-4] + ".csv") as stream:
        for chunk in pd.read_csv(stream, chunksize=300000, float_precision="round_trip"):
            if list(chunk.columns) != ["Exness", "Symbol", "Timestamp", "Bid", "Ask"]:
                raise ValueError("unexpected tick CSV schema")
            if (
                (chunk.Exness != "exness").any()
                or (chunk.Symbol != "XAUUSDm").any()
                or not chunk.Timestamp.str.endswith("Z").all()
            ):
                raise ValueError("wrong provider/symbol or non-UTC timestamps")
            t = (
                pd.DatetimeIndex(pd.to_datetime(chunk.Timestamp, format="ISO8601", utc=True))
                .as_unit("ms")
                .asi8
            )
            b, a = chunk.Bid.to_numpy(dtype=float), chunk.Ask.to_numpy(dtype=float)
            if (
                not np.isfinite(b).all()
                or not np.isfinite(a).all()
                or (b <= 0).any()
                or (a < b).any()
                or (np.diff(t) < 0).any()
                or (t < begin_ms).any()
                or (t >= end_ms).any()
                or (previous is not None and t[0] < previous)
            ):
                raise ValueError("invalid/crossed/out-of-range/unsorted ticks")
            previous = int(t[-1])
            segments.append((t, b, a))
    if not segments:
        raise ValueError("empty month is not history")
    t, b, a = (np.concatenate([s[i] for s in segments]) for i in range(3))
    minute = t // 60000
    first = np.r_[0, np.flatnonzero(np.diff(minute)) + 1]
    last = np.r_[first[1:] - 1, len(t) - 1]
    minutes_frame = pd.DataFrame(
        dict(
            bid_open=b[first],
            bid_high=np.maximum.reduceat(b, first),
            bid_low=np.minimum.reduceat(b, first),
            bid_close=b[last],
        ),
        index=pd.to_datetime(minute[first] * 60000, unit="ms", utc=True),
    )
    canonical = aggregate_bars(minutes_frame)
    cache = root / "discovery" / (item["month"] + ".npz")
    np.savez_compressed(cache, time=t, bid=b, ask=a)
    days, counts = np.unique(t // 86400000, return_counts=True)
    audit = dict(
        item,
        ticks=len(t),
        first_utc=pd.Timestamp(int(t[0]), unit="ms", tz="UTC").isoformat(),
        last_utc=pd.Timestamp(int(t[-1]), unit="ms", tz="UTC").isoformat(),
        nonempty_days=len(days),
        daily_ticks={
            str(pd.Timestamp(int(d) * 86400000, unit="ms", tz="UTC").date()): int(n)
            for d, n in zip(days, counts)
        },
        cache_sha256=sha256(cache),
        canonical_bars=len(canonical),
    )
    print(f"Audited {item['month']} ticks={len(t)} canonical={len(canonical)}", flush=True)
    return audit, canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", default="2024-09")
    parser.add_argument("--end", default="2025-10", help="exclusive month")
    parser.add_argument("--holdout-from", default="2025-07")
    args = parser.parse_args()
    catalog = list(months(args.start, args.end))
    if len(catalog) < 13 or not args.start < args.holdout_from < args.end:
        parser.error("need >=13 monthly archives and increasing discovery/holdout bounds")
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    if (root / "dataset.json").exists():
        raise ValueError("completed dataset already exists; never overwrite")
    with ThreadPoolExecutor(max_workers=3) as pool:
        archives = list(pool.map(lambda month: acquire(root, month), catalog))
    manifest = dict(
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        provider="Exness public indicative tick history",
        endpoint=BASE,
        symbol="XAUUSDm",
        target_demo_parity_verified=False,
        discovery_start=args.start + "-01",
        discovery_end=args.holdout_from + "-01",
        holdout_start=args.holdout_from + "-01",
        holdout_end=args.end + "-01",
        holdout_policy="downloaded zipped source only; no indicators/trades/selection evaluated",
        archives=archives,
        imported_months=[],
    )
    (root / "archive-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (root / "discovery").mkdir(exist_ok=True)
    audits, frames = [], []
    for item in archives:
        if item["month"] >= args.holdout_from:
            continue
        audit, frame = import_month(root, item)
        audits.append(audit)
        frames.append(frame)
    total = sum(a["ticks"] for a in audits)
    tape = root / "discovery" / "tape"
    tape.mkdir(exist_ok=True)
    for key, dtype in [("time", "int64"), ("bid", "float64"), ("ask", "float64")]:
        output = np.lib.format.open_memmap(
            tape / (key + ".npy"), mode="w+", dtype=dtype, shape=(total,)
        )
        offset = 0
        for item in audits:
            with np.load(root / "discovery" / (item["month"] + ".npz")) as month:
                values = month[key]
                output[offset : offset + len(values)] = values
                offset += len(values)
        output.flush()
        del output
    bars = pd.concat(frames)
    bars.to_csv(root / "discovery" / "bars.csv", index_label="bar_open_utc")
    broker_source = Path("data/b1_hybrid_exness_6mo_fixed_2026_09_28/manifest.json")
    broker = json.loads(broker_source.read_text())
    dataset = dict(
        manifest,
        imported_months=audits,
        discovery_ticks=total,
        verified_nonempty_discovery_months=len(audits),
        holdout_nonempty_coverage_verified=False,
        broker_spec_is_research_assumption=True,
        broker_spec_source_sha256=sha256(broker_source),
        broker=dict(broker["symbol_spec"], leverage=broker["account"]["leverage"]),
        artifacts={
            "discovery/bars.csv": sha256(root / "discovery/bars.csv"),
            **{
                f"discovery/tape/{k}.npy": sha256(tape / (k + ".npy"))
                for k in ("time", "bid", "ask")
            },
        },
    )
    (root / "dataset.json").write_text(json.dumps(dataset, indent=2) + "\n")
    print(
        json.dumps(
            {
                "stage": "discovery_ready_holdout_sealed",
                "ticks": total,
                "canonical_bars": len(bars),
                "imported_months": len(audits),
                "sealed_months": len(archives) - len(audits),
            }
        ),
        flush=True,
    )


def load_discovery(root):
    """Verify imported source/tape hashes; never access held-out prices."""
    root = Path(root)
    meta = json.loads((root / "dataset.json").read_text())
    for item in meta["imported_months"]:
        if sha256(root / item["file"]) != item["sha256"]:
            raise ValueError("discovery archive changed")
    for name, digest in meta["artifacts"].items():
        if sha256(root / name) != digest:
            raise ValueError("discovery artifact changed")
    raw = pd.read_csv(root / "discovery/bars.csv")
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw.pop("bar_open_utc"), utc=True))
    ticks = [
        np.load(root / f"discovery/tape/{k}.npy", mmap_mode="r") for k in ("time", "bid", "ask")
    ]
    if len(ticks[0]) != meta["discovery_ticks"] or (np.diff(ticks[0]) < 0).any():
        raise ValueError("discovery tape chronology/count mismatch")
    from scripts.research.breakout_logic import features

    audit = dict(
        dataset_path=str(root),
        dataset_sha256=sha256(root / "dataset.json"),
        artifacts=meta["artifacts"],
        raw_ticks=meta["discovery_ticks"],
        canonical_bars=len(raw),
        start_utc=meta["discovery_start"],
        end_utc=meta["discovery_end"],
        public_indicative_feed=True,
        target_demo_parity_verified=False,
        historical_holdout_not_prospective=True,
        holdout_prices_accessed=False,
    )
    return features(raw), ticks, meta["broker"], audit


if __name__ == "__main__":
    main()
