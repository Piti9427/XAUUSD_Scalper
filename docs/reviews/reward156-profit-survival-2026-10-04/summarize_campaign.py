"""Generate readable verdict and policy/config comparison from completed artifacts."""

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    if not __debug__:
        raise RuntimeError("Summary verification requires assertions enabled; do not use -O")
    complete = json.loads((ROOT / "COMPLETE.json").read_text())
    validation = json.loads((ROOT / "validation.json").read_text())
    assert validation["status"] == "VERIFIED"
    for name, expected in validation["consumed_artifact_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    assert (
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == validation["summarizer_sha256"]
    )
    assert (
        hashlib.sha256((ROOT / "verify_campaign.py").read_bytes()).hexdigest()
        == validation["verifier_sha256"]
    )
    checks = json.loads((ROOT / "checks.json").read_text())
    assert (
        hashlib.sha256((ROOT / "unittest.log").read_bytes()).hexdigest()
        == checks["unittest"]["log_sha256"]
    )
    data = json.loads((ROOT / "results.json").read_text())
    rows = data["rows"]
    decision = json.loads((ROOT / "verdict.json").read_text())
    assert decision == data["verdict"]
    assert validation["behavior_sha256"] == complete["behavior_sha256"]
    test_evidence = (
        f"Full suite:{checks['unittest']['tests']}tests/{checks['unittest']['seconds']}seconds/"
        + checks["unittest"]["summary"]
        + ". "
    )
    catalog = []
    for name in ("seed-catalog.json", "one-factor-catalog.json", "combination-catalog.json"):
        path = ROOT / name
        if path.exists():
            catalog += json.loads(path.read_text())
    ordered = sorted(
        data["candidates"],
        key=lambda c: (-c["passing_continuous"], -c["worst_net"], c["worst_dd"], c["config_id"]),
    )
    candidate_name = decision["selected"] or ordered[0]["name"]
    candidate = next(c for c in catalog if c["name"] == candidate_name)
    ranking = next(c for c in ordered if c["name"] == candidate_name)
    policy = [
        ("Full profit", ">0 and above trial30", ">=USD50 and above BOTH controls"),
        ("DD", "<=35%", "<=45%"),
        ("Reset-half profit", ">0 and above trial30", ">=-USD20"),
        ("WR/RR", "strict baseline comparison; RR>1", "report-only; undefined preserved"),
        ("BUY+SELL", "each full/half cell", "full cells only"),
        (
            "Cost views used for qualification",
            "current-spec swap",
            "no_swap AND swap plus swap0.5x/1.5x finalists",
        ),
        ("Risk/lot/capital", "10% ceiling/fixed0.01/USD200", "same"),
    ]
    lines = [
        "# Reward156 profit/survival v2 — measured verdict",
        "",
        f"Selected: **{decision['selected'] or 'NONE'}**. Holdout: `{decision['holdout']}`.",
        f"Evaluated {complete['evaluated_candidates']} configurations; {complete['cells']} cells; "
        f"{complete['fresh_full_result_matches']} fresh complete-result matches.",
        "Demo: unchanged trial30. Profit/survival qualification applies to modeled research scenarios.",
        "",
        "## Policy relaxation",
        "",
        "| Rule | Frozen v1 | Owner-approved v2 |",
        "|---|---|---|",
    ]
    lines += ["| " + " | ".join(p) + " |" for p in policy]
    lines += [
        "",
        "## Configuration result",
        "",
        f"{'Discovery winner' if decision['selected'] else 'Highest-ranked measured candidate'}: `{candidate_name}`; "
        f"continuous passes **{ranking['passing_continuous']}/8**, worst net **${ranking['worst_net']:.2f}**, "
        f"worst DD **{ranking['worst_dd']:.2f}%**.",
        "",
        "```json",
        json.dumps(candidate, indent=2),
        "```",
        "",
        "## Paired continuous accounts",
        "",
        "| Dataset | Cost/view | trial30 net | Original Reward156 net | Candidate net | Candidate DD% | Trades | Failed v2 gates |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    comparisons = []
    for row in rows:
        if (
            row["contract"] != candidate_name
            or row["window"] != "full"
            or row["cost_view"] not in ("swap", "no_swap")
        ):
            continue
        peers = {
            p["contract"]: p["metrics"]
            for p in rows
            if p["contract"] in ("trial30", "reward156_original")
            and all(p[k] == row[k] for k in ("dataset", "window", "cost", "cost_view"))
        }
        metrics = row["metrics"]
        failed = [k for k, v in row["gates"].items() if not v]
        lines.append(
            f"| {row['dataset']} | {row['cost']}/{row['cost_view']} | {peers['trial30']['net_usd']:.2f} | "
            f"{peers['reward156_original']['net_usd']:.2f} | {metrics['net_usd']:.2f} | "
            f"{metrics['max_dd_pct']:.2f} | {metrics['trades']} | {', '.join(failed) or 'PASS'} |"
        )
        comparisons.append(
            dict(
                dataset=row["dataset"],
                cost=row["cost"],
                cost_view=row["cost_view"],
                candidate=row["contract"],
                failed_gates=failed,
            )
        )
    lines += [
        "",
        "## Diagnosis and scope",
        "",
        "Per-side net/loss/MAE/MFE and multi-loss days: `diagnostics/`. Independently replayed "
        "swap/no-swap admission divergence: `cost-path-divergence.json`. "
        "`swap_on_losing_non_tp_exits` includes losing SL/end exits; it is not a protection-only metric.",
        "A: Sep2024–Jun2025 discovery10months; B: Oct2025–Sep2026 discovery12months. "
        "Halves reset USD200 account state; profits are not added to continuous account results.",
        "Base: archived spread, modeled slippage/commission0. Stress: spread+0.20USD/oz, "
        "slippage0.10USD/oz, commission0. Current-spec swap and assumed UTC rollover are sensitivity "
        "scenarios; historical rates/rollover/DST/entitlement and live broker parity remain unverified.",
        "Archived seeds retain their own RSI formula; frozen Reward156 retains zero-loss RSI semantics. "
        "Strategy-specific filters/exits/circuits differ explicitly. Market/account/cost environments stay paired.",
        "Historical holdout opening is conditional on a locked discovery qualifier; holdout is not prospective.",
        "",
        "## Completion evidence",
        "",
        test_evidence + "Changed-Python Ruff and syntax compilation passed. "
        "No configured static typechecker; compilation is not typechecking. "
        "Standards/Spec findings fixed and re-reviewed.",
        "Independent `verify_campaign.py`: source/input/checkpoint hashes, complete ledger cashflow, "
        "lot/risk invariants, recomputed policy/adaptive catalog, fresh-repeat attestations and "
        "v1 control full-result parity. See `validation.json` and `completion-audit.md`.",
        "",
        "V1 performance/qualification artifacts remain immutable. "
        "A complete finite experiment can end with the profit objective unmet.",
    ]
    (ROOT / "summary.md").write_text("\n".join(lines) + "\n")
    (ROOT / "policy-comparison.json").write_text(
        json.dumps(dict(policy=policy, candidate=candidate, comparisons=comparisons), indent=2)
        + "\n"
    )
    print(candidate_name, ranking["passing_continuous"], "/8")


if __name__ == "__main__":
    main()
