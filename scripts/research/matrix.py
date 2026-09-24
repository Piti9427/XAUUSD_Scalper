"""Audit a completed exploratory run and export traceable comparison matrices.

Usage: python -m scripts.research.matrix --baseline PATH --output NEW_PATH
No strategy run or parameter search occurs here. All performance cells are read
from a completed baseline and reconciled against its trade logs.
"""

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

MODES = ("common", "native")
FILTERS = ("rsi", "body", "fvg", "h1ema", "h1structure")
BASE_NAMES = (
    "Donchian20",
    "Donchian30",
    "Donchian40",
    "State15",
    "State20",
    "State25",
    "ATR1.25",
    "ATR1.5",
    "EMA10x30",
    "EMA20x50",
    "ORB30",
    "ORB60",
    "AsianBreak",
    "AsianRetest",
    "SweepReversal",
    "SweepMSS",
    "GSS_OTE",
)
DRILL_NAMES = ("A_TrendStructure", "B_Donchian30_RSI", "C_State25_RSI_FVG", "D_ATR1.5_RSI_FVG")
METRICS = (
    "trades",
    "net",
    "total_r",
    "expectancy_r",
    "pf",
    "win_rate",
    "max_closed_dd",
    "max_equity_dd",
    "recovery",
    "max_loss_streak",
    "long_pf",
    "short_pf",
    "avg_trade",
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def number(value):
    return None if value in (None, "") else float(value)


def close(actual, expected):
    return math.isclose(actual, expected, rel_tol=1e-8, abs_tol=1e-7)


def check_trade_log(path, annual):
    """Reconcile values and enforce causal, non-overlapping trade chronology."""
    count = 0
    net = total_r = 0.0
    gains = losses = 0.0
    previous_exit = None
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        required = {"entry_time", "exit_time", "signal_time", "net", "r"}
        if not required <= set(reader.fieldnames or ()):  # corrupt/partial log
            raise ValueError(f"Missing trade columns: {path}")
        for trade in reader:
            count += 1
            signal = datetime.fromisoformat(trade["signal_time"])
            entry = datetime.fromisoformat(trade["entry_time"])
            exit_at = datetime.fromisoformat(trade["exit_time"])
            if any(value.utcoffset() != timedelta(0) for value in (signal, entry, exit_at)):
                raise ValueError(f"Non-UTC trade timestamp {count}: {path}")
            if not (signal <= entry <= exit_at) or (
                previous_exit is not None and entry <= previous_exit
            ):
                raise ValueError(f"Noncausal/overlapping trade {count}: {path}")
            previous_exit = exit_at
            value = float(trade["net"])
            r_value = float(trade["r"])
            if not (math.isfinite(value) and math.isfinite(r_value)):
                raise ValueError(f"Nonfinite trade {count}: {path}")
            net += value
            total_r += r_value
            gains += max(value, 0.0)
            losses -= min(value, 0.0)
    if (
        count != int(annual["trades"])
        or not close(net, float(annual["net"]))
        or not close(total_r, float(annual["total_r"]))
    ):
        raise ValueError(f"Trade/annual reconciliation failed: {path}")
    pf = number(annual["pf"])
    if (pf is None) != (losses == 0) or (losses and not close(gains / losses, pf)):
        raise ValueError(f"Trade/annual PF mismatch: {path}")
    return count, net, total_r, gains, losses


def audited_run(baseline, code_dir, expected_names=120, expected_years=17):
    baseline = Path(baseline)
    if not (baseline / "COMPLETE").is_file():
        raise ValueError("Baseline is incomplete: COMPLETE marker missing")
    manifest = json.loads((baseline / "manifest.json").read_text())
    if manifest.get("version") != "btg-research-v1":
        raise ValueError("Unsupported baseline version")
    specs = manifest["strategies"]
    names = [s["name"] for s in specs]
    years = manifest["years"]
    if (
        len(names) != expected_names
        or len(set(names)) != len(names)
        or len(years) != expected_years
        or len(set(years)) != len(years)
    ):
        raise ValueError("Strategy/year coverage mismatch")
    if expected_names == 120 and tuple(names[:17]) != BASE_NAMES:
        raise ValueError("17-family base membership changed")
    if expected_names == 120:
        expected_filters = {f"{base}__{flt}" for base in BASE_NAMES for flt in FILTERS}
        if not expected_filters <= set(names):
            raise ValueError("85 single-filter variants missing")
    for filename, digest in manifest["code_sha256"].items():
        path = Path(code_dir) / filename
        if not path.is_file() or sha256(path) != digest:
            raise ValueError(f"Baseline code hash mismatch: {filename}")
    if (
        number(manifest["costs"]["commission_per_unit_roundtrip"]) != 0
        or number(manifest["costs"]["slippage"]) != 0
        or number(manifest["costs"]["swap_per_unit_night"]) != 0
        or manifest["delay_minutes"] != 0
    ):
        raise ValueError("Matrix requires observed-spread baseline, no scenario costs/delay")
    summary = read_csv(baseline / "summary.csv")
    annual = read_csv(baseline / "annual.csv")
    expected_pairs = {(n, m) for n in names for m in MODES}
    expected_keys = {(n, m, str(y)) for n, m in expected_pairs for y in years}
    summary_map = {(r["strategy"], r["mode"]): r for r in summary}
    annual_map = {(r["strategy"], r["mode"], r["year"]): r for r in annual}
    if len(summary) != len(expected_pairs) or set(summary_map) != expected_pairs:
        raise ValueError("Summary coverage or duplicate rows")
    if len(annual) != len(expected_keys) or set(annual_map) != expected_keys:
        raise ValueError("Annual coverage or duplicate rows")
    totals = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0, 0])
    for key in sorted(expected_keys):
        name, mode, year = key
        row = annual_map[key]
        path = baseline / "trades" / f"{name}__{mode}__{year}.csv"
        if not path.is_file():
            raise ValueError(f"Trade log missing: {path}")
        n, net, r, gains, losses = check_trade_log(path, row)
        total = totals[(name, mode)]
        total[0] += n
        total[1] += net
        total[2] += r
        total[3] += gains
        total[4] += losses
        total[5] += net > 0
    for key, row in summary_map.items():
        n, net, r, gains, losses, positive = totals[key]
        pf = number(row["pf"])
        if (
            n != int(row["trades"])
            or not close(net, float(row["net"]))
            or not close(r, float(row["total_r"]))
            or positive != int(row["positive_years"])
        ):
            raise ValueError(f"Annual/summary reconciliation failed: {key}")
        if (pf is None) != (losses == 0) or (losses and not close(gains / losses, pf)):
            raise ValueError(f"Annual/summary PF mismatch: {key}")
        if row["production_ready"].lower() != "false":
            raise ValueError(f"Unexpected production promotion: {key}")
    return manifest, specs, summary_map, annual_map


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"No rows for {path.name}")
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def build_matrix(baseline, output, code_dir, expected_names=120, expected_years=17):
    baseline, output = Path(baseline).resolve(), Path(output)
    manifest, specs, summary, annual = audited_run(
        baseline, code_dir, expected_names, expected_years
    )
    names = [s["name"] for s in specs]
    bases = [n for n in BASE_NAMES if n in names]
    specs_by_name = {s["name"]: s for s in specs}

    def metric_row(name, mode):
        row = summary[(name, mode)]
        return {
            "strategy": name,
            "mode": mode,
            "family": specs_by_name[name]["family"],
            "filters": "+".join(specs_by_name[name]["filters"]),
            "contract_status": "reconstructed",
            "production_ready": "False",
            **{k: row[k] for k in METRICS if k in row},
            "years": row["years"],
            "positive_years": row["positive_years"],
            "worst_year_net": row["worst_year_net"],
            "source_summary": str(baseline / "summary.csv"),
            "source_trade_logs": str(baseline / "trades" / f"{name}__{mode}__YEAR.csv"),
        }

    family_rows = [metric_row(n, m) for n in bases for m in MODES]
    variant_rows = [metric_row(n, m) for n in names for m in MODES]
    ablations = []
    for base in bases:
        for flt in FILTERS:
            variant = f"{base}__{flt}"
            if variant not in specs_by_name:
                continue
            for mode in MODES:
                b, v = summary[(base, mode)], summary[(variant, mode)]
                matched = [
                    (annual[(base, mode, str(y))], annual[(variant, mode, str(y))])
                    for y in manifest["years"]
                ]
                ablations.append(
                    {
                        "base": base,
                        "filter": flt,
                        "variant": variant,
                        "mode": mode,
                        "base_trades": b["trades"],
                        "variant_trades": v["trades"],
                        "base_net": b["net"],
                        "variant_net": v["net"],
                        "delta_net": float(v["net"]) - float(b["net"]),
                        "base_total_r": b["total_r"],
                        "variant_total_r": v["total_r"],
                        "delta_total_r": float(v["total_r"]) - float(b["total_r"]),
                        "years_variant_net_higher": sum(
                            float(x[1]["net"]) > float(x[0]["net"]) for x in matched
                        ),
                        "years_base_net_higher": sum(
                            float(x[0]["net"]) > float(x[1]["net"]) for x in matched
                        ),
                        "years_equal_net": sum(
                            float(x[0]["net"]) == float(x[1]["net"]) for x in matched
                        ),
                        "contract_status": "reconstructed",
                        "production_ready": "False",
                        "source_summary": str(baseline / "summary.csv"),
                        "source_annual": str(baseline / "annual.csv"),
                    }
                )
    annual_rows = []
    for n in names:
        for m in MODES:
            for y in manifest["years"]:
                row = annual[(n, m, str(y))]
                annual_rows.append(
                    {
                        **row,
                        "contract_status": "reconstructed",
                        "source_trade_log": str(baseline / "trades" / f"{n}__{m}__{y}.csv"),
                    }
                )
    drill = [metric_row(n, m) for n in DRILL_NAMES if n in names for m in MODES]
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    output.mkdir(parents=True)
    files = {
        "family-matrix.csv": family_rows,
        "variant-matrix.csv": variant_rows,
        "ablation-matrix.csv": ablations,
        "annual-matrix.csv": annual_rows,
        "a-d-drilldown.csv": drill,
    }
    for filename, rows in files.items():
        write_csv(output / filename, rows)
    provenance = {
        "status": "audited_reconstructed_research_only",
        "selection": "No production candidate selected; no untouched OOS, original broad-search source, or verified broker costs/ticks",
        "baseline_dir": str(baseline),
        "source_revision": manifest["source_revision"],
        "input_sha256": [
            {"file": x["file"], "sha256": x["sha256"], "url": x["url"]} for x in manifest["inputs"]
        ],
        "baseline_sha256": {
            x: sha256(baseline / x)
            for x in ("manifest.json", "summary.csv", "annual.csv", "data-audit.json", "COMPLETE")
        },
        "code_sha256": manifest["code_sha256"],
        "counts": {
            "families": len(bases),
            "specs": len(names),
            "modes": 2,
            "years": len(manifest["years"]),
            "family_rows": len(family_rows),
            "variant_rows": len(variant_rows),
            "ablation_rows": len(ablations),
            "annual_rows": len(annual_rows),
            "trade_logs_verified": len(annual_rows),
        },
        "output_sha256": {x: sha256(output / x) for x in files},
    }
    (output / "matrix-manifest.json").write_text(json.dumps(provenance, indent=2) + "\n")
    (output / "COMPLETE").write_text("Audited matrix complete; reconstructed research only.\n")
    return provenance


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--code-dir", type=Path, default=Path(__file__).parent)
    args = p.parse_args()
    print(json.dumps(build_matrix(args.baseline, args.output, args.code_dir)["counts"], indent=2))


if __name__ == "__main__":
    main()
