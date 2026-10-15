"""Finite, swap-inclusive economic comparison using actual shared MQL5 core."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
import pandas as pd
from scripts.research.native_frequency_replay import CASES, VIEWS, replay_case, monthly_metrics
from scripts.research.reward156_search import prepare_candidate
from scripts.research.c22_frequency_data import load_bars
from scripts.research.smc_challenger_adapter import swap_debits, validate_tape

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "runs/c22-tuning-loop-2026-10-07/campaign-01/input"
DEFAULT_OUTPUT = ROOT / "runs/native-frequency-economic-2026-10-14"
SOURCES = [
    "scripts/research/native_frequency_campaign.py",
    "scripts/research/native_frequency_replay.py",
    "scripts/research/native_frequency_bridge.cpp",
    "mql5/FrequencyResearchCore.mqh",
    "scripts/research/breakout_replay.py",
    "scripts/research/breakout_entry.py",
    "scripts/research/breakout_models.py",
    "scripts/research/rollover.py",
    "scripts/research/smc_challenger_adapter.py",
    "scripts/research/campaign_signals.py",
    "scripts/research/reward156_search.py",
    "scripts/research/reward156_tuning.py",
    "config/research-c22-qualified-b823f4aefe10fc72.json",
]


def verify_complete(out):
    marker = Path(out) / "COMPLETE.json"
    if not marker.exists():
        return
    for name, expected in json.loads(marker.read_text())["artifacts"].items():
        if digest(Path(out) / name) != expected:
            raise ValueError("completed artifact drift: " + name)


def require_fresh_output(out):
    """Incomplete runs are evidence only; rerun into a new directory."""
    if any(Path(out).iterdir()):
        raise ValueError("incomplete campaign requires fresh output directory")


def verify_repeats(out, cells):
    expected = {(name, view) for name in CASES for view in VIEWS}
    if set(cells) != expected:
        raise ValueError("incomplete economic cells")
    for (name, view), cell in cells.items():
        repeated = json.loads((Path(out) / "repeats" / (name + "-" + view + ".json")).read_text())
        if repeated != cell:
            raise ValueError("full-result repeat mismatch")
    return len(expected)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def prepare_minutes(ticks):
    """Vectorized bounded tick groups; carry same-minute seams before aggregation."""
    times, bid, _ = ticks
    blocks = []
    for begin in range(0, len(times), 2_000_000):
        stop = min(begin + 2_000_000, len(times))
        minute = times[begin:stop] // 60000
        starts = np.r_[0, np.flatnonzero(np.diff(minute)) + 1]
        ends = np.r_[starts[1:] - 1, len(minute) - 1]
        price = bid[begin:stop]
        blocks.append(
            np.column_stack(
                (
                    minute[starts],
                    price[starts],
                    np.maximum.reduceat(price, starts),
                    np.minimum.reduceat(price, starts),
                    price[ends],
                )
            )
        )
    groups = np.concatenate(blocks)
    stamps = groups[:, 0].astype(np.int64)
    starts = np.r_[0, np.flatnonzero(np.diff(stamps)) + 1]
    ends = np.r_[starts[1:] - 1, len(stamps) - 1]
    return pd.DataFrame(
        dict(
            open=groups[starts, 1],
            high=np.maximum.reduceat(groups[:, 2], starts),
            low=np.minimum.reduceat(groups[:, 3], starts),
            close=groups[ends, 4],
        ),
        index=pd.DatetimeIndex(pd.to_datetime(stamps[starts] * 60000, unit="ms", utc=True)),
    )


def bridge_frames(out, minutes, ticks, metadata):
    compiler = shutil.which("clang++") or shutil.which("g++")
    if compiler is None:
        raise ValueError("native C++ compiler missing")
    binary = out / "native-detector"
    subprocess.run(
        [
            compiler,
            "-O2",
            "-std=c++17",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(ROOT / "mql5"),
            str(ROOT / "scripts/research/native_frequency_bridge.cpp"),
            "-o",
            str(binary),
        ],
        check=True,
    )
    times, bid, ask = ticks
    decisions = minutes.index.as_unit("ms").asi8 + 60000
    idx = np.searchsorted(times, decisions)
    valid = idx < len(times)
    safe = np.minimum(idx, len(times) - 1)
    packet = out / "native-input.txt"
    with packet.open("w") as f:
        for i, (stamp, row) in enumerate(minutes.iterrows()):
            f.write(
                f"{int(stamp.timestamp())} {row.open:.17g} {row.high:.17g} {row.low:.17g} {row.close:.17g} {int(times[safe[i]]) if valid[i] else -1} {float(bid[safe[i]]):.17g} {float(ask[safe[i]]):.17g}\n"
            )
    source = out / "native-frames.csv"
    with packet.open() as stdin, source.open("w") as stdout:
        subprocess.run(
            [
                str(binary),
                str(int(pd.Timestamp(metadata["requested_start_utc"]).timestamp())),
                str(int(pd.Timestamp(metadata["requested_end_utc"]).timestamp())),
                str(metadata["broker"]["trade_tick_size"]),
            ],
            stdin=stdin,
            stdout=stdout,
            check=True,
        )
    columns = [
        "case_id",
        "utc",
        "open",
        "high",
        "low",
        "close",
        "atr",
        "direction",
        "raw_direction",
        "stop_anchor",
        "native_entry",
        "native_stop",
        "native_target",
    ]
    combined = pd.read_csv(source, names=columns, float_precision="round_trip")
    frames = {}
    for i, name in enumerate(CASES):
        frame = combined.loc[combined.case_id == i].drop(columns=["case_id", "utc"]).copy()
        frame.index = pd.DatetimeIndex(
            pd.to_datetime(combined.loc[combined.case_id == i, "utc"], unit="s", utc=True)
        )
        frame.to_csv(out / (name + ".csv"), index_label="bar_open_utc")
        frames[name] = frame
    # Full historical detector parity, not economic parity.
    frozen = load_bars(INPUT / "bars.csv")
    native = frames["c22_tuned"]
    frozen.index = frozen.index.as_unit("ms")
    native.index = native.index.as_unit("ms")
    pd.testing.assert_frame_equal(
        native[["open", "high", "low", "close"]],
        frozen[["open", "high", "low", "close"]],
        check_names=False,
        atol=1e-10,
        rtol=1e-12,
    )
    contract = json.loads(
        (ROOT / "config/research-c22-qualified-b823f4aefe10fc72.json").read_text()
    )
    reference, _ = prepare_candidate(frozen, contract)
    np.testing.assert_array_equal(native.raw_direction.to_numpy(), reference.direction.to_numpy())
    proof = dict(
        bars=len(native),
        native_core_sha256=digest(ROOT / "mql5/FrequencyResearchCore.mqh"),
        full_historical_detector_match=True,
        native_tester_economic_parity=False,
        directions={str(k): int(v) for k, v in reference.direction.value_counts().items()},
        binary_sha256=digest(binary),
    )
    write(out / "detector-parity.json", proof)
    return frames


def execute(task):
    out, name, view, meta = task
    out = Path(out)
    frame = load_bars(out / (name + ".csv"))
    ticks = tuple(
        np.load(INPUT / "tape" / (k + ".npy"), mmap_mode="r") for k in ["time", "bid", "ask"]
    )
    result = replay_case(
        frame,
        ticks,
        meta["broker"],
        strategy=name,
        view=view,
        start=pd.Timestamp(meta["requested_start_utc"]),
        end=pd.Timestamp(meta["requested_end_utc"]),
    )
    charges = swap_debits(result, meta["broker"])
    metrics = monthly_metrics(
        result,
        first_quote=pd.Timestamp(meta["actual_first_quote"]),
        last_quote=pd.Timestamp(meta["actual_last_quote"]),
    )
    return dict(case=name, view=view, metrics=metrics, result=result, swap_debits=charges)


def select(cells):
    paired = {name: {v: cells[(name, v)]["metrics"] for v in VIEWS} for name in CASES}
    baseline = paired["c22_tuned"]
    qualifiers = []
    diagnostics = []
    gates = {}
    for name, pair in paired.items():
        safe = all(
            m["net_usd"] > 0
            and m["max_dd_pct"] <= 40
            and not m["bankrupt"]
            and m["max_admitted_risk_pct"] <= 10 + 1e-8
            and m["full_months"] > 0
            for m in pair.values()
        )
        improve = all(
            m["net_usd"] >= baseline[v]["net_usd"]
            and m["mean_entries"] > baseline[v]["mean_entries"]
            and m["median_month_net"] >= baseline[v]["median_month_net"]
            and m["positive_month_ratio"] >= baseline[v]["positive_month_ratio"]
            for v, m in pair.items()
        )
        gates[name] = dict(risk_positive_pair=safe, strict_monthly_frequency_improvement=improve)
        if safe:
            diagnostics.append(name)
        if safe and improve and name != "c22_tuned":
            qualifiers.append(name)

    def rank(name):
        values = list(paired[name].values())
        return (
            -min(m["median_month_net"] for m in values),
            -min(m["positive_month_ratio"] for m in values),
            -min(m["net_usd"] for m in values),
            max(m["max_dd_pct"] for m in values),
            -min(m["mean_entries"] for m in values),
            name,
        )

    qualifiers.sort(key=rank)
    diagnostics.sort(key=rank)
    return dict(
        verdict="STRICT_IMPROVEMENT" if qualifiers else "NO_IMPROVEMENT",
        selected=qualifiers[0] if qualifiers else None,
        qualified_order=qualifiers,
        diagnostic_champion=diagnostics[0] if diagnostics else None,
        gates=gates,
        paired=paired,
    )


def run(out, workers):
    out = Path(out).resolve()
    if not out.is_relative_to(ROOT / "runs"):
        raise ValueError("outputs must be under runs")
    out.mkdir(exist_ok=True, parents=True)
    if (out / "COMPLETE.json").exists():
        verify_complete(out)
        print("existing COMPLETE artifacts verified; no rerun", flush=True)
        return
    require_fresh_output(out)
    meta = json.loads((INPUT / "manifest.json").read_text())
    sources = {p: digest(ROOT / p) for p in SOURCES}
    protocol = dict(
        schema="native_detector_cases_v2_fresh_run",
        spec_sha256=digest(ROOT / "docs/specs/2026-10-14-native-frequency-economic-cases.md"),
        sources=sources,
        input_manifest_sha256=digest(INPUT / "manifest.json"),
        cases=list(CASES),
        costs={k: vars(v) for k, v in VIEWS.items()},
        broker=meta["broker"],
        start=meta["requested_start_utc"],
        end=meta["requested_end_utc"],
        swap_required=True,
        native_tester=False,
        discovery_reused=True,
        cost_status="COST_INCONCLUSIVE",
        runtime=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__),
    )
    path = out / "protocol.json"
    if path.exists() and json.loads(path.read_text()) != protocol:
        raise ValueError("protocol/source drift")
    write(path, protocol)
    proofs = {}
    for name in ["tape/time.npy", "tape/bid.npy", "tape/ask.npy", "bars.csv"]:
        actual = digest(INPUT / name)
        if actual != meta["artifacts"][name]:
            raise ValueError("input hash mismatch " + name)
        proofs[name] = actual
    write(out / "input-verified.json", proofs)
    print("input hashes verified", flush=True)
    ticks = tuple(
        np.load(INPUT / "tape" / (k + ".npy"), mmap_mode="r") for k in ["time", "bid", "ask"]
    )
    validate_tape(ticks)
    minutes = prepare_minutes(ticks)
    minutes.to_csv(out / "minutes.csv", index_label="bar_open_utc")
    print("complete physical M1", len(minutes), flush=True)
    bridge_frames(out, minutes, ticks, meta)
    print("full historical native detector parity PASS", flush=True)
    prepared_paths = [
        "native-detector",
        "minutes.csv",
        "native-input.txt",
        "native-frames.csv",
        "detector-parity.json",
    ] + [name + ".csv" for name in CASES]
    prepared_hashes = {name: digest(out / name) for name in prepared_paths}
    write(out / "prepared-verified.json", prepared_hashes)
    cells = {}
    pending = []
    (out / "cells").mkdir(exist_ok=True)
    (out / "repeats").mkdir(exist_ok=True)
    for name in CASES:
        for view in VIEWS:
            pending.append((str(out), name, view, meta))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for cell in pool.map(execute, pending):
            name, view = cell["case"], cell["view"]
            write(out / "cells" / (name + "-" + view + ".json"), cell)
            cells[(name, view)] = cell
            print(
                "cell",
                name,
                view,
                cell["metrics"]["net_usd"],
                cell["metrics"]["mean_entries"],
                flush=True,
            )
    # Every cell repeats fully before any selection.
    tasks = []
    for name in CASES:
        for view in VIEWS:
            tasks.append((str(out), name, view, meta))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for repeated in pool.map(execute, tasks):
            name, view = repeated["case"], repeated["view"]
            if repeated != cells[(name, view)]:
                raise ValueError("full-result repeat mismatch")
            write(out / "repeats" / (name + "-" + view + ".json"), repeated)
            print("repeat", name, view, "PASS", flush=True)
    full_repeats = verify_repeats(out, cells)
    for name, expected in prepared_hashes.items():
        if digest(out / name) != expected:
            raise ValueError("prepared artifact drift: " + name)
    for name, expected in sources.items():
        if digest(ROOT / name) != expected:
            raise ValueError("source drift during campaign: " + name)
    # Preserve exact sources beside immutable results.
    for name in sources:
        target = out / "source_snapshot" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    verdict = select(cells)
    write(out / "results.json", verdict)
    artifacts = {
        str(p.relative_to(out)): digest(p)
        for p in sorted(out.rglob("*"))
        if p.is_file()
        if p.name != "COMPLETE.json"
    }
    write(
        out / "COMPLETE.json",
        dict(
            status="COMPLETE",
            verdict=verdict["verdict"],
            selected=verdict["selected"],
            cells=len(cells),
            full_repeats=full_repeats,
            artifacts=artifacts,
        ),
    )
    print(
        "COMPLETE",
        verdict["verdict"],
        verdict["selected"],
        "diagnostic",
        verdict["diagnostic_champion"],
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 2:
        raise ValueError("workers must be1 or2")
    run(args.output, args.workers)
