"""Independent immutable-cell, budget, cost and full-tick audit for C22 overlays.

No broker connection, trade submission or economic replay is performed. The
source tick tape is independently scanned against each supplied closed ledger.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
from itertools import product
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.c22_learning_verify import (
    DATA, GUARDS, ROOT, VIEWS, IndependentTapeAudit, equal, read, sha,
)


ALGORITHM = "c22_risk_closure_v1"
OVERLAY_KEYS = {"daily_budget", "drawdown_budget", "net_be_first", "dd_pause_hours"}
DAY_MS = 86_400_000
HELPER = ROOT / "scripts/research/c22_learning_verify.py"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    pending.replace(path)


def path_in_runs(relative):
    path = Path(relative)
    assert not path.is_absolute() and ".." not in path.parts, relative
    result = (ROOT / path).resolve()
    assert result.is_relative_to((ROOT / "runs").resolve()), relative
    return result


def overlay_identity(native_rules, overlay):
    value = dict(native_rules=native_rules, overlay=overlay, schema=1)
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def independent_catalog(native_rules):
    overlays = []
    for daily, drawdown, be in product((False, True), repeat=3):
        for pause in ((0, 24) if drawdown else (0,)):
            overlay = dict(daily_budget=daily, drawdown_budget=drawdown,
                           net_be_first=be, dd_pause_hours=pause)
            overlays.append((overlay_identity(native_rules, overlay), overlay))
    assert len(overlays) == len(dict(overlays)) == 12
    return dict(overlays)


def validate_inputs(out, protocol):
    assert protocol["algorithm"] == ALGORITHM
    assert protocol["holdout"] is False and protocol["cost_status"] == "COST_INCONCLUSIVE"
    assert set(protocol["views"]) == set(VIEWS)
    assert protocol["repeat_policy"] == "selected_profit_all_six_fresh"
    assert sha(DATA / "manifest.json") == protocol["input_manifest_sha256"]
    for name, digest in protocol["input_hashes"].items():
        assert sha(DATA / name) == digest, "Input hash drift: " + name
    for name, digest in protocol["sources"].items():
        source = (ROOT / name).resolve()
        assert source.is_relative_to(ROOT) and sha(source) == digest, name
        assert sha(out / "source_snapshot" / name) == digest, name
    assert "scripts/research/c22_risk_verify.py" in protocol["sources"]
    parent = {}
    for name in ("protocol", "complete", "audit", "selected"):
        binding = protocol["parent"][name]
        path = path_in_runs(binding["path"])
        assert sha(path) == binding["sha256"], name
        parent[name] = read(path)
    assert parent["complete"]["status"] == "EXHAUSTIVE_COMPLETE"
    assert parent["audit"]["status"] == "PASS"
    assert parent["audit"]["parent_completion_sha256"] == protocol["parent"]["complete"]["sha256"]
    assert parent["selected"]["rules_id"] == "26b8bcd69e043653"
    assert parent["selected"]["rules"] == protocol["native_rules"]
    assert parent["selected"]["protocol_sha256"] == protocol["parent"]["protocol"]["sha256"]
    assert protocol["broker"] == parent["protocol"]["broker"]
    assert protocol["views"] == parent["protocol"]["views"]
    assert protocol["start"] == parent["protocol"]["start"]
    assert protocol["end"] == parent["protocol"]["end"]
    assert protocol["original_floors"] == parent["protocol"]["original_floors"]
    # Preserve every frozen source pin, including the old engine and its Rules.
    for name, digest in parent["protocol"]["sources"].items():
        assert protocol["sources"].get(name) == digest, "Frozen source omitted: " + name
    catalog = read(out / "catalog.json")
    assert catalog["schema"] == 1 and catalog["algorithm"] == ALGORITHM
    assert catalog["finite_domain"] == len(catalog["profiles"]) == 12
    assert sha(out / "catalog.json") == protocol["catalog_sha256"]
    expected = independent_catalog(protocol["native_rules"])
    actual = {profile["name"]: profile["overlay"] for profile in catalog["profiles"]}
    assert len(actual) == 12 and actual == expected, "Risk domain changed"
    off = dict(daily_budget=False, drawdown_budget=False, net_be_first=False, dd_pause_hours=0)
    assert protocol["baseline_overlay_id"] == overlay_identity(protocol["native_rules"], off)
    references = {}
    assert set(protocol["references"]) == {f"{view}-{guard}" for view in VIEWS for guard in GUARDS}
    for key, binding in protocol["references"].items():
        path = path_in_runs(binding["path"])
        assert sha(path) == binding["sha256"], key
        assert parent["audit"]["payload_hashes"][binding["path"]] == binding["sha256"], key
        if "proof_path" in binding:
            proof = path_in_runs(binding["proof_path"])
            assert sha(proof) == binding["proof_sha256"]
            record = read(proof)
            assert record["path"] == binding["path"] and record["sha256"] == binding["sha256"]
        references[key] = path
    return catalog, references


def read_cell(out, key, folder="cells"):
    assert folder in ("cells", "repeats")
    parts = key.split("-")
    assert len(parts) == 3 and len(parts[0]) == 16
    assert all(c in "0123456789abcdef" for c in parts[0])
    assert parts[1] in VIEWS and parts[2] in GUARDS
    proof_path = out / (folder + "-integrity") / (key + ".json")
    proof = read(proof_path)
    assert proof.get("origin", "new") == "new", "New overlay cells must be freshly evaluated"
    path = path_in_runs(proof["path"])
    assert path == out / folder / (key + ".json.gz")
    assert sha(path) == proof["sha256"], key
    cell = read(path)
    assert cell["profile"]["name"] == parts[0]
    assert cell["view"] == parts[1] and cell["guard"] == parts[2]
    return cell, proof, sha(proof_path)


class AuditCache:
    """Cache only identical independently checked math over identical payloads."""

    def __init__(self, out, context, enabled=True):
        self.enabled = enabled
        self.context = context
        self.identity = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
        self.root = out / "audit-cache" / self.identity
        self.index_path = self.root / "index.json"
        self.hits = 0
        if enabled and self.index_path.exists():
            index = read(self.index_path)
            assert index["context"] == context
            self.records = index["records"]
        else:
            self.records = {}

    def get(self, key, proof, proof_hash):
        path = self.root / (key + ".json")
        if not self.enabled or key not in self.records:
            return None
        assert sha(path) == self.records[key], "Audit-cache record hash drift"
        record = read(path)
        assert record["context"] == self.context
        assert record["payload_sha256"] == proof["sha256"] and record["proof_sha256"] == proof_hash
        self.hits += 1
        return record["checked"]

    def put(self, key, proof, proof_hash, checked):
        if self.enabled:
            path = self.root / (key + ".json")
            write(path, dict(context=self.context,
                payload_sha256=proof["sha256"], proof_sha256=proof_hash, checked=checked))
            self.records[key] = sha(path)
            write(self.index_path, dict(context=self.context, records=self.records))


def full_tick_and_peaks(auditor, cell):
    """Rebuild executable equity/DD and the high-water before every later entry."""
    result, cost = cell["result"], cell["result"]["costs"]
    cash = peak = minimum = 200.0
    max_dd = 0.0
    quoted = 0
    history = []
    for trade in result["ledger"]:
        born = int(trade["entry_ms"])
        closed = int(pd.Timestamp(trade["exit_time_utc"]).value // 10**6)
        direction = trade["direction"]
        factor = auditor.broker["trade_contract_size"] * trade["volume"]
        fee = cost["commission_per_lot"] * trade["volume"]
        left = int(np.searchsorted(auditor.times, born))
        first_exit = int(np.searchsorted(auditor.times, closed))
        last_exit = int(np.searchsorted(auditor.times, closed, side="right"))
        raw = auditor.tape["bid" if direction == 1 else "ask"]
        exit_quotes = raw[first_exit:last_exit] - direction * cost["extra_spread"] / 2
        if trade["reason"] == "END_OF_SAMPLE":
            assert int(auditor.times[-1]) == closed
            right = len(auditor.times)
            equal(float(exit_quotes[-1] - direction * cost["slippage"]), trade["exit"], "end fill")
        else:
            assert trade["reason"] in ("SL", "TP")
            valid = (direction * (exit_quotes - trade["target"]) >= 0 if trade["reason"] == "TP" else
                     np.isclose(exit_quotes - direction * cost["slippage"], trade["exit"], atol=1e-8, rtol=0))
            matches = np.flatnonzero(valid)
            assert len(matches), "Exit absent from source tape"
            right = first_exit + int(matches[0]) + 1
        assert right > left
        equal(cash, trade["entry_equity"], "full-tick entry cash")
        entry_peak = peak
        for cursor in range(left, right, 100_000):
            stop = min(cursor + 100_000, right)
            quote = raw[cursor:stop] - direction * cost["extra_spread"] / 2
            swap = auditor.swap_value(trade, auditor.times[cursor:stop])
            marks = cash - fee + direction * (quote - trade["entry"]) * factor + swap
            if stop == right and trade["reason"] == "TP":
                marks[-1] = cash - fee + direction * (trade["target"] - trade["entry"]) * factor + swap[-1]
            peaks = np.maximum.accumulate(np.r_[peak, marks])[1:]
            max_dd = max(max_dd, float(np.max((peaks - marks) / peaks)))
            peak = max(peak, float(marks.max()))
            minimum = min(minimum, float(marks.min()))
            quoted += len(marks)
        cash += trade["net"]
        max_dd = max(max_dd, (peak - cash) / peak)
        peak, minimum = max(peak, cash), min(minimum, cash)
        history.append(dict(entry_ms=born, exit_ms=closed, cash=cash, peak=peak, entry_peak=entry_peak))
    equal(cash, result["final_balance"], "full-tick final cash")
    equal(max_dd * 100, result["max_dd_pct"], "full-tick maximum DD")
    equal(minimum, cell["metrics"]["min_observed_equity"], "full-tick minimum equity")
    return dict(max_dd_pct=max_dd * 100, min_equity=minimum, final_cash=cash,
                held_quote_observations=quoted), history


def _flat_prefix(history, stamp):
    previous = [row for row in history if row["entry_ms"] < stamp and row["exit_ms"] <= stamp]
    assert not any(row["entry_ms"] < stamp < row["exit_ms"] for row in history), "Budget evaluated while held"
    return previous[-1] if previous else dict(cash=200.0, peak=200.0)


def _baseline(auditor, cell, stamp):
    boundary = stamp // DAY_MS * DAY_MS
    baseline = 200.0
    for trade in cell["result"]["ledger"]:
        born = int(trade["entry_ms"])
        closed = int(pd.Timestamp(trade["exit_time_utc"]).value // 10**6)
        if closed < boundary:
            baseline += trade["net"]
        elif born < boundary <= closed:
            index = int(np.searchsorted(auditor.times, boundary))
            observed = int(auditor.times[index])
            assert boundary <= observed < boundary + 1000, "Missing held-midnight proof"
            direction = trade["direction"]
            quote = float(auditor.tape["bid" if direction == 1 else "ask"][index])
            quote -= direction * cell["result"]["costs"]["extra_spread"] / 2
            if trade["reason"] == "TP" and closed == observed:
                quote = trade["target"]
            factor = auditor.broker["trade_contract_size"] * trade["volume"]
            fee = cell["result"]["costs"]["commission_per_lot"] * trade["volume"]
            baseline += direction * (quote - trade["entry"]) * factor - fee
            baseline += auditor.swap_value(trade, observed)
            break
    return baseline


def audit_budgets(auditor, cell, overlay, history):
    records = cell["result"]["overlay"]["budget_decisions"]
    state = dict(pause_started_ms=None, resume_not_before_ms=None, last_signal_ms=None,
                 last_stamp_ms=None, episodes=0, resumes=0)
    counts = Counter()
    admitted = []
    for event in records:
        assert event["state_before"] == state
        stamp, signal = event["stamp_ms"], event["signal_ms"]
        assert type(stamp) is int and type(signal) is int and 0 <= stamp - signal <= 90_000
        assert state["last_stamp_ms"] is None or stamp >= state["last_stamp_ms"]
        assert state["last_signal_ms"] is None or signal > state["last_signal_ms"]
        prefix = _flat_prefix(history, stamp)
        equal(prefix["cash"], event["equity"], "budget flat equity")
        equal(prefix["peak"], event["peak"], "budget full-tick equity peak")
        equal(_baseline(auditor, cell, stamp), event["day_start"], "budget day baseline")
        assert event["risk"] > 0 and math.isfinite(event["risk"])
        assert event["risk"] <= event["equity"] * .1 + 1e-8
        equal(event["equity"] - event["risk"], event["projected_equity"], "projected equity")
        equal(.9 * event["day_start"], event["daily_floor"], "daily floor")
        equal(.6 * event["peak"], event["drawdown_floor"], "DD floor")
        projected = Decimal(str(event["equity"])) - Decimal(str(event["risk"]))
        daily_failed = overlay["daily_budget"] and projected <= Decimal(".90") * Decimal(str(event["day_start"]))
        dd_failed = overlay["drawdown_budget"] and projected <= Decimal(".60") * Decimal(str(event["peak"]))
        reasons = []
        if daily_failed:
            reasons.append("daily_budget")
        if dd_failed:
            reasons.append("drawdown_budget")
        state["last_signal_ms"], state["last_stamp_ms"] = signal, stamp
        started = dd_failed and overlay["dd_pause_hours"] == 24 and state["pause_started_ms"] is None
        if started:
            state["pause_started_ms"] = stamp
            state["resume_not_before_ms"] = stamp + DAY_MS
            state["episodes"] += 1
        if state["resume_not_before_ms"] is not None:
            if stamp < state["resume_not_before_ms"]:
                reasons.append("dd_pause")
            elif signal < state["resume_not_before_ms"]:
                reasons.append("stale_signal")
        resumed = not reasons and state["pause_started_ms"] is not None
        if resumed:
            state["pause_started_ms"] = state["resume_not_before_ms"] = None
            state["resumes"] += 1
        assert event["reasons"] == reasons
        assert event["allowed"] is (not reasons)
        assert event["started_pause"] is bool(started) and event["resumed"] is bool(resumed)
        assert event["state_after"] == state
        counts.update(reasons)
        if not reasons:
            admitted.append((stamp, event["direction"], event["risk"]))
    ledger = cell["result"]["ledger"]
    assert len(admitted) == len(ledger), "Missing/extra budget admission event"
    for witness, trade in zip(admitted, ledger):
        assert witness[:2] == (trade["entry_ms"], trade["direction"])
        equal(witness[2], trade["risk_usd"], "admitted risk")
    assert cell["result"]["overlay"]["state"] == state
    assert cell["result"]["overlay"]["rejections"] == {
        key: counts[key] for key in ("daily_budget", "drawdown_budget", "dd_pause", "stale_signal")}
    return dict(decisions=len(records), admitted=len(admitted), episodes=state["episodes"],
                resumes=state["resumes"], ongoing_pause=state["pause_started_ms"] is not None,
                rejections=dict(counts))


def audit_net_be(auditor, cell, overlay):
    events = cell["result"]["overlay"]["be_adjustments"]
    if not overlay["net_be_first"]:
        assert events == []
        return dict(adjustments=0)
    trades = {trade["entry_ms"]: trade for trade in cell["result"]["ledger"]}
    seen = set()
    cost = cell["result"]["costs"]
    grid = Decimal(str(auditor.broker["trade_tick_size"]))
    for event in events:
        entry = event["entry_ms"]
        assert entry in trades and entry not in seen
        seen.add(entry)
        trade = trades[entry]
        direction = trade["direction"]
        stamp, signal = event["stamp_ms"], event["signal_ms"]
        assert entry < signal <= stamp <= pd.Timestamp(trade["exit_time_utc"]).value // 10**6
        assert signal % 900_000 == 0 and event["success"] is True
        assert event["direction"] == direction and trade.get("net_be_done") is True
        assert trade["stop_updates"] == 1
        factor = auditor.broker["trade_contract_size"] * trade["volume"]
        fee = cost["commission_per_lot"] * trade["volume"]
        swap = float(auditor.swap_value(trade, stamp))
        for field, value in (("entry", trade["entry"]), ("factor", factor), ("fee", fee),
                             ("exit_slippage", cost["slippage"]), ("risk_usd", trade["risk_usd"]),
                             ("accrued_swap", swap), ("target", trade["target"]),
                             ("native_trigger", trade["risk_usd"] * cell["result"]["rules"]["protect_after_r"])):
            equal(event[field], value, "BE " + field)
        raw = trade["entry"] + direction * ((fee - swap) / factor + cost["slippage"])
        rounded = float((Decimal(str(raw)) / grid).to_integral_value(
            rounding=ROUND_CEILING if direction == 1 else ROUND_FLOOR) * grid)
        equal(rounded, event["new_stop"], "net BE rounded price")
        assert direction * (event["new_stop"] - event["old_stop"]) > 0
        equal(event["old_stop"], trade["initial_stop"], "first BE previous stop")
        assert direction * (event["executable"] - event["new_stop"]) > 0
        activation = event.get("activation_stamp_ms", stamp)
        activation_net = event.get("activation_net", event["native_activation_net"])
        assert entry < activation <= stamp
        assert activation_net + 1e-8 >= event["native_trigger"], "BE trigger changed"
        # The exact event tick can share a millisecond with several tape rows.
        first = int(np.searchsorted(auditor.times, stamp))
        last = int(np.searchsorted(auditor.times, stamp, side="right"))
        quotes = auditor.tape["bid" if direction == 1 else "ask"][first:last]
        quotes = quotes - direction * cost["extra_spread"] / 2
        assert np.isclose(quotes, event["executable"], atol=1e-8, rtol=0).any()
        first = int(np.searchsorted(auditor.times, activation))
        last = int(np.searchsorted(auditor.times, activation, side="right"))
        quotes = auditor.tape["bid" if direction == 1 else "ask"][first:last]
        quoted_net = direction * (quotes - direction * cost["extra_spread"] / 2 - trade["entry"]) * factor
        quoted_net -= fee + cost["slippage"] * factor
        assert np.isclose(quoted_net, activation_net, atol=1e-8, rtol=0).any()
        net_at_stop = direction * (event["new_stop"] - direction * cost["slippage"] - trade["entry"]) * factor - fee + swap
        assert net_at_stop >= -1e-7, "BE is negative at modeled adjustment-time costs"
    for entry, trade in trades.items():
        assert bool(trade.get("net_be_done")) == (entry in seen)
        assert trade["stop_updates"] == int(entry in seen)
    return dict(adjustments=len(events), positive_swap_adjustments=sum(e["accrued_swap"] > 0 for e in events),
                negative_swap_adjustments=sum(e["accrued_swap"] < 0 for e in events))


def qualify(rows, floors):
    return all(rows[guard][view]["metrics"]["survival"] and
               rows[guard][view]["metrics"]["net_usd"] > 0 and
               rows[guard][view]["metrics"]["max_dd_pct"] <= 40
               for guard in GUARDS for view in VIEWS) and all(
        rows[guard][view]["metrics"]["net_usd"] + 1e-7 >= floors[guard][view]["net_usd"]
        for guard in GUARDS for view in ("base", "stress"))


def rank(rows):
    return (-rows["raw"]["base"]["metrics"]["net_usd"],
            -rows["raw"]["stress"]["metrics"]["net_usd"],
            max(rows[guard][view]["metrics"]["max_dd_pct"] for guard in GUARDS for view in VIEWS))


def verify(out, *, allow_partial=False, use_cache=True):
    out = Path(out).resolve()
    assert out.is_relative_to((ROOT / "runs").resolve())
    protocol = read(out / "protocol.json")
    catalog, references = validate_inputs(out, protocol)
    profiles = {profile["name"]: profile for profile in catalog["profiles"]}
    expected = {f"{name}-{view}-{guard}" for name in profiles for view in VIEWS for guard in GUARDS}
    proofs = {p.stem for p in (out / "cells-integrity").glob("*.json")}
    assert proofs <= expected, "Undeclared cells"
    if not allow_partial:
        assert proofs == expected, ("Incomplete matrix", len(proofs), len(expected))
    context = dict(protocol_sha256=sha(out / "protocol.json"), verifier_sha256=sha(Path(__file__)),
                   accounting_helper_sha256=sha(HELPER), full_tick_dd=True)
    cache = AuditCache(out, context, enabled=use_cache)
    auditor = IndependentTapeAudit(protocol, read(DATA / "manifest.json")["last_quote_utc"])
    summaries, audit_rows, payloads = {}, {}, {}
    entries = 0
    baseline = protocol["baseline_overlay_id"]
    for number, key in enumerate(sorted(proofs), 1):
        cell, proof, proof_hash = read_cell(out, key)
        name, view, guard = key.split("-")
        assert cell["profile"] == profiles[name]
        assert cell["result"]["rules"] == protocol["native_rules"]
        assert set(profiles[name]["overlay"]) == OVERLAY_KEYS
        checked = cache.get(key, proof, proof_hash)
        if checked is None:
            accounting = auditor.audit_cell(cell)
            full_tick, history = full_tick_and_peaks(auditor, cell)
            if name == baseline:
                assert "overlay" not in cell["result"]
                reference = read(references[f"{view}-{guard}"])
                assert cell["result"] == reference["result"], "Overlay-off native replay drift"
                assert cell["metrics"] == reference["metrics"]
                overlay_checked = dict(baseline_exact=True)
            else:
                result_overlay = cell["result"]["overlay"]
                assert result_overlay["version"] == 1 and result_overlay["config"] == profiles[name]["overlay"]
                overlay_checked = dict(budgets=audit_budgets(auditor, cell, profiles[name]["overlay"], history),
                                       net_be=audit_net_be(auditor, cell, profiles[name]["overlay"]))
            checked = dict(entries=accounting["entries"], metrics=cell["metrics"], risk=accounting["risk"],
                           full_tick=full_tick, overlay=overlay_checked)
            cache.put(key, proof, proof_hash, checked)
        summaries.setdefault(name, {}).setdefault(guard, {})[view] = dict(metrics=checked["metrics"], risk=checked["risk"])
        entries += checked["entries"]
        audit_rows[key] = checked
        payloads[proof["path"]] = proof["sha256"]
        print("PASS immutable risk cell", number, "/", len(proofs), key,
              "cache" if cache.hits else "full-tick", flush=True)
    if proofs != expected:
        result = dict(status="PARTIAL", coverage=len(proofs), required=len(expected),
                      protocol_sha256=context["protocol_sha256"], audited_cells=audit_rows,
                      audit_cache_hits=cache.hits, cost_status="COST_INCONCLUSIVE")
        write(out / "independent-verification-partial.json", result)
        return result
    qualified = sorted(name for name in profiles if qualify(summaries[name], protocol["original_floors"]))
    assert baseline in qualified, "Preserved baseline no longer qualifies"
    selected = min(qualified, key=lambda name: (*rank(summaries[name]), name != baseline, name))
    results = read(out / "results.json")
    assert results["selected"]["profit"] == selected
    assert sorted(results["qualified"]) == qualified
    for name in profiles:
        for guard in GUARDS:
            for view in VIEWS:
                saved = results["summaries"][name][guard][view]
                assert saved["metrics"] == summaries[name][guard][view]["metrics"]
                for field, value in saved["risk"].items():
                    equal(value, summaries[name][guard][view]["risk"][field], "summary risk " + field)
    repeat_keys = {f"{selected}-{view}-{guard}" for view in VIEWS for guard in GUARDS}
    assert {p.stem for p in (out / "repeats-integrity").glob("*.json")} == repeat_keys
    for key in sorted(repeat_keys):
        repeat, proof, _ = read_cell(out, key, folder="repeats")
        original, _, _ = read_cell(out, key)
        assert repeat["result"] == original["result"], "Fresh repeat changed ledger/equity/policy state"
        assert repeat["metrics"] == original["metrics"]
        payloads[proof["path"]] = proof["sha256"]
    completion = read(out / "COMPLETE.json")
    assert completion["status"] == "MATRIX_EVALUATED_AWAITING_AUDIT"
    for name, digest in completion.get("artifacts", {}).items():
        assert sha(out / name) == digest, name
    result = dict(status="PASS", economic_replays=0, finite_domain=12, cells=72,
                  entries=entries, fresh_repeats=6, independent_full_tick_dd_cells=72,
                  selected=dict(profit=selected), qualified=qualified,
                  cost_status="COST_INCONCLUSIVE", holdout=False,
                  protocol_sha256=context["protocol_sha256"], source_sha256=context["verifier_sha256"],
                  helper_sha256=context["accounting_helper_sha256"], completion_sha256=sha(out / "COMPLETE.json"),
                  audit_cache_hits=cache.hits, audited_cells=audit_rows, payload_hashes=payloads,
                  scope="Immutable72-path accounting,source-tick DD/HWM,budget/pause/NetBE invariants and6fresh repeats; reused history,no broker/economic qualification")
    write(out / "independent-verification.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()
    result = verify(args.out, allow_partial=args.allow_partial, use_cache=not args.no_cache)
    print(json.dumps({key: value for key, value in result.items() if key != "audited_cells"}, indent=2))


if __name__ == "__main__":
    main()
