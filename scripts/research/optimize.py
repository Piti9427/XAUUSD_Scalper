"""Retrospective expanding-window selection from an audited BotTradeGold run.

Usage: python -m scripts.research.optimize --baseline PATH --output NEW_PATH

This reuses verified annual backtests. It never labels historical folds untouched
OOS and never promotes a strategy for live execution.
"""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from .matrix import BASE_NAMES, FILTERS, MODES, audited_run, sha256, write_csv


def _contract_key(spec):
    # Names and reconstruction labels do not alter signals or execution.
    return json.dumps(
        {key: value for key, value in spec.items() if key not in ("name", "reconstruction")},
        sort_keys=True,
    )


def _groups(specs):
    names = {spec["name"] for spec in specs}
    if tuple(spec["name"] for spec in specs[:17]) != BASE_NAMES:
        raise ValueError("17 base configurations changed")
    groups = {base: [base] + [f"{base}__{flt}" for flt in FILTERS] for base in BASE_NAMES}
    if any(not set(members) <= names for members in groups.values()):
        raise ValueError("Missing base or ablation")
    unique = {}
    aliases = []
    for spec in specs:
        key = _contract_key(spec)
        if key in unique:
            aliases.append({"alias": spec["name"], "canonical": unique[key]})
        else:
            unique[key] = spec["name"]
    return groups, sorted(unique.values()), aliases


def _candidate_row(name, year, train_years, annual, mode):
    past = [annual[(name, mode, str(y))] for y in train_years]
    future = annual[(name, mode, str(year))]
    past_net = [float(row["net"]) for row in past]
    return {
        "strategy": name,
        "mode": mode,
        "test_year": year,
        "train_first_year": train_years[0],
        "train_last_year": train_years[-1],
        "train_years": len(train_years),
        "train_trades": sum(int(row["trades"]) for row in past),
        "train_net": sum(past_net),
        "train_median_annual_net": statistics.median(past_net),
        "train_positive_years": sum(value > 0 for value in past_net),
        "test_trades": int(future["trades"]),
        "test_net": float(future["net"]),
        "test_total_r": float(future["total_r"]),
        "test_pf": future["pf"],
    }


def _rank(row):
    # Objective is explicit and fixed before reading a future year's outcome.
    return (
        -row["train_median_annual_net"],
        -row["train_net"],
        -row["train_positive_years"],
        -row["train_trades"],
        row["strategy"],
    )


def build_walkforward(
    specs, annual, years, mode="native", first_test_year=2018, last_test_year=2025
):
    """Select per base and globally using prior years only; test next year once."""
    if mode not in MODES:
        raise ValueError("Unsupported mode")
    if (
        not years
        or years != sorted(set(years))
        or first_test_year <= years[0]
        or last_test_year < first_test_year
    ):
        raise ValueError("Invalid chronological folds")
    if last_test_year > 2025:
        raise ValueError("Partial 2026 is excluded from fold selection")
    if set(range(years[0], last_test_year + 1)) - set(years):
        raise ValueError("Annual history has missing years")
    groups, unique_names, aliases = _groups(specs)
    rows = []
    selected = []
    for year in range(first_test_year, last_test_year + 1):
        train = [y for y in years if y < year]
        fold = {name: _candidate_row(name, year, train, annual, mode) for name in unique_names}
        rows.extend(fold.values())
        for base, members in groups.items():
            winner = min((fold[name] for name in members), key=_rank)
            benchmark = fold[base]
            selected.append(
                {
                    "scope": "base_group",
                    "base": base,
                    **winner,
                    "base_test_net": benchmark["test_net"],
                    "base_test_trades": benchmark["test_trades"],
                }
            )
        winner = min(fold.values(), key=_rank)
        selected.append(
            {
                "scope": f"global_{len(unique_names)}_unique_contracts",
                "base": "",
                **winner,
                "base_test_net": "",
                "base_test_trades": "",
            }
        )
    by_scope = defaultdict(list)
    for row in selected:
        by_scope[(row["scope"], row["base"])].append(row)
    summaries = []
    for (scope, base), fold_rows in sorted(by_scope.items()):
        summaries.append(
            {
                "scope": scope,
                "base": base,
                "test_first_year": first_test_year,
                "test_last_year": last_test_year,
                "folds": len(fold_rows),
                "selected_contracts": ";".join(sorted({row["strategy"] for row in fold_rows})),
                "selected_test_trades": sum(row["test_trades"] for row in fold_rows),
                "selected_test_net": sum(row["test_net"] for row in fold_rows),
                "selected_positive_test_years": sum(row["test_net"] > 0 for row in fold_rows),
                "base_test_net": sum(float(row["base_test_net"]) for row in fold_rows)
                if base
                else "",
                "production_ready": False,
            }
        )
    return rows, selected, summaries, aliases


def build_custom_walkforward(
    names, annual, years, mode="native", first_test_year=2018, last_test_year=2025
):
    """Use the same frozen objective for a declared candidate set."""
    if not names or len(set(names)) != len(names) or mode not in MODES:
        raise ValueError("Invalid candidate pool")
    if (
        not years
        or years != sorted(set(years))
        or first_test_year <= years[0]
        or last_test_year < first_test_year
        or last_test_year > 2025
        or set(range(years[0], last_test_year + 1)) - set(years)
    ):
        raise ValueError("Invalid complete-year folds")
    candidates, selected = [], []
    for year in range(first_test_year, last_test_year + 1):
        train = [y for y in years if y < year]
        fold = [_candidate_row(name, year, train, annual, mode) for name in names]
        candidates.extend(fold)
        selected.append(min(fold, key=_rank))
    summary = {
        "folds": len(selected),
        "test_first_year": first_test_year,
        "test_last_year": last_test_year,
        "selected_contracts": ";".join(sorted({row["strategy"] for row in selected})),
        "selected_test_trades": sum(row["test_trades"] for row in selected),
        "selected_test_net": sum(row["test_net"] for row in selected),
        "selected_positive_test_years": sum(row["test_net"] > 0 for row in selected),
        "selected_negative_train_net_folds": sum(row["train_net"] <= 0 for row in selected),
        "production_ready": False,
    }
    return candidates, selected, [summary]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=MODES, default="native")
    parser.add_argument("--first-test-year", type=int, default=2018)
    parser.add_argument("--last-test-year", type=int, default=2025)
    args = parser.parse_args()
    code_dir = Path(__file__).parent
    manifest, specs, _, annual = audited_run(args.baseline, code_dir)
    candidates, selected, summaries, aliases = build_walkforward(
        specs, annual, manifest["years"], args.mode, args.first_test_year, args.last_test_year
    )
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "candidate-folds.csv", candidates)
    write_csv(output / "selected-folds.csv", selected)
    write_csv(output / "selection-summary.csv", summaries)
    report = {
        "status": "retrospective_walkforward_research_only",
        "production_ready": False,
        "reason": "Contracts were reconstructed and all historical years were previously exposed during research; broker costs/ticks and untouched OOS remain unavailable.",
        "baseline": str(args.baseline.resolve()),
        "baseline_manifest_sha256": sha256(args.baseline / "manifest.json"),
        "optimizer_sha256": sha256(__file__),
        "source_revision": manifest["source_revision"],
        "mode": args.mode,
        "first_test_year": args.first_test_year,
        "last_test_year": args.last_test_year,
        "selection_objective": "maximum training median annual net, then total net, positive years, trades, lexicographic name",
        "group_policy": "17 bases each compete against their five single-filter ablations; global pool includes unique contracts among all 120 specs",
        "aliases_excluded_from_global_pool": aliases,
        "cost_policy": manifest["cost_status"],
        "counts": {
            "unique_contracts": len({row["strategy"] for row in candidates}),
            "candidate_fold_rows": len(candidates),
            "selected_fold_rows": len(selected),
            "summary_rows": len(summaries),
        },
    }
    for filename in ("candidate-folds.csv", "selected-folds.csv", "selection-summary.csv"):
        report.setdefault("output_sha256", {})[filename] = sha256(output / filename)
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "COMPLETE").write_text(
        "Audited retrospective selection completed; not live eligible.\n"
    )
    print(json.dumps(report["counts"], indent=2))


if __name__ == "__main__":
    main()
