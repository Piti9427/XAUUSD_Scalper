"""Offline C22 preparation CLI. Exit0 means report written, not qualification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .artifacts import write_json, write_text
from .contract import build_manifest, compare_events
from .dashboard import build_dashboard, canvas_source
from .data_quality import audit_data
from .forward import draft_protocol, freeze_cohort, record_evidence, review_cohort
from .ledger import reconcile_export

ROOT = Path(__file__).resolve().parents[3]


def _output_path(value: Path) -> Path:
    path = value.resolve()
    if not path.is_relative_to(ROOT / "runs"):
        raise ValueError("Preparation outputs must stay under this repository's ignored runs/")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    manifest = commands.add_parser(
        "manifest", help="Bind complete Rules and current research evidence"
    )
    manifest.add_argument("--campaign", type=Path, required=True)
    manifest.add_argument("--candidate")
    parity = commands.add_parser("parity", help="Compare independent bound event snapshots")
    parity.add_argument("--reference", type=Path, required=True)
    parity.add_argument("--observed", type=Path, required=True)
    parity.add_argument("--candidate")
    costs = commands.add_parser(
        "costs", help="Normalize exported broker history without connecting"
    )
    costs.add_argument("--export", type=Path, required=True)
    costs.add_argument("--policy", type=Path)
    data = commands.add_parser("data", help="Bounded, read-only data quality checks")
    data.add_argument("--manifest", type=Path, required=True)
    data.add_argument("--bars", type=Path)
    data.add_argument("--ticks", type=Path)
    data.add_argument("--max-rows", type=int, default=10000)
    protocol = commands.add_parser(
        "protocol-template", help="Draft undecided criteria, without cohort activation"
    )
    protocol.add_argument("--manifest", type=Path, required=True)
    freeze = commands.add_parser(
        "freeze-cohort", help="Bind reviewed version/criteria; never activate execution"
    )
    freeze.add_argument("--manifest", type=Path, required=True)
    freeze.add_argument("--parity", type=Path, required=True)
    freeze.add_argument("--criteria", type=Path, required=True)
    freeze.add_argument("--cohort-dir", type=Path, required=True)
    observe = commands.add_parser(
        "record-evidence", help="Append candidate-bound prospective snapshots"
    )
    observe.add_argument("--cohort-dir", type=Path, required=True)
    observe.add_argument("--evidence", type=Path, required=True)
    observe.add_argument(
        "--kind", choices=["shadow", "broker_demo", "operational_stop", "review"], required=True
    )
    observe.add_argument("--observed-utc", required=True)
    review = commands.add_parser(
        "review-cohort", help="Validate and read the preserved observation chain"
    )
    review.add_argument("--cohort-dir", type=Path, required=True)
    dashboard = commands.add_parser("dashboard", help="Join snapshots without mixing cohorts")
    dashboard.add_argument("--reports", type=Path, nargs="+", required=True)
    dashboard.add_argument("--demo-report", type=Path)
    prepare = commands.add_parser("prepare", help="Build all five preparation snapshots")
    prepare.add_argument("--campaign", type=Path, required=True)
    prepare.add_argument("--candidate")
    prepare.add_argument("--export", type=Path, required=True)
    prepare.add_argument("--policy", type=Path)
    prepare.add_argument("--data-manifest", type=Path, required=True)
    prepare.add_argument("--bars", type=Path)
    prepare.add_argument("--max-rows", type=int, default=10000)
    prepare.add_argument("--demo-report", type=Path)
    prepare.add_argument("--out-dir", type=Path, required=True)
    for item in (manifest, parity, costs, data, protocol, review, dashboard):
        item.add_argument("--out", type=Path, required=True)
    return parser


def _prepare(args: argparse.Namespace) -> dict[str, Any]:
    directory = _output_path(args.out_dir)
    names = ("candidate.json", "costs.json", "data.json", "protocol.json", "dashboard.json")
    for name in names:
        if (directory / name).exists():
            raise FileExistsError(f"Preserve completed artifact: {directory / name}")
    if (directory / "canvas-source.txt").exists():
        raise FileExistsError("Preserve completed Canvas source; choose a new snapshot directory")
    manifest = build_manifest(args.campaign, args.candidate)
    write_json(directory / names[0], manifest)
    write_json(directory / names[1], reconcile_export(args.export, args.policy))
    write_json(
        directory / names[2], audit_data(args.data_manifest, args.bars, max_rows=args.max_rows)
    )
    write_json(directory / names[3], draft_protocol(directory / names[0]))
    result = build_dashboard([directory / name for name in names[:-1]], args.demo_report)
    write_json(directory / names[4], result)
    write_text(directory / "canvas-source.txt", canvas_source(result))
    return {
        "status": result["status"],
        "out_dir": str(directory),
        "artifacts": [*names, "canvas-source.txt"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            summary = _prepare(args)
        elif args.command == "freeze-cohort":
            result = freeze_cohort(
                args.manifest, args.parity, args.criteria, _output_path(args.cohort_dir)
            )
            summary = {"status": result["status"], "cohort_id": result["cohort_id"]}
        elif args.command == "record-evidence":
            result = record_evidence(
                _output_path(args.cohort_dir),
                args.evidence,
                kind=args.kind,
                observed_utc=args.observed_utc,
            )
            summary = {"status": "EVIDENCE_RECORDED", "sequence": result["sequence"]}
        else:
            output = _output_path(args.out)
            if output.exists():
                raise FileExistsError(f"Preserve completed artifact: {output}")
            if args.command == "manifest":
                result = build_manifest(args.campaign, args.candidate)
            elif args.command == "parity":
                result = compare_events(args.reference, args.observed, candidate_id=args.candidate)
            elif args.command == "costs":
                result = reconcile_export(args.export, args.policy)
            elif args.command == "data":
                result = audit_data(args.manifest, args.bars, args.ticks, args.max_rows)
            elif args.command == "protocol-template":
                result = draft_protocol(args.manifest)
            elif args.command == "review-cohort":
                result = review_cohort(_output_path(args.cohort_dir))
            else:
                result = build_dashboard(args.reports, args.demo_report)
            write_json(output, result)
            summary = {"status": result["status"], "out": str(output)}
        print(json.dumps({**summary, "execution_authorized": False}, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
