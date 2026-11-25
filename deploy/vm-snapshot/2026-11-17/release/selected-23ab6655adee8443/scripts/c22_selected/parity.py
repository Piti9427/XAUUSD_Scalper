"""Bounded offline detector/entry-price agreement; never a trading replay."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import math
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.c22_selected.strategy import CANDIDATE_ID, ROOT, SelectedBarCache, decide
from scripts.qualification.c22.artifacts import make_report, parse_utc, read_json, source_ref
from scripts.research.c22_frequency_adapter import prepare
from scripts.research.c22_frequency_data import load_bars
from scripts.research.c22_loop_store import read_cell
from scripts.research.reward156_tuning import closed_h4_ema


# The original9e entry seed is fixed; only its signals are used here. Selected
# geometry is compared against the immutable native Rules/ledger, not this seed.
REFERENCE_SEED = {
    "strategy": "reward156", "formula": "archived", "buy_pause_drawdown": 0.0,
    "risk_cap": 0.1, "rsi_period": 7, "rsi_threshold": 30, "sell_lookback": 48,
    "sell_ema": 50, "macro_span": 200, "buy_stop_atr": 2.0, "buy_target_rr": 2.0,
    "buy_protect_mode": "break_even", "stop_atr": 2.5, "sell_target": "r1.35",
    "protect_mode": "break_even", "daily_loss_limit": 0.1, "max_daily_losses": 2,
    "cooldown_bars": 0, "entry_session": "all", "risk_mode": "static", "buy_ema": 50,
}
_COLUMNS = ("raw_direction", "direction", "atr", "ema50", "hh", "ll", "macro_ema",
            "macro_blocked", "macro_unavailable")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound_sources(campaign: Path, bars: Path, sources: list) -> tuple[dict, dict, dict]:
    protocol_path = campaign / "protocol.json"
    complete_path = campaign / "COMPLETE.json"
    audit_path = campaign / "independent-verification.json"
    protocol, complete, audit = (read_json(path) for path in (protocol_path, complete_path, audit_path))
    if complete["status"] != "EXHAUSTIVE_COMPLETE" or audit["status"] != "PASS":
        raise ValueError("Final research completion and audit PASS required")
    if (complete["selected"]["profit"] != CANDIDATE_ID
            or audit["selected"] != complete["selected"]
            or audit["parent_completion_sha256"] != _sha(complete_path)
            or complete["artifacts"]["protocol.json"] != _sha(protocol_path)):
        raise ValueError("Selected research completion/audit binding mismatch")
    if _sha(bars) != protocol["input_hashes"]["bars.csv"]:
        raise ValueError("Archived bars source drift")
    for relative, expected in protocol.get("sources", {}).items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or _sha(path) != expected:
            raise ValueError("Frozen research source drift: " + relative)
    sources.extend(source_ref(path) for path in (protocol_path, complete_path, audit_path, bars))
    return protocol, complete, audit


def _detector(cache: SelectedBarCache, reference: pd.DataFrame, mismatches: list) -> dict:
    actual = cache.frame
    if actual is None or not actual.index.equals(reference.index):
        raise ValueError("Detector index mismatch")
    checks = {}
    for column in _COLUMNS:
        if column not in actual or column not in reference:
            raise ValueError("Detector comparison column unavailable: " + column)
        left = reference[column].to_numpy(dtype=float)
        right = actual[column].to_numpy(dtype=float)
        equal = np.isclose(left, right, rtol=0.0, atol=1e-10, equal_nan=True)
        bad = np.flatnonzero(~equal)
        checks[column] = {"compared": len(equal), "mismatches": len(bad)}
        for index in bad[:10]:
            mismatches.append({"scope": "detector", "field": column,
                               "bar_open_utc": pd.Timestamp(str(reference.index[index])).isoformat()})
    return checks


def _entry_contexts(result: dict) -> dict:
    contexts = {}
    for event in result["context_events"]:
        if event["reason"] != "admitted":
            continue
        key = (int(parse_utc(event["time_utc"]).timestamp() * 1000), int(event["direction"]))
        if key in contexts:
            raise ValueError("Duplicate admitted context identity")
        contexts[key] = parse_utc(event["signal_close_utc"])
    return contexts


def _geometry_path(
    campaign: Path, protocol: dict, complete: dict, audit: dict, guard: str, view: str,
    cache: SelectedBarCache, tape: dict, sources: list, mismatches: list,
) -> dict:
    key = f"{CANDIDATE_ID}-{view}-{guard}"
    proof_path = campaign / "cells-integrity" / (key + ".json")
    proof = read_json(proof_path)
    relative = str(proof_path.relative_to(ROOT))
    if (complete["artifacts"][str(proof_path.relative_to(campaign))] != _sha(proof_path)
            or audit["audited_cells"][relative] != _sha(proof_path)
            or audit["payload_hashes"][proof["path"]] != proof["sha256"]):
        raise ValueError("Audited selected cell binding mismatch: " + key)
    cell = read_cell(campaign, key)
    result = cell["result"]
    sources.extend((source_ref(proof_path), source_ref(ROOT / proof["path"])))
    if cache.rules is None or result["rules"] != asdict(cache.rules):
        raise ValueError("Selected native28 Rules mismatch: " + key)
    costs = protocol["views"][view]
    if result["costs"] != costs:
        raise ValueError("Selected scenario cost binding mismatch: " + key)
    contexts = _entry_contexts(result)
    summary = {"view": view, "guard": guard, "entries_compared": 0,
               "buy_entries": 0, "sell_entries": 0, "guard_boundary_differences": 0,
               "max_abs_geometry_delta": 0.0}
    original_row = cache.row
    try:
        for trade in result["ledger"]:
            stamp, direction = int(trade["entry_ms"]), int(trade["direction"])
            closed = contexts.get((stamp, direction))
            if closed is None:
                raise ValueError("Recorded signal-close context unavailable: " + key)
            bar_open = pd.Timestamp(closed) - pd.Timedelta(minutes=15)
            if cache.frame is None or bar_open not in cache.frame.index:
                raise ValueError("Recorded entry bar absent from supplied archive")
            cache.row = cache.frame.loc[bar_open]
            if int(cache.row.direction) != direction:
                mismatches.append({"scope": "geometry", "view": view, "guard": guard,
                                   "field": "direction", "entry_ms": stamp})
            index = int(np.searchsorted(tape["time"], stamp, side="left"))
            if index >= len(tape["time"]) or int(tape["time"][index]) != stamp:
                raise ValueError("Recorded entry quote timestamp absent from tape")
            # Canonical replay widens spread symmetrically around the recorded
            # mid: half below Bid, half above Ask. Slippage is applied by decide.
            half_spread = float(costs["extra_spread"]) / 2
            bid = float(tape["bid"][index]) - half_spread
            ask = float(tape["ask"][index]) + half_spread
            if not all(math.isfinite(value) and value > 0 for value in (bid, ask)) or ask < bid:
                raise ValueError("Invalid recorded entry quote")
            equity = float(trade["entry_equity"])
            if not math.isfinite(equity) or equity <= 0 or float(trade["volume"]) != 0.01:
                raise ValueError("Invalid recorded entry account/volume")
            runtime_cost = {"slippage_allowance_price": costs["slippage"],
                            "commission_per_lot": costs["commission_per_lot"]}
            plan = decide(cache, bid, ask, protocol["broker"], runtime_cost, equity)
            if isinstance(plan, str):
                mismatches.append({"scope": "geometry", "view": view, "guard": guard,
                                   "field": "admission", "reason": plan, "entry_ms": stamp})
                continue
            for field, value in (("entry", plan.entry), ("initial_stop", plan.stop),
                                 ("target", plan.target), ("risk_usd", plan.risk)):
                delta = abs(value - float(trade[field]))
                summary["max_abs_geometry_delta"] = max(summary["max_abs_geometry_delta"], delta)
                if delta > 1e-8:
                    mismatches.append({"scope": "geometry", "view": view, "guard": guard,
                                       "field": field, "entry_ms": stamp,
                                       "reference": float(trade[field]), "adapter": value})
            summary["entries_compared"] += 1
            summary["buy_entries" if direction == 1 else "sell_entries"] += 1
    finally:
        cache.row = original_row
    return summary


def run_parity(bars_path: Path, campaign_dir: Path) -> dict:
    """Compare archive bars and persisted selected entries; read tape only at entries."""
    bars_path, campaign = Path(bars_path).resolve(), Path(campaign_dir).resolve()
    sources = [source_ref(Path(__file__)), source_ref(ROOT / "scripts/c22_selected/strategy.py")]
    mismatches, paths, detector_checks = [], [], {}
    coverage = {"bars_compared": 0, "cost_guard_paths": 0, "geometry_entries_compared": 0,
                "buy_geometry_entries": 0, "sell_geometry_entries": 0,
                "tick_scan_performed": False, "full_tick_input_rehashed": False}
    input_tape = {}
    rules = None
    try:
        protocol, complete, audit = _bound_sources(campaign, bars_path, sources)
        bars = load_bars(bars_path)
        reference, _ = prepare(bars, REFERENCE_SEED)
        reference["macro_ema"] = closed_h4_ema(bars, 200)
        cache = SelectedBarCache()
        cache.append(bars)
        detector_checks = _detector(cache, reference, mismatches)
        coverage["bars_compared"] = len(bars)
        coverage["buy_signals"] = int((reference.direction == 1).sum())
        coverage["sell_signals"] = int((reference.direction == -1).sum())
        rules = asdict(cache.rules) if cache.rules is not None else None
        tape = {}
        for name in ("time", "bid", "ask"):
            path = bars_path.parent / "tape" / (name + ".npy")
            tape[name] = np.load(path, mmap_mode="r", allow_pickle=False)
            input_tape[name] = {"path": str(path), "declared_sha256": protocol["input_hashes"][f"tape/{name}.npy"],
                                "hash_status": "DECLARED_NOT_REHASHED", "observations": len(tape[name])}
        if len({len(array) for array in tape.values()}) != 1 or any(array.ndim != 1 for array in tape.values()):
            raise ValueError("Input tape shape mismatch")
        for guard in ("raw", "cent"):
            for view in ("base", "stress", "fee"):
                path = _geometry_path(campaign, protocol, complete, audit, guard, view,
                                      cache, tape, sources, mismatches)
                paths.append(path)
                coverage["cost_guard_paths"] += 1
                coverage["geometry_entries_compared"] += path["entries_compared"]
                coverage["buy_geometry_entries"] += path["buy_entries"]
                coverage["sell_geometry_entries"] += path["sell_entries"]
        if not coverage["geometry_entries_compared"]:
            raise ValueError("No recorded entry geometry available")
    except (OSError, ValueError, KeyError, TypeError, AssertionError) as exc:
        mismatches.append({"scope": "input_or_binding", "reason": str(exc)})
    return make_report(
        "selected_adapter_parity", "PARITY_FAIL" if mismatches else "PRICE_DETECTOR_PARITY_PASS",
        candidate_id=CANDIDATE_ID, sources=sources, coverage=coverage,
        reasons=["CODE_INPUT_AGREEMENT_ONLY" if not mismatches else "MISMATCH_OR_MISSING_EVIDENCE"],
        detector_checks=detector_checks, geometry_paths=paths, mismatches=mismatches,
        native_rules=rules, input_tape=input_tape, reference_seed=REFERENCE_SEED,
        lifecycle_context_scope="NOT_TESTED_BY_PRICE_PARITY", broker_fill_parity=False,
        runtime_qualified=False, economic_replay_performed=False,
        limitations=[
            "Shared canonical detector and entry helpers; not independent algorithm validation",
            "Recorded entry prices only; no lifecycle, cooldown, broker fills or future profitability qualification",
            "Cent paths are compared separately; no raw outcome substitutes a cent geometry",
            "Large tape hashes are declared from audited protocol, not freshly rehashed",
            "Modeled swap remains part of persisted economic paths; no new economic evaluation performed",
        ],
    )
