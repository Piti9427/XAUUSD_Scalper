"""Frozen, resumable OFFLINE12-profile C22 risk experiment; no broker imports."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from decimal import Decimal, ROUND_HALF_UP
import fcntl
import gzip
import hashlib
import importlib.util
import inspect
from itertools import product
import json
import multiprocessing
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

from scripts.research.breakout_models import Costs, Rules
from scripts.research.c22_frequency_adapter import prepare
from scripts.research.c22_frequency_data import load_bars
from scripts.research.c22_loop_store import load_summary
from scripts.research.c22_matrix_tuning import closing_recovery
from scripts.research.c22_performance_campaign import (
    INPUT, ROOT, SEED, VIEWS, diagnostics, qualifies, read, sha, write,
)
from scripts.research.c22_risk_policy import RiskOverlay
from scripts.research.c22_risk_replay import replay
from scripts.research.rollover import SwapPolicy

PARENT = ROOT / "runs/c22-exhaustive-loop-2026-10-25"
SPEC = ROOT / "specs/c22-risk-closure-2026-10-26.md"
DEFAULT_OUT = ROOT / "runs/c22-risk-closure-2026-10-26"
ALGORITHM = "c22_risk_closure_v1"
GUARDS = ("raw", "cent")
_WORKER = None


def identity(native_rules, overlay):
    return hashlib.sha256(json.dumps(
        dict(schema=1, native_rules=native_rules, overlay=overlay), sort_keys=True
    ).encode()).hexdigest()[:16]


def catalog(native_rules):
    profiles = []
    for daily, dd, be in product((False, True), repeat=3):
        for pause in ((0, 24) if dd else (0,)):
            overlay = asdict(RiskOverlay(daily_budget=daily, drawdown_budget=dd,
                                        net_be_first=be, dd_pause_hours=pause))
            label = "+".join(x for x, active in (("D1", daily), ("P1", dd), ("B1", be)) if active) or "Native26b8"
            if pause:
                label += "+pause24h"
            profiles.append(dict(name=identity(native_rules, overlay), label=label, overlay=overlay))
    assert len(profiles) == len({p["name"] for p in profiles}) == 12
    return dict(schema=1, algorithm=ALGORITHM, finite_domain=12, profiles=profiles)


def _safe_out(out):
    out = Path(out).resolve()
    if not out.is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("Research output must remain under runs/")
    return out


def load_payload(path):
    path = Path(path)
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return read(path)


def _reference(protocol, view, guard):
    binding = protocol["references"][view + "-" + guard]
    path = (ROOT / binding["path"]).resolve()
    assert path.is_relative_to((ROOT / "runs").resolve()) and sha(path) == binding["sha256"]
    assert sha(ROOT / binding["proof_path"]) == binding["proof_sha256"]
    return load_payload(path)


def validate(protocol, out, *, inputs=True):
    assert protocol["algorithm"] == ALGORITHM and protocol["holdout"] is False
    assert protocol["cost_status"] == "COST_INCONCLUSIVE"
    for name, digest in protocol["sources"].items():
        assert sha(ROOT / name) == digest, "Source drift: " + name
        assert sha(out / "source_snapshot" / name) == digest, "Snapshot drift: " + name
    for record in protocol["parent"].values():
        assert sha(ROOT / record["path"]) == record["sha256"]
    assert sha(INPUT / "manifest.json") == protocol["input_manifest_sha256"]
    if inputs:
        for name, digest in protocol["input_hashes"].items():
            assert sha(INPUT / name) == digest, "Input drift: " + name
    assert sha(out / "catalog.json") == protocol["catalog_sha256"]
    assert read(out / "catalog.json") == catalog(protocol["native_rules"])
    for view in VIEWS:
        for guard in GUARDS:
            cell = _reference(protocol, view, guard)
            assert cell["result"]["rules"] == protocol["native_rules"]
            assert cell["result"].get("swap_policy") is not None


def freeze(out):
    out = _safe_out(out)
    if (out / "protocol.json").exists():
        protocol = read(out / "protocol.json")
        validate(protocol, out)
        return protocol, read(out / "catalog.json")
    assert "OWNER-CONFIRMED" in SPEC.read_text()
    parent = read(PARENT / "protocol.json")
    complete, audit = read(PARENT / "COMPLETE.json"), read(PARENT / "independent-verification.json")
    selected = read(PARENT / "selected-profit-research.json")
    cfg = read(ROOT / "config/c22-selected-demo.json")
    for name, digest in cfg["research_proof"].items():
        assert sha(PARENT / name) == digest
    assert audit["status"] == "PASS" and audit["finite_domain"] == 5184
    assert complete["selected"]["profit"] == selected["rules_id"] == "26b8bcd69e043653"
    refs = {}
    for view in VIEWS:
        for guard in GUARDS:
            proof_path = PARENT / "cells-integrity" / f'26b8bcd69e043653-{view}-{guard}.json'
            proof = read(proof_path)
            assert complete["artifacts"][str(proof_path.relative_to(PARENT))] == sha(proof_path)
            assert audit["payload_hashes"][proof["path"]] == proof["sha256"]
            refs[view + "-" + guard] = dict(path=proof["path"], sha256=proof["sha256"],
                proof_path=str(proof_path.relative_to(ROOT)), proof_sha256=sha(proof_path))
    cats = catalog(selected["rules"])
    sources = dict(parent["sources"])
    paths = [SPEC, Path(__file__), ROOT / "scripts/research/c22_risk_policy.py",
             ROOT / "scripts/research/c22_risk_replay.py", ROOT / "scripts/research/c22_risk_verify.py",
             ROOT / "scripts/research/c22_risk_report.py", ROOT / "scripts/research/c22_risk_control.py",
             ROOT / "tests/research/test_c22_risk_policy.py", ROOT / "tests/research/test_c22_risk_replay.py"]
    for path in paths:
        sources[str(path.relative_to(ROOT))] = sha(path)
    baseline = next(p["name"] for p in cats["profiles"] if p["label"] == "Native26b8")
    write(out / "catalog.json", cats)
    protocol = dict(schema=1, algorithm=ALGORITHM, sources=sources,
        input_hashes=parent["input_hashes"], input_manifest_sha256=parent["input_manifest_sha256"],
        broker=parent["broker"], views=parent["views"], start=parent["start"], end=parent["end"],
        original_floors=parent["original_floors"], native_rules=selected["rules"],
        native_rules_id=selected["rules_id"], parent={
            key:dict(path=str((PARENT / name).relative_to(ROOT)), sha256=sha(PARENT / name))
            for key, name in (("protocol", "protocol.json"), ("complete", "COMPLETE.json"),
                             ("audit", "independent-verification.json"), ("selected", "selected-profit-research.json"))},
        references=refs, catalog_sha256=sha(out / "catalog.json"), baseline_overlay_id=baseline,
        repeat_policy="selected_profit_all_six_fresh", cost_status="COST_INCONCLUSIVE", holdout=False,
        ranking="max raw base net, raw stress net, lower worst matched DD; baseline wins exact ties",
        finite_domain=12, expected_paths=72, real_money="PROHIBITED", execution_authorized=False)
    for name, digest in sources.items():
        assert sha(ROOT / name) == digest
        target = out / "source_snapshot" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    write(out / "protocol.json", protocol)
    validate(protocol, out)
    return protocol, cats


def _cent_replay():
    source = inspect.getsource(replay)
    assert source.count("if net < 0:") == 1
    def cent_loss(net):
        return Decimal(str(float(net))).quantize(Decimal(".01"), rounding=ROUND_HALF_UP) < 0
    scope = dict(replay.__globals__, _cent_loss=cent_loss)
    exec(compile(source.replace("if net < 0:", "if _cent_loss(net):"), "<risk-cent-replay>", "exec"), scope)
    return scope["replay"]


def init_worker(protocol, out):
    global _WORKER
    frame, _ = prepare(load_bars(INPUT / "bars.csv"), read(SEED))
    modspec = importlib.util.spec_from_file_location("risk_accounting_audit", ROOT / "runs/c22-real-data-audit-2026-10-24/run_audit_v2.py")
    audit = importlib.util.module_from_spec(modspec)
    modspec.loader.exec_module(audit)
    swap = SwapPolicy.from_broker(protocol["broker"])
    assert swap is not None
    _WORKER = dict(protocol=protocol, out=Path(out), frame=frame,
        ticks=[np.load(INPUT / "tape" / f"{key}.npy", mmap_mode="r") for key in ("time", "bid", "ask")],
        audit=audit, swap=swap, cent=_cent_replay(), last_quote=read(INPUT / "manifest.json")["last_quote_utc"])


def read_cell(out, key, folder="cells"):
    assert folder in ("cells", "repeats")
    proof = read(out / (folder + "-integrity") / (key + ".json"))
    path = (ROOT / proof["path"]).resolve()
    assert path == (out / folder / (key + ".json.gz")).resolve()
    assert sha(path) == proof["sha256"]
    cell = load_payload(path)
    assert key == f'{cell["profile"]["name"]}-{cell["view"]}-{cell["guard"]}'
    return cell


def execute_cell(job):
    profile, view, guard, repeat = job
    state = _WORKER
    protocol, out = state["protocol"], state["out"]
    folder = "repeats" if repeat else "cells"
    key = f'{profile["name"]}-{view}-{guard}'
    if (out / (folder + "-integrity") / (key + ".json")).exists():
        return key, read_cell(out, key, folder)["summary"]
    assert shutil.disk_usage(out).free > 2 * 1024**3, "Insufficient disk"
    begun = time.monotonic()
    result = (state["cent"] if guard == "cent" else replay)(
        state["frame"], state["ticks"], protocol["broker"], Rules(**protocol["native_rules"]),
        Costs(**protocol["views"][view]), start=pd.Timestamp(protocol["start"]), end=pd.Timestamp(protocol["end"]),
        swap_policy=state["swap"], capture_events=True, capture_context=True,
        overlay=RiskOverlay(**profile["overlay"]))
    assert result.get("swap_policy") is not None
    baseline = profile["name"] == protocol["baseline_overlay_id"]
    if baseline:
        assert result == _reference(protocol, view, guard)["result"], "Overlay-off parity failure"
    checks = state["audit"].independent_audit(result, protocol["broker"], Costs(**protocol["views"][view]))
    metrics = state["audit"].metrics(result)
    minimum = min([200.0] + [x["equity_usd"] for x in result["equity"]])
    metrics.update(min_observed_equity=minimum, survival=bool(minimum > 0 and result["final_balance"] > 0
                   and not result["rejections"]["bankrupt"]))
    dx = diagnostics(result, state["last_quote"])
    dx["actual_closing_recovery"] = closing_recovery(result, state["last_quote"])
    cell = dict(profile=profile, view=view, guard=guard, result=result, metrics=metrics,
                diagnostics=dx, checks=checks)
    cell["summary"] = load_summary(cell)
    if repeat:
        original = read_cell(out, key)
        assert all(cell[k] == original[k] for k in ("result", "metrics", "diagnostics", "summary")), "Fresh repeat drift"
    target = out / folder / (key + ".json.gz")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".pending")
    with temporary.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=1, fileobj=stream, mtime=0) as zipped:
            zipped.write(json.dumps(cell, allow_nan=False, separators=(",", ":")).encode())
    temporary.replace(target)
    write(out / (folder + "-integrity") / (key + ".json"),
          dict(path=str(target.relative_to(ROOT)), sha256=sha(target), origin="new"))
    print(folder, key, profile["label"], "net", round(metrics["net_usd"], 4),
          "DD", round(metrics["max_dd_pct"], 4), "seconds", round(time.monotonic() - begun, 2), flush=True)
    return key, cell["summary"]


def leaders(protocol, profiles, summaries):
    complete = [p["name"] for p in profiles if all(set(summaries.get(p["name"], {}).get(g, {})) == set(VIEWS) for g in GUARDS)]
    eligible = [name for name in complete if all(qualifies(
        {v:summaries[name][g][v]["metrics"] for v in VIEWS}, protocol["original_floors"][g]) for g in GUARDS)]
    baseline = protocol["baseline_overlay_id"]
    def rank(name):
        return (-summaries[name]["raw"]["base"]["metrics"]["net_usd"],
                -summaries[name]["raw"]["stress"]["metrics"]["net_usd"],
                max(summaries[name][g][v]["metrics"]["max_dd_pct"] for g in GUARDS for v in VIEWS),
                name != baseline, name)
    return dict(profit=min(eligible, key=rank) if eligible else None), sorted(eligible), sorted(complete)


def run(out, *, workers=2):
    out = _safe_out(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        protocol, cats = freeze(out)
        if (out / "COMPLETE.json").exists():
            done = read(out / "COMPLETE.json")
            for name, digest in done["artifacts"].items():
                assert sha(out / name) == digest, "Completed artifact drift: " + name
            for folder in ("cells", "repeats"):
                for path in (out / (folder + "-integrity")).glob("*.json"):
                    read_cell(out, path.stem, folder)
            return read(out / "results.json")
        profiles = cats["profiles"]
        summaries = {}
        def record(key, summary):
            name, view, guard = key.split("-")
            summaries.setdefault(name, {}).setdefault(guard, {})[view] = summary
            selected, eligible, complete = leaders(protocol, profiles, summaries)
            value = dict(schema=1, protocol_sha256=sha(out / "protocol.json"),
                status="PARTIAL", expected_paths=72, evaluated_paths=sum(len(rows) for x in summaries.values() for rows in x.values()),
                completed_profiles=len(complete), summaries=summaries, selected=selected, qualified=eligible)
            write(out / "checkpoint.json", value)
            write(out / "results.json", value)
        for path in sorted((out / "cells-integrity").glob("*.json")):
            record(path.stem, read_cell(out, path.stem)["summary"])
        baseline = next(p for p in profiles if p["name"] == protocol["baseline_overlay_id"])
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
                                 initializer=init_worker, initargs=(protocol, str(out))) as pool:
            for group in ([baseline], [p for p in profiles if p != baseline]):
                jobs = [(p, v, g, False) for p in group for g in GUARDS for v in VIEWS
                        if not (out / "cells-integrity" / f'{p["name"]}-{v}-{g}.json').exists()]
                for future in as_completed([pool.submit(execute_cell, job) for job in jobs]):
                    key, summary = future.result()
                    record(key, summary)
                if group == [baseline]:
                    assert all(set(summaries[baseline["name"]][g]) == set(VIEWS) for g in GUARDS)
                    write(out / "BASELINE_PARITY_PASS.json", dict(status="PASS", paths=6,
                          protocol_sha256=sha(out / "protocol.json"), baseline_overlay_id=baseline["name"]))
            selected, _, _ = leaders(protocol, profiles, summaries)
            chosen = next(p for p in profiles if p["name"] == (selected["profit"] or baseline["name"]))
            jobs = [(chosen, v, g, True) for g in GUARDS for v in VIEWS]
            for future in as_completed([pool.submit(execute_cell, job) for job in jobs]):
                future.result()
        value = read(out / "results.json")
        assert value["evaluated_paths"] == 72 and value["completed_profiles"] == 12
        value["status"] = "MATRIX_EVALUATED_AWAITING_AUDIT"
        write(out / "results.json", value)
        immutable = [out / name for name in ("protocol.json", "catalog.json", "results.json", "BASELINE_PARITY_PASS.json")]
        immutable += list((out / "cells-integrity").glob("*.json"))
        immutable += list((out / "repeats-integrity").glob("*.json"))
        artifacts = {str(p.relative_to(out)):sha(p) for p in sorted(immutable)}
        write(out / "COMPLETE.json", dict(status="MATRIX_EVALUATED_AWAITING_AUDIT", paths=72,
            profiles=12, fresh_repeats=6, selected=value["selected"], artifacts=artifacts))
        print("All72 paths and6 fresh repeats computed; independent audit required", flush=True)
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    run(args.out, workers=args.workers)


if __name__ == "__main__":
    main()
