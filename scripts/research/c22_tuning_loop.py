"""Bounded, diversified C22 research loop; mandatory swap, fixed qualification."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

from scripts.research.c22_context_campaign import (
    BASELINE,
    REPO,
    VIEWS,
    campaign_lock,
    digest,
    read,
    require,
    verify_baseline,
)
from scripts.research.c22_frequency_adapter import (
    DOMAINS,
    baseline_config,
    config_id,
    next_round,
    validate,
)
from scripts.research.c22_frequency_campaign import (
    candidate_rows,
    execute_cell,
    frozen_parity,
    run_cells,
    source_hashes,
)
from scripts.research.c22_frequency_data import prepare_input, verify_input
from scripts.research.c22_frequency_policy import qualify, winner_rank
from scripts.research.c22_frequency_store import Store
from scripts.research.c22_tuning_search import LANES, exploration_rank, select_parents
from scripts.research.reward156_tuning import atomic_json
from scripts.research.rollover import SwapPolicy

DEFAULT_CONFIG = REPO / "config/c22-tuning-loop.json"


def validate_config(config):
    pins = dict(
        policy="c22_diversified_loop_v1",
        research_only=True,
        initial_equity=200,
        volume=0.01,
        risk_cap=0.1,
        new_variants_per_campaign=300,
        max_campaigns=3,
        seed_count=3,
        repeat_top=5,
        lanes=list(LANES),
        views=list(VIEWS),
        swap_required=True,
    )
    require(set(config) == set(pins) | {"prior_campaign"}, "unknown loop config keys")
    require(
        all(type(config[k]) is type(v) and config[k] == v for k, v in pins.items()),
        "loop pins changed",
    )
    require(isinstance(config["prior_campaign"], str), "prior campaign path required")


def load_prior(root):
    root = Path(root)
    complete = read(root / "COMPLETE.json")
    require(complete["status"] == "COMPLETE", "prior campaign incomplete")
    for key, name in (
        ("results_sha256", "results.json"),
        ("protocol_sha256", "protocol.json"),
        ("checkpoint_sha256", "checkpoint.json"),
    ):
        require(
            digest(root / "search" / name) == complete[key], "prior completion binding mismatch"
        )
    protocol = read(root / "search/protocol.json")
    store = Store(root / "search", protocol)
    for name, expected in protocol["sources"].items():
        require(digest(root / "source_snapshot" / name) == expected, "prior frozen source drift")
    result = store.get("results.json")
    require(result["cost_status"] == "COST_INCONCLUSIVE", "unexpected prior cost status")
    # Search continuation consumes only declared configs and swap-inclusive rows.
    for item in result["candidates"].values():
        validate(item["config"])
        require(set(item["metrics"]) == set(VIEWS), "prior swap views mismatch")
    return result, dict(
        path=str(root.resolve()),
        complete_sha256=digest(root / "COMPLETE.json"),
        results_sha256=complete["results_sha256"],
    )


def continuation_catalog(prior):
    rows = {i: c["metrics"] for i, c in prior["candidates"].items()}
    chosen = select_parents(rows, set(), prior["controls"])
    seeds = [
        dict(id=p["id"], lane=p["lane"], config=prior["candidates"][p["id"]]["config"])
        for p in chosen
    ]
    return seeds


def tune(store, manifest, input_root, seeds, excluded, budget, workers, max_cells, repeat_top):
    base = baseline_config()
    base_id = config_id(base)
    catalog = [dict(id=base_id, config=base), *seeds]
    spent, complete = run_cells(catalog, manifest, input_root, store, workers, max_cells)
    if not complete:
        return dict(status="PARTIAL", phase="seeds"), spent
    controls = candidate_rows(store, base_id)
    configs = {c["id"]: c["config"] for c in catalog}
    rows = {i: candidate_rows(store, i) for i in configs}
    expanded = set()
    new = []
    round_number = 1
    while len(new) < budget:
        parents = select_parents(rows, expanded, controls)
        if not parents:
            break
        batch = next_round(
            [configs[p["id"]] for p in parents], set(configs) | set(excluded), budget - len(new)
        )
        if not batch:
            expanded.update(p["id"] for p in parents)
            continue
        store.put(
            f"rounds/{round_number:03}.json",
            dict(round=round_number, parents=parents, catalog=batch),
        )
        allowance = None if max_cells is None else max(0, max_cells - spent)
        used, complete = run_cells(batch, manifest, input_root, store, workers, allowance)
        spent += used
        if not complete:
            return dict(
                status="PARTIAL", phase="search", new_variants=len(new), round=round_number
            ), spent
        expanded.update(p["id"] for p in parents)
        for item in batch:
            configs[item["id"]] = item["config"]
            rows[item["id"]] = candidate_rows(store, item["id"])
            new.append(item["id"])
        round_number += 1
    candidates = [i for i in configs if i != base_id]
    decisions = {i: qualify(rows[i], controls) for i in candidates}
    winners = sorted(
        (i for i in candidates if decisions[i]["qualified"]), key=lambda i: winner_rank(i, rows[i])
    )
    diagnostics = []
    for lane in ("frequency", "balanced"):
        identity = min(candidates, key=lambda i: exploration_rank(i, rows[i], controls, lane))
        if identity not in diagnostics:
            diagnostics.append(identity)
    finalists = list(dict.fromkeys([base_id, *winners[:repeat_top], *diagnostics]))
    store.put(
        "finalists.json", dict(ids=finalists, qualified_order=winners, diagnostic_ids=diagnostics)
    )
    for identity in finalists:
        for view in VIEWS:
            name = f"repeats/{identity}-{view}.json"
            if store.get(name) is not None:
                continue
            if max_cells is not None and spent >= max_cells:
                return dict(status="PARTIAL", phase="repeats", new_variants=len(new)), spent
            fresh = execute_cell((str(input_root), configs[identity], view, manifest))
            require(
                fresh == store.get(f"cells/{identity}-{view}.json"),
                "fresh complete-result mismatch",
            )
            store.put(
                name,
                dict(
                    full_result_match=True,
                    cell_sha256=store.state["artifacts"][f"cells/{identity}-{view}.json"],
                ),
            )
            spent += 1
    result = dict(
        status="QUALIFIED" if winners else "NO_QUALIFIER",
        cost_status="COST_INCONCLUSIVE",
        new_variants=len(new),
        seed_ids=[s["id"] for s in seeds],
        new_ids=new,
        qualified_order=winners,
        selected=winners[0] if winners else None,
        baseline_id=base_id,
        controls=controls,
        repeated=finalists,
        diagnostic_ids=diagnostics,
        candidates={
            i: dict(config=configs[i], metrics=rows[i], **decisions[i]) for i in candidates
        },
        input_last_quote=manifest["actual_last_quote"],
        retrospective_reused_data=True,
        real_money="PROHIBITED",
        demo="UNCHANGED",
    )
    store.put("results.json", result)
    return result, spent


def marker(store, result):
    return dict(
        status="COMPLETE",
        verdict=result["status"],
        results_sha256=store.state["artifacts"]["results.json"],
        protocol_sha256=digest(store.root / "protocol.json"),
        checkpoint_sha256=digest(store.checkpoint),
    )


def run_campaign(output, baseline, seeds, excluded, protocol, workers, allowance):
    output.mkdir(parents=True, exist_ok=True)
    with campaign_lock(output):
        completed = output / "COMPLETE.json"
        try:
            manifest = prepare_input(baseline, output / "input")
            policy = SwapPolicy.from_broker(manifest["broker"])
            original, old, hashes = verify_baseline(baseline)
            config = protocol["config"]
            bound = dict(
                protocol,
                input_sha256=digest(output / "input/manifest.json"),
                seeds=seeds,
                excluded_ids=sorted(excluded),
                swap_policy=asdict(policy),
                baseline_hashes=hashes,
            )
            store = Store(output / "search", bound)
            for name, expected in protocol["sources"].items():
                target = output / "source_snapshot" / name
                if target.exists():
                    require(digest(target) == expected, "snapshot drift")
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(REPO / name, target)
            if completed.exists():
                require(
                    read(completed) == marker(store, store.get("results.json")),
                    "completion marker drift",
                )
            frozen_parity(baseline, store, original, old)
            result, spent = tune(
                store,
                manifest,
                output / "input",
                seeds,
                excluded,
                config["new_variants_per_campaign"],
                workers,
                allowance,
                config["repeat_top"],
            )
            if result["status"] != "PARTIAL":
                require(source_hashes() == protocol["sources"], "source drift during replay")
                require(verify_input(output / "input") == manifest, "input drift during replay")
                _, _, fresh_hashes = verify_baseline(baseline)
                require(fresh_hashes == hashes, "baseline drift during replay")
                atomic_json(completed, marker(store, result))
                (output / "BLOCKED.json").unlink(missing_ok=True)
            return result, spent
        except Exception as error:
            completed.unlink(missing_ok=True)
            atomic_json(
                output / "BLOCKED.json", dict(status="BLOCKED", selected=None, reason=str(error))
            )
            raise


def run(output, config_path=DEFAULT_CONFIG, *, baseline=BASELINE, workers=4, max_cells=None):
    output = Path(output).resolve()
    config_path = Path(config_path).resolve()
    baseline = Path(baseline).resolve()
    require(
        output.is_relative_to(REPO / "runs") and output != REPO / "runs",
        "output must be under runs/",
    )
    require(type(workers) is int and 1 <= workers <= 4, "workers must be1..4")
    require(max_cells is None or type(max_cells) is int and max_cells >= 0, "invalid cell budget")
    config = read(config_path)
    validate_config(config)
    prior_path = Path(config["prior_campaign"]).resolve()
    require(
        not output.is_relative_to(prior_path) and not prior_path.is_relative_to(output),
        "loop overlaps prior evidence",
    )
    require(
        not output.is_relative_to(baseline) and not baseline.is_relative_to(output),
        "loop overlaps baseline",
    )
    output.mkdir(parents=True, exist_ok=True)
    with campaign_lock(output):
        complete_path = output / "COMPLETE.json"
        try:
            if not complete_path.exists():
                require(
                    shutil.disk_usage(output).free >= 5 * 1024**3,
                    "insufficient disk: need at least5GiB free before tuning",
                )
            prior, provenance = load_prior(prior_path)
            sources = source_hashes()
            protocol = dict(
                schema=1,
                config=config,
                config_sha256=digest(config_path),
                sources=sources,
                domains={k: list(v) for k, v in DOMAINS.items()},
                prior=provenance,
                runtime=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__),
            )
            state = Store(output / "loop-state", protocol)
            prior_rows = prior
            excluded = set(prior["candidates"]) | {prior["baseline_id"]}
            spent = 0
            campaigns = []
            for number in range(1, config["max_campaigns"] + 1):
                seeds = continuation_catalog(prior_rows)
                state.put(
                    f"catalogs/{number:02}.json", dict(seeds=seeds, excluded_ids=sorted(excluded))
                )
                allowance = None if max_cells is None else max(0, max_cells - spent)
                current = output / f"campaign-{number:02}"
                result, used = run_campaign(
                    current, baseline, seeds, excluded, protocol, workers, allowance
                )
                spent += used
                if result["status"] == "PARTIAL":
                    return dict(status="PARTIAL", campaign=number, phase=result["phase"])
                record = dict(
                    number=number,
                    status=result["status"],
                    new_variants=result["new_variants"],
                    results_sha256=digest(current / "search/results.json"),
                    complete_sha256=digest(current / "COMPLETE.json"),
                )
                state.put(f"campaigns/{number:02}.json", record)
                campaigns.append(record)
                excluded.update(result["candidates"])
                prior_rows = result
                if result["qualified_order"]:
                    break
            require(
                source_hashes() == sources and digest(config_path) == protocol["config_sha256"],
                "loop source/config drift",
            )
            _, fresh_provenance = load_prior(prior_path)
            require(fresh_provenance == provenance, "prior changed during loop")
            summary = dict(
                status=prior_rows["status"],
                selected=prior_rows["selected"],
                campaigns=campaigns,
                new_variants=sum(c["new_variants"] for c in campaigns),
                qualified_order=prior_rows["qualified_order"],
                cost_status="COST_INCONCLUSIVE",
                last_campaign=len(campaigns),
                demo="UNCHANGED",
                real_money="PROHIBITED",
            )
            state.put("results.json", summary)
            completion = dict(
                status="COMPLETE",
                verdict=summary["status"],
                protocol_sha256=digest(state.root / "protocol.json"),
                results_sha256=state.state["artifacts"]["results.json"],
                checkpoint_sha256=digest(state.checkpoint),
            )
            if complete_path.exists():
                require(read(complete_path) == completion, "loop completion drift")
            atomic_json(complete_path, completion)
            (output / "BLOCKED.json").unlink(missing_ok=True)
            return summary
        except Exception as error:
            complete_path.unlink(missing_ok=True)
            atomic_json(
                output / "BLOCKED.json", dict(status="BLOCKED", selected=None, reason=str(error))
            )
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-cells", type=int)
    args = parser.parse_args()
    try:
        result = run(
            args.output,
            args.config,
            baseline=args.baseline,
            workers=args.workers,
            max_cells=args.max_cells,
        )
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps(dict(status="BLOCKED", reason=str(error))), file=sys.stderr)
        return 1
    print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
