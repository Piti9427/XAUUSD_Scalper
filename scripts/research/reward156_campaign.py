"""Resumable paired profit/survival campaign. Offline research only."""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

from scripts.research.breakout_logic import Costs, replay
from scripts.research.public_exness_archive import load_discovery
from scripts.research.rollover import SwapPolicy
from scripts.research.reward156_search import (
    POLICY,
    GROUPS,
    cell_gates,
    combinations,
    config_id,
    prepare_candidate,
    rank,
    seeds,
    variant_catalog,
)
from scripts.research.reward156_tuning import SOURCES, atomic_json, summary
from scripts.research.tune_breakout_logic import sha256

CONFIG = Path("config/reward156-profit-survival.json")
OUTPUT = Path("docs/reviews/reward156-profit-survival-2026-10-04")
PLAN = Path(".cursor/plans/long-term_macro_gate_99f085f3.plan.md")
CONTROLS = [
    dict(name="trial30", strategy="trial30", macro_span=0, buy_pause_drawdown=0.0),
    dict(name="reward156_original", strategy="reward156", macro_span=0, buy_pause_drawdown=0.05),
]
EXTRA_SOURCES = [
    "scripts/research/reward156_search.py",
    "scripts/research/reward156_campaign.py",
    "scripts/research/campaign_signals.py",
    "scripts/research/reward156_holdout.py",
]


class Checkpoints:
    """Every cached result is hash-attested, including unrepeated screening cells."""

    def __init__(self, output, digest):
        self.output, self.digest = output, digest

    def execute(self, key, execute, repeat=False):
        path = self.output / "cells" / (key + ".json")
        proof = self.output / "integrity" / (key + ".json")
        if path.exists() and proof.exists():
            meta = json.loads(proof.read_text())
            if meta["behavior_sha256"] != self.digest or meta["result_sha256"] != sha256(path):
                raise ValueError("checkpoint integrity mismatch: " + key)
            result = json.loads(path.read_text())
        else:
            result = execute()
            atomic_json(path, result)
            meta = dict(
                behavior_sha256=self.digest,
                result_sha256=sha256(path),
                fresh_full_result_match=False,
            )
            atomic_json(proof, meta)
        if repeat and not meta["fresh_full_result_match"]:
            if execute() != result:
                raise ValueError("full result repeat mismatch: " + key)
            meta["fresh_full_result_match"] = True
            atomic_json(proof, meta)
        return result


def validate_config(config):
    if any(
        config.get(k) != v
        for k, v in dict(
            version=2,
            policy=POLICY,
            research_only=True,
            initial_equity=200.0,
            volume=0.01,
            risk_cap=0.1,
            daily_loss_limit=0.2,
        ).items()
    ):
        raise ValueError("profit/survival contract pins changed")
    if config["limits"] != dict(
        one_factor_per_seed=27, selected_seeds=2, new_configs=62, finalists=6
    ):
        raise ValueError("finite search limits changed")
    if config["seeds"] != seeds() or config["domains"] != json.loads(json.dumps(GROUPS)):
        raise ValueError("registered catalog/domain drift")
    original = json.loads(Path("config/reward156-tuning.json").read_text())
    if config["datasets"] != original["datasets"] or config["costs"] != original["costs"]:
        raise ValueError("paired market/cost environment drift")
    from scripts.research.reward156_tuning import validate_config as validate_v1

    validate_v1(original)


def freeze(output, config_path, config):
    source_hashes = {p: sha256(p) for p in [*SOURCES, *EXTRA_SOURCES]}
    contract = dict(
        policy=POLICY,
        config=config,
        config_sha256=sha256(config_path),
        sources=source_hashes,
        runtime=dict(python=sys.version, pandas=pd.__version__, numpy=np.__version__),
        datasets={
            n: sha256(Path(d["path"]) / "dataset.json") for n, d in config["datasets"].items()
        },
        plan_spec_sha256=hashlib.sha256(PLAN.read_text().split("---", 2)[2].encode()).hexdigest(),
    )
    digest = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    contract["behavior_sha256"] = digest
    target = output / "contract.json"
    if target.exists():
        if json.loads(target.read_text()) != contract:
            raise ValueError("resume source/config/input drift; new output required")
    else:
        atomic_json(target, contract)
    for source, expected in source_hashes.items():
        snapshot = output / "source_snapshot" / source
        if snapshot.exists():
            if sha256(snapshot) != expected:
                raise ValueError("source snapshot drift")
        else:
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, snapshot)
    return digest


def diagnose(result):
    ledger = result["ledger"]
    by_side = {}
    for side, direction in [("BUY", 1), ("SELL", -1)]:
        trades = [t for t in ledger if t["direction"] == direction]
        by_side[side] = dict(
            trades=len(trades),
            net=sum(t["net"] for t in trades),
            losses=sum(t["net"] < 0 for t in trades),
            median_mae_usd=float(np.median([t["mae_usd"] for t in trades])) if trades else None,
            median_mfe_usd=float(np.median([t["mfe_usd"] for t in trades])) if trades else None,
            swap_on_losing_non_tp_exits=sum(
                t.get("swap_usd", 0) for t in trades if t["reason"] != "TP" and t["net"] < 0
            ),
        )
    losses = {}
    for t in ledger:
        if t["net"] < 0:
            day = t["exit_time_utc"][:10]
            losses.setdefault(day, []).append(t["net"])
    return dict(
        by_side=by_side,
        multiple_loss_days={
            d: dict(losses=len(v), net=sum(v)) for d, v in losses.items() if len(v) > 1
        },
    )


def path_divergence(no_swap, swap):
    """Compare observed admission paths, not post-hoc swap subtraction."""
    left = [
        (e["time_utc"], e["direction"])
        for e in no_swap["admission_events"]
        if e["reason"] == "admitted"
    ]
    right = [
        (e["time_utc"], e["direction"])
        for e in swap["admission_events"]
        if e["reason"] == "admitted"
    ]
    mismatch = next(
        (
            i
            for i in range(max(len(left), len(right)))
            if (left[i] if i < len(left) else None) != (right[i] if i < len(right) else None)
        ),
        None,
    )
    return dict(
        first_different_admission_index=mismatch,
        no_swap_admission=left[mismatch] if mismatch is not None and mismatch < len(left) else None,
        swap_admission=right[mismatch] if mismatch is not None and mismatch < len(right) else None,
        no_swap_risk_rejections=no_swap["rejections"]["risk_cap"],
        swap_risk_rejections=swap["rejections"]["risk_cap"],
    )


class Campaign:
    def __init__(self, config, output, digest):
        self.config, self.output = config, output
        self.checkpoints = Checkpoints(output, digest)
        self.datasets, self.rows = {}, {}
        for name, ds in config["datasets"].items():
            frame, ticks, broker, audit = load_discovery(Path(ds["path"]))
            if audit["start_utc"] != ds["start"] or audit["end_utc"] != ds["end"]:
                raise ValueError("discovery bounds mismatch")
            self.datasets[name] = (frame, ticks, broker)
            atomic_json(output / ("input-" + name + ".json"), audit)
            print(f"Loaded {name}: {len(frame)} bars / {len(ticks[0]):,} ticks", flush=True)

    def cells(self, candidate, windows=("full",), views=("no_swap", "swap"), repeat=False):
        for name, ds in self.config["datasets"].items():
            raw, ticks, broker = self.datasets[name]
            frame, rules = prepare_candidate(raw, candidate)
            bounds = [pd.Timestamp(ds[k], tz="UTC") for k in ("start", "split", "end")]
            ranges = dict(
                full=(bounds[0], bounds[2]),
                first_half=(bounds[0], bounds[1]),
                second_half=(bounds[1], bounds[2]),
            )
            policy = SwapPolicy.from_broker(broker)
            for window in windows:
                start, end = ranges[window]
                for cost, options in self.config["costs"].items():
                    for view in views:
                        swap = (
                            None
                            if view == "no_swap"
                            else replace(
                                policy,
                                long_points=policy.long_points
                                * {"swap": 1.0, "swap_0.5": 0.5, "swap_1.5": 1.5}[view],
                                short_points=policy.short_points
                                * {"swap": 1.0, "swap_0.5": 0.5, "swap_1.5": 1.5}[view],
                            )
                        )
                        key = "-".join((name, window, cost, view, candidate["name"]))
                        result = self.checkpoints.execute(
                            key,
                            lambda: replay(
                                frame,
                                ticks,
                                broker,
                                rules,
                                Costs(**options),
                                start=start,
                                end=end,
                                swap_policy=swap,
                                capture_events=True,
                            ),
                            repeat,
                        )
                        metrics = summary(result, frame, start, end)
                        metrics["bankrupt"] = any(
                            t["reason"] == "BANKRUPT" for t in result["ledger"]
                        ) or any(p["equity_usd"] <= 0 for p in result["equity"])
                        row = dict(
                            dataset=name,
                            window=window,
                            cost=cost,
                            cost_view=view,
                            contract=candidate["name"],
                            config_id=config_id(candidate),
                            start_utc=start.isoformat(),
                            end_exclusive_utc=end.isoformat(),
                            metrics=metrics,
                        )
                        if candidate["name"] not in {c["name"] for c in CONTROLS}:
                            peers = [
                                self.rows["-".join((name, window, cost, view, c["name"]))][
                                    "metrics"
                                ]
                                for c in CONTROLS
                            ]
                            row["gates"] = cell_gates(metrics, peers, window)
                        self.rows[key] = row
                        atomic_json(self.output / "diagnostics" / (key + ".json"), diagnose(result))
                        print(
                            f"{key}: net={metrics['net_usd']:.2f} DD={metrics['max_dd_pct']:.2f} "
                            f"trades={metrics['trades']}",
                            flush=True,
                        )
        return [r for r in self.rows.values() if r["contract"] == candidate["name"]]

    def qualified(self, candidate, windows=("full",), views=("no_swap", "swap")):
        rows = [
            r
            for r in self.rows.values()
            if r["contract"] == candidate["name"]
            and r["window"] in windows
            and r["cost_view"] in views
        ]
        return len(rows) == 2 * len(windows) * 2 * len(views) and all(
            all(r["gates"].values()) for r in rows
        )

    def validate_finalists(self, catalog, already):
        passing = [c for c in catalog if self.qualified(c) and c["name"] not in already]
        passing.sort(key=lambda c: rank(c, list(self.rows.values()))[1:])
        selected = passing[: max(0, self.config["limits"]["finalists"] - len(already))]
        # Freeze finalist list before any reset-half or extra swap result.
        atomic_json(self.output / ("finalists-" + str(len(already)) + ".json"), selected)
        for c in selected:
            already.append(c["name"])
            self.cells(c, windows=("full", "first_half", "second_half"), repeat=True)
            self.cells(c, views=("swap_0.5", "swap_1.5"), repeat=True)
        return [
            c
            for c in catalog
            if c["name"] in already
            and self.qualified(c, windows=("full", "first_half", "second_half"))
            and self.qualified(c, views=("swap_0.5", "swap_1.5"))
        ]

    def register(self, filename, catalog):
        path = self.output / filename
        if path.exists() and json.loads(path.read_text()) != catalog:
            raise ValueError("registered adaptive catalog drift")
        atomic_json(path, catalog)

    def report(self, catalog, winner, finalists):
        rows = list(self.rows.values())
        verdict = dict(
            policy=POLICY,
            selected=winner["name"] if winner else None,
            finalists=finalists,
            demo="UNCHANGED_TRIAL30",
            real_money="NO_GO",
            holdout="LOCKED_PENDING" if winner else "NOT_OPENED_NO_QUALIFIER",
            costs="COST_INCONCLUSIVE",
        )
        divergences = {}
        for row in rows:
            if row["window"] == "full" and row["cost_view"] == "swap":
                prefix = "-".join((row["dataset"], row["window"], row["cost"]))
                suffix = "-" + row["contract"] + ".json"
                no_swap = json.loads(
                    (self.output / "cells" / (prefix + "-no_swap" + suffix)).read_text()
                )
                swap = json.loads((self.output / "cells" / (prefix + "-swap" + suffix)).read_text())
                divergences[prefix + suffix] = path_divergence(no_swap, swap)
        atomic_json(self.output / "cost-path-divergence.json", divergences)
        summaries = []
        for c in catalog:
            cells = [
                r
                for r in rows
                if r["contract"] == c["name"]
                and r["window"] == "full"
                and r["cost_view"] in ("no_swap", "swap")
            ]
            summaries.append(
                dict(
                    name=c["name"],
                    config_id=config_id(c),
                    passing_continuous=sum(all(r["gates"].values()) for r in cells),
                    worst_net=min(r["metrics"]["net_usd"] for r in cells),
                    worst_dd=max(r["metrics"]["max_dd_pct"] for r in cells),
                    failed_gates={
                        g: sum(not r["gates"][g] for r in cells) for g in cells[0]["gates"]
                    },
                )
            )
        atomic_json(
            self.output / "results.json", dict(rows=rows, verdict=verdict, candidates=summaries)
        )
        pd.DataFrame(
            [
                {
                    **{k: v for k, v in r.items() if k not in ("metrics", "gates")},
                    **{k: v for k, v in r["metrics"].items() if k != "rejections"},
                    **{"gate_" + k: v for k, v in r.get("gates", {}).items()},
                }
                for r in rows
            ]
        ).to_csv(self.output / "report.csv", index=False)
        lines = [
            "# Reward156 profit/survival v2",
            "",
            "Independent USD200/fixed0.01/risk ceiling10%; current-spec swap sensitivity.",
            "A:10 months; B:12 months. Reused discovery; historical cost/live parity unverified.",
            "All continuous cells: net>=50 and above both controls; DD<=45%.",
            "Reset halves: net>=-20, >=10 trades; WR/RR report-only.",
            "",
            "| Candidate | Passing continuous /8 | Worst net USD | Worst DD % |",
            "|---|---:|---:|---:|",
        ]
        for c in sorted(
            summaries,
            key=lambda c: (
                -c["passing_continuous"],
                -c["worst_net"],
                c["worst_dd"],
                c["config_id"],
            ),
        ):
            lines.append(
                f"| {c['name']} | {c['passing_continuous']} | {c['worst_net']:.2f} | {c['worst_dd']:.2f} |"
            )
        lines += [
            "",
            "```json",
            json.dumps(verdict, indent=2),
            "```",
            "",
            "V1 verdict unchanged; policy relaxation and strategy changes reported separately.",
            "No candidate passing all gates means profit objective remains unmet. Demo unchanged.",
        ]
        (self.output / "report.md").write_text("\n".join(lines) + "\n")
        return verdict


def run(config_path=CONFIG, output=OUTPUT):
    config = json.loads(config_path.read_text())
    validate_config(config)
    output.mkdir(parents=True, exist_ok=True)
    digest = freeze(output, config_path, config)
    campaign = Campaign(config, output, digest)
    # Controls written first. Repeats attest current source rather than borrowing old artifacts.
    for c in CONTROLS:
        campaign.cells(c, windows=("full", "first_half", "second_half"), repeat=True)
        campaign.cells(c, views=("swap_0.5", "swap_1.5"), repeat=True)
    atomic_json(output / "baseline-matrix.json", list(campaign.rows.values()))
    catalog = config["seeds"]
    campaign.register("seed-catalog.json", catalog)
    for c in catalog:
        campaign.cells(c)
    atomic_json(output / "seed-matrix.json", list(campaign.rows.values()))
    finalists = []
    winners = campaign.validate_finalists(catalog, finalists)
    if not winners:
        chosen = sorted(catalog, key=lambda c: rank(c, list(campaign.rows.values())))[:2]
        campaign.register("chosen-seeds.json", chosen)
        generated, references = variant_catalog(chosen, catalog)
        seen = {config_id(c) for c in [*catalog, *generated]}
        campaign.register("one-factor-references.json", references)
        campaign.register("one-factor-catalog.json", generated)
        for c in generated:
            campaign.cells(c)
        combined = []
        for seed in chosen:
            group_winners = [
                min(
                    [
                        c
                        for c in references[config_id(seed)]
                        if c["parent"] == config_id(seed) and c["group"] == group
                    ],
                    key=lambda c: rank(c, list(campaign.rows.values())),
                )
                for group in GROUPS
            ]
            for c in combinations(seed, group_winners):
                if config_id(c) not in seen:
                    combined.append(c)
                    seen.add(config_id(c))
        if len(generated) + len(combined) > config["limits"]["new_configs"]:
            raise ValueError("finite search budget exceeded")
        campaign.register("combination-catalog.json", combined)
        for c in combined:
            campaign.cells(c)
        catalog = [*catalog, *generated, *combined]
        winners = campaign.validate_finalists(catalog, finalists)
    winners.sort(key=lambda c: rank(c, list(campaign.rows.values()))[1:])
    winner = winners[0] if winners else None
    verdict = campaign.report(catalog, winner, finalists)
    if winner:
        atomic_json(
            output / "discovery-results.json", json.loads((output / "results.json").read_text())
        )
        atomic_json(
            output / "selection-lock.json",
            dict(
                candidate=winner,
                behavior_sha256=digest,
                discovery_results_sha256=sha256(output / "discovery-results.json"),
            ),
        )
        # Holdout is deliberately separate and guarded by persisted selection.
        from scripts.research.reward156_holdout import run_holdout

        verdict["holdout"] = run_holdout(campaign, winner)
        results = json.loads((output / "results.json").read_text())
        results["verdict"] = verdict
        atomic_json(output / "results.json", results)
        with (output / "report.md").open("a") as handle:
            handle.write("\nFinal holdout verdict: " + verdict["holdout"] + "\n")
        atomic_json(output / "verdict.json", verdict)
    else:
        atomic_json(output / "verdict.json", verdict)
    proofs = [json.loads(p.read_text()) for p in (output / "integrity").glob("*.json")]
    atomic_json(
        output / "COMPLETE.json",
        dict(
            behavior_sha256=digest,
            cells=len(proofs),
            fresh_full_result_matches=sum(p["fresh_full_result_match"] for p in proofs),
            evaluated_candidates=len(catalog),
            selected=verdict["selected"],
            holdout=verdict["holdout"],
            results_sha256=sha256(output / "results.json"),
            captured_utc=datetime.now(timezone.utc).isoformat(),
        ),
    )
    print(json.dumps(verdict, indent=2), flush=True)
    return verdict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.config, args.output)


if __name__ == "__main__":
    main()
