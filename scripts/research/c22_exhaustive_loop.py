"""Resume an exhaustive, frozen C22 native grid; research and swap required."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import fcntl
import gzip
from itertools import product
import json
import multiprocessing
from pathlib import Path
import shutil

from scripts.research.breakout_models import Rules
from scripts.research.c22_learning_loop import (
    LANES, RISK_FIELDS, SPACE, choose, objective, qualified, reduced_risk,
)
from scripts.research.c22_loop_store import (
    add_reference, execute_cell, init_worker, load_summary, read_cell,
)
from scripts.research.c22_matrix_tuning import DOMAINS, identity
from scripts.research.c22_performance_campaign import ROOT, INPUT, VIEWS, read, write, sha, qualifies


PARENT = ROOT / "runs/c22-learning-loop-2026-10-25"
SPEC = ROOT / "specs/c22-exhaustive-loop-2026-10-25.md"
BATCH_SIZE = 32
CLAIM = "Best within the complete frozen 5184 grid; not future profit or all-strategy optimality"


def full_catalog(seed):
    axes = tuple(DOMAINS)
    cases = []
    for values in product(*(DOMAINS[key] for key in axes)):
        rules = Rules(**(seed | dict(zip(axes, values))))
        cases.append(dict(name=identity(rules), rules=asdict(rules)))
    assert len(cases) == SPACE == 5184
    assert len({case["name"] for case in cases}) == SPACE
    return dict(schema=1, axes=list(axes), finite_domain=SPACE, cases=cases)


def batch_catalog(catalog, number):
    start = (number - 1) * BATCH_SIZE
    stop = min(start + BATCH_SIZE, len(catalog["cases"]))
    if not 0 <= start < stop:
        raise ValueError("Batch number outside frozen grid")
    return catalog["cases"][start:stop]


def is_evaluated(rows, floors):
    if set(rows.get("raw", {})) != set(VIEWS):
        return False
    raw_pass = qualifies({view: rows["raw"][view]["metrics"] for view in VIEWS}, floors["raw"])
    return not raw_pass or set(rows.get("cent", {})) == set(VIEWS)


def leaders(names, summaries, initial, floors, incumbents=None):
    baseline = summaries[initial]
    accepted = sorted(name for name in names if qualified(summaries[name], floors))
    assert initial in accepted
    current = {lane: initial for lane in LANES} if incumbents is None else incumbents
    assert set(current) == set(LANES) and all(name in accepted for name in current.values())
    selected = {lane: choose(current[lane], accepted, summaries, lane, floors, baseline) for lane in LANES}
    strict = sorted(name for name in accepted if reduced_risk(summaries[name], baseline))
    alternatives = dict(max_worst_net=min(accepted, key=lambda name: (
        -min(summaries[name][guard][view]["metrics"]["net_usd"]
             for guard in ("raw", "cent") for view in VIEWS),
        *objective(summaries[name], "profit"), name)))
    for field in RISK_FIELDS:
        alternatives["min_" + field] = min(accepted, key=lambda name: (
            max(summaries[name][guard][view]["risk"][field]
                for guard in ("raw", "cent") for view in VIEWS),
            *objective(summaries[name], "profit"), name))
    return dict(selected=selected, qualified=accepted, strict_downside_improvers=strict,
                repair_status="STRICT_DOWNSIDE_IMPROVEMENT" if strict else "NO_STRICT_DOWNSIDE_IMPROVEMENT",
                selected_repair_strict=reduced_risk(summaries[selected["repair"]], baseline),
                diagnostic_alternatives=alternatives)


def published_state(active, current_batch_names, summaries, initial, floors, incumbents):
    """Count completed current cells without promoting an uncommitted batch."""
    visited = sorted(name for name in active | current_batch_names
                     if is_evaluated(summaries[name], floors))
    state = leaders(active, summaries, initial, floors, incumbents)
    assert state["selected"] == incumbents, "Active batch results require an explicit leader commit"
    return visited, state


def _read_state(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def _write_state(path, value):
    payload = json.dumps(value, allow_nan=False, separators=(",", ":")).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".pending")
    with pending.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=1, fileobj=stream, mtime=0) as target:
            target.write(payload)
    pending.replace(path)


def freeze(out):
    prior = read(PARENT / "protocol.json")
    old_result = read(PARENT / "results.json")
    parent_complete = read(PARENT / "COMPLETE.json")
    audit = read(PARENT / "independent-verification.json")
    assert parent_complete["status"] == "CONVERGED_BLOCK_SEARCH" and audit["status"] == "PASS"
    assert audit["parent_completion_sha256"] == sha(PARENT / "COMPLETE.json")
    for name, digest in parent_complete["artifacts"].items():
        assert sha(PARENT / name) == digest, name
    sources = dict(prior["sources"])
    for path in (Path(__file__), SPEC):
        sources[str(path.relative_to(ROOT))] = sha(path)
    for name, digest in sources.items():
        assert sha(ROOT / name) == digest, name
    assert sha(INPUT / "manifest.json") == prior["input_manifest_sha256"]
    for name, digest in prior["input_hashes"].items():
        assert sha(INPUT / name) == digest, name
    bindings = {}
    for proof_path in sorted((PARENT / "cells-integrity").glob("*.json")):
        proof = read(proof_path)
        source = (ROOT / proof["path"]).resolve()
        assert source.is_relative_to((ROOT / "runs").resolve())
        assert sha(source) == proof["sha256"], str(source)
        assert audit["payload_hashes"][proof["path"]] == proof["sha256"]
        bindings[proof_path.stem] = dict(proof_sha256=sha(proof_path), path=proof["path"],
                                         sha256=proof["sha256"])
    assert len(bindings) == audit["cells"] == 570
    initial = prior["initial"]
    catalog = full_catalog(old_result["cases"][initial]["rules"])
    catalog_path = out / "catalog.json"
    if catalog_path.exists():
        assert read(catalog_path) == catalog, "Frozen complete catalog drift"
    else:
        write(catalog_path, catalog)
    protocol = dict(schema=1, algorithm="exhaustive_native_grid_v1", sources=sources,
        input_hashes=prior["input_hashes"], input_manifest_sha256=prior["input_manifest_sha256"],
        parent_complete_sha256=sha(PARENT / "COMPLETE.json"),
        parent_results_sha256=sha(PARENT / "results.json"),
        parent_audit_sha256=sha(PARENT / "independent-verification.json"), parent_cell_bindings=bindings,
        broker=prior["broker"], views=prior["views"], start=prior["start"], end=prior["end"],
        original_floors=prior["original_floors"], benchmark_hashes=prior["benchmark_hashes"],
        domains={key: list(values) for key, values in DOMAINS.items()},
        finite_domain=SPACE, initial=initial, lanes=list(LANES), risk_fields=list(RISK_FIELDS),
        catalog_sha256=sha(catalog_path), batch_size=BATCH_SIZE,
        cost_status="COST_INCONCLUSIVE", holdout=False, claim=CLAIM)
    if (out / "protocol.json").exists():
        assert read(out / "protocol.json") == protocol, "Protocol drift"
    else:
        write(out / "protocol.json", protocol)
        for name, digest in sources.items():
            target = out / "source_snapshot" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
            assert sha(target) == digest
    return protocol, catalog, old_result


def run(out, workers=2, max_new_cells=None):
    protocol, catalog, old_result = freeze(out)
    if (out / "COMPLETE.json").exists():
        for name, digest in read(out / "COMPLETE.json")["artifacts"].items():
            assert sha(out / name) == digest, name
        for path in (out / "cells-integrity").glob("*.json"):
            record = read(path)
            assert sha(ROOT / record["path"]) == record["sha256"], path.name
        print("Already exhaustive-complete; hashes verified", flush=True)
        return read(out / "results.json")
    cases = {case["name"]: case for case in catalog["cases"]}
    summaries = {name: {} for name in cases}
    cell_bindings = {}
    checkpoint_path = out / "checkpoint.json"
    if checkpoint_path.exists():
        checkpoint = read(checkpoint_path)
        assert checkpoint["protocol_sha256"] == sha(out / "protocol.json")
        cached = checkpoint["summaries_cache"]
        cache_path = (ROOT / cached["path"]).resolve()
        assert cache_path.is_relative_to(out.resolve()) and sha(cache_path) == cached["sha256"]
        state = _read_state(cache_path)
        assert state["cases"] == cases
        summaries, cell_bindings = state["summaries"], state["cell_bindings"]
        for key, binding in cell_bindings.items():
            proof_path = out / "cells-integrity" / (key + ".json")
            assert sha(proof_path) == binding["proof_sha256"], key
            proof = read(proof_path)
            assert proof["path"] == binding["path"] and proof["sha256"] == binding["sha256"]
            assert sha(ROOT / proof["path"]) == proof["sha256"], key

    def remember(key, summary):
        name, view, guard = key.rsplit("-", 2)
        assert name in cases
        summaries[name].setdefault(guard, {})[view] = summary
        proof_path = out / "cells-integrity" / (key + ".json")
        proof = read(proof_path)
        cell_bindings[key] = dict(proof_sha256=sha(proof_path), path=proof["path"], sha256=proof["sha256"])

    for key, binding in protocol["parent_cell_bindings"].items():
        proof_path = out / "cells-integrity" / (key + ".json")
        if not proof_path.exists():
            summary = add_reference(out, key, ROOT / binding["path"])
            remember(key, summary)
        elif key not in cell_bindings:
            remember(key, load_summary(read_cell(out, key)))
        name, view, guard = key.rsplit("-", 2)
        assert summaries[name][guard][view] == old_result["summaries"][name][guard][view]
    # Recover cells completed after the last atomically published cache pointer.
    for proof_path in sorted((out / "cells-integrity").glob("*.json")):
        if proof_path.stem not in cell_bindings:
            remember(proof_path.stem, load_summary(read_cell(out, proof_path.stem)))

    floors, initial = protocol["original_floors"], protocol["initial"]
    assert qualified(summaries[initial], floors)
    batches, spent = [], 0
    active = set(old_result["visited"])
    current_batch_names = set()
    incumbents = {lane: initial for lane in LANES}
    phase, batch_number = "initializing", 0

    def state_now():
        # Cached results from a later interrupted batch must not rewrite the
        # historical leaders of earlier deterministic batch records on resume.
        return published_state(active, current_batch_names, summaries, initial, floors, incumbents)

    def checkpoint(reason):
        visited, state = state_now()
        # Alternate two cache slots: the currently published cache is untouched
        # until the next payload and pointer have both been committed. Economic
        # cells and every historical batch record remain permanently retained.
        previous_slot = read(checkpoint_path).get("cache_slot", 1) if checkpoint_path.exists() else 1
        slot = 1 - previous_slot
        snapshot = out / "checkpoints" / f"state-slot-{slot}.json.gz"
        cache = dict(cases=cases, summaries=summaries, cell_bindings=cell_bindings)
        _write_state(snapshot, cache)
        value = dict(status="PARTIAL", reason=reason, initial=initial, finite_domain=SPACE,
            visited=visited, visited_cases=len(visited), cases_count=len(cases),
            processed_batches=len(batches), batches=batches, phase=phase, batch=batch_number,
            new_cells_this_invocation=spent, protocol_sha256=sha(out / "protocol.json"),
            cache_slot=slot,
            summaries_cache=dict(path=str(snapshot.relative_to(ROOT)), sha256=sha(snapshot)), **state)
        write(checkpoint_path, value)
        return value

    def update_progress(done, total):
        visited, state = state_now()
        write(out / "progress.json", dict(status="PARTIAL", phase=phase, batch=batch_number,
            done=done, new_jobs=total, new_cells_this_invocation=spent,
            selected=state["selected"], visited_cases=len(visited), finite_domain=SPACE))

    context = multiprocessing.get_context("spawn")
    try:
        with ProcessPoolExecutor(max_workers=workers, mp_context=context,
                                 initializer=init_worker, initargs=(protocol, str(out))) as pool:
            def jobs(items):
                nonlocal spent
                missing = []
                for rules, view, guard, repeat in items:
                    name = identity(Rules(**rules))
                    key = f"{name}-{view}-{guard}"
                    folder = "repeats" if repeat else "cells"
                    proof_path = out / (folder + "-integrity") / (key + ".json")
                    if proof_path.exists():
                        if repeat:
                            repeated = read_cell(out, key, "repeats")
                            original = read_cell(out, key)
                            assert all(repeated[k] == original[k] for k in ("result", "metrics", "diagnostics"))
                        elif key not in cell_bindings:
                            remember(key, load_summary(read_cell(out, key)))
                    else:
                        missing.append((rules, view, guard, repeat))
                allowance = len(missing) if max_new_cells is None else max(0, max_new_cells - spent)
                pending = missing[:allowance]
                futures = {pool.submit(execute_cell, item): item for item in pending}
                errors = []
                for done, future in enumerate(as_completed(futures), 1):
                    item = futures[future]
                    try:
                        key, summary, origin = future.result()
                        assert origin == "new"
                        spent += 1
                        if not item[3]:
                            remember(key, summary)
                    except Exception as error:
                        errors.append(f"{type(error).__name__}: {error}")
                    update_progress(done, len(pending))
                if errors:
                    raise RuntimeError("Economic worker failed; incomplete: " + "; ".join(errors))
                return len(pending) == len(missing)

            for batch_number in range(1, (SPACE + BATCH_SIZE - 1) // BATCH_SIZE + 1):
                candidates = batch_catalog(catalog, batch_number)
                frozen = dict(number=batch_number, start_index=(batch_number-1)*BATCH_SIZE,
                    stop_index=min(batch_number*BATCH_SIZE, SPACE),
                    catalog_sha256=protocol["catalog_sha256"], candidates=[c["name"] for c in candidates])
                cat_path = out / "batches" / f"{batch_number:03}-catalog.json"
                if cat_path.exists():
                    assert read(cat_path) == frozen, "Frozen batch catalog drift"
                else:
                    write(cat_path, frozen)
                _, before = state_now()
                current_batch_names = {case["name"] for case in candidates}
                phase = "raw"
                if not jobs([(case["rules"], view, "raw", False) for case in candidates for view in VIEWS]):
                    return checkpoint("NEW_CELL_BUDGET_REACHED")
                raw_pass = [case for case in candidates if qualifies(
                    {view:summaries[case["name"]]["raw"][view]["metrics"] for view in VIEWS}, floors["raw"])]
                phase = "cent"
                if not jobs([(case["rules"], view, "cent", False) for case in raw_pass for view in VIEWS]):
                    return checkpoint("NEW_CELL_BUDGET_REACHED")
                active.update(current_batch_names)
                current_batch_names.clear()
                incumbents = leaders(active, summaries, initial, floors, incumbents)["selected"]
                visited, after = state_now()
                result = dict(frozen, raw_qualified=[case["name"] for case in raw_pass],
                    fully_qualified=[case["name"] for case in candidates if qualified(summaries[case["name"]], floors)],
                    selected_before=before["selected"], selected_after=after["selected"],
                    strict_downside_improvers=len(after["strict_downside_improvers"]), visited_cases=len(visited),
                    improved={lane: objective(summaries[after["selected"][lane]], lane) <
                        objective(summaries[before["selected"][lane]], lane) for lane in LANES})
                result_path = out / "batches" / f"{batch_number:03}-result.json"
                if result_path.exists():
                    assert read(result_path) == result, "Historical batch result drift"
                else:
                    write(result_path, result)
                batches.append(result)
                checkpoint("BATCH_COMPLETE")
                print("BATCH", batch_number, "visited", len(visited), "of", SPACE,
                      "selected", after["selected"], flush=True)
            visited, selected = state_now()
            assert len(visited) == SPACE
            phase = "final-repeat"
            for name in sorted(set(selected["selected"].values())):
                if not jobs([(cases[name]["rules"], view, guard, True)
                             for guard in ("raw", "cent") for view in VIEWS]):
                    return checkpoint("NEW_CELL_BUDGET_REACHED")
    except Exception as error:
        checkpoint(f"ERROR: {type(error).__name__}: {error}")
        raise

    visited, selected = state_now()
    result = dict(status="EXHAUSTIVE_COMPLETE", initial=initial, visited=visited, cases=cases,
        summaries=summaries, batches=batches, phases=batches, finite_domain=SPACE,
        cost_status="COST_INCONCLUSIVE", holdout=False, claim=CLAIM, **selected)
    write(out / "results.json", result)
    for lane, name in selected["selected"].items():
        write(out / f"selected-{lane}-research.json", dict(status="RESEARCH_ONLY", rules_id=name,
            rules=cases[name]["rules"], lane=lane, protocol_sha256=sha(out / "protocol.json"),
            runtime_qualified=False, adapter_required=True, real_money="PROHIBITED"))
    paths = [path for folder in ("cells", "cells-integrity", "repeats", "repeats-integrity", "batches")
             for path in (out / folder).glob("*") if path.is_file()]
    paths += [out / name for name in ("protocol.json", "catalog.json", "results.json",
                                      "selected-profit-research.json", "selected-repair-research.json")]
    cell_proofs = list((out / "cells-integrity").glob("*.json"))
    write(out / "COMPLETE.json", dict(status="EXHAUSTIVE_COMPLETE", selected=selected["selected"],
        visited_cases=len(visited), finite_domain=SPACE, processed_batches=len(batches),
        new_economic_cells=sum(read(path)["origin"] == "new" for path in cell_proofs),
        reused_parent_cells=sum(read(path)["origin"] == "reused" for path in cell_proofs),
        fresh_repeats=len(list((out / "repeats").glob("*.json.gz"))),
        artifacts={str(path.relative_to(out)): sha(path) for path in paths}))
    phase = "complete"
    update_progress(0, 0)
    write(out / "progress.json", dict(status="EXHAUSTIVE_COMPLETE", visited_cases=SPACE,
        finite_domain=SPACE, selected=selected["selected"], processed_batches=len(batches)))
    print("EXHAUSTIVE_COMPLETE", selected["selected"], "visited", len(visited), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="runs/c22-exhaustive-loop-2026-10-25")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-new-cells", type=int)
    args = parser.parse_args()
    out = (ROOT / args.output).resolve()
    if not out.is_relative_to((ROOT / "runs").resolve()) or args.workers not in (1, 2, 3, 4):
        raise ValueError("Require runs/ output and 1–4 workers")
    if args.max_new_cells is not None and args.max_new_cells < 0:
        raise ValueError("Cell budget must be nonnegative")
    out.mkdir(parents=True, exist_ok=True)
    with (out / ".lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(out, args.workers, args.max_new_cells)


if __name__ == "__main__":
    main()
