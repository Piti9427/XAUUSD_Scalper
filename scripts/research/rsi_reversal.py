"""Standalone RSI cross-back research; never adds a live or grid execution path.

Run with a completed, code-matching BotTradeGold baseline to compare all 120
existing specifications on identical price bytes, years, and execution rules.
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from .data import REVISION, acquire, load_year
from .engine import Costs, metrics, simulate
from .evidence_gate import verify_source_cache
from .matrix import audited_run, check_trade_log, sha256
from .run import classify
from .strategies import Spec, features


SPEC = Spec("RSI14_CrossBack_30_70_M15", "rsi_reversal")


def rsi_reversal_signals(frame):
    """Use only adjacent completed UTC M15 bars and their causal RSI14 values."""
    current = frame.rsi
    previous = current.shift()
    adjacent = frame.index.to_series().diff() == pd.Timedelta(minutes=SPEC.timeframe)
    direction = np.where(
        adjacent & (previous <= 30) & (current > 30),
        1,
        np.where(adjacent & (previous >= 70) & (current < 70), -1, 0),
    )
    valid = frame.atr.notna() & (frame.atr > 0) & (frame.high > frame.low)
    return pd.DataFrame(
        {"direction": np.where(valid, direction, 0), "limit": np.nan},
        index=frame.index,
    )


def run(cache, output, years, baseline=None):
    cache, output = Path(cache), Path(output)
    years = sorted(set(years))
    if not years or any(year < 2010 or year > 2026 for year in years):
        raise ValueError("Years must be within pinned source range 2010–2026")
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    baseline_rows = []
    baseline_hashes = None
    if baseline is not None:
        baseline = Path(baseline)
        old_manifest, specs, _, _ = audited_run(
            baseline, Path(__file__).parent, expected_names=120, expected_years=len(years)
        )
        if old_manifest["years"] != years or old_manifest["source_revision"] != REVISION:
            raise ValueError("Baseline years or source revision differ")
        if old_manifest["costs"] != asdict(Costs()) or old_manifest["delay_minutes"] != 0:
            raise ValueError("Baseline execution costs or delay differ")
        verify_source_cache(cache, old_manifest)
        baseline_rows = pd.read_csv(baseline / "summary.csv").to_dict("records")
        baseline_hashes = {
            name: sha256(baseline / name)
            for name in ("manifest.json", "summary.csv", "annual.csv", "COMPLETE")
        }
        if len(specs) != 120 or len(baseline_rows) != 240:
            raise ValueError("Incomplete baseline comparison")
    inputs = acquire(cache, years, download=False)
    if baseline is not None:
        expected = {item["file"]: item["sha256"] for item in old_manifest["inputs"]}
        if {item["file"]: item["sha256"] for item in inputs} != expected:
            raise ValueError("Price inputs differ from baseline")
    output.mkdir(parents=True)
    trade_dir = output / "trades"
    trade_dir.mkdir()
    annual, audits, pooled = [], [], {"common": [], "native": []}
    for year in years:
        m1, audit = load_year(cache, year)
        audits.append(audit)
        frame = features(m1, SPEC.timeframe)
        signal = rsi_reversal_signals(frame)
        for mode in ("common", "native"):
            trades, dd = simulate(m1, frame, signal, SPEC, Costs(), native=mode == "native")
            row = {"strategy": SPEC.name, "mode": mode, "year": year, **metrics(trades, dd)}
            annual.append(row)
            pooled[mode].append(trades)
            path = trade_dir / f"{SPEC.name}__{mode}__{year}.csv"
            trades.to_csv(path, index=False)
            check_trade_log(path, row)
        print(f"{year}: paired={len(m1):,}, candidate done", flush=True)
    summaries = []
    for mode in ("common", "native"):
        rows = [row for row in annual if row["mode"] == mode]
        trades = pd.concat(pooled[mode], ignore_index=True)
        summary = {
            "strategy": SPEC.name,
            "mode": mode,
            **metrics(trades),
            "years": len(rows),
            "positive_years": sum(row["net"] > 0 for row in rows),
            "worst_year_net": min(row["net"] for row in rows),
            "max_annual_equity_dd": max(row["max_equity_dd"] for row in rows),
            "screen": classify(rows),
            "production_ready": False,
        }
        if summary["screen"] == "REVIEW_CANDIDATE" and (
            summary["pf"] is None
            or summary["pf"] < 1.1
            or any(
                trades.loc[trades.direction == direction, "net"].sum() < 0 for direction in (1, -1)
            )
        ):
            summary["screen"] = "WATCH"
        summaries.append(summary)
    pd.DataFrame(annual).to_csv(output / "annual.csv", index=False)
    pd.DataFrame(summaries).to_csv(output / "summary.csv", index=False)
    (output / "data-audit.json").write_text(json.dumps(audits, indent=2) + "\n")
    if baseline_rows:
        comparison = pd.concat(
            [pd.DataFrame(baseline_rows), pd.DataFrame(summaries)], ignore_index=True
        )
        comparison["research_contract"] = np.where(
            comparison.strategy == SPEC.name, "rsi-crossback-v1", "btg-research-v1"
        )
        comparison.to_csv(output / "comparison.csv", index=False)
    manifest = {
        "version": "rsi-crossback-research-v1",
        "candidate": asdict(SPEC),
        "signal_rule": "RSI14 previous <=30 and current >30 buys; previous >=70 and current <70 sells; adjacent complete M15 bars only; next M1 open",
        "source_status": "new research assumption; video does not specify thresholds or exact exit",
        "years": years,
        "partial_years": [2026] if 2026 in years else [],
        "source_revision": REVISION,
        "inputs": inputs,
        "costs": asdict(Costs()),
        "baseline": str(baseline.resolve()) if baseline is not None else None,
        "baseline_sha256": baseline_hashes,
        "code_sha256": {
            name: sha256(Path(__file__).with_name(name))
            for name in (
                "rsi_reversal.py",
                "strategies.py",
                "engine.py",
                "data.py",
                "matrix.py",
                "run.py",
            )
        },
        "selection": "retrospective research only; not a qualifying sample or live selection",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "COMPLETE").write_text("Candidate run and trade logs reconciled; research only.\n")
    return summaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    summaries = run(args.cache, args.output, args.years, args.baseline)
    print(
        pd.DataFrame(summaries)[["strategy", "mode", "trades", "net", "pf", "screen"]].to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
