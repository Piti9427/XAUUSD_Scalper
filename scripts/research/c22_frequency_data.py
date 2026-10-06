"""Fresh current-month acquisition plus immutable historical prefix, no gap filling."""

from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd

from scripts.research.c22_context_campaign import digest, read, require, verify_baseline
from scripts.research.public_exness_archive import BASE, acquire, import_month, months
from scripts.research.reward156_tuning import atomic_json
from scripts.research.c22_tuning_data import clone_tape


def load_bars(path):
    frame = pd.read_csv(path)
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.pop("bar_open_utc"), utc=True))
    return frame


def verify_input(root):
    manifest = read(root / "manifest.json")
    for name, expected in manifest["artifacts"].items():
        require(digest(root / name) == expected, "input artifact drift: " + name)
    return manifest


def prepare_input(baseline, root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if (root / "manifest.json").exists():
        return verify_input(root)
    original, old, hashes = verify_baseline(baseline)
    request = root / "request.json"
    if request.exists():
        requested = read(request)
    else:
        requested = dict(
            requested_end_utc=datetime.now(timezone.utc).isoformat(),
            requested_start_utc=original["start"],
            baseline_hashes=hashes,
        )
        atomic_json(request, requested)
    require(requested["baseline_hashes"] == hashes, "acquisition baseline drift")
    end = pd.Timestamp(requested["requested_end_utc"])
    historical_end = pd.Timestamp(old["last_quote_utc"]).normalize().replace(day=1)
    # Never reuse the old campaign's partial-month cache. Every newly needed
    # month is fetched into this campaign; a resumed request retains its cutoff.
    month_list = list(
        months(historical_end.strftime("%Y-%m"), (end + pd.DateOffset(months=1)).strftime("%Y-%m"))
    )
    listing_path = root / "archive-listing.json"
    if not listing_path.exists():
        import json

        with urlopen(BASE + "/", timeout=60) as response:
            listing = json.load(response)
        atomic_json(
            listing_path,
            dict(
                url=BASE + "/",
                checked_utc=datetime.now(timezone.utc).isoformat(),
                entries=listing,
                start_is_scope_not_earliest_claim=True,
            ),
        )
    (root / "discovery").mkdir(exist_ok=True)
    imported, frames = [], []
    for month in month_list:
        item_path = root / (month + "-download.json")
        if item_path.exists():
            item = read(item_path)
            require(digest(root / item["file"]) == item["sha256"], "download drift")
        else:
            require(
                not list(root.glob(f"Exness_XAUUSDm_{month.replace('-', '_')}.zip")),
                "unbound archive; use fresh campaign input directory",
            )
            item = acquire(root, month)
            atomic_json(item_path, item)
        audit_path = root / (month + "-audit.json")
        bars_path = root / (month + "-bars.csv")
        if audit_path.exists():
            audit = read(audit_path)
            require(
                digest(root / "discovery" / (month + ".npz")) == audit["cache_sha256"]
                and digest(bars_path) == audit["bars_sha256"],
                "monthly import drift",
            )
            frame = load_bars(bars_path)
        else:
            audit, frame = import_month(root, item)
            frame.to_csv(bars_path, index_label="bar_open_utc")
            audit["bars_sha256"] = digest(bars_path)
            atomic_json(audit_path, audit)
        imported.append(audit)
        frames.append(frame)
    source = baseline / "input/continuous-tape"
    historical_times = np.load(source / "time.npy", mmap_mode="r")
    cutoff = int(np.searchsorted(historical_times, historical_end.value // 10**6))
    end_ms = end.value // 10**6
    lengths = []
    for item in imported:
        with np.load(root / "discovery" / (item["month"] + ".npz")) as tape:
            lengths.append(int(np.searchsorted(tape["time"], end_ms)))
    total = cutoff + sum(lengths)
    tape_root = root / "tape"
    tape_root.mkdir(exist_ok=True)
    for key in ("time", "bid", "ask"):
        target = tape_root / (key + ".npy")
        # No complete manifest exists here: these are owned, incomplete writes.
        # COW clone preserves historical prefix without duplicating all tape pages.
        target.unlink(missing_ok=True)
        output = clone_tape(source / (key + ".npy"), target, total)
        offset = cutoff
        for item, length in zip(imported, lengths):
            with np.load(root / "discovery" / (item["month"] + ".npz")) as tape:
                output[offset : offset + length] = tape[key][:length]
                offset += length
        output.flush()
        del output
    historical_bars = load_bars(baseline / "input/continuous-bars.csv")
    bars = pd.concat([historical_bars.loc[historical_bars.index < historical_end], *frames])
    bars = bars.loc[bars.index + pd.Timedelta(minutes=15) <= end]
    require(
        bars.index.is_monotonic_increasing and not bars.index.has_duplicates, "bar seam overlap"
    )
    bars.to_csv(root / "bars.csv", index_label="bar_open_utc")
    times = np.load(tape_root / "time.npy", mmap_mode="r")
    for offset in range(0, total, 1000000):
        require(
            not (np.diff(times[max(0, offset - 1) : offset + 1000000]) < 0).any(),
            "tick seam overlap",
        )
    manifest = dict(
        requested_start_utc=original["start"],
        requested_end_utc=end.isoformat(),
        actual_first_quote=pd.Timestamp(int(times[0]), unit="ms", tz="UTC").isoformat(),
        actual_last_quote=pd.Timestamp(int(times[-1]), unit="ms", tz="UTC").isoformat(),
        historical_prefix_ticks=cutoff,
        ticks=total,
        bars=len(bars),
        imported_months=imported,
        broker=old["broker"],
        costs=original["costs"],
        baseline_hashes=hashes,
        costs_status="COST_INCONCLUSIVE",
        fill_missing=False,
        artifacts={
            str(p.relative_to(root)): digest(p)
            for p in sorted(root.rglob("*"))
            if p.is_file() and p.suffix != ".part"
        },
    )
    atomic_json(root / "manifest.json", manifest)
    return manifest
