"""Retrospective walk-forward research on audited saved Exness quotes.

No broker connection. Previously searched history is not an untouched holdout.
Each fold starts with $200; fold returns must not be compounded.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.pure_b1.provenance import sha256_file
from scripts.research.data import bars as aggregate_bars
from scripts.research.exness_demo_config_search import run_config, signal_frame, _slice_ticks
from scripts.research.pure_b1_target_replay import START, END, _load_inputs

CORE = dict(donchian=30, rsi_mode="band_30_70", use_ema50=True,
            stop_atr=2.5, target_atr=6.25)
GRID = [dict(donchian=d, rsi_mode="off", use_ema50=False,
             stop_atr=2.5, target_atr=t)
        for d in (40, 48, 56, 64, 72) for t in (3.0, 3.25, 3.5)]
BOUNDARIES = [pd.Timestamp(d, tz="UTC") for d in
              ("2026-06-28", "2026-07-28", "2026-08-28", "2026-09-28")]


def choose(rows):
    """Training-only screen; no fallback to an ineligible winner."""
    eligible = [r for r in rows if r["trades"] >= 20 and r["return_pct"] > 0
                and r["max_tick_equity_dd_pct"] <= 40]
    return max(eligible, key=lambda r: (r["return_pct"] /
               max(r["max_tick_equity_dd_pct"], 1), -r["donchian"],
               -r["target_atr"]), default=None)


def audit_capture(baseline, capture, reference):
    """Verify raw hashes, exact tape identity, and independently rebuilt bars."""
    meta = json.loads((capture / "manifest.json").read_text())
    if not (capture / "COMPLETE").exists() or not meta["target_demo_verified"]:
        raise ValueError("incomplete or unverified capture")
    tape = [np.load(baseline / "tape" / f"{k}.npy", mmap_mode="r")
            for k in ("time", "bid", "ask")]
    offset = 0
    minutes = []
    for day in meta["days"]:
        path = capture / (day["day"] + ".npz")
        if sha256_file(path) != day["sha256"]:
            raise ValueError(f"raw hash mismatch: {path.name}")
        with np.load(path) as z:
            t, b, a = z["time_msc"], z["bid"], z["ask"]
        n = len(t)
        lo = pd.Timestamp(day["day"], tz="UTC").value // 10**6
        if (n != day["ticks"] or not (n == len(b) == len(a))
                or (np.diff(t) < 0).any() or not np.isfinite(b).all()
                or not np.isfinite(a).all() or (b <= 0).any() or (a < b).any()
                or (n and (t[0] < lo or t[-1] >= lo + 86400000))):
            raise ValueError(f"invalid ticks: {path.name}")
        for raw, saved in zip((t, b, a), tape):
            if not np.array_equal(raw, saved[offset:offset+n]):
                raise ValueError(f"raw/tape mismatch: {path.name}")
        offset += n
        if n:
            minute = t // 60000
            first = np.r_[0, np.flatnonzero(np.diff(minute)) + 1]
            last = np.r_[first[1:] - 1, n - 1]
            minutes.append(pd.DataFrame(dict(bid_open=b[first],
                bid_high=np.maximum.reduceat(b, first),
                bid_low=np.minimum.reduceat(b, first), bid_close=b[last]),
                index=pd.to_datetime(minute[first]*60000, unit="ms", utc=True)))
    if any(len(v) != offset for v in tape) or (np.diff(tape[0]) < 0).any():
        raise ValueError("tape length or global chronology mismatch")
    rebuilt = aggregate_bars(pd.concat(minutes))
    rebuilt.index = rebuilt.index.as_unit(reference.index.unit)
    pd.testing.assert_frame_equal(rebuilt, reference[list(rebuilt.columns)],
                                  check_names=False, check_freq=False,
                                  check_exact=False, rtol=0, atol=1e-9)
    return dict(raw_days_verified=len(meta["days"]), raw_ticks_verified=offset,
                canonical_m15_verified=len(rebuilt), raw_tape_exact_match=True,
                capture_manifest_sha256=sha256_file(capture / "manifest.json"),
                tape_sha256={k: sha256_file(baseline / "tape" / f"{k}.npy")
                             for k in ("time", "bid", "ask")})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    baseline = Path("data/b1_hybrid_baseline_6mo_fixed_2026_09_28")
    capture = Path("data/b1_hybrid_exness_6mo_fixed_2026_09_28")
    bars, ticks, broker = _load_inputs(baseline, capture)
    bars = bars[["open", "high", "low", "close"]]
    protocol = dict(grid=GRID, train_start=str(START), fold_boundaries=list(map(str, BOUNDARIES)),
        selection="Training trades >=20, return >0, DD <=40%; maximize return/DD. Otherwise cash.",
        screen_dd_is_research_only=True, initial_balance_each_run=200,
        independent_folds_not_compoundable=True, untouched_holdout=False,
        prior_search="Entire tape already inspected; 54 + 60 configurations previously searched.",
        commission_per_lot=0, swap_applied=False, slippage_measured=False,
        stress="Bid -0.10 / Ask +0.10 USD per oz at every tick; unchanged signal bars; hypothetical spread stress.",
        order_api_called=False, live_execution="NO-GO")
    # Persist rules before observing search outcomes.
    (args.output / "protocol.json").write_text(json.dumps(protocol, indent=2)+"\n")
    audit = audit_capture(baseline, capture, bars)
    print(json.dumps({"audit": audit}), flush=True)
    # Prefix invariance checks that later prices cannot change earlier indicators/signals.
    for spec in [CORE] + GRID:
        kwargs = {k: spec[k] for k in ("donchian", "rsi_mode", "use_ema50")}
        prefix = bars.loc[bars.index < BOUNDARIES[0]]
        pd.testing.assert_frame_equal(signal_frame(bars, **kwargs).loc[prefix.index],
                                      signal_frame(prefix, **kwargs))
    calibration = run_config(bars, ticks, broker, CORE, start=START, end=END)
    if abs(calibration["final_balance"]-132.98) > .005 or calibration["trades"] != 4:
        raise ValueError("baseline reproduction failed")
    folds = []
    for end_train, end_test in zip(BOUNDARIES, BOUNDARIES[1:]):
        training_ticks = _slice_ticks(ticks, START, end_train)
        training_bars = bars.loc[bars.index + pd.Timedelta(minutes=15) < end_train]
        rows = [run_config(training_bars, training_ticks, broker, s, start=START, end=end_train)
                for s in GRID]
        selected = choose(rows)
        fold = dict(train_end_exclusive=str(end_train), test_end_exclusive=str(end_test),
                    training_rows=rows, selected=selected)
        test_ticks = _slice_ticks(ticks, end_train, end_test)
        fold["core_test"] = run_config(bars, test_ticks, broker, CORE,
                                       start=end_train, end=end_test)
        if selected:
            spec = {k: selected[k] for k in CORE}
            fold["test"] = run_config(bars, test_ticks, broker, spec, start=end_train, end=end_test)
            stress = [test_ticks[0], test_ticks[1]-.10, test_ticks[2]+.10]
            fold["test_spread_stress"] = run_config(bars, stress, broker, spec,
                                                   start=end_train, end=end_test)
            fold["test_spread_stress"]["hypothetical_extra_spread_usd_per_oz"] = .20
        else:
            fold["test"] = None
            fold["decision"] = "CASH: no eligible training configuration"
        folds.append(fold)
        (args.output / f"fold-{len(folds)}.json").write_text(json.dumps(fold, indent=2)+"\n")
        print(json.dumps({"fold": len(folds), "selected": selected,
                          "test": fold["test"]}), flush=True)
    full = []
    for spec in GRID:
        full.append(run_config(bars, ticks, broker, spec, start=START, end=END))
        print(json.dumps({"full": full[-1]}), flush=True)
    sources = [Path(__file__), Path("scripts/research/exness_demo_config_search.py"),
               Path("scripts/research/b1_hybrid_six_month.py"),
               Path("scripts/research/pure_b1_target_replay.py"),
               Path("scripts/research/data.py"), Path("scripts/pure_b1/decision.py"),
               Path("scripts/pure_b1/quote_time.py"), Path("scripts/pure_b1/provenance.py"),
               Path("scripts/strategy.py")]
    result = dict(protocol=protocol, audit=audit, calibration=calibration, folds=folds,
                  full_window_descriptive_only=full, prefix_invariance_passed=True,
                  sources_sha256={str(p): sha256_file(p) for p in sources})
    (args.output / "results.json").write_text(json.dumps(result, indent=2)+"\n")
    (args.output / "COMPLETE").write_text(sha256_file(args.output / "results.json")+"\n")


if __name__ == "__main__":
    main()
