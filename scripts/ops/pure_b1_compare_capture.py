#!/usr/bin/env python3
"""Compare immutable Pure B1 broker M15 capture with Bid ticks and saved reference."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts.pure_b1.parity import compare_bars, compare_signals, ticks_to_m15


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _bars(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.pop("bar_open_utc"), utc=True))
    return frame[["open", "high", "low", "close"]]


def compare_capture(capture: Path, reference: Path) -> dict:
    manifest = json.loads((capture / "manifest.json").read_text())
    m15 = capture / "m15_bid.csv"
    tick_file = capture / "ticks" / "ticks.csv.gz"
    tick_manifest = capture / "ticks" / "manifest.json"
    for file, key in (
        (m15, "m15_sha256"),
        (tick_file, "tick_sha256"),
        (tick_manifest, "tick_manifest_sha256"),
    ):
        if _digest(file) != manifest[key]:
            raise ValueError(f"capture hash mismatch: {file.name}")
    if manifest["schema"] not in {
        "pure-b1-broker-capture-v1",
        "pure-b1-broker-capture-v2",
    }:
        raise ValueError("unexpected capture schema")
    terminal = None
    if manifest["schema"] == "pure-b1-broker-capture-v2":
        for file, key in (
            (capture / "m1_bid.csv", "m1_sha256"),
            (capture / "m15_terminal.csv", "terminal_m15_sha256"),
        ):
            if _digest(file) != manifest[key]:
                raise ValueError(f"capture hash mismatch: {file.name}")
        terminal = _bars(capture / "m15_terminal.csv")
    broker = _bars(m15)
    with gzip.open(tick_file, "rt", encoding="utf-8") as handle:
        tick_bars = ticks_to_m15(pd.read_csv(handle))
    # Tick capture may start/end within a candle; compare only fully bounded bars.
    start = pd.Timestamp(manifest["requested_start_utc"])
    end = pd.Timestamp(manifest["requested_end_utc"])
    tick_bars = tick_bars[
        (tick_bars.index >= start) & (tick_bars.index + pd.Timedelta(minutes=15) <= end)
    ]
    reference_bars = _bars(reference)
    tick_result = compare_bars(broker, tick_bars, tolerance=0.001)
    reference_result = compare_bars(broker, reference_bars, tolerance=0.001)
    signal_result = compare_signals(broker, reference_bars)
    checks = (
        tick_result["status"],
        reference_result["status"],
        signal_result["status"],
    )
    return {
        "status": "RESEARCH_ONLY",
        "parity_gate": "PASS"
        if all(check == "PASS" for check in checks)
        else "FAIL"
        if "FAIL" in checks
        else "INCONCLUSIVE",
        "parity_code_sha256": _digest(
            Path(__file__).resolve().parents[1] / "pure_b1" / "parity.py"
        ),
        "compare_code_sha256": _digest(Path(__file__)),
        "capture_manifest_sha256": _digest(capture / "manifest.json"),
        "reference_sha256": _digest(reference),
        "broker_vs_ticks": tick_result,
        "terminal_vs_canonical": compare_bars(terminal, broker, tolerance=0.001)
        if terminal is not None
        else None,
        "broker_vs_reference": reference_result,
        "signal_parity": signal_result,
        "order_api_called": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path("data/b1_hybrid_baseline_6mo_fixed_2026_09_28/reference_bars.csv"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = compare_capture(args.capture, args.reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "parity_gate": result["parity_gate"],
                "broker_vs_ticks": result["broker_vs_ticks"]["status"],
                "broker_vs_reference": result["broker_vs_reference"]["status"],
                "signal_parity": result["signal_parity"]["status"],
                "order_api_called": False,
            }
        )
    )


if __name__ == "__main__":
    main()
