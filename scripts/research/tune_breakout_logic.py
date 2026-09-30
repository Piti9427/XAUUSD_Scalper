"""Finite, auditable logic search; never retries against validation outcomes."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.breakout_logic import Rules, Costs, features, replay, dominates
from scripts.research.data import bars as aggregate_bars

START = pd.Timestamp("2026-03-28", tz="UTC")
TRAIN_END = pd.Timestamp("2026-06-28", tz="UTC")
VALID_END = pd.Timestamp("2026-08-28", tz="UTC")
END = pd.Timestamp("2026-09-28", tz="UTC")
STRESS = Costs(extra_spread=0.20, slippage=0.10)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_data():
    root = Path("data/b1_hybrid_baseline_6mo_fixed_2026_09_28")
    capture = Path("data/b1_hybrid_exness_6mo_fixed_2026_09_28")
    if not (root / "COMPLETE").exists() or not (capture / "COMPLETE").exists():
        raise ValueError("incomplete archive")
    manifest = json.loads((root / "manifest.json").read_text())
    meta = json.loads((capture / "manifest.json").read_text())
    if manifest["capture_manifest_sha256"] != sha256(capture / "manifest.json"):
        raise ValueError("capture manifest changed")
    if (
        meta["symbol"] != "XAUUSDm"
        or meta["account"]["currency"] != "USD"
        or not meta["target_demo_verified"]
    ):
        raise ValueError("unexpected archived broker")
    raw = pd.read_csv(root / "reference_bars.csv")
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw.pop("bar_open_utc"), utc=True))
    if sha256(root / "reference_bars.csv") != manifest["artifacts_sha256"]["reference_bars.csv"]:
        raise ValueError("reference bars changed")
    ticks = [np.load(root / "tape" / f"{k}.npy", mmap_mode="r") for k in ("time", "bid", "ask")]
    minutes, offset = [], 0
    for day in meta["days"]:
        path = capture / (day["day"] + ".npz")
        if sha256(path) != day["sha256"]:
            raise ValueError("raw capture changed")
        with np.load(path) as data:
            t, b, a = (data[k] for k in ("time_msc", "bid", "ask"))
        n = len(t)
        if n != day["ticks"] or any(
            not np.array_equal(v, tape[offset : offset + n]) for v, tape in zip((t, b, a), ticks)
        ):
            raise ValueError("raw/tape mismatch")
        offset += n
        if n:
            minute = t // 60000
            first = np.r_[0, np.flatnonzero(np.diff(minute)) + 1]
            last = np.r_[first[1:] - 1, n - 1]
            minutes.append(
                pd.DataFrame(
                    dict(
                        bid_open=b[first],
                        bid_high=np.maximum.reduceat(b, first),
                        bid_low=np.minimum.reduceat(b, first),
                        bid_close=b[last],
                    ),
                    index=pd.to_datetime(minute[first] * 60000, unit="ms", utc=True),
                )
            )
    if any(len(v) != offset for v in ticks) or (np.diff(ticks[0]) < 0).any():
        raise ValueError("invalid full tape chronology")
    rebuilt = aggregate_bars(pd.concat(minutes))
    rebuilt.index = rebuilt.index.as_unit(raw.index.unit)
    pd.testing.assert_frame_equal(
        rebuilt,
        raw[list(rebuilt.columns)],
        check_names=False,
        check_freq=False,
        check_exact=False,
        rtol=0,
        atol=1e-9,
    )
    audit = dict(
        raw_ticks=offset,
        canonical_bars=len(rebuilt),
        capture_manifest_sha256=sha256(capture / "manifest.json"),
        reference_sha256=sha256(root / "reference_bars.csv"),
        tape_sha256={k: sha256(root / "tape" / f"{k}.npy") for k in ("time", "bid", "ask")},
    )
    broker = dict(meta["symbol_spec"], leverage=meta["account"]["leverage"])
    return features(rebuilt), ticks, broker, audit


def hypotheses(batch="original"):
    if batch == "entry_quality":
        return [
            Rules(entry_guard=guard, protect_mode=protect, entry_mode=entry)
            for guard in ("buy_only", "sell_only", "body_dominant", "close_extreme", "prior_day")
            for protect in ("off", "break_even", "runner")
            for entry in ("immediate", "confirm")
        ]
    if batch == "protection":
        return [
            Rules(entry_mode=entry, protect_mode=protect, stop_mode=stop)
            for protect in ("break_even", "candle_trail", "runner")
            for entry in ("immediate", "confirm", "retest")
            for stop in ("atr", "structure")
        ]
    # Exhaustive predeclared rule combinations, not adaptive indicator optimization.
    return [
        Rules(failed, reset, stale, mode, stop_mode)
        for stop_mode in ("atr", "structure")
        for mode in ("immediate", "confirm", "retest")
        for failed in (0, 1, 2)
        for reset in (False, True)
        for stale in (0, 4, 8, 16)
        if (failed, reset, stale, mode, stop_mode) != (0, False, 0, "immediate", "atr")
    ]


def metrics(result):
    return {k: v for k, v in result.items() if k not in ("ledger", "equity")}


def choose_training(rows):
    eligible = [row for row in rows if row["training_pass"]]
    return min(
        eligible,
        key=lambda r: (r["base"]["max_dd_pct"], -r["base"]["net_usd"], r["trial"]),
        default=None,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--batch", choices=("original", "protection", "entry_quality"), default="original"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sources = [
        Path(__file__),
        Path("scripts/research/breakout_logic.py"),
        Path("scripts/research/data.py"),
    ]
    source_hashes = {str(p): sha256(p) for p in sources}
    candidates = hypotheses(args.batch)
    protocol = dict(
        batch=args.batch,
        baseline=asdict(Rules()),
        candidates=[asdict(r) for r in candidates],
        train=[str(START), str(TRAIN_END)],
        validation=[str(TRAIN_END), str(VALID_END)],
        diagnostic=[str(VALID_END), str(END)],
        stress=asdict(STRESS),
        selection="Training-only strict dominance, rank by lower DD then higher net.",
        min_train_trades=20,
        min_test_trades=10,
        untouched_holdout=False,
        order_api_called=False,
        stop=f"Exhaust declared {len(candidates)} candidates; evaluate at most one training winner; never retune on validation.",
        success="strict dominance on train, validation and final diagnostic",
        missing_cost_evidence=[
            "historical swap entitlement",
            "measured broker slippage",
            "broker fills",
        ],
        live_execution="NO-GO",
    )
    (args.output / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    frame, ticks, broker, audit = load_data()
    # Truncate bars before training end, so selection cannot read later OHLC.
    training = frame.loc[frame.index + pd.Timedelta(minutes=15) < TRAIN_END]
    rows = []

    def run(label, rules, start, end, source_frame=frame):
        pair = []
        for suffix, costs in (("base", Costs()), ("stress", STRESS)):
            result = replay(source_frame, ticks, broker, rules, costs, start=start, end=end)
            (args.output / f"{label}-{suffix}.json").write_text(json.dumps(result, indent=2) + "\n")
            pair.append(metrics(result))
        return pair

    full, full_stress = run("full-baseline", Rules(), START, END)
    if abs(full["final_balance"] - 533.62) > 0.02 or full["trades"] != 266:
        raise ValueError("baseline differs from archived calibration; diagnose before tuning")
    baseline, baseline_stress = run("train-baseline", Rules(), START, TRAIN_END, training)
    for index, rules in enumerate(candidates, 1):
        base, stressed = run(f"trial-{index:02}", rules, START, TRAIN_END, training)
        passed = dominates(base, baseline, stressed, baseline_stress, min_trades=20)
        row = dict(
            trial=index, rules=asdict(rules), base=base, stress=stressed, training_pass=passed
        )
        rows.append(row)
        with (args.output / "trials.jsonl").open("a") as stream:
            stream.write(json.dumps(row) + "\n")
        print(
            json.dumps(
                dict(
                    trial=index,
                    rules=asdict(rules),
                    passed=passed,
                    net=base["net_usd"],
                    dd=base["max_dd_pct"],
                    rr=base["realized_rr"],
                )
            ),
            flush=True,
        )
    winner = choose_training(rows)
    evaluation = []
    if winner is not None:
        rules = Rules(**winner["rules"])
        # Selection frozen before either evaluation window is read.
        (args.output / "selected.json").write_text(json.dumps(winner, indent=2) + "\n")
        for label, start, end in (
            ("validation", TRAIN_END, VALID_END),
            ("diagnostic", VALID_END, END),
        ):
            ref, ref_stress = run(label + "-baseline", Rules(), start, end)
            base, stressed = run(label + "-selected", rules, start, end)
            evaluation.append(
                dict(
                    window=label,
                    baseline=ref,
                    baseline_stress=ref_stress,
                    candidate=base,
                    stress=stressed,
                    passed=dominates(base, ref, stressed, ref_stress, min_trades=10),
                )
            )
    full_candidate = None
    if winner is not None:
        full_candidate = run("full-selected", Rules(**winner["rules"]), START, END)
    passed = winner is not None and all(r["passed"] for r in evaluation)
    archived_path = Path("docs/reviews/2026-09-29-exness-demo-config-search.md")
    archive_comparison = dict(
        reference=str(archived_path),
        reference_sha256=sha256(archived_path) if archived_path.exists() else None,
        archived_final_balance=533.62,
        archived_trades=266,
        archived_dd_pct=56.89,
        balance_delta_usd=full["final_balance"] - 533.62,
        trade_delta=full["trades"] - 266,
        dd_delta_percentage_points=full["max_dd_pct"] - 56.89,
        note="Archived values rounded; new engine records entry spread immediately and caps TP overshoot in equity/MFE. Compare base only, stress differs by design.",
    )
    if source_hashes != {str(p): sha256(p) for p in sources}:
        raise ValueError("source changed during run; no COMPLETE evidence")
    result = dict(
        protocol=protocol,
        audit=audit,
        training_baseline=baseline,
        training_baseline_stress=baseline_stress,
        trials=rows,
        selected=winner,
        evaluation=evaluation,
        archived_baseline_comparison=archive_comparison,
        full_baseline=full,
        full_baseline_stress=full_stress,
        full_candidate=full_candidate,
        status="RESEARCH_PASS" if passed else "NO_QUALIFIED_STRATEGY",
        source_sha256=source_hashes,
    )
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.output / "COMPLETE").write_text(sha256(args.output / "results.json") + "\n")
    print(
        json.dumps(
            dict(
                status=result["status"],
                selected=winner["rules"] if winner else None,
                baseline_full_net=full["net_usd"],
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
