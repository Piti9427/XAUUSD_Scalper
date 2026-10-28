"""Compressed offline C22 cells and process-local canonical replay workers.

Proofs bind both newly computed cells and immutable cells reused from earlier
campaigns. This module never opens a broker connection or changes strategy code.
"""

from dataclasses import asdict
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import time

import numpy as np
import pandas as pd

from scripts.research.breakout_models import Costs, Rules
from scripts.research.breakout_replay import replay
from scripts.research.c22_frequency_adapter import prepare
from scripts.research.c22_frequency_data import load_bars
from scripts.research.c22_matrix_tuning import DOMAINS, closing_recovery
from scripts.research.c22_performance_campaign import (
    INPUT, ROOT, SEED, VIEWS, cent_engine, diagnostics, read, sha, write,
)
from scripts.research.rollover import SwapPolicy


_KEY = re.compile(r"[0-9a-f]{16}-(base|stress|fee)-(raw|cent)\Z")
_WORKER = None
MIN_FREE_BYTES = 2 * 1024**3


def rules_id(rules):
    """Use the previous campaign's exact full-Rules identity encoding."""
    values = asdict(rules) if isinstance(rules, Rules) else rules
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:16]


def _output(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("Cell output must remain under runs/")
    return path


def _proof_path(out, key, folder):
    if folder not in ("cells", "repeats") or not _KEY.fullmatch(key):
        raise ValueError("Invalid cell folder/key")
    return _output(out) / (folder + "-integrity") / (key + ".json")


def _payload_path(relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Cell proof requires a safe ROOT-relative path")
    resolved = (ROOT / path).resolve()
    if not resolved.is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("Cell proof escaped runs/")
    if not (resolved.name.endswith(".json") or resolved.name.endswith(".json.gz")):
        raise ValueError("Unsupported cell encoding")
    return resolved


def _read_payload(path):
    if path.name.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return read(path)


def _validate_cell(cell, key):
    assert cell["view"] in VIEWS and cell["guard"] in ("raw", "cent")
    rules = cell["result"]["rules"]
    assert cell["case"]["rules"] == rules, "Cell case/result Rules mismatch"
    name = rules_id(rules)
    assert cell["case"]["name"] == name, "Cell Rules identity mismatch"
    assert key == f'{name}-{cell["view"]}-{cell["guard"]}', "Cell key mismatch"


def read_cell(out, key, folder="cells"):
    """Read a cell only after checking its immutable payload hash and identity."""
    proof = read(_proof_path(out, key, folder))
    assert proof["origin"] in ("new", "reused"), "Unsupported cell origin"
    path = _payload_path(proof["path"])
    assert sha(path) == proof["sha256"], f"Cell hash mismatch: {key}"
    cell = _read_payload(path)
    _validate_cell(cell, key)
    return cell


def add_reference(out, key, path):
    """Bind a previously verified result without copying or rewriting it.

    The parent validates the supplying campaign's COMPLETE manifest before
    calling this function. This proof additionally binds the exact source cell.
    Existing local proofs are never overwritten by a different source.
    """
    proof_path = _proof_path(out, key, "cells")
    source = Path(path).resolve()
    relative = str(source.relative_to(ROOT))
    source = _payload_path(relative)
    cell = _read_payload(source)
    _validate_cell(cell, key)
    if proof_path.exists():
        current = read_cell(out, key)
        assert current["result"] == cell["result"], "Conflicting cached results"
        assert current["metrics"] == cell["metrics"], "Conflicting cached metrics"
        return load_summary(current)
    write(proof_path, dict(path=relative, sha256=sha(source), origin="reused"))
    return load_summary(cell)


def load_summary(cell):
    """Return small economic/risk data; preserve full evidence in the payload."""
    metrics = cell["metrics"]
    dx = cell["diagnostics"]
    recovery = dx.get("actual_closing_recovery")
    if recovery is None:
        last = read(INPUT / "manifest.json")["last_quote_utc"]
        recovery = closing_recovery(cell["result"], last)
    completed = recovery["longest_completed"]
    ongoing = recovery["ongoing"]
    completed_days = completed["days"] if completed else 0.0
    ongoing_days = ongoing["days"] if ongoing else 0.0
    worst = dx["worst_run_by_loss_pct"]
    longest = dx["longest_loss_run"]
    return dict(metrics=metrics, risk=dict(
        dd=metrics["max_dd_pct"], streak=metrics["max_consecutive_losses"],
        severity=worst["loss_pct_of_start_equity"] if worst else 0.0,
        completed_days=completed_days, ongoing_days=ongoing_days,
        recovery=max(completed_days, ongoing_days),
        longest_run_net=longest["net_usd"] if longest else 0.0,
        longest_run_severity=longest["loss_pct_of_start_equity"] if longest else 0.0,
        min_equity=metrics["min_observed_equity"],
    ))


def init_worker(protocol, out):
    """Initialize pure inputs once per process; no executable/broker interfaces."""
    global _WORKER
    out = _output(out)
    assert sha(INPUT / "manifest.json") == protocol["input_manifest_sha256"]
    broker = protocol["broker"]
    swap = SwapPolicy.from_broker(broker)
    assert swap is not None, "Every economic cell requires modeled swap"
    frame, base = prepare(load_bars(INPUT / "bars.csv"), read(SEED))
    spec = importlib.util.spec_from_file_location(
        "c22_loop_worker_audit", ROOT / "runs/c22-real-data-audit-2026-10-24/run_audit_v2.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    _WORKER = dict(
        protocol=protocol, out=out, frame=frame, base=asdict(base), audit=audit,
        ticks=[np.load(INPUT / "tape" / f"{key}.npy", mmap_mode="r")
               for key in ("time", "bid", "ask")],
        swap=swap, costs={view: Costs(**protocol["views"][view]) for view in VIEWS},
        last_quote=read(INPUT / "manifest.json")["last_quote_utc"], cent=cent_engine(),
    )


def _rules(values, base):
    rules = Rules(**values)
    assert asdict(rules) == values, "Require complete explicit Rules"
    assert all(values[key] == value for key, value in base.items() if key not in DOMAINS), \
        "Only declared native tuning axes may change"
    assert all(values[key] in allowed for key, allowed in DOMAINS.items()), "Outside tuning domain"
    assert rules.sizing_mode == "fixed" and rules.buy_sizing_mode in (None, "fixed")
    assert rules.risk_cap == .1 and rules.daily_loss_limit == .1 and rules.max_daily_losses == 2
    assert rules.holding_mode == "legacy" and rules.risk_mode == "static"
    return rules


def _save_gzip(out, key, folder, cell):
    target = out / folder / (key + ".json.gz")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".pending")
    payload = json.dumps(cell, allow_nan=False, separators=(",", ":")).encode("utf-8")
    with temporary.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=1, fileobj=stream, mtime=0) as zipped:
            zipped.write(payload)
    temporary.replace(target)
    write(_proof_path(out, key, folder), dict(
        path=str(target.relative_to(ROOT)), sha256=sha(target), origin="new"))


def _matches_original(cell, original):
    for key in ("result", "metrics", "diagnostics"):
        assert cell[key] == original[key], f"Fresh repeat {key} differs"


def execute_cell(job):
    """Execute one complete canonical economic view or verify its saved proof."""
    if _WORKER is None:
        raise RuntimeError("init_worker must run before execute_cell")
    values, view, guard, repeat = job
    state = _WORKER
    assert view in VIEWS and guard in ("raw", "cent") and type(repeat) is bool
    rules = _rules(values, state["base"])
    name = rules_id(rules)
    key = f"{name}-{view}-{guard}"
    folder = "repeats" if repeat else "cells"
    proof = _proof_path(state["out"], key, folder)
    if proof.exists():
        cell = read_cell(state["out"], key, folder)
        assert cell["result"]["rules"] == values
        if repeat:
            _matches_original(cell, read_cell(state["out"], key))
        return key, load_summary(cell), read(proof)["origin"]
    if shutil.disk_usage(state["out"]).free < MIN_FREE_BYTES:
        raise RuntimeError("Insufficient disk space; research is incomplete, not converged")
    begun = time.monotonic()
    protocol = state["protocol"]
    result = (state["cent"] if guard == "cent" else replay)(
        state["frame"], state["ticks"], protocol["broker"], rules, state["costs"][view],
        start=pd.Timestamp(protocol["start"]), end=pd.Timestamp(protocol["end"]),
        swap_policy=state["swap"], capture_events=True, capture_context=True)
    assert result["swap_policy"] is not None
    checks = state["audit"].independent_audit(result, protocol["broker"], state["costs"][view])
    metrics = state["audit"].metrics(result)
    minimum = min([200.0] + [mark["equity_usd"] for mark in result["equity"]])
    metrics.update(min_observed_equity=minimum, survival=bool(
        minimum > 0 and result["final_balance"] > 0 and not result["rejections"]["bankrupt"]))
    dx = diagnostics(result, state["last_quote"])
    dx["actual_closing_recovery"] = closing_recovery(result, state["last_quote"])
    cell = dict(case=dict(name=name, rules=values), view=view, guard=guard, result=result,
                metrics=metrics, diagnostics=dx, checks=checks)
    _validate_cell(cell, key)
    if repeat:
        _matches_original(cell, read_cell(state["out"], key))
    _save_gzip(state["out"], key, folder, cell)
    print(folder, key, "net", round(metrics["net_usd"], 4), "DD",
          round(metrics["max_dd_pct"], 4), "seconds", round(time.monotonic() - begun, 2), flush=True)
    return key, load_summary(cell), "new"
