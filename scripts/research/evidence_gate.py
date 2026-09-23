"""Fail-closed evidence screen for completed BotTradeGold research runs.

This reports observed performance and arithmetic cost headroom. It cannot
certify a strategy for live trading or infer missing broker execution costs.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from .matrix import BASE_NAMES, audited_run, sha256, write_csv


def verify_source_cache(cache, manifest):
    """Rehash every price file named by the completed run, without redownloading."""
    cache = Path(cache)
    inputs = manifest["inputs"]
    if not inputs or len({item["file"] for item in inputs}) != len(inputs):
        raise ValueError("Missing or duplicate source files in run manifest")
    total_bytes = 0
    for item in inputs:
        name = item["file"]
        if Path(name).name != name or not name.endswith(".csv"):
            raise ValueError(f"Unsafe source filename: {name}")
        path = cache / name
        if not path.is_file():
            raise ValueError(f"Source file missing: {path}")
        size = path.stat().st_size
        if size != int(item["bytes"]):
            raise ValueError(f"Source size mismatch: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != item["sha256"]:
            raise ValueError(f"Source hash mismatch: {path}")
        total_bytes += size
    return {"files_verified": len(inputs), "bytes_verified": total_bytes}


def evidence_row(name, spec, summary, annual, years, units):
    """One spec; all numbers come from audited summary/annual rows."""
    native = summary[name, "native"]
    common = summary[name, "common"]
    native_years = [annual[name, "native", str(year)] for year in years]
    native_net = float(native["net"])
    trades = int(native["trades"])
    yearly_nets = [float(row["net"]) for row in native_years]
    positive_year_nets = [max(0.0, value) for value in yearly_nets]
    sum_positive = sum(positive_year_nets)
    if not (math.isfinite(native_net) and math.isfinite(units) and units > 0):
        raise ValueError(f"Invalid net or units: {name}")
    cost_budget = native_net / (trades * units) if native_net > 0 and trades else None
    status = (
        "no_observed_trades" if not trades else
        "nonpositive_reconstructed_native" if native_net <= 0 else
        "positive_reconstructed_only"
    )
    return {
        "strategy": name,
        "family": spec["family"],
        "contract_status": "reconstructed",
        "research_status": status,
        "production_ready": False,
        "common_net": float(common["net"]),
        "common_total_r": float(common["total_r"]),
        "native_net": native_net,
        "native_total_r": float(native["total_r"]),
        "native_trades": trades,
        "native_pf": native["pf"],
        "positive_years": int(native["positive_years"]),
        "years": len(years),
        "latest_year": years[-1],
        "latest_year_net": yearly_nets[-1],
        "net_excluding_latest_year": sum(yearly_nets[:-1]),
        "largest_positive_year_share": max(positive_year_nets) / sum_positive if sum_positive else None,
        "extra_cost_to_zero_per_unit_roundtrip": cost_budget,
        "cost_budget_units": "USD per 1 oz per trade, in addition to observed historical Bid/Ask spread",
        "source_trade_logs": f"trades/{name}__native__YEAR.csv",
    }


def build_gate(baseline, cache, output, code_dir, expected_names=120, expected_years=17):
    """Audit source bytes and every trade log before writing a research-only screen."""
    baseline, output = Path(baseline).resolve(), Path(output)
    manifest, specs, summary, annual = audited_run(
        baseline, code_dir, expected_names=expected_names, expected_years=expected_years
    )
    source_check = verify_source_cache(cache, manifest)
    years = sorted(manifest["years"])
    units = float(manifest["costs"]["units"])
    rows = [
        evidence_row(spec["name"], spec, summary, annual, years, units)
        for spec in specs
    ]
    base_names = set(BASE_NAMES)
    family_rows = [row for row in rows if row["strategy"] in base_names]
    if expected_names == 120 and len(family_rows) != 17:
        raise ValueError("17-family screen incomplete")
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    output.mkdir(parents=True)
    write_csv(output / "family-screen.csv", family_rows)
    write_csv(output / "all-specs-screen.csv", rows)
    gate = {
        "status": "audited_research_screen_only",
        "production_ready": False,
        "reason": "Original strategy parity, broker ticks and non-spread costs, independent post-selection validation, and forward execution evidence are not established by this run.",
        "basis": "Native net sign only screens the reconstructed contract; it does not prove or disprove the original named strategy.",
        "cost_budget_definition": "native_net / (native_trades * units) when native_net > 0; algebraic headroom only, not a measured cost or profit forecast",
        "source_cache": source_check,
        "source_revision": manifest["source_revision"],
        "baseline": str(baseline),
        "baseline_sha256": {name: sha256(baseline / name) for name in
                            ("manifest.json", "summary.csv", "annual.csv", "data-audit.json", "COMPLETE")},
        "code_sha256": manifest["code_sha256"],
        "audit_code_sha256": {name: sha256(Path(__file__).with_name(name)) for name in
                              ("matrix.py", "evidence_gate.py")},
        "counts": {"families": len(family_rows), "specs": len(rows), "years": len(years)},
        "output_sha256": {name: sha256(output / name) for name in
                          ("family-screen.csv", "all-specs-screen.csv")},
    }
    (output / "gate-manifest.json").write_text(json.dumps(gate, indent=2) + "\n")
    (output / "COMPLETE").write_text("Price bytes and trade logs audited; research screen only.\n")
    return gate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-dir", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    gate = build_gate(args.baseline, args.cache, args.output, args.code_dir)
    print(json.dumps(gate["counts"], indent=2))


if __name__ == "__main__":
    main()
