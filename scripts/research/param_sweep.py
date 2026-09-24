"""Run declared handoff parameter candidates on verified historical Bid/Ask data.

This is a bounded, reconstructed research experiment, not original-code parity.
Usage: python -m scripts.research.param_sweep --spec-file PATH --cache PATH --output NEW_PATH
"""

import argparse
import json
import math
import re
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .data import REVISION, acquire, load_year
from .engine import Costs, metrics, simulate
from .matrix import check_trade_log, sha256, write_csv
from .optimize import build_custom_walkforward
from .strategies import Spec, features, signals

ALLOWED_FIELDS = {
    "name",
    "family",
    "lookback",
    "sl",
    "tp",
    "filters",
    "handoff_reference",
    "known_mismatch",
}
ALLOWED_FAMILIES = {"donchian", "state", "orb", "ote"}
ALLOWED_FILTERS = {"fvg", "h1ema", "h1structure", "rsi", "body"}


def load_candidates(path):
    source = json.loads(Path(path).read_text())
    if source.get("version") != "btg-handoff-parameter-v1" or not isinstance(
        source.get("candidates"), list
    ):
        raise ValueError("Unsupported candidate declaration")
    specs = []
    names = set()
    for row in source["candidates"]:
        if (
            not isinstance(row, dict)
            or set(row) - ALLOWED_FIELDS
            or not {"name", "family", "sl", "tp", "filters", "handoff_reference", "known_mismatch"}
            <= set(row)
        ):
            raise ValueError("Invalid candidate fields")
        name = row["name"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", name)
            or name in names
        ):
            raise ValueError("Invalid or duplicate candidate name")
        names.add(name)
        if (
            row["family"] not in ALLOWED_FAMILIES
            or not isinstance(row["filters"], list)
            or not set(row["filters"]) <= ALLOWED_FILTERS
            or len(row["filters"]) != len(set(row["filters"]))
        ):
            raise ValueError("Unsupported family or filters")
        if (
            not isinstance(row.get("lookback", 20), int)
            or isinstance(row.get("lookback", 20), bool)
            or row.get("lookback", 20) <= 0
        ):
            raise ValueError("Invalid lookback")
        for field in ("sl", "tp"):
            value = row[field]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"Invalid {field}")
        if not all(
            isinstance(row[field], str) and row[field].strip()
            for field in ("handoff_reference", "known_mismatch")
        ):
            raise ValueError("Missing provenance or mismatch disclosure")
        specs.append(
            Spec(
                name,
                row["family"],
                lookback=row.get("lookback", 20),
                filters=tuple(row["filters"]),
                sl=float(row["sl"]),
                tp=float(row["tp"]),
            )
        )
    if not specs:
        raise ValueError("No declared candidates")
    return source, specs


def audit_outputs(output, annual, summary, names, years):
    """Reconcile every trade log to annual and pooled metrics before COMPLETE."""
    expected = {(name, year) for name in names for year in years}
    actual = [(row["strategy"], row["year"]) for row in annual]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("Candidate/year coverage or duplicate annual rows")
    summary_names = [row["strategy"] for row in summary]
    if len(summary_names) != len(names) or set(summary_names) != set(names):
        raise ValueError("Summary candidate coverage or duplicates")
    pooled = {}
    for row in annual:
        name, year = row["strategy"], row["year"]
        path = output / "trades" / f"{name}__native__{year}.csv"
        count, net, total_r, gains, losses = check_trade_log(path, row)
        totals = pooled.setdefault(name, [0, 0.0, 0.0, 0.0, 0.0, 0])
        totals[0] += count
        totals[1] += net
        totals[2] += total_r
        totals[3] += gains
        totals[4] += losses
        totals[5] += net > 0
    for row in summary:
        count, net, total_r, gains, losses, positive = pooled[row["strategy"]]
        if not (
            count == row["trades"]
            and math.isclose(net, row["net"], abs_tol=1e-6)
            and math.isclose(total_r, row["total_r"], abs_tol=1e-6)
            and positive == row["positive_years"]
            and ((row["pf"] is None) == (losses == 0))
            and (losses == 0 or math.isclose(gains / losses, row["pf"], rel_tol=1e-8))
        ):
            raise ValueError(f"Summary reconciliation failed: {row['strategy']}")


def run(spec_file, cache, output, years):
    years = sorted(set(years))
    if not years or any(year < 2010 or year > 2026 for year in years):
        raise ValueError("Pinned historical data covers 2010–2026 (2026 is partial)")
    declaration, specs = load_candidates(spec_file)
    source_inputs = acquire(cache, years, download=False)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "trades").mkdir()
    manifest = {
        "version": "btg-handoff-parameter-sweep-v1",
        "status": "reconstructed_partial_rule_match_research_only",
        "production_ready": False,
        "years": years,
        "partial_years": [2026] if 2026 in years else [],
        "sample_end_policy": "Open positions close at last available M1 bar of each scored year",
        "mode": "native",
        "source_revision": REVISION,
        "source_inputs": source_inputs,
        "candidate_file_sha256": sha256(spec_file),
        "declaration": declaration,
        "costs": asdict(Costs()),
        "code_sha256": {
            file: sha256(Path(__file__).parent / file)
            for file in (
                "param_sweep.py",
                "optimize.py",
                "matrix.py",
                "data.py",
                "strategies.py",
                "engine.py",
            )
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    annual = []
    audits = []
    pooled = {spec.name: [] for spec in specs}
    for year in years:
        m1, audit = load_year(cache, year)
        audits.append(audit)
        frame = features(m1, 15)
        for spec in specs:
            log, equity_dd = simulate(m1, frame, signals(frame, spec), spec, Costs(), native=True)
            log.to_csv(output / "trades" / f"{spec.name}__native__{year}.csv", index=False)
            annual.append({"strategy": spec.name, "year": year, **metrics(log, equity_dd)})
            pooled[spec.name].append(log)
        pd.DataFrame(annual).to_csv(output / "annual.csv", index=False)
        (output / "data-audit.json").write_text(json.dumps(audits, indent=2) + "\n")
        print(f"{year}: {len(m1):,} paired M1 rows, {len(specs)} candidates", flush=True)
    summary = []
    for spec in specs:
        rows = [row for row in annual if row["strategy"] == spec.name]
        all_trades = pd.concat(pooled[spec.name], ignore_index=True)
        summary.append(
            {
                "strategy": spec.name,
                **metrics(all_trades),
                "max_annual_equity_dd": max(row["max_equity_dd"] for row in rows),
                "years": len(rows),
                "positive_years": sum(row["net"] > 0 for row in rows),
                "worst_year_net": min(row["net"] for row in rows),
                "production_ready": False,
            }
        )
    pd.DataFrame(summary).to_csv(output / "summary.csv", index=False)
    audit_outputs(output, annual, summary, [spec.name for spec in specs], years)
    if years == list(range(2010, 2026)):
        annual_map = {(row["strategy"], "native", str(row["year"])): row for row in annual}
        candidate_folds, selected_folds, selection_summary = build_custom_walkforward(
            [spec.name for spec in specs], annual_map, years
        )
        write_csv(output / "candidate-folds.csv", candidate_folds)
        write_csv(output / "selected-folds.csv", selected_folds)
        write_csv(output / "selection-summary.csv", selection_summary)
        manifest["selection_status"] = "retrospective_exposed_years_not_untouched_oos"
    else:
        manifest["selection_status"] = "not_run_requires_complete_2010_2025_history"
    manifest["output_sha256"] = {
        str(path.relative_to(output)): sha256(path) for path in sorted(output.rglob("*.csv"))
    }
    manifest["output_sha256"]["data-audit.json"] = sha256(output / "data-audit.json")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "COMPLETE").write_text(
        "Declared reconstructed parameter experiment complete; not live eligible.\n"
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec-file", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--years", type=int, nargs="+", default=list(range(2010, 2026)))
    args = parser.parse_args()
    for row in run(args.spec_file, args.cache, args.output, args.years):
        print(row["strategy"], row["trades"], row["net"], row["positive_years"])


if __name__ == "__main__":
    main()
