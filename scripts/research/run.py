"""python -m scripts.research.run --cache PATH --output PATH --years 2010 2012 ..."""

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
import numpy as np
import pandas as pd
from .data import acquire, load_year, REVISION
from .strategies import registry, features, signals, apply_filters
from .engine import Costs, simulate, metrics


def classify(rows):
    n = sum(x["trades"] for x in rows)
    if len(rows) < 5 or n < 200:
        return "INSUFFICIENT"
    positive = sum(x["net"] > 0 for x in rows) / len(rows)
    if sum(x["net"] for x in rows) <= 0 or positive < 0.5:
        return "REJECT_RESEARCH"
    # Promotion requires checking the pooled evidence and profit concentration too.
    total = sum(x["net"] for x in rows)
    profits = sum(max(0, x["net"]) for x in rows)
    concentration = max(max(0, x["net"]) for x in rows) / profits if profits else 1.0
    if positive >= 0.65 and concentration <= 0.5 and total > 0:
        return "REVIEW_CANDIDATE"
    return "WATCH"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--years", type=int, nargs="+", default=list(range(2010, 2027)))
    p.add_argument("--download", action="store_true")
    p.add_argument("--names", nargs="+")
    p.add_argument("--units", type=float, default=1.0)
    p.add_argument("--commission", type=float, default=0.0)
    p.add_argument("--slippage", type=float, default=0.0)
    p.add_argument("--swap", type=float, default=0.0)
    p.add_argument("--delay-minutes", type=int, default=0)
    args = p.parse_args()
    years = sorted(set(args.years))
    if any(y < 2010 or y > 2026 for y in years):
        p.error("Pinned source covers 2010–2026")
    specs = registry()
    if args.names:
        unknown = set(args.names) - {s.name for s in specs}
        if unknown:
            p.error(f"Unknown names: {sorted(unknown)}")
        specs = [s for s in specs if s.name in args.names]
    # Existing outputs are immutable; fail rather than mix old/new partial reports.
    args.output.mkdir(parents=True, exist_ok=False)
    source = acquire(args.cache, years, download=args.download)
    costs = Costs(args.units, args.commission, args.slippage, args.swap)
    config = {
        "version": "btg-research-v1",
        "years": years,
        "strategies": [asdict(s) for s in specs],
        "costs": asdict(costs),
        "delay_minutes": args.delay_minutes,
        "source_revision": REVISION,
        "inputs": source,
        "selection": "frozen exploratory screen; no untouched OOS; no production promotion",
        "year_policy": "reset positions/indicators annually; end-of-year liquidation; no cross-year compounding",
        "cost_status": "historical spread; user-specified other costs are scenarios; broker costs unverified",
        "native_policy": "native SL/TP where specified, reconstructed defaults elsewhere; sideway=no entry",
        "common_policy": "2 ATR / 2R, all regimes for raw-signal diagnostic",
        "runtime": {"pandas": pd.__version__, "numpy": np.__version__},
        "code_sha256": {
            x.name: hashlib.sha256(x.read_bytes()).hexdigest()
            for x in Path(__file__).parent.glob("*.py")
        },
    }
    (args.output / "manifest.json").write_text(json.dumps(config, indent=2))
    annual = []
    breakdown = []
    months = []
    equal = []
    audits = []
    pooled = {}
    for year in years:
        m1, audit = load_year(args.cache, year)
        audits.append(audit)
        frames = {tf: features(m1, tf) for tf in {s.timeframe for s in specs}}
        logs = {}
        raw_signals = {}
        for spec in specs:
            f = frames[spec.timeframe]
            raw_spec = replace(
                spec, name="", filters=(), sl=2.0, tp=2.0, reconstruction=True
            )
            if raw_spec not in raw_signals:
                raw_signals[raw_spec] = signals(f, raw_spec)
            sig = apply_filters(f, raw_signals[raw_spec], spec)
            for native in (False, True):
                mode = "native" if native else "common"
                log, dd = simulate(m1, f, sig, spec, costs, native, args.delay_minutes)
                row = {
                    "strategy": spec.name,
                    "mode": mode,
                    "year": year,
                    **metrics(log, dd),
                }
                annual.append(row)
                logs[spec.name, mode] = log
                pooled.setdefault((spec.name, mode), []).append(log)
                path = args.output / "trades"
                path.mkdir(exist_ok=True)
                log.to_csv(path / f"{spec.name}__{mode}__{year}.csv", index=False)
                for regime in ("trend", "expansion", "sideway"):
                    breakdown.append(
                        {
                            "strategy": spec.name,
                            "mode": mode,
                            "year": year,
                            "regime": regime,
                            **metrics(log[log.regime == regime]),
                        }
                    )
                if not log.empty:
                    for month, part in log.groupby(log.entry_time.dt.month):
                        months.append(
                            {
                                "strategy": spec.name,
                                "mode": mode,
                                "year": year,
                                "month": int(month),
                                **metrics(part),
                            }
                        )
        for mode in ("common", "native"):
            selected = {name: log for (name, m), log in logs.items() if m == mode}
            count = min(map(len, selected.values()))
            for name, log in selected.items():
                sample = (
                    log.iloc[np.linspace(0, len(log) - 1, count, dtype=int)]
                    if count
                    else log.iloc[:0]
                )
                equal.append(
                    {"strategy": name, "mode": mode, "year": year, **metrics(sample)}
                )
        pd.DataFrame(annual).to_csv(args.output / "annual.csv", index=False)
        (args.output / "data-audit.json").write_text(json.dumps(audits, indent=2))
        print(f"{year}: paired={len(m1):,}, strategies={len(specs)}, done", flush=True)
    summaries = []
    for (name, mode), logs in pooled.items():
        rows = [r for r in annual if r["strategy"] == name and r["mode"] == mode]
        log = pd.concat(logs, ignore_index=True)
        summary = {
            "strategy": name,
            "mode": mode,
            **metrics(log),
            "years": len(rows),
            "positive_years": sum(r["net"] > 0 for r in rows),
            "worst_year_net": min(r["net"] for r in rows),
            "max_annual_equity_dd": max(r["max_equity_dd"] for r in rows),
            "screen": classify(rows),
            "production_ready": False,
        }
        # Require PF margin and both sides nonnegative for candidate review.
        if summary["screen"] == "REVIEW_CANDIDATE" and (
            summary["pf"] is None
            or summary["pf"] < 1.1
            or any(log.loc[log.direction == d, "net"].sum() < 0 for d in (1, -1))
        ):
            summary["screen"] = "WATCH"
        summaries.append(summary)
    for name, rows in [
        ("summary", summaries),
        ("regimes", breakdown),
        ("months", months),
        ("equal_n", equal),
    ]:
        pd.DataFrame(rows).to_csv(args.output / f"{name}.csv", index=False)
    (args.output / "COMPLETE").write_text(
        "All requested strategy/year runs completed. Research only.\n"
    )
    print(
        pd.DataFrame(summaries)
        .sort_values("net", ascending=False)[
            ["strategy", "mode", "trades", "net", "pf", "screen"]
        ]
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
