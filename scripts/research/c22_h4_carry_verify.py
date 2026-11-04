"""Independent causal H4, admission, immutable-cell and source-tick audit.

No producer carry/selector call, replay, broker, or economic evaluation occurs.
Frozen accounting helpers are reused without modifying their equations.
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

from scripts.research.c22_frequency_adapter import prepare
from scripts.research.c22_frequency_data import load_bars
from scripts.research.c22_learning_verify import (
    DATA, GUARDS, ROOT, VIEWS, IndependentTapeAudit, equal, loss, read, sha,
)
from scripts.research.c22_performance_campaign import SEED
from scripts.research.c22_risk_verify import (
    _baseline, full_tick_and_peaks, path_in_runs, qualify, rank, read_cell, write,
)

BASE = "26b8bcd69e043653"
ALGORITHM = "c22_strict_h4_carry_v1"
PARENT_SHA = "a104009031a88558cc07d21a6beb485f79d3aa17e4d0046217c55122f670700b"
TEST = "tests/research/test_c22_h4_carry_verify.py"
SELF = "scripts/research/c22_h4_carry_verify.py"
M15 = 900_000
H4 = 16 * M15
POLICY = dict(
    schema=1, source="strict_16_complete_M15_per_UTC_calendar_H4", ema_span=200,
    ema_adjust=False, ema_min_periods=200, publication="H4_open_plus_4h",
    decision="M15_open_plus_15min", max_age_hours_exclusive=8,
    age_clock="elapsed_UTC_no_session_subtraction",
    missing_bucket="no_new_close_no_EMA_update_no_age_reset",
    unknown_session="cause_unknown_retained_carry_permitted_only_inside_bound",
    direction="native_raw_direction_before_macro_mask",
)


def _ema(values, span):
    average = None
    output = []
    alpha = 2 / (span + 1)
    for number, value in enumerate(values, 1):
        average = float(value) if average is None else (
            average if average == value else (1 - alpha) * average + alpha * float(value)
        )
        output.append(average if number >= span else float("nan"))
    return np.asarray(output)


def independent_h4(bars, *, span=200):
    """Rebuild actual 16-slot observations and publication-time EMA recursively."""
    index = bars.index
    assert span >= 1 and index.tz is not None and str(index.tz) == "UTC"
    assert index.is_monotonic_increasing and not index.has_duplicates
    stamps = index.as_unit("ms").asi8
    assert len(stamps) and not (stamps % M15).any(), "unaligned M15"
    assert np.isfinite(bars[["open", "high", "low", "close"]].to_numpy()).all()
    buckets = {}
    for number, stamp in enumerate(stamps):
        buckets.setdefault(int(stamp // H4 * H4), []).append(number)
    strict, finite = {}, []
    average = None
    accepted = 0
    alpha = 2 / (span + 1)
    for opening in range(int(stamps[0] // H4 * H4), int(stamps[-1] // H4 * H4) + H4, H4):
        members = buckets.get(opening, [])
        complete = len(members) == 16 and np.array_equal(
            stamps[members], np.arange(opening, opening + H4, M15)
        )
        value = float("nan")
        if complete:
            close = float(bars.close.iloc[members[-1]])
            average = close if average is None else (
                average if average == close else (1 - alpha) * average + alpha * close
            )
            accepted += 1
            if accepted >= span:
                value = average
                finite.append((opening + H4, value))
        strict[opening + H4] = value
    rows = []
    cursor = -1
    for stamp in stamps:
        decision = int(stamp) + M15
        while cursor + 1 < len(finite) and finite[cursor + 1][0] <= decision:
            cursor += 1
        source, value = finite[cursor] if cursor >= 0 else (None, None)
        age = (decision - source) / 3_600_000 if source is not None else None
        available = age is not None and 0 <= age < 8
        carried = available and not np.isfinite(strict.get(decision // H4 * H4, np.nan))
        rows.append(dict(
            signal_ms=decision, source_end_utc=None if source is None else
            pd.Timestamp(source, unit="ms", tz="UTC").isoformat(), age_hours=age,
            macro_ema=value if available else None, carried=bool(carried),
            status="CARRIED_CAUSE_UNKNOWN" if carried else "CURRENT_STRICT_H4" if available
            else "WARMUP" if source is None else "EXPIRED",
            strict_ema=strict.get(decision // H4 * H4, np.nan),
        ))
    return rows


def independent_raw(bars, seed):
    """Rebuild pinned RSI cross BUY / prior-range SELL before H4 masking."""
    assert seed["strategy"] == "reward156" and seed["formula"] == "archived"
    assert seed["entry_session"] == "all" and seed["macro_span"] == 200
    assert seed["buy_ema"] == seed["sell_ema"] == 50
    assert seed["rsi_period"] == 7 and seed["rsi_threshold"] == 30
    assert seed["sell_lookback"] == 48
    close = bars.close
    average = pd.Series(_ema(close, 50), index=bars.index)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(7).mean()
    debit = (-delta.clip(upper=0)).rolling(7).mean()
    rsi = (100 - 100 / (1 + gain / debit)).mask((gain == 0) & (debit == 0), 50)
    buy = ((rsi.shift(1) < 30) & (rsi >= 30) & (delta > 0)
           & (close > average) & (average > average.shift(4)))
    low = bars.low.rolling(48).min().shift(1)
    high = bars.high.rolling(48).max().shift(1)
    sell = (close < low) & (close < average) & (average < average.shift(4))
    raw = pd.Series(np.select([sell, buy], [-1, 1], 0), index=bars.index)
    high, low = high.mask(raw == 1, close), low.mask(raw == 1, close)
    return raw, high, low


def reconstruct(bars, native, seed):
    raw, high, low = independent_raw(bars, seed)
    assert bars.index.equals(native.index)
    assert np.array_equal(raw.to_numpy(), native.raw_direction.to_numpy()), "raw direction drift"
    np.testing.assert_allclose(high, native.hh, atol=1e-10, rtol=0, equal_nan=True)
    np.testing.assert_allclose(low, native.ll, atol=1e-10, rtol=0, equal_nan=True)
    rows = independent_h4(bars)
    for index, row in enumerate(rows):
        direction = int(raw.iloc[index])
        close = float(bars.close.iloc[index])
        strict = row.pop("strict_ema")
        native_direction = direction if direction * (close - strict) > 0 else 0
        macro = row["macro_ema"]
        candidate = direction if macro is not None and direction * (close - macro) > 0 else 0
        assert native_direction == int(native.direction.iloc[index]), "native macro drift"
        row.update(raw_direction=direction, native_direction=native_direction,
                   candidate_direction=candidate, atr=float(native.atr.iloc[index]),
                   range_high=float(high.iloc[index]), range_low=float(low.iloc[index]))
    return rows


def audit_context(cell, signals):
    """Compare every raw setup witness; omitted or forged context fails closed."""
    if not cell["profile"]["carry"]:
        assert cell["h4_context"] == []
        return dict(witnesses=0)
    expected = [s for s in signals if s["raw_direction"]]
    assert len(cell["h4_context"]) == len(expected), "missing H4 witness"
    for saved, row in zip(cell["h4_context"], expected):
        want = {key: row[key] for key in (
            "source_end_utc", "age_hours", "carried", "status", "macro_ema",
            "raw_direction", "native_direction", "candidate_direction",
        )}
        want["signal_close_utc"] = pd.Timestamp(row["signal_ms"], unit="ms", tz="UTC").isoformat()
        assert set(saved) == set(want), "H4 witness schema"
        for key, value in want.items():
            if key in ("macro_ema", "age_hours") and value is not None:
                equal(saved[key], value, "H4 " + key)
            else:
                assert saved[key] == value, ("H4 " + key, saved[key], value)
    return dict(witnesses=len(expected), statuses=dict(Counter(s["status"] for s in expected)))


def _exit_index(auditor, trade, cost):
    closed = int(pd.Timestamp(trade["exit_time_utc"]).value // 10**6)
    if trade["reason"] == "END_OF_SAMPLE":
        assert closed == int(auditor.times[-1])
        return len(auditor.times) - 1
    assert trade["reason"] in ("SL", "TP"), "unsupported exit proof"
    left = int(np.searchsorted(auditor.times, closed))
    right = int(np.searchsorted(auditor.times, closed, side="right"))
    direction = trade["direction"]
    quotes = auditor.tape["bid" if direction == 1 else "ask"][left:right]
    quotes = quotes - direction * cost["extra_spread"] / 2
    valid = direction * (quotes - trade["target"]) >= 0 if trade["reason"] == "TP" else (
        np.isclose(quotes - direction * cost["slippage"], trade["exit"], atol=1e-8, rtol=0)
    )
    matches = np.flatnonzero(valid)
    assert len(matches), "exit source quote missing"
    return left + int(matches[0])


def _geometry(signal, direction, bid, ask, broker, rules, costs, cash):
    """Independent fixed-lot gate geometry; frozen helper owns economic accounting."""
    grid = Decimal(str(broker["trade_tick_size"]))
    def rounded(value):
        return float((Decimal(str(value)) / grid).to_integral_value(
            rounding=ROUND_FLOOR if direction == 1 else ROUND_CEILING) * grid)
    entry = float(ask if direction == 1 else bid) + direction * costs["slippage"]
    stop_atr = rules["buy_stop_atr"] if direction == 1 else rules["stop_atr"]
    stop = rounded(entry - direction * signal["atr"] * stop_atr)
    executable = bid if direction == 1 else ask
    if not np.isfinite(stop) or direction * (executable - stop) <= 0:
        return "invalid_stop", None
    rr = rules["buy_target_rr"] if direction == 1 else rules["target_rr"]
    target = rounded(entry + direction * abs(entry - stop) * rr)
    factor = broker["trade_contract_size"] * .01
    fee = costs["commission_per_lot"] * .01
    risk = (abs(entry - stop) + costs["slippage"]) * factor + fee
    reason = "risk_cap" if risk > cash * rules["risk_cap"] else "margin" if (
        cash - fee <= entry * factor / broker["leverage"]) else "admitted"
    return reason, dict(entry=entry, initial_stop=stop, target=target, risk_usd=risk)


def audit_admissions(auditor, cell, signals):
    """Reconstruct causal first-quote capacity/cooldown/daily/risk decisions."""
    result, guard = cell["result"], cell["guard"]
    rules, costs, trades = result["rules"], result["costs"], result["ledger"]
    assert "overlay" not in result
    assert rules["entry_mode"] == "immediate" and rules["entry_guard"] == "off"
    assert rules["reset_after_exit"] is False and rules["session_mode"] == "all"
    assert not rules["min_depth_atr"] and not rules["buy_pause_drawdown"]
    assert rules["risk_mode"] == "static" and rules["sizing_mode"] == "fixed"
    assert rules["stop_mode"] == "atr" and rules["buy_stop_mode"] is None
    assert rules["buy_risk_cap"] is None and rules["buy_sizing_mode"] is None
    start = int(pd.Timestamp(result["start_utc"]).value // 10**6)
    end = int(pd.Timestamp(result["end_exclusive_utc"]).value // 10**6)
    field = "candidate_direction" if cell["profile"]["carry"] else "native_direction"
    selected = [s for s in signals if s[field] and start <= s["signal_ms"] < end
                and s["signal_ms"] <= int(auditor.times[-1])]
    events = result["context_events"]
    assert len(events) == len(selected), "missing/extra signal context event"
    # Forced sample-end liquidation occurs after all decisions, even when the
    # final quote shares a decision timestamp.
    ends = [len(auditor.times) if t["reason"] == "END_OF_SAMPLE" else _exit_index(auditor, t, costs) for t in trades]
    admitted, checked, processed = {}, [], []
    counts = Counter()
    for signal, event in zip(selected, events):
        direction, stamp = signal[field], signal["signal_ms"]
        index = int(np.searchsorted(auditor.times, stamp))
        observed = int(auditor.times[index])
        assert event["signal_close_utc"] == pd.Timestamp(stamp, unit="ms", tz="UTC").isoformat()
        assert event["time_utc"] == pd.Timestamp(observed, unit="ms", tz="UTC").isoformat()
        assert event["direction"] == direction
        previous = [trades[n] for n in processed if ends[n] <= index]
        held = [trades[n] for n in processed if ends[n] > index]
        assert len(held) <= 1, "capacity overlap"
        cash = 200.0 + sum(t["net"] for t in previous)
        day = observed // 86_400_000
        losses = [t for t in previous if loss(t["net"], guard)]
        cooldown = max([0] + [ends[n] for n, t in enumerate(trades) if t in losses])
        cooldown_ms = int(auditor.times[cooldown]) + rules["cooldown_bars"] * M15 if losses else 0
        daily_losses = sum(int(pd.Timestamp(t["exit_time_utc"]).value // 10**6) // 86_400_000 == day
                           for t in losses)
        geometry = None
        if observed - stamp > 90_000:
            reason = "late_quote"
        elif held:
            reason = "busy"
        elif observed < cooldown_ms:
            reason = "cooldown"
        elif daily_losses >= rules["max_daily_losses"]:
            reason = "daily_loss_count"
        else:
            try:
                baseline = _baseline(auditor, cell, observed)
            except AssertionError as exc:
                if "Missing held-midnight proof" not in str(exc):
                    raise
                baseline = None
            if baseline is None:
                reason = "day_start_unknown"
            elif cash <= 0:
                reason = "bankrupt"
            elif baseline - cash >= baseline * rules["daily_loss_limit"]:
                reason = "daily_loss"
            else:
                assert np.isfinite([signal["atr"], signal["range_high"], signal["range_low"]]).all()
                bid = float(auditor.tape["bid"][index]) - costs["extra_spread"] / 2
                ask = float(auditor.tape["ask"][index]) + costs["extra_spread"] / 2
                reason, geometry = _geometry(signal, direction, bid, ask, auditor.broker, rules, costs, cash)
        assert event["reason"] == reason, ("causal admission reason", stamp, event["reason"], reason)
        identity = (stamp, direction)
        assert identity not in {x["identity"] for x in checked}, "duplicate signal"
        checked.append(dict(identity=identity, reason=reason, observed_ms=observed,
                            holder_entry_ms=held[0]["entry_ms"] if held else None,
                            position_open=bool(held)))
        counts[reason] += 1
        if reason == "admitted":
            key = (observed, direction)
            assert key not in admitted, "duplicate admission"
            admitted[key] = (signal, geometry)
            matches = [n for n, t in enumerate(trades) if (t["entry_ms"], t["direction"]) == key]
            assert len(matches) == 1, "admission ledger identity"
            processed.append(matches[0])
    assert len(admitted) == len(trades), "missing/extra ledger admission"
    for trade in trades:
        signal, geometry = admitted[(trade["entry_ms"], trade["direction"])]
        for key, value in geometry.items():
            equal(trade[key], value, "entry " + key)
        equal(trade["range_high"], signal["range_high"], "entry range high")
        equal(trade["range_low"], signal["range_low"], "entry range low")
    assert result["signal_count"] == len(selected)
    assert len(result["admission_events"]) == len(events)
    for event, saved, decision in zip(events, result["admission_events"], checked):
        assert set(saved) == {"direction", "reason", "time_utc", "position_open"}
        assert all(saved[k] == event[k] for k in ("direction", "reason", "time_utc"))
        assert saved["position_open"] is decision["position_open"], "admission capacity witness"
    for reason, count in result["rejections"].items():
        assert count == counts[reason], ("rejection count", reason, count, counts[reason])
    return checked


def audit_cost_fields(auditor, cell):
    """Verify published signed cost components against frozen ledger convention."""
    result, costs = cell["result"], cell["result"]["costs"]
    fields = ("commission_usd", "modeled_slippage_usd", "modeled_extra_spread_proxy_usd",
              "quoted_spread_proxy_usd", "explicit_cost_attribution_usd", "net_before_swap_usd")
    totals = Counter()
    for trade in result["ledger"]:
        factor = auditor.broker["trade_contract_size"] * trade["volume"]
        fee = costs["commission_per_lot"] * trade["volume"]
        slipped = costs["slippage"] * factor * (1 if trade["reason"] == "TP" else 2)
        extra = costs["extra_spread"] * factor
        exit_index = _exit_index(auditor, trade, costs)
        entry_index = int(np.searchsorted(auditor.times, trade["entry_ms"]))
        spread_entry = float(auditor.tape["ask"][entry_index] - auditor.tape["bid"][entry_index]) + costs["extra_spread"]
        spread_exit = float(auditor.tape["ask"][exit_index] - auditor.tape["bid"][exit_index]) + costs["extra_spread"]
        equal(trade["entry_spread"], spread_entry, "source entry spread")
        expected = dict(commission_usd=fee, modeled_slippage_usd=slipped,
                        modeled_extra_spread_proxy_usd=extra,
                        quoted_spread_proxy_usd=(spread_entry + spread_exit) / 2 * factor,
                        explicit_cost_attribution_usd=fee + slipped + extra,
                        net_before_swap_usd=trade["net"] - trade["swap_usd"])
        for key, value in expected.items():
            equal(trade[key], value, "cost component " + key)
            totals[key] += value
    for key in fields:
        equal(result[key], totals[key], "total cost " + key)
    return dict(totals)


def audit_closing_recovery(result, diagnostics, last_quote):
    """Require completed episodes and right-censored ongoing closing drawdown."""
    cash = peak = 200.0
    peak_time = pd.Timestamp(result["start_utc"])
    active, completed = None, []
    for trade in result["ledger"]:
        cash += trade["net"]
        closed = pd.Timestamp(trade["exit_time_utc"])
        if cash < peak and active is None:
            active = dict(start=peak_time.isoformat(), first_underwater_exit=closed.isoformat(), previous_peak=peak)
        if cash >= peak:
            if active is not None:
                completed.append(dict(active, end=closed.isoformat(), recovered_to=cash,
                                      days=(closed - peak_time).total_seconds() / 86400))
                active = None
            peak, peak_time = cash, closed
    ongoing = dict(active, balance=cash, days=(pd.Timestamp(last_quote) - peak_time).total_seconds() / 86400) if active else None
    expected = dict(completed_count=len(completed), longest_completed=max(completed, key=lambda e: e["days"], default=None), ongoing=ongoing)
    assert diagnostics["actual_closing_recovery"] == expected, "closing recovery/censoring drift"
    return expected


def audit_source_pins(out, sources):
    for name, digest in sources.items():
        path = (ROOT / name).resolve()
        assert not Path(name).is_absolute() and ".." not in Path(name).parts
        assert path.is_relative_to(ROOT) and sha(path) == sha(out / "source_snapshot" / name) == digest, name


def audit_loaded_sources(protocol):
    """A saved pin list cannot excuse changed or newly loaded audit dependencies."""
    for module in tuple(sys.modules.values()):
        origin = getattr(module, "__file__", None)
        if not origin:
            continue
        path = Path(origin).resolve()
        if path.suffix == ".pyc":
            path = Path(importlib.util.source_from_cache(str(path)))
        if not path.is_file():
            continue
        repository = path.is_relative_to(ROOT)
        name = str(path.relative_to(ROOT)) if repository else str(path)
        pins = protocol["sources"] if repository else protocol["runtime_sources"]
        assert pins.get(name) == sha(path), "unbound loaded audit dependency: " + name


def opportunity_delta(native, candidate):
    """Identity/capacity attribution only; never sum hypothetical isolated PnL."""
    control = {tuple(x["identity"]): x for x in native}
    changed = {tuple(x["identity"]): x for x in candidate}
    control_entries = {k for k, v in control.items() if v["reason"] == "admitted"}
    changed_entries = {k for k, v in changed.items() if v["reason"] == "admitted"}
    def rows(keys):
        return [dict(signal_ms=k[0], direction=k[1], native_reason=control.get(k, {}).get("reason", "MACRO_BLOCKED"),
                     candidate_reason=changed.get(k, {}).get("reason", "MACRO_BLOCKED"),
                     candidate_holder_entry_ms=changed.get(k, {}).get("holder_entry_ms")) for k in sorted(keys)]
    return dict(retained=rows(control_entries & changed_entries), lost=rows(control_entries - changed_entries),
                newly_admitted=rows(changed_entries - control_entries),
                newly_visible=rows(set(changed) - set(control)),
                rejected_candidate_counts=dict(Counter(x["reason"] for x in candidate if x["reason"] != "admitted")),
                counterfactual_pnl_added=False, capacity="ONE_SHARED_POSITION")


def validate_inputs(out, protocol):
    assert protocol["algorithm"] == ALGORITHM and protocol["policy"] == POLICY
    assert protocol["execution_authorized"] is False and protocol["holdout"] is False
    assert protocol["cost_status"] == "COST_INCONCLUSIVE" and protocol["real_money"] == "PROHIBITED"
    assert protocol["native_rules_id"] == protocol["baseline_id"] == BASE
    assert protocol["initial_balance"] == 200 and protocol["finite_domain"] == 2
    assert protocol["expected_paths"] == 12 and protocol["expected_selected_repeats"] == 6
    assert protocol["repeat_policy"] == "selected_profit_all_six_fresh"
    assert sha(DATA / "manifest.json") == protocol["input_manifest_sha256"]
    for name, digest in protocol["input_hashes"].items():
        assert sha(DATA / name) == digest, "input drift: " + name
    required = {SELF, TEST, "scripts/research/c22_h4_carry.py", "tests/research/test_c22_h4_carry.py",
                "specs/c22-h4-carry-2026-10-30.md", "scripts/__init__.py",
                str(SEED.relative_to(ROOT)), "runs/c22-real-data-audit-2026-10-24/run_audit_v2.py"}
    assert required <= set(protocol["sources"]), "verifier/source freeze incomplete"
    audit_source_pins(out, protocol["sources"])
    for name, digest in protocol["runtime_sources"].items():
        assert sha(Path(name)) == digest, "runtime source drift: " + name
    versions = protocol["runtime_versions"]
    assert versions == dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__,
                            executable_sha256=sha(Path(sys.executable).resolve()))
    parents = {}
    for name, binding in protocol["parent"].items():
        path = path_in_runs(binding["path"])
        assert sha(path) == binding["sha256"]
        parents[name] = read(path)
    assert protocol["parent"]["protocol"]["sha256"] == PARENT_SHA
    assert parents["audit"]["status"] == "PASS" and parents["final"]["status"] == "VERIFIED_COMPLETE"
    parent = parents["protocol"]
    for key in ("broker", "views", "start", "end", "original_floors", "native_rules", "references",
                "input_hashes", "input_manifest_sha256"):
        assert protocol[key] == parent[key], "parent binding " + key
    for name, digest in parent["sources"].items():
        assert protocol["sources"].get(name) == digest, "inherited source omitted"
    references = {}
    assert set(protocol["references"]) == {f"{v}-{g}" for v in VIEWS for g in GUARDS}
    for key, binding in protocol["references"].items():
        path, proof = path_in_runs(binding["path"]), path_in_runs(binding["proof_path"])
        assert sha(path) == binding["sha256"] and sha(proof) == binding["proof_sha256"]
        record = read(proof)
        assert record["path"] == binding["path"] and record["sha256"] == binding["sha256"]
        references[key] = path
    assert sha(out / "catalog.json") == protocol["catalog_sha256"]
    catalog = read(out / "catalog.json")
    descriptor = dict(algorithm=ALGORITHM, native_rules=protocol["native_rules"], signal_seed=read(SEED), h4_policy=POLICY)
    identity = hashlib.sha256(json.dumps(descriptor, sort_keys=True).encode()).hexdigest()[:16]
    assert identity == protocol["candidate_id"] and identity != BASE
    assert catalog == dict(schema=1, algorithm=ALGORITHM, finite_domain=2, profiles=[
        dict(name=BASE, label="Native26b8", carry=False),
        dict(name=identity, label="B-strict-H4-carry-under8h", carry=True, descriptor=descriptor),
    ])
    return catalog, references


def audit_repeat(repeat, original):
    assert repeat["protocol_sha256"] == original["protocol_sha256"]
    assert repeat["profile"] == original["profile"]
    assert all(repeat[k] == original[k] for k in ("result", "metrics", "diagnostics", "summary", "h4_context")), "fresh full-result repeat drift"


def choose(rows, floors):
    qualified = sorted(name for name in rows if qualify(rows[name], floors))
    assert BASE in qualified
    eligible = [name for name in qualified if name == BASE or (
        all(rows[name][g][v]["metrics"]["net_usd"] + 1e-7 >= rows[BASE][g][v]["metrics"]["net_usd"]
            for g in GUARDS for v in VIEWS)
        and rows[name]["raw"]["base"]["metrics"]["net_usd"] > rows[BASE]["raw"]["base"]["metrics"]["net_usd"] + 1e-7)]
    return min(eligible, key=lambda n: (*rank(rows[n]), n != BASE)), sorted(eligible)


def verify(out, *, report_dir=None):
    out = Path(out).resolve()
    assert out.is_relative_to(ROOT / "runs")
    protocol = read(out / "protocol.json")
    catalog, references = validate_inputs(out, protocol)
    audit_loaded_sources(protocol)
    profiles = {p["name"]: p for p in catalog["profiles"]}
    expected = {f"{n}-{v}-{g}" for n in profiles for v in VIEWS for g in GUARDS}
    assert {p.stem for p in (out / "cells-integrity").glob("*.json")} == expected, "12 primary paths required"
    bars = load_bars(DATA / "bars.csv")
    native, _ = prepare(bars, read(SEED))
    signals = reconstruct(bars, native, read(SEED))
    auditor = IndependentTapeAudit(protocol, read(DATA / "manifest.json")["last_quote_utc"])
    rows, audits, payloads, admissions, cells = {}, {}, {}, {}, {}
    for key in sorted(expected):
        cell, proof, _ = read_cell(out, key)
        name, view, guard = key.split("-")
        assert cell["protocol_sha256"] == sha(out / "protocol.json")
        assert cell["profile"] == profiles[name] and cell["result"]["rules"] == protocol["native_rules"]
        context = audit_context(cell, signals)
        accounting = auditor.audit_cell(cell)
        cost_fields = audit_cost_fields(auditor, cell)
        recovery = audit_closing_recovery(cell["result"], cell["diagnostics"], auditor.last_quote)
        ticks, _ = full_tick_and_peaks(auditor, cell)
        actual = audit_admissions(auditor, cell, signals)
        if name == BASE:
            assert cell["result"] == read(references[f"{view}-{guard}"])["result"], "entire native result parity"
        admissions[key] = actual
        rows.setdefault(name, {}).setdefault(guard, {})[view] = dict(metrics=cell["metrics"], risk=accounting["risk"])
        audits[key] = dict(accounting=accounting, full_tick=ticks, context=context, cost_fields=cost_fields, recovery=recovery,
                           decisions=len(actual), reasons=dict(Counter(x["reason"] for x in actual)))
        payloads[proof["path"]] = proof["sha256"]
        cells[key] = cell
        print("PASS independent H4 cell", len(audits), "/12", key, flush=True)
    selected, eligible = choose(rows, protocol["original_floors"])
    results = read(out / "results.json")
    assert results["selected"] == selected and sorted(results["qualified"]) == eligible
    assert results["evaluated_paths"] == 12 and results["fresh_repeats"] == 6
    for name in profiles:
        for guard in GUARDS:
            for view in VIEWS:
                saved = results["summaries"][name][guard][view]
                assert saved["metrics"] == rows[name][guard][view]["metrics"]
                for field, value in saved["risk"].items():
                    equal(value, rows[name][guard][view]["risk"][field], "summary risk")
    repeats = {f"{selected}-{v}-{g}" for v in VIEWS for g in GUARDS}
    assert {p.stem for p in (out / "repeats-integrity").glob("*.json")} == repeats
    for key in sorted(repeats):
        repeat, proof, _ = read_cell(out, key, "repeats")
        original = cells[key]
        audit_repeat(repeat, original)
        payloads[proof["path"]] = proof["sha256"]
    complete = read(out / "COMPLETE.json")
    assert complete["status"] == "MATRIX_EVALUATED_AWAITING_INDEPENDENT_H4_AND_TICK_AUDIT"
    assert complete["paths"] == 12 and complete["fresh_repeats"] == 6 and complete["selected"] == selected
    required = {"protocol.json", "catalog.json", "results.json"} | {
        f"{folder}-integrity/{key}.json" for folder, keys in (("cells", expected), ("repeats", repeats)) for key in keys}
    assert set(complete["artifacts"]) == required, "completion proof coverage"
    for name, digest in complete["artifacts"].items():
        assert sha(out / name) == digest, name
    candidate = protocol["candidate_id"]
    opportunities = {f"{v}-{g}": opportunity_delta(admissions[f"{BASE}-{v}-{g}"], admissions[f"{candidate}-{v}-{g}"])
                     for v in VIEWS for g in GUARDS}
    # Recheck sources after auditing, so a concurrent source edit cannot pass.
    validate_inputs(out, protocol)
    audit_loaded_sources(protocol)
    value = dict(status="PASS", primary_cells=12, fresh_repeats=6, independent_full_tick_dd_cells=12,
                 economic_replays=0, selected_profit=selected, qualified=eligible,
                 retain_native=selected == BASE, cost_status="COST_INCONCLUSIVE", holdout=False,
                 protocol_sha256=sha(out / "protocol.json"), source_sha256=sha(Path(__file__)),
                 completion_sha256=sha(out / "COMPLETE.json"), audited_cells=audits,
                 opportunities=opportunities, payload_hashes=payloads,
                 limits="Historical code/accounting agreement only; modeled swap and unknown gap cause; no forward or broker parity qualification")
    report_dir = Path(report_dir or ROOT / "runs/c22-h4-independent-review-2026-10-30").resolve()
    assert report_dir.is_relative_to(ROOT / "runs")
    write(report_dir / "independent-verification.json", value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args()
    value = verify(args.out, report_dir=args.report_dir)
    print(json.dumps({k: v for k, v in value.items() if k not in ("audited_cells", "opportunities", "payload_hashes")}, indent=2))


if __name__ == "__main__":
    main()
