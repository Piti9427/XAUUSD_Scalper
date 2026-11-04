"""Independently audit completed C22 tuning artifacts; never replay economics."""

import argparse
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FIRST = ROOT / "runs/c22-performance-2026-10-25"
PARENT = ROOT / "runs/c22-performance-refine-2026-10-25"
DATA = ROOT / "runs/c22-real-data-audit-2026-10-24/input"
VIEWS = ("base", "stress", "fee")
GUARDS = ("raw", "cent")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def equal(left, right, label):
    assert math.isclose(left, right, abs_tol=1e-7, rel_tol=1e-11), (label, left, right)


def loss(net, guard):
    if guard == "cent":
        return Decimal(str(float(net))).quantize(Decimal(".01"), rounding=ROUND_HALF_UP) < 0
    assert guard == "raw"
    return net < 0


def identity(rules):
    return hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()[:16]


def qualify(metrics, floor):
    return set(metrics) == set(VIEWS) and all(
        m["survival"] and m["net_usd"] > 0 and m["max_dd_pct"] <= 40
        for m in metrics.values()
    ) and all(metrics[v]["net_usd"] + 1e-7 >= floor[v]["net_usd"] for v in ("base", "stress"))


def rank(metrics):
    return (-metrics["base"]["net_usd"], -metrics["stress"]["net_usd"],
            max(m["max_dd_pct"] for m in metrics.values()))


def run(out):
    completion = out / "COMPLETE.json"
    assert completion.exists(), "Campaign incomplete; auditing cannot precede COMPLETE"
    complete_hash = sha(completion)
    complete = read(completion)
    protocol = read(out / "protocol.json")
    first = read(FIRST / "protocol.json")
    assert sha(DATA / "manifest.json") == first["input_manifest_sha256"], "Parent input manifest drift"
    assert sha(DATA / "manifest.json") == protocol["input_manifest_sha256"], "Campaign input manifest drift"
    assert sha(PARENT / "COMPLETE.json") == protocol["parent_complete_sha256"]
    for name, digest in protocol["sources"].items():
        assert sha(ROOT / name) == digest, name
        assert sha(out / "source_snapshot" / name) == digest, name
    for name, digest in protocol["input_hashes"].items():
        assert sha(DATA / name) == digest, name
    for name, digest in protocol["benchmark_hashes"].items():
        assert sha(ROOT / name) == digest, name
    for name, digest in complete["artifacts"].items():
        assert sha(out / name) == digest, name

    broker = protocol["broker"]
    assert broker["swap_mode"] == 1, "Independent calendar only supports declared point-mode swap"
    assert broker["swap_rollover3days"] == 3, "Independent calendar expects declared Wednesday triple"
    days = pd.date_range(pd.Timestamp(protocol["start"]).normalize(),
                         pd.Timestamp(protocol["end"]).normalize(), freq="D")
    previous = (days.dayofweek.to_numpy() - 1) % 7
    weights = np.where(previous >= 5, 0, np.where(previous == 2, 3, 1))
    stamps = days.as_unit("ms").asi8
    accrued = np.r_[0.0, np.cumsum(weights)]
    times = np.load(DATA / "tape/time.npy", mmap_mode="r")
    tape = {k: np.load(DATA / "tape" / f"{k}.npy", mmap_mode="r") for k in ("bid", "ask")}

    def swap_units(entry, end):
        return accrued[np.searchsorted(stamps, end, side="right")] - accrued[
            np.searchsorted(stamps, entry, side="right")]

    def swap_value(trade, end):
        rate = broker["swap_long"] if trade["direction"] == 1 else broker["swap_short"]
        return swap_units(trade["entry_ms"], end) * rate * broker["point"] * broker[
            "trade_contract_size"] * trade["volume"]

    cells = {}
    audited = []
    entries = 0
    for path in sorted((out / "cells").glob("*.json")):
        cell = read(path)
        result, guard = cell["result"], cell["guard"]
        rules, cost, trades = result["rules"], result["costs"], result["ledger"]
        assert cell["view"] in VIEWS and guard in GUARDS
        assert result["swap_policy"] is not None
        assert rules == cell["case"]["rules"]
        assert identity(rules) == cell["case"]["name"]
        assert rules["sizing_mode"] == "fixed" and rules["buy_sizing_mode"] in (None, "fixed")
        assert rules["risk_cap"] == .1 and rules["daily_loss_limit"] == .1
        assert rules["max_daily_losses"] == 2 and rules["holding_mode"] == "legacy"
        assert not rules["failed_closes"] and not rules["stagnant_bars"]
        assert cost == protocol["views"][cell["view"]]
        cash, counts, last_exit, cooldown_until = 200.0, Counter(), None, 0
        for trade in trades:
            born, closed = pd.Timestamp(trade["entry_time_utc"]), pd.Timestamp(trade["exit_time_utc"])
            assert born.tzinfo and closed.tzinfo and born <= closed
            assert born.utcoffset().total_seconds() == closed.utcoffset().total_seconds() == 0
            assert last_exit is None or last_exit <= born
            assert trade["volume"] == .01
            equal(cash, trade["entry_equity"], "entry cash")
            entry_ms, exit_ms = born.value // 10**6, closed.value // 10**6
            assert entry_ms == trade["entry_ms"] and entry_ms >= cooldown_until
            factor = broker["trade_contract_size"] * trade["volume"]
            fee = cost["commission_per_lot"] * trade["volume"]
            initial = (abs(trade["entry"] - trade["initial_stop"]) + cost["slippage"]) * factor + fee
            equal(initial, trade["risk_usd"], "initial stop risk")
            equal(initial / cash * 100, trade["risk_pct"], "initial risk percentage")
            assert trade["risk_pct"] <= trade["admission_cap_pct"] + 1e-8 <= 10 + 1e-8
            assert counts[str(born.date())] < rules["max_daily_losses"]
            swap = swap_value(trade, exit_ms)
            equal(swap, trade["swap_usd"], "calendar swap")
            net = trade["direction"] * (trade["exit"] - trade["entry"]) * factor - fee + swap
            equal(net, trade["net"], "trade net")

            midnight = born.normalize()
            boundary = midnight.value // 10**6
            past = [x for x in trades if pd.Timestamp(x["exit_time_utc"]) < midnight]
            held = [x for x in trades if x["entry_ms"] < boundary and
                    pd.Timestamp(x["exit_time_utc"]) >= midnight]
            assert len(held) <= 1
            baseline = 200 + sum(x["net"] for x in past)
            if held:
                position = held[0]
                index = int(np.searchsorted(times, boundary))
                stamp = int(times[index])
                assert boundary <= stamp < boundary + 1000
                direction = position["direction"]
                quote = float(tape["bid" if direction == 1 else "ask"][index]) - direction * cost["extra_spread"] / 2
                if position["reason"] == "TP" and pd.Timestamp(position["exit_time_utc"]).value // 10**6 == stamp:
                    quote = position["target"]
                held_factor = broker["trade_contract_size"] * position["volume"]
                baseline += direction * (quote - position["entry"]) * held_factor
                baseline -= cost["commission_per_lot"] * position["volume"]
                baseline += swap_value(position, stamp)
            assert baseline - cash < baseline * rules["daily_loss_limit"] + 1e-7
            if loss(trade["net"], guard):
                counts[str(closed.date())] += 1
                cooldown_until = exit_ms + rules["cooldown_bars"] * 900000
            cash += net
            last_exit = closed
            entries += 1
        equal(cash, result["final_balance"], "final cash")
        equal(cash - 200, result["net_usd"], "final net")
        equal(cell["metrics"]["net_usd"], result["net_usd"], "metric net")
        equal(cell["metrics"]["max_dd_pct"], result["max_dd_pct"], "metric DD")
        observed_min = min([200.0] + [mark["equity_usd"] for mark in result["equity"]])
        equal(cell["metrics"]["min_observed_equity"], observed_min, "metric minimum equity")
        assert cell["metrics"]["survival"] == bool(observed_min > 0 and cash > 0 and
            not result["rejections"]["bankrupt"])
        equal(sum(x["swap_usd"] for x in trades), result["swap_usd"], "total swap")
        assert result["trades"] == len(trades)
        recovery = cell["diagnostics"]["actual_closing_recovery"]
        episode_count = 0
        below_peak = False
        closing_cash = closing_peak = 200.0
        peak_time = pd.Timestamp(result["start_utc"])
        longest_days = None
        for trade in trades:
            closing_cash += trade["net"]
            closed = pd.Timestamp(trade["exit_time_utc"])
            below_peak = below_peak or closing_cash < closing_peak
            if closing_cash >= closing_peak:
                if below_peak:
                    duration = (closed - peak_time).total_seconds() / 86400
                    longest_days = duration if longest_days is None else max(longest_days, duration)
                    episode_count += 1
                    below_peak = False
                closing_peak, peak_time = closing_cash, closed
        assert recovery["completed_count"] == episode_count
        if longest_days is None:
            assert recovery["longest_completed"] is None
        else:
            equal(recovery["longest_completed"]["days"], longest_days, "actual completed recovery")
        assert (recovery["ongoing"] is not None) == below_peak
        cells[path.stem] = cell
        audited.append(str(path.relative_to(ROOT)))

    summary = read(out / "results.json")
    assert set(summary["cases"]) == {cell["case"]["name"] for cell in cells.values()}

    def metrics(name, guard):
        return {view: cells[f"{name}-{view}-{guard}"]["metrics"] for view in VIEWS}

    floors = protocol["original_floors"]
    for name, digest in protocol["benchmark_hashes"].items():
        cell = read(ROOT / name)
        guard = "cent" if name.endswith("-cent.json") else "raw"
        view = Path(name).stem.removesuffix("-cent").rsplit("-", 1)[1]
        assert cell["metrics"] == floors[guard][view]
    fully_qualified = []
    for name in summary["cases"]:
        raw_ok = qualify(metrics(name, "raw"), floors["raw"])
        if raw_ok:
            assert all(f"{name}-{view}-cent" in cells for view in VIEWS), "Missing cent review"
            if qualify(metrics(name, "cent"), floors["cent"]):
                fully_qualified.append(name)
    assert set(fully_qualified) == set(summary["qualified"])
    selected = summary["selected"]
    assert selected == min(fully_qualified, key=lambda n: (*rank(metrics(n, "raw")), n))
    assert selected == complete["selected"]
    current = summary["original"]
    seen = {current}
    for number, result in enumerate(summary["rounds"], start=1):
        catalog = read(out / "rounds" / f"{number}-catalog.json")
        saved_result = read(out / "rounds" / f"{number}-result.json")
        assert saved_result == result
        assert catalog["incumbent"] == result["incumbent"] == current
        assert len(catalog["catalog"]) <= 18
        assert result["candidates"] == [case["name"] for case in catalog["catalog"]]
        before = summary["cases"][current]["rules"]
        expected_neighbors = []
        for parameter, values in protocol["domains"].items():
            for value in values:
                if value == before[parameter]:
                    continue
                candidate = dict(before, **{parameter: value})
                name = identity(candidate)
                if name not in seen:
                    expected_neighbors.append(name)
        assert result["candidates"] == expected_neighbors, "Declared neighbor omitted or duplicated"
        expected_raw = [name for name in expected_neighbors if qualify(metrics(name, "raw"), floors["raw"])]
        expected_full = [name for name in expected_raw if qualify(metrics(name, "cent"), floors["cent"])]
        assert result["raw_qualified"] == expected_raw and result["fully_qualified"] == expected_full
        for case in catalog["catalog"]:
            assert case["name"] not in seen and identity(case["rules"]) == case["name"]
            changed = [key for key in before if before[key] != case["rules"][key]]
            assert changed == [case["parameter"]]
            seen.add(case["name"])
        winner = result["selected"]
        strict_improvement = rank(metrics(winner, "raw")) < rank(metrics(current, "raw"))
        assert result["improved"] == strict_improvement, "Identity tie replacement is not objective improvement"
        assert winner == current or strict_improvement
        if number > 1:
            assert catalog["previous_result_sha256"] == sha(out / "rounds" / f"{number-1}-result.json")
        current = winner
    assert current == selected and seen == set(summary["cases"])
    assert len(summary["cases"]) - 1 <= 36
    assert complete["economic_cells"] == len(cells) and complete["new_contracts"] == len(summary["cases"]) - 1
    assert summary["improved"] == (rank(metrics(selected, "raw")) < rank(metrics(summary["original"], "raw")))

    repeats = list((out / "repeats").glob("*.json"))
    assert len(repeats) == 6
    for path in repeats:
        assert read(path) == cells[path.stem]

    full_tick = {}
    for guard in GUARDS:
        for view in VIEWS:
            cell = cells[f"{selected}-{view}-{guard}"]
            result, cost = cell["result"], cell["result"]["costs"]
            cash = peak = 200.0
            max_dd = 0.0
            minimum = 200.0
            quoted = 0
            assert qualify(metrics(selected, guard), floors[guard])
            for trade in result["ledger"]:
                direction = trade["direction"]
                factor = broker["trade_contract_size"] * trade["volume"]
                fee = cost["commission_per_lot"] * trade["volume"]
                entry, exit_ms = trade["entry_ms"], pd.Timestamp(trade["exit_time_utc"]).value // 10**6
                left = int(np.searchsorted(times, entry))
                raw = tape["bid" if direction == 1 else "ask"]
                a = int(np.searchsorted(times, exit_ms))
                b = int(np.searchsorted(times, exit_ms, side="right"))
                exit_quotes = raw[a:b] - direction * cost["extra_spread"] / 2
                if trade["reason"] == "END_OF_SAMPLE":
                    assert int(times[-1]) == exit_ms
                    right = len(times)
                    equal(float(exit_quotes[-1] - direction * cost["slippage"]), trade["exit"], "sample-end fill")
                else:
                    assert trade["reason"] in ("SL", "TP"), "Unsupported selected exit contract"
                    valid = (direction * (exit_quotes - trade["target"]) >= 0 if trade["reason"] == "TP" else
                             np.isclose(exit_quotes - direction * cost["slippage"], trade["exit"], atol=1e-8, rtol=0))
                    matches = np.flatnonzero(valid)
                    assert len(matches), "Selected exit absent from source tape"
                    right = a + int(matches[0]) + 1
                assert right > left
                equal(cash, trade["entry_equity"], "full-tick entry cash")
                for cursor in range(left, right, 100000):
                    stop = min(cursor + 100000, right)
                    quote = raw[cursor:stop] - direction * cost["extra_spread"] / 2
                    swap = swap_value(trade, times[cursor:stop])
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
            equal(cash, result["final_balance"], "full-tick final cash")
            equal(max_dd * 100, result["max_dd_pct"], "full-tick DD")
            equal(minimum, cell["metrics"]["min_observed_equity"], "full-tick minimum equity")
            full_tick[f"{view}-{guard}"] = dict(max_dd_pct=max_dd * 100, min_equity=minimum,
                final_cash=cash, held_quote_observations=quoted)
            print("PASS full-tick", view, guard, "DD", round(max_dd * 100, 6), "quotes", quoted, flush=True)

    assert sha(completion) == complete_hash, "Completion changed during audit"
    report = dict(status="PASS", economic_replays=0, cells=len(audited), entries=entries,
        selected=selected, independent_full_tick_dd=full_tick,
        scope="Saved-cell cash/swap/risk/daily/cooldown/nonoverlap; cent review completeness; strict round objective; selected six full-tick DD",
        cost_status="COST_INCONCLUSIVE", source_sha256=sha(Path(__file__)),
        parent_completion_sha256=complete_hash, input_manifest_sha256=sha(DATA / "manifest.json"),
        audited_cells=audited)
    target = out / "independent-verification.json"
    pending = target.with_suffix(".json.pending")
    pending.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    pending.replace(target)
    print("PASS", len(audited), "cells /", entries, "entries / selected six full-tick DD paths", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="runs/c22-matrix-tuning-2026-10-25")
    args = parser.parse_args()
    out = (ROOT / args.output).resolve()
    if not out.is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("Machine outputs must remain under runs/")
    run(out)


if __name__ == "__main__":
    main()
