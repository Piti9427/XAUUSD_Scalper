"""Audit captured Demo quotes and record frozen challenger signals; never trade."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from .shadow_capture import sha256, utc_time
from .strategies import features, registry, signals


CHALLENGERS = ("GSS_OTE__h1structure", "Donchian20_H4", "AsianRetest__h1ema")
TICK_COLUMNS = ("time_msc", "bid", "ask", "flags")
# Intentional freeze of the audited research signal implementation and bar builder.
FROZEN_CODE_SHA256 = {
    "strategies.py": "4f4157bbeafb5458ce3bbf3a1b4a1d1b4d62dc61ff99c1ba46372614d07a6d3f",
    "data.py": "541d00d3836454034ea77b9ed66b4a8386c391a0929ec87e013f502a4e8eeffe",
}


def load_capture(folder: Path) -> tuple[dict, pd.DataFrame]:
    """Read only a sealed capture; reject edits, missing identity, and bad quotes."""
    if not (folder / "COMPLETE").is_file():
        raise ValueError(f"capture lacks COMPLETE: {folder}")
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest.get("schema") != "btg-shadow-ticks-v1" or manifest.get("order_api_called") is not False:
        raise ValueError("invalid read-only capture manifest")
    if manifest.get("tick_file") != "ticks.csv.gz":
        raise ValueError("unexpected tick filename")
    path = folder / "ticks.csv.gz"
    if sha256(path) != manifest.get("tick_sha256"):
        raise ValueError("capture tick hash mismatch")
    freeze = utc_time(manifest["freeze_at"])
    start = utc_time(manifest["requested_start"])
    end = utc_time(manifest["requested_end"])
    if start < freeze or not start < end or end - start > timedelta(days=1):
        raise ValueError("invalid capture window")
    rows = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not set(TICK_COLUMNS).issubset(reader.fieldnames or ()):
            raise ValueError("capture lacks required tick fields")
        for row in reader:
            stamp = int(row["time_msc"])
            bid, ask = float(row["bid"]), float(row["ask"])
            if (stamp < int(start.timestamp() * 1000)
                    or stamp > int(end.timestamp() * 1000)
                    or not math.isfinite(bid) or not math.isfinite(ask)
                    or bid <= 0 or ask < bid):
                raise ValueError("invalid captured quote or timestamp")
            rows.append((stamp, bid, ask, int(row["flags"])))
    if not rows or len(rows) != manifest.get("tick_count"):
        raise ValueError("capture tick count mismatch")
    if rows[0][0] != manifest.get("first_tick_msc") or rows[-1][0] != manifest.get("last_tick_msc"):
        raise ValueError("capture endpoint mismatch")
    if any(b[0] < a[0] for a, b in zip(rows, rows[1:])):
        raise ValueError("captured ticks are unordered")
    return manifest, pd.DataFrame(rows, columns=TICK_COLUMNS)


def minute_bars(ticks: pd.DataFrame) -> pd.DataFrame:
    """Observed quote bars only. No synthetic minute, forward fill, or execution."""
    frame = ticks.copy()
    frame.index = pd.to_datetime(frame.time_msc, unit="ms", utc=True)
    bid = frame.bid.resample("1min", label="left", closed="left").ohlc()
    ask = frame.ask.resample("1min", label="left", closed="left").ohlc()
    return bid.add_prefix("bid_").join(ask.add_prefix("ask_")).dropna()


def record_signals(captures: list[Path], output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    if not captures:
        raise ValueError("at least one sealed capture is required")
    loaded = [load_capture(path) for path in captures]
    identity = [
        (m["account"]["login"], m["account"]["server"],
         m["account"]["currency"], m["account"]["trade_mode"],
         m["symbol"], m["symbol_specification"], m["freeze_at"])
        for m, _ in loaded
    ]
    if any(value != identity[0] for value in identity[1:]):
        raise ValueError("capture account/symbol/freeze mismatch")
    windows = sorted((utc_time(m["requested_start"]), utc_time(m["requested_end"])) for m, _ in loaded)
    if any(right[0] < left[1] for left, right in zip(windows, windows[1:])):
        raise ValueError("overlapping capture windows")
    ticks = pd.concat([frame for _, frame in loaded], ignore_index=True).sort_values(
        "time_msc", kind="stable"
    )
    identical_ticks = int(ticks.duplicated(subset=list(TICK_COLUMNS)).sum())
    m1 = minute_bars(ticks)
    if m1.empty:
        raise ValueError("no observed quote minute")
    minute_gaps = int((m1.index.to_series().diff() > pd.Timedelta(minutes=1)).sum())
    for filename, frozen_sha in FROZEN_CODE_SHA256.items():
        if sha256(Path(__file__).with_name(filename)) != frozen_sha:
            raise ValueError(f"frozen signal code changed: {filename}")
    specs = {spec.name: spec for spec in registry() if spec.name in CHALLENGERS}
    if set(specs) != set(CHALLENGERS) or any(specs[name].entry != "market" for name in CHALLENGERS):
        raise ValueError("frozen challenger registry changed")
    records = []
    for name in CHALLENGERS:
        spec = specs[name]
        frame = features(m1, spec.timeframe)
        direction = signals(frame, spec).direction
        for bar_open, side in direction[direction != 0].items():
            available = bar_open + pd.Timedelta(minutes=spec.timeframe)
            records.append({
                "strategy": name,
                "bar_open_utc": bar_open.isoformat(),
                "signal_available_utc": available.isoformat(),
                "side": "buy" if side == 1 else "sell",
                "atr": float(frame.loc[bar_open, "atr"]),
                "signal_only": True,
                "qualification_status": "INCONCLUSIVE",
            })
    records.sort(key=lambda row: (row["signal_available_utc"], row["strategy"]))
    output.mkdir(parents=True)
    ledger = output / "signals.csv"
    fields = ("strategy", "bar_open_utc", "signal_available_utc", "side", "atr",
              "signal_only", "qualification_status")
    with ledger.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    audit = {
        "schema": "btg-shadow-signals-v1",
        "status": "INCONCLUSIVE",
        "scope": "signals only; no orders, fills, P&L, or qualification",
        "order_api_called": False,
        "frozen_signal_code_sha256": FROZEN_CODE_SHA256,
        "monitor_code_sha256": sha256(Path(__file__)),
        "captured_inputs": [
            {"manifest_sha256": sha256(path / "manifest.json"),
             "tick_sha256": m["tick_sha256"], "folder": str(path)}
            for path, (m, _) in zip(captures, loaded)
        ],
        "account": loaded[0][0]["account"],
        "symbol": loaded[0][0]["symbol"],
        "symbol_specification": loaded[0][0]["symbol_specification"],
        "freeze_at": loaded[0][0]["freeze_at"],
        "tick_count": len(ticks),
        "identical_tick_rows": identical_ticks,
        "observed_m1_minutes": len(m1),
        "minute_gaps": minute_gaps,
        "strategy_contracts": [asdict(specs[name]) for name in CHALLENGERS],
        "signal_count": len(records),
        "signals_sha256": sha256(ledger),
    }
    (output / "manifest.json").write_text(json.dumps(audit, indent=2) + "\n")
    (output / "COMPLETE").write_text("Signals audited; no simulated trades.\n")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = record_signals(args.capture, args.output)
    print(json.dumps({key: result[key] for key in
                      ("status", "symbol", "tick_count", "signal_count", "minute_gaps")}))


if __name__ == "__main__":
    main()
