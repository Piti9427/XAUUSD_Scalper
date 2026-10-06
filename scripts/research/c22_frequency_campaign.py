"""Resumable C22 frequency search. Offline research only; every cell includes swap."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

from scripts.research.breakout_logic import Costs, replay
from scripts.research.c22_context_campaign import (
    BASELINE,
    NAME,
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
    prepare,
)
from scripts.research.c22_frequency_data import load_bars, prepare_input, verify_input
from scripts.research.c22_frequency_policy import metrics, qualify, search_rank, winner_rank
from scripts.research.c22_frequency_store import Store
from scripts.research.rollover import SwapPolicy
from scripts.research.reward156_tuning import atomic_json

DEFAULT_CONFIG = REPO / "config/c22-frequency.json"


def validate_config(config):
    pins = dict(
        policy="c22_frequency_v1",
        research_only=True,
        initial_equity=200,
        volume=0.01,
        risk_cap=0.1,
        expand_top=3,
        repeat_top=5,
        start_utc="2024-09-01T00:00:00+00:00",
        swap_required=True,
        views=list(VIEWS),
    )
    require(set(config) == set(pins) | {"max_variants"}, "unknown campaign config keys")
    require(
        all(type(config[k]) is type(v) and config[k] == v for k, v in pins.items()),
        "campaign invariant changed",
    )
    require(
        type(config["max_variants"]) is int and config["max_variants"] == 300,
        "variant budget must be 300; use --max-cells for PARTIAL execution",
    )


def execute_cell(task):
    """Process boundary: read immutable input, prepare causal frame, replay continuously."""
    root, contract, view, manifest = task
    root = Path(root)
    frame, rules = prepare(load_bars(root / "bars.csv"), contract)
    ticks = [
        np.load(root / "tape" / (key + ".npy"), mmap_mode="r") for key in ("time", "bid", "ask")
    ]
    policy = SwapPolicy.from_broker(manifest["broker"])
    result = replay(
        frame,
        ticks,
        manifest["broker"],
        rules,
        Costs(**manifest["costs"][view.split("-")[0]]),
        start=pd.Timestamp(manifest["requested_start_utc"]),
        end=pd.Timestamp(manifest["requested_end_utc"]),
        swap_policy=policy,
        capture_events=True,
        capture_context=True,
    )
    row = metrics(result, manifest["broker"], policy)
    diagnostics = {
        key: int(frame[key].sum())
        for key in ("h4_warmup", "h4_incomplete", "h4_directional_mismatch", "macro_unavailable")
    }
    diagnostics["raw_signals"] = int((frame.raw_direction != 0).sum())
    diagnostics["signals"] = int((frame.direction != 0).sum())
    return dict(
        config_id=config_id(contract),
        view=view,
        metrics=row,
        diagnostics=diagnostics,
        result=result,
    )


def source_hashes():
    # Conservative replay dependency superset, excluding operational runners.
    paths = [REPO / "scripts/strategy.py", *(REPO / "scripts/research").glob("*.py")]
    return {str(p.relative_to(REPO)): digest(p) for p in sorted(paths)}


def frozen_parity(baseline, store, original, manifest):
    if store.get("baseline-parity.json") is not None:
        return
    frame, rules = prepare(load_bars(baseline / "input/continuous-bars.csv"), baseline_config())
    ticks = [
        np.load(baseline / "input/continuous-tape" / (k + ".npy"), mmap_mode="r")
        for k in ("time", "bid", "ask")
    ]
    proofs = {}
    for view in VIEWS:
        result = replay(
            frame,
            ticks,
            manifest["broker"],
            rules,
            Costs(**original["costs"][view.split("-")[0]]),
            start=pd.Timestamp(original["start"]),
            end=pd.Timestamp(original["end"]),
            swap_policy=SwapPolicy.from_broker(manifest["broker"]),
            capture_events=True,
        )
        expected_path = baseline / "cells" / (view + "-" + NAME + ".json")
        require(result == read(expected_path), "frozen full-result parity mismatch: " + view)
        proofs[view] = dict(full_result_match=True, expected_sha256=digest(expected_path))
        print("archived parity", view, "PASS", flush=True)
    store.put("baseline-parity.json", proofs)


def run_cells(catalog, manifest, input_root, store, workers, allowance):
    tasks, names = [], []
    for item in catalog:
        for view in VIEWS:
            name = f"cells/{item['id']}-{view}.json"
            if store.get(name) is None:
                tasks.append((str(input_root), item["config"], view, manifest))
                names.append(name)
    selected = tasks if allowance is None else tasks[:allowance]
    if selected:
        # map returns in frozen catalog order regardless of scheduling/completion.
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for name, payload in zip(names, pool.map(execute_cell, selected)):
                store.put(name, payload)
                row = payload["metrics"]
                print(
                    name,
                    f"net={row['net_usd']:.2f} DD={row['max_dd_pct']:.2f} "
                    f"mean_entries={row['mean_entries']:.2f}",
                    flush=True,
                )
    return len(selected), len(selected) == len(tasks)


def candidate_rows(store, identity):
    return {view: store.get(f"cells/{identity}-{view}.json")["metrics"] for view in VIEWS}


def search(store, manifest, input_root, config, workers, max_cells):
    base = baseline_config()
    baseline_id = config_id(base)
    baseline = dict(id=baseline_id, config=base)
    spent, complete = run_cells([baseline], manifest, input_root, store, workers, max_cells)
    if not complete:
        return dict(status="PARTIAL", cells=spent)
    controls = candidate_rows(store, baseline_id)
    configs, rows, expanded = {baseline_id: base}, {baseline_id: controls}, set()
    round_number = 1
    while len(configs) - 1 < config["max_variants"]:
        eligible = [i for i in configs if i not in expanded]
        eligible.sort(key=lambda i: search_rank(i, rows[i], controls))
        parents = eligible[: config["expand_top"]]
        catalog = next_round(
            [configs[i] for i in parents], configs, config["max_variants"] - len(configs) + 1
        )
        if not catalog:
            # Exhausted parents do not prematurely stop unexplored candidates.
            expanded.update(parents)
            if not parents:
                break
            continue
        frozen = dict(round=round_number, parents=parents, catalog=catalog)
        store.put(f"rounds/{round_number:03d}.json", frozen)
        allowance = None if max_cells is None else max(0, max_cells - spent)
        used, complete = run_cells(catalog, manifest, input_root, store, workers, allowance)
        spent += used
        if not complete:
            return dict(status="PARTIAL", evaluated_variants=len(configs) - 1, round=round_number)
        expanded.update(parents)
        for item in catalog:
            configs[item["id"]] = item["config"]
            rows[item["id"]] = candidate_rows(store, item["id"])
        round_number += 1
    candidates = [i for i in configs if i != baseline_id]
    decisions = {i: qualify(rows[i], controls) for i in candidates}
    winners = [i for i in candidates if decisions[i]["qualified"]]
    winners.sort(key=lambda i: winner_rank(i, rows[i]))
    finalists = [baseline_id, *winners[: config["repeat_top"]]]
    store.put("finalists.json", dict(ids=finalists, qualified_order=winners))
    for identity in finalists:
        for view in VIEWS:
            name = f"repeats/{identity}-{view}.json"
            if store.get(name) is None:
                if max_cells is not None and spent >= max_cells:
                    return dict(
                        status="PARTIAL", evaluated_variants=len(candidates), phase="repeats"
                    )
                fresh = execute_cell((str(input_root), configs[identity], view, manifest))
                require(
                    fresh == store.get(f"cells/{identity}-{view}.json"),
                    "fresh full-result repeat mismatch: " + identity + "-" + view,
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
        variants=len(candidates),
        selected=winners[0] if winners else None,
        qualified_order=winners,
        baseline_id=baseline_id,
        controls=controls,
        candidates={
            i: dict(config=configs[i], metrics=rows[i], **decisions[i]) for i in candidates
        },
        repeated=finalists,
        demo="UNCHANGED",
        real_money="PROHIBITED",
        retrospective_reused_data=True,
        input_last_quote=manifest["actual_last_quote"],
    )
    store.put("results.json", result)
    return result


def campaign(
    baseline, output, config_path=DEFAULT_CONFIG, *, workers=2, max_cells=None, prepare_only=False
):
    baseline, output, config_path = (
        Path(baseline).resolve(),
        Path(output).resolve(),
        Path(config_path).resolve(),
    )
    require(
        output.is_relative_to(REPO / "runs") and output != REPO / "runs",
        "output must be under runs/",
    )
    require(
        not output.is_relative_to(baseline) and not baseline.is_relative_to(output),
        "output overlaps baseline",
    )
    require(type(workers) is int and 1 <= workers <= 4, "workers must be 1..4")
    require(max_cells is None or type(max_cells) is int and max_cells >= 0, "invalid max-cells")
    output.mkdir(parents=True, exist_ok=True)
    with campaign_lock(output):
        complete_path = output / "COMPLETE.json"
        try:
            config = read(config_path)
            validate_config(config)
            manifest = prepare_input(baseline, output / "input")
            policy = SwapPolicy.from_broker(manifest["broker"])
            require(manifest["requested_start_utc"] == config["start_utc"], "start drift")
            require(
                manifest["costs"]["base"]["extra_spread"] == 0
                and manifest["costs"]["base"]["slippage"] == 0
                and manifest["costs"]["stress"]["extra_spread"] == 0.2
                and manifest["costs"]["stress"]["slippage"] == 0.1,
                "cost model drift",
            )
            if prepare_only:
                return dict(status="INPUT_READY", last_quote=manifest["actual_last_quote"])
            original, old, hashes = verify_baseline(baseline)
            sources = source_hashes()
            protocol = dict(
                schema=1,
                config=config,
                config_sha256=digest(config_path),
                sources=sources,
                domains={k: list(v) for k, v in DOMAINS.items()},
                baseline=baseline_config(),
                baseline_hashes=hashes,
                input_sha256=digest(output / "input/manifest.json"),
                swap_policy=asdict(policy),
                runtime=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__),
                cost_status="COST_INCONCLUSIVE",
            )
            store = Store(output / "search", protocol)
            if complete_path.exists():
                marker = read(complete_path)
                require(
                    marker
                    == dict(
                        status="COMPLETE",
                        verdict=store.get("results.json")["status"],
                        results_sha256=store.state["artifacts"]["results.json"],
                        checkpoint_sha256=digest(store.checkpoint),
                        protocol_sha256=digest(store.root / "protocol.json"),
                    ),
                    "completion marker mismatch",
                )
            for name, expected in sources.items():
                target = output / "source_snapshot" / name
                if target.exists():
                    require(digest(target) == expected, "source snapshot drift")
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(REPO / name, target)
            frozen_parity(baseline, store, original, old)
            result = search(store, manifest, output / "input", config, workers, max_cells)
            if result["status"] != "PARTIAL":
                require(
                    source_hashes() == sources and digest(config_path) == protocol["config_sha256"],
                    "source/config changed during campaign",
                )
                require(verify_input(output / "input") == manifest, "input changed during campaign")
                _, _, final_hashes = verify_baseline(baseline)
                require(final_hashes == hashes, "baseline changed during campaign")
                marker = dict(
                    status="COMPLETE",
                    verdict=result["status"],
                    results_sha256=store.state["artifacts"]["results.json"],
                    checkpoint_sha256=digest(store.checkpoint),
                    protocol_sha256=digest(store.root / "protocol.json"),
                )
                atomic_json(complete_path, marker)
                (output / "BLOCKED.json").unlink(missing_ok=True)
            return {k: v for k, v in result.items() if k not in ("candidates", "controls")}
        except Exception as error:
            complete_path.unlink(missing_ok=True)
            atomic_json(
                output / "BLOCKED.json", dict(status="BLOCKED", selected=None, reason=str(error))
            )
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--max-cells", type=int, help="Bound new executions only; resume keeps original budget"
    )
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    try:
        result = campaign(
            args.baseline,
            args.output,
            args.config,
            workers=args.workers,
            max_cells=args.max_cells,
            prepare_only=args.prepare_only,
        )
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps(dict(status="BLOCKED", reason=str(error))), file=sys.stderr)
        return 1
    print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
