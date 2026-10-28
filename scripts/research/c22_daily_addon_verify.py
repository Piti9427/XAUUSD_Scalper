"""Independent causal signal,capacity,daily MTM and full-tick joint audit.

Never invokes the replay or the producer's selector/daily/attribution functions.
"""

import argparse
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import gzip
import json
from pathlib import Path
import statistics

import numpy as np
import pandas as pd

from scripts.research.c22_learning_verify import (
    DATA,
    ROOT,
    GUARDS,
    VIEWS,
    IndependentTapeAudit,
    equal,
    read,
    sha,
)
from scripts.research.c22_risk_verify import full_tick_and_peaks, qualify, rank, write
from scripts.research.c22_frequency_adapter import prepare
from scripts.research.c22_frequency_data import load_bars
from scripts.research.c22_performance_campaign import SEED

BASE = "26b8bcd69e043653"
JOINT = "d6f493f5f0dbf8b7"


def _ema(values, span):
    output = []
    average = None
    count = 0
    alpha = 2 / (span + 1)
    for value in values:
        count += 1
        average = (
            float(value)
            if average is None
            else average
            if average == value
            else (1 - alpha) * average + alpha * float(value)
        )
        output.append(average if count >= span else float("nan"))
    return output


def independent_selector(bars, native, enabled):
    """Explicit prior48 slices,recursive EMA and published H4 chronology."""
    closes = bars.close.to_numpy()
    average = _ema(closes, 50)
    buckets = bars.close.resample("4h", origin="start_day", label="left", closed="left").agg(
        ["last", "count"]
    )
    current = None
    complete = 0
    published = {}
    alpha = 2 / 201
    for stamp, row in buckets.iterrows():
        value = float("nan")
        if row["count"] == 16:
            complete += 1
            current = (
                float(row["last"])
                if current is None
                else current
                if current == row["last"]
                else (1 - alpha) * current + alpha * float(row["last"])
            )
            if complete >= 200:
                value = current
        published[int((stamp + pd.Timedelta(hours=4)).value // 10**6)] = value
    records = []
    highs = bars.high.to_numpy()
    lows = bars.low.to_numpy()
    for index, stamp in enumerate(bars.index):
        decision = stamp + pd.Timedelta(minutes=15)
        macro = published.get(int(decision.floor("4h").value // 10**6), float("nan"))
        high = float(max(highs[index - 48 : index])) if index >= 48 else float("nan")
        low = float(min(lows[index - 48 : index])) if index >= 48 else float("nan")
        addon = bool(
            index >= 50
            and closes[index] > high
            and closes[index] > average[index]
            and average[index] > average[index - 4]
            and closes[index] > macro
        )
        core = int(native.direction.iloc[index])
        direction = core if core else 1 if addon and enabled else 0
        origin = "native" if core else "addon" if direction else "none"
        records.append(
            dict(
                signal_ms=int(decision.value // 10**6),
                direction=direction,
                native_direction=core,
                addon_eligible=addon,
                origin=origin,
                range_high=float(native.hh.iloc[index]) if origin != "addon" else high,
                range_low=float(native.ll.iloc[index]) if origin != "addon" else low,
                atr=float(native.atr.iloc[index]),
            )
        )
    return records


def audit_daily(auditor, result, report, entries):
    """Sum per-trade boundary vectors; independently verify daily metadata."""
    start = pd.Timestamp(result["start_utc"])
    end = min(
        pd.Timestamp(result["end_exclusive_utc"]),
        pd.Timestamp(int(auditor.times[-1]) + 1, unit="ms", tz="UTC"),
    )
    bounds = (
        [start]
        + [
            x
            for x in pd.date_range(
                start.normalize() + pd.Timedelta(days=1), end.normalize(), freq="D"
            )
            if x < end
        ]
        + [end]
    )
    stamps = np.array([x.value // 10**6 for x in bounds[1:]], dtype=np.int64)
    equity = np.full(len(stamps), 200.0)
    held_count = np.zeros(len(stamps), dtype=int)
    quote_indices = np.searchsorted(auditor.times, stamps, side="left") - 1
    costs = result["costs"]
    origins = {e["entry_ms"]: e["origin"] for e in entries}
    for trade in result["ledger"]:
        exit_ms = int(pd.Timestamp(trade["exit_time_utc"]).value // 10**6)
        equity[exit_ms < stamps] += trade["net"]
        held = (trade["entry_ms"] < stamps) & (stamps <= exit_ms)
        held_count[held] += 1
        if not held.any():
            continue
        indices = quote_indices[held]
        assert (indices >= 0).all()
        assert (auditor.times[indices] >= trade["entry_ms"]).all()
        side = "bid" if trade["direction"] == 1 else "ask"
        executable = auditor.tape[side][indices] - trade["direction"] * costs["extra_spread"] / 2
        factor = auditor.broker["trade_contract_size"] * trade["volume"]
        marks = trade["direction"] * (executable - trade["entry"]) * factor
        marks -= costs["commission_per_lot"] * trade["volume"]
        marks += auditor.swap_value(trade, stamps[held] - 1)
        equity[held] += marks
    assert (held_count <= 1).all(), "daily capacity overlap"
    assert len(report["days"]) == len(equity)
    prior = 200.0
    prior_verified = True
    complete = []
    verified = []
    no_entry = held_no_entry = unverified = partial = 0
    for index, row in enumerate(report["days"]):
        left, right = bounds[index : index + 2]
        assert row["start_utc"] == left.isoformat() and row["end_utc"] == right.isoformat()
        equal(prior, row["start_equity_usd"], "daily opening equity")
        equal(float(equity[index]), row["end_equity_usd"], "daily closing equity")
        net = float(equity[index] - prior)
        equal(net, row["net_usd"], "daily MTM delta")
        if held_count[index]:
            quote = int(auditor.times[quote_indices[index]])
            age = (int(stamps[index]) - 1 - quote) / 1000
            recent = 0 <= age <= 60
            assert row["end_quote_utc"] == pd.Timestamp(quote, unit="ms", tz="UTC").isoformat()
            equal(age, row["end_quote_age_seconds"], "daily quote age")
            assert row["end_coverage"] == (
                "RECENT_ACTUAL_QUOTE_MODEL" if recent else "STALE_ACTUAL_QUOTE_MODEL"
            )
        else:
            recent = True
            assert row["end_quote_utc"] is None and row["end_coverage"] == "FLAT_REALIZED_CASH"
        assert row["start_price_verified"] is prior_verified and row["end_price_verified"] is bool(
            recent
        )
        born = [
            t
            for t in result["ledger"]
            if left.value // 10**6 <= t["entry_ms"] < right.value // 10**6
        ]
        closes = [t for t in result["ledger"] if left <= pd.Timestamp(t["exit_time_utc"]) < right]
        assert row["entries"] == len(born) and row["closes"] == len(closes)
        assert row["native_entries"] == sum(origins[t["entry_ms"]] == "native" for t in born)
        assert row["addon_entries"] == sum(origins[t["entry_ms"]] == "addon" for t in born)
        assert row["no_entry_day"] is (len(born) == 0)
        held_during = any(
            t["entry_ms"] < right.value // 10**6 and pd.Timestamp(t["exit_time_utc"]) >= left
            for t in result["ledger"]
        )
        assert row["held_during_day"] is held_during
        full = left == left.normalize() and right - left == pd.Timedelta(days=1)
        assert row["full_calendar_day"] is bool(full)
        partial += not full
        if full:
            complete.append(net)
            no_entry += not bool(born)
            held_no_entry += not bool(born) and held_during
            if prior_verified and recent:
                verified.append(net)
            else:
                unverified += 1
        prior = float(equity[index])
        prior_verified = bool(recent)
    equal(prior, result["final_balance"], "daily final account")
    equal(report["net_reconciliation_usd"], result["net_usd"], "daily telescoping net")
    assert report["partial_days"] == partial and report["complete_no_entry_days"] == no_entry
    assert (
        report["complete_held_no_entry_days"] == held_no_entry
        and report["unverified_complete_days"] == unverified
    )
    for key, values in [("modeled_complete", complete), ("verified_complete", verified)]:
        d = report["distribution"][key]
        assert d["count"] == len(values) and d["positive"] == sum(x > 1e-7 for x in values)
        assert d["negative"] == sum(x < -1e-7 for x in values) and d["flat"] == sum(
            abs(x) <= 1e-7 for x in values
        )
        for field, value in [
            ("mean_usd", statistics.mean(values) if values else None),
            ("median_usd", statistics.median(values) if values else None),
            ("worst_usd", min(values) if values else None),
            ("best_usd", max(values) if values else None),
        ]:
            if value is None:
                assert d[field] is None
            else:
                equal(value, d[field], "daily distribution " + field)
    assert (
        report["qualification"] == "COST_INCONCLUSIVE"
        and report["daily_profit_guaranteed"] is False
    )
    return dict(
        days=len(equity),
        complete_days=len(complete),
        verified_complete_days=len(verified),
        final_equity=prior,
        unverified_complete_days=unverified,
        no_entry_complete_days=no_entry,
    )


def audit_selection_and_capacity(auditor, cell, signals, control):
    result = cell["result"]
    start = int(pd.Timestamp(result["start_utc"]).value // 10**6)
    end = int(pd.Timestamp(result["end_exclusive_utc"]).value // 10**6)
    selected = [
        s
        for s in signals
        if s["direction"]
        and start <= s["signal_ms"] < end
        and s["signal_ms"] <= int(auditor.times[-1])
    ]
    witnesses = cell["signal_witnesses"]
    assert len(witnesses) == len(selected)
    for expected, saved in zip(selected, witnesses):
        for key in saved:
            if key in ("range_high", "range_low"):
                equal(expected[key], saved[key], "signal " + key)
            else:
                assert expected[key] == saved[key], key
    contexts = result["context_events"]
    assert len(contexts) == len(selected)
    event_by_entry = {}
    event_by_signal = {}
    for expected, event in zip(selected, contexts):
        stamp = int(pd.Timestamp(event["signal_close_utc"]).value // 10**6)
        assert expected["signal_ms"] == stamp and event["direction"] == expected["direction"]
        observed = int(pd.Timestamp(event["time_utc"]).value // 10**6)
        assert observed >= stamp
        event_by_signal[(stamp, event["direction"])] = (event, expected)
        if event["reason"] == "admitted":
            assert 0 <= observed - stamp <= 90000
            event_by_entry[(observed, event["direction"])] = (event, expected)
    entries = cell["attribution"]["entries"]
    assert len(entries) == len(result["ledger"]) == len(event_by_entry)
    seen = set()
    previous = None
    contribution = {"native": 0.0, "addon": 0.0}
    signatures = set()
    grid = Decimal(str(auditor.broker["trade_tick_size"]))
    for trade, saved in zip(result["ledger"], entries):
        key = (trade["entry_ms"], trade["direction"])
        event, signal = event_by_entry[key]
        assert key not in seen
        seen.add(key)
        exit_ms = int(pd.Timestamp(trade["exit_time_utc"]).value // 10**6)
        assert previous is None or trade["entry_ms"] >= previous
        previous = exit_ms
        assert saved == dict(
            entry_ms=key[0],
            exit_ms=exit_ms,
            direction=key[1],
            signal_ms=signal["signal_ms"],
            origin=signal["origin"],
            net_usd=trade["net"],
        )
        contribution[signal["origin"]] += trade["net"]
        if signal["origin"] == "native":
            signatures.add((signal["signal_ms"], trade["direction"]))
        index = int(np.searchsorted(auditor.times, signal["signal_ms"]))
        assert int(auditor.times[index]) == trade["entry_ms"]
        raw = float(auditor.tape["ask" if trade["direction"] == 1 else "bid"][index])
        raw += trade["direction"] * (
            result["costs"]["extra_spread"] / 2 + result["costs"]["slippage"]
        )
        equal(raw, trade["entry"], "source first quote entry")
        stop = trade["entry"] - trade["direction"] * 2.5 * signal["atr"]
        stop = float(
            (Decimal(str(stop)) / grid).to_integral_value(
                rounding=ROUND_FLOOR if trade["direction"] == 1 else ROUND_CEILING
            )
            * grid
        )
        equal(stop, trade["initial_stop"], "native ATR geometry")
        rr = 3.0 if trade["direction"] == 1 else 1.35
        target = trade["entry"] + trade["direction"] * abs(trade["entry"] - stop) * rr
        target = float(
            (Decimal(str(target)) / grid).to_integral_value(
                rounding=ROUND_FLOOR if trade["direction"] == 1 else ROUND_CEILING
            )
            * grid
        )
        equal(target, trade["target"], "native target geometry")
    for key, value in contribution.items():
        equal(value, cell["attribution"]["closed_net_by_source"][key], "origin net")
    reference = {
        (int(pd.Timestamp(e["signal_close_utc"]).value // 10**6), e["direction"])
        for e in control["context_events"]
        if e["reason"] == "admitted"
    }
    expected_missing = reference - signatures
    saved_missing = cell["attribution"]["missed_control_native"]
    assert {
        (int(pd.Timestamp(x["signal_close_utc"]).value // 10**6), x["direction"])
        for x in saved_missing
    } == expected_missing
    known = ambiguous = 0
    for saved in saved_missing:
        key = (int(pd.Timestamp(saved["signal_close_utc"]).value // 10**6), saved["direction"])
        event, _ = event_by_signal[key]
        stamp = int(pd.Timestamp(event["time_utc"]).value // 10**6)
        holders = [x for x in entries if x["entry_ms"] < stamp < x["exit_ms"]]
        boundaries = [x for x in entries if stamp in (x["entry_ms"], x["exit_ms"])]
        holder = (
            holders[0]["origin"]
            if len(holders) == 1
            else "AMBIGUOUS_SAME_MS_BOUNDARY"
            if boundaries
            else "NO_STRICT_HELD_WITNESS"
        )
        assert saved["joint_reason"] == event["reason"] and saved["holder"] == holder
        known += event["reason"] == "busy" and holder == "addon"
        ambiguous += event["reason"] == "busy" and holder == "AMBIGUOUS_SAME_MS_BOUNDARY"
    assert cell["attribution"]["known_busy_with_addon"] == known
    assert cell["attribution"]["ambiguous_busy_boundaries"] == ambiguous
    assert cell["attribution"]["counterfactual_pnl_added"] is False
    extra = {(x["signal_ms"], x["direction"]) for x in cell["attribution"]["extra_joint_native"]}
    assert extra == signatures - reference
    return dict(
        selected_signals=len(selected),
        entries=len(entries),
        missed_control_native=len(expected_missing),
        extra_joint_native=len(extra),
        known_busy_with_addon=known,
        capacity="ONE_SHARED_POSITION",
    )


def _cell(out, key, folder="cells"):
    proof = read(out / (folder + "-integrity") / (key + ".json"))
    path = (ROOT / proof["path"]).resolve()
    assert path == (out / folder / (key + ".json.gz")).resolve() and sha(path) == proof["sha256"]
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    assert key == f"{value['profile']['name']}-{value['view']}-{value['guard']}"
    return value, proof


def verify(out):
    out = Path(out).resolve()
    assert out.is_relative_to(ROOT / "runs")
    p = read(out / "protocol.json")
    complete = read(out / "COMPLETE.json")
    assert (
        p["algorithm"] == "c22_joint_buy48_v1"
        and p["holdout"] is False
        and p["execution_authorized"] is False
    )
    for name, digest in p["sources"].items():
        assert sha(ROOT / name) == sha(out / "source_snapshot" / name) == digest, name
    assert sha(DATA / "manifest.json") == p["input_manifest_sha256"]
    for name, digest in p["input_hashes"].items():
        assert sha(DATA / name) == digest, name
    for item in p["parent"].values():
        assert sha(ROOT / item["path"]) == item["sha256"]
    parent = read(ROOT / p["parent"]["protocol"]["path"])
    pre = read(ROOT / p["parent"]["prereg"]["path"])
    assert p["catalog_sha256"] == pre["catalog_sha256"]
    for key in ("broker", "views", "start", "end", "original_floors", "native_rules", "references"):
        assert p[key] == parent[key], key
    for name, digest in parent["sources"].items():
        assert p["sources"].get(name) == digest
    for name, digest in complete["artifacts"].items():
        assert sha(out / name) == digest, name
    assert sha(out / "catalog.json") == p["catalog_sha256"]
    profiles = {x["name"]: x for x in read(out / "catalog.json")["profiles"]}
    assert set(profiles) == {BASE, JOINT}
    expected = {f"{n}-{v}-{g}" for n in profiles for v in VIEWS for g in GUARDS}
    assert {x.stem for x in (out / "cells-integrity").glob("*.json")} == expected
    bars = load_bars(DATA / "bars.csv")
    native, _ = prepare(bars, read(SEED))
    selectors = {
        name: independent_selector(bars, native, profile["addon"])
        for name, profile in profiles.items()
    }
    auditor = IndependentTapeAudit(p, read(DATA / "manifest.json")["last_quote_utc"])
    rows = {}
    checks = {}
    payloads = {}
    for key in sorted(expected):
        c, proof = _cell(out, key)
        name, view, guard = key.split("-")
        assert c["profile"] == profiles[name] and c["result"]["rules"] == p["native_rules"]
        reference = p["references"][view + "-" + guard]
        assert sha(ROOT / reference["path"]) == reference["sha256"]
        control = read(ROOT / reference["path"])["result"]
        accounting = auditor.audit_cell(c)
        ticks, _ = full_tick_and_peaks(auditor, c)
        if name == BASE:
            assert c["result"] == control, "native parity"
        capacity = audit_selection_and_capacity(auditor, c, selectors[name], control)
        daily = audit_daily(auditor, c["result"], c["daily"], c["attribution"]["entries"])
        rows.setdefault(name, {}).setdefault(guard, {})[view] = {
            "metrics": c["metrics"],
            "risk": accounting["risk"],
        }
        checks[key] = dict(accounting=accounting, full_tick=ticks, capacity=capacity, daily=daily)
        payloads[proof["path"]] = proof["sha256"]
        print("PASS independent joint cell", len(checks), "/12", key, flush=True)
    eligible = sorted(n for n in profiles if qualify(rows[n], p["original_floors"]))
    assert BASE in eligible
    selected = min(eligible, key=lambda n: (*rank(rows[n]), n != BASE))
    saved = read(out / "results.json")
    assert saved["selected"] == selected and saved["qualified"] == eligible
    for name in profiles:
        for guard in GUARDS:
            for view in VIEWS:
                summary = saved["summaries"][name][guard][view]
                assert summary["metrics"] == rows[name][guard][view]["metrics"]
                for key, value in summary["risk"].items():
                    equal(value, rows[name][guard][view]["risk"][key], "summary risk")
    repeat_keys = {f"{selected}-{v}-{g}" for v in VIEWS for g in GUARDS}
    assert {x.stem for x in (out / "repeats-integrity").glob("*.json")} == repeat_keys
    for key in repeat_keys:
        fresh, proof = _cell(out, key, "repeats")
        original, _ = _cell(out, key)
        assert all(
            fresh[k] == original[k]
            for k in (
                "result",
                "metrics",
                "diagnostics",
                "summary",
                "daily",
                "attribution",
                "signal_witnesses",
            )
        )
        payloads[proof["path"]] = proof["sha256"]
    all_nets = all(
        rows[JOINT][g][v]["metrics"]["net_usd"] + 1e-7 >= rows[BASE][g][v]["metrics"]["net_usd"]
        for g in GUARDS
        for v in VIEWS
    )
    improvement = (
        JOINT in eligible
        and all_nets
        and rows[JOINT]["raw"]["base"]["metrics"]["net_usd"]
        > rows[BASE]["raw"]["base"]["metrics"]["net_usd"] + 1e-7
    )
    value = dict(
        status="PASS",
        primary_cells=12,
        fresh_repeats=6,
        full_tick_dd_cells=12,
        selected_profit=selected,
        qualified=eligible,
        strict_profit_improvement=improvement,
        retain_native=not improvement,
        daily_profit_guaranteed=False,
        cost_status="COST_INCONCLUSIVE",
        holdout=False,
        protocol_sha256=sha(out / "protocol.json"),
        source_sha256=sha(Path(__file__)),
        completion_sha256=sha(out / "COMPLETE.json"),
        audited_cells=checks,
        payload_hashes=payloads,
    )
    write(out / "independent-verification.json", value)
    write(
        out / "FINAL.json",
        dict(
            status="VERIFIED_COMPLETE",
            paths=12,
            fresh_repeats=6,
            full_tick_dd_paths=12,
            audit_sha256=sha(out / "independent-verification.json"),
            selected_profit=selected,
            strict_profit_improvement=improvement,
            retain_native=not improvement,
            demo_changed=False,
            cost_status="COST_INCONCLUSIVE",
            holdout=False,
        ),
    )
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    verify(args.out)
