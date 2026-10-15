"""Finite, predeclared B1 challenger research; source mirror stays read-only."""

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_engine(source):
    spec = importlib.util.spec_from_file_location("btg_frozen_handoff", Path(source) / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_features(engine, raw):
    d = engine.features(raw)
    for n in (20, 40):
        high, low = d.high.shift().rolling(n).max(), d.low.shift().rolling(n).min()
        d[f"B{n}"] = np.select(
            [(d.close > high) & (d.rsi <= 75), (d.close < low) & (d.rsi >= 25)], [1, -1], default=0
        )
    fast, slow = engine.ema(d.close, 20), engine.ema(d.close, 50)
    d["P1"] = np.select(
        [
            (fast > slow)
            & (d.low <= fast)
            & (d.close > fast)
            & (d.close > d.open)
            & d.rsi.between(50, 75),
            (fast < slow)
            & (d.high >= fast)
            & (d.close < fast)
            & (d.close < d.open)
            & d.rsi.between(25, 50),
        ],
        [1, -1],
        default=0,
    )
    trend = np.select(
        [(d.h1_close > d.h1_ema) & (d.h1_slope > 0), (d.h1_close < d.h1_ema) & (d.h1_slope < 0)],
        [1, -1],
        default=0,
    )
    d["B1_H1"] = d.B1.where(d.B1 == trend, 0)
    d["B1_BODY"] = d.B1.where((d.close - d.open) * d.B1 >= 0.5 * (d.high - d.low), 0)
    hour = (d.index + pd.Timedelta(minutes=15)).hour
    d["B1_SESSION"] = d.B1.where((hour >= 7) & (hour < 17), 0)
    d["B1_SL2"] = d.B1
    d["B1_TP25"] = d.B1
    columns = [
        "B1",
        "MR2",
        "B20",
        "B40",
        "P1",
        "B1_H1",
        "B1_BODY",
        "B1_SESSION",
        "B1_SL2",
        "B1_TP25",
    ]
    d.loc[d.h1_slope.isna(), columns] = 0
    return d


def parameters(name):
    if name == "MR2":
        return 2.0, 2.5
    return (2.0 if name == "B1_SL2" else 2.5), (2.5 if name == "B1_TP25" else 3.5)


def simulate_candidate(engine, frame, name, start, end, cost, sized):
    d = frame.loc[frame.index < pd.Timestamp(end)].copy()
    d["B1"] = d[name]
    previous = copy.deepcopy(engine.C)
    sl, tp = parameters(name)
    engine.C["B1"].update(sl_atr=sl, tp_r=tp)
    try:
        tr, curve, metrics = engine.simulate(d, start, ["B1"], cost, sized)
        if not tr.empty:
            tr["strategy"] = name
        return tr, curve, metrics
    finally:
        engine.C = previous


def select_candidate(rows, names):
    """Later-window rows cannot participate, even if their returns are huge."""
    indexed = {
        (r["window"], r["strategy"], r["cost_r"]): r
        for r in rows
        if r["window"] in ("pre_primary", "early", "late")
    }
    eligible = []
    decisions = []
    for name in names:
        reasons = []
        for cost in (0.1, 0.15):
            row = indexed.get(("pre_primary", name, cost))
            base = indexed.get(("pre_primary", "B1", cost))
            if row is None or base is None:
                reasons.append(f"missing pre_primary cost {cost}")
                continue
            if row["trades"] < 30:
                reasons.append(f"small pre_primary sample {cost}")
            if row["pf"] is None or row["pf"] < 1.1:
                reasons.append(f"PF below 1.1 {cost}")
            if row["return_pct"] <= max(0.0, base["return_pct"]):
                reasons.append(f"no positive return improvement {cost}")
            if (
                row["max_dd_pct_barclose"] > base["max_dd_pct_barclose"]
                or row["max_dd_pct_barclose"] >= 12
            ):
                reasons.append(f"DD exceeds baseline/limit {cost}")
            if row["stop_triggered"]:
                reasons.append(f"hard stop {cost}")
        for window in ("early", "late"):
            row = indexed.get((window, name, 0.15))
            if row is None or row["trades"] < 10 or row["total_r"] <= 0 or row["stop_triggered"]:
                reasons.append(f"weak {window} block")
        decisions.append({"strategy": name, "eligible": not reasons, "reasons": reasons})
        if not reasons:
            eligible.append(indexed[("pre_primary", name, 0.15)])
    ranked = sorted(
        eligible, key=lambda r: (-r["return_pct"], r["max_dd_pct_barclose"], r["strategy"])
    )
    return {
        "selected": ranked[0]["strategy"] if ranked else "B1",
        "eligible": [r["strategy"] for r in ranked],
        "decisions": decisions,
        "locked_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    out = args.output
    inputs = out / "inputs"
    (inputs / "data").mkdir(parents=True)
    (out / "ledgers").mkdir()
    contract = Path("config/b1_profit_research_v1.json")
    cfg = json.loads(contract.read_text())
    shutil.copy2(contract, out / "contract.json")
    source = args.source
    original_results = json.loads((source / "results/results.json").read_text())
    if sha(source / "data/verified.csv") != original_results["data"]["verified_sha256"]:
        raise ValueError("handoff data hash mismatch")
    for name in (
        "run.py",
        "contract.json",
        "data/verified.csv",
        "data/manifest.json",
        "data/audit.json",
    ):
        shutil.copy2(source / name, inputs / name)
    engine = load_engine(inputs)
    raw = pd.read_csv(inputs / "data/verified.csv", parse_dates=["datetime"]).set_index("datetime")
    if raw.index.tz is None or raw.index.has_duplicates or not raw.index.is_monotonic_increasing:
        raise ValueError("invalid source timestamps")
    frame = candidate_features(engine, raw)
    names = ["B1", "MR2", *cfg["challengers"]]
    for n in (1300, 5000, 10000, 14000):
        prefix = candidate_features(engine, raw.iloc[:n])
        pd.testing.assert_frame_equal(prefix[names], frame.iloc[:n][names])
    windows = {
        "early": (cfg["discovery_start"], cfg["inner_split"]),
        "late": (cfg["inner_split"], cfg["primary_start"]),
        "pre_primary": (cfg["discovery_start"], cfg["primary_start"]),
        "primary": (cfg["primary_start"], cfg["end_exclusive"]),
        "robustness": (cfg["discovery_start"], cfg["end_exclusive"]),
    }
    rows = []
    monthly = []
    breakdowns = []
    checks = ["Four prefix causality checks passed for every candidate"]
    for window, (start, end) in windows.items():
        for name in names:
            for cost in cfg["costs_r"]:
                tr, _, _ = simulate_candidate(engine, frame, name, start, end, cost, False)
                sized, curve, p = simulate_candidate(engine, frame, name, start, end, cost, True)
                row = {
                    "window": window,
                    "strategy": name,
                    "cost_r": cost,
                    **engine.stats(tr),
                    **p,
                    "sized_trades": len(sized),
                }
                rows.append(row)
                stem = f"{window}_{name}_{cost:.2f}"
                tr.to_csv(out / "ledgers" / f"{stem}_trades.csv", index=False)
                sized.to_csv(out / "ledgers" / f"{stem}_sized.csv", index=False)
                curve.to_csv(out / "ledgers" / f"{stem}_equity.csv", index=False)
                if not sized.empty:
                    np.testing.assert_allclose(
                        sized.exit_equity,
                        sized.entry_equity + sized.budget * sized.net_r,
                        atol=1e-9,
                    )
                for month, part in (
                    tr.groupby(tr.exit_time.dt.strftime("%Y-%m")) if not tr.empty else []
                ):
                    monthly.append(
                        {
                            "window": window,
                            "strategy": name,
                            "cost_r": cost,
                            "month": month,
                            **engine.stats(part),
                        }
                    )
                if not tr.empty and window in ("primary", "robustness"):
                    for side, part in tr.groupby("side"):
                        breakdowns.append(
                            {
                                "window": window,
                                "strategy": name,
                                "cost_r": cost,
                                "direction": int(side),
                                **engine.stats(part),
                            }
                        )
        print(window + " complete", flush=True)
        if window == "pre_primary":
            locked = select_candidate(rows, list(cfg["challengers"]))
            (out / "selection_locked.json").write_text(json.dumps(locked, indent=2))
            print("Pre-primary locked selection: " + locked["selected"], flush=True)
    # Reproduce the delivered baseline rather than assuming conventions match.
    reference = json.loads((source / "results/primary_3m_confirmation.json").read_text())
    for expected in reference["rows"]:
        observed = next(
            r
            for r in rows
            if r["window"] == "primary"
            and r["strategy"] == expected["strategy"]
            and r["cost_r"] == expected["cost_r"]
        )
        for key in ("trades", "total_r", "return_pct", "max_dd_pct_barclose"):
            if not np.isclose(observed[key], expected[key], atol=1e-8):
                raise AssertionError((key, observed, expected))
    checks.append("B1/MR2 primary counts, R, sized returns and DD reproduce handoff exactly")
    checks.append("Every sized ledger reconciles entry equity plus budget times net R")
    pd.DataFrame(rows).to_csv(out / "metrics.csv", index=False)
    pd.DataFrame(monthly).to_csv(out / "monthly.csv", index=False)
    pd.DataFrame(breakdowns).to_csv(out / "directions.csv", index=False)
    result = {
        "version": cfg["version"],
        "selected_before_primary": locked["selected"],
        "rows": rows,
        "checks": checks,
        "contract_sha256": sha(contract),
        "input_sha256": {
            str(p.relative_to(inputs)): sha(p)
            for p in inputs.rglob("*")
            if p.is_file() and "__pycache__" not in str(p)
        },
        "research_code_sha256": sha(__file__),
        "primary_is_untouched_oos": False,
        "production_ready": False,
        "capital_model": "ideal proportional $100, no broker minimum lot; costs are R proxies",
    }
    (out / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    (out / "COMPLETE").write_text("Finite retrospective research completed; no live approval.\n")


if __name__ == "__main__":
    main()
