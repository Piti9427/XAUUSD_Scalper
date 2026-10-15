"""Frequency campaign qualification and independent ledger accounting."""

import math

import pandas as pd

from scripts.research.c22_context_campaign import VIEWS, require, reconcile
from scripts.research.reward156_tuning import blocking


def utc(value):
    stamp = pd.Timestamp(value)
    require(stamp.tzinfo is not None and stamp.utcoffset() == pd.Timedelta(0), "aware UTC required")
    return stamp


def monthly(ledger, start, end):
    start, end = utc(start), utc(end)
    require(start < end, "invalid monthly bounds")
    first = start.normalize().replace(day=1)
    months = pd.date_range(first, end, freq="MS", inclusive="left")
    full, partial, realized = {}, {}, {}
    for month in months:
        key = month.strftime("%Y-%m")
        target = full if month >= start and month + pd.DateOffset(months=1) <= end else partial
        target[key] = 0
        realized[key] = 0.0
    for trade in ledger:
        born, exit_time = utc(trade["entry_time_utc"]), utc(trade["exit_time_utc"])
        require(start <= born <= exit_time < end, "trade outside monthly window")
        key = born.strftime("%Y-%m")
        target = full if key in full else partial
        target[key] += 1
        realized[exit_time.strftime("%Y-%m")] += trade["net"]
    yearly = {}
    for key, value in realized.items():
        yearly[key[:4]] = yearly.get(key[:4], 0.0) + value
    return dict(
        full_month_entries=full,
        partial_month_entries=partial,
        mean_entries=sum(full.values()) / len(full) if full else 0.0,
        monthly_realized_net=realized,
        yearly_realized_net=yearly,
    )


def cost_attribution(ledger):
    # Replay quoted spread already includes stressed widening. Extra-spread
    # attribution is descriptive and must not be charged a second time here.
    sums = {
        key: sum(t[key] for t in ledger)
        for key in ("quoted_spread_proxy_usd", "modeled_slippage_usd", "commission_usd", "swap_usd")
    }
    total = (
        sums["quoted_spread_proxy_usd"]
        + sums["modeled_slippage_usd"]
        + sums["commission_usd"]
        - sums["swap_usd"]
    )
    return dict(
        sums,
        cost_proxy_per_trade=total / len(ledger) if ledger else None,
        swap_debit_usd=-sum(min(0, t["swap_usd"]) for t in ledger),
        swap_credit_usd=sum(max(0, t["swap_usd"]) for t in ledger),
    )


def metrics(result, broker, swap_policy):
    require("swap_policy" in result and "swap_usd" in result, "mandatory swap missing")
    reconcile(result, broker, result["context_dd_witnesses"])
    start, end = utc(result["start_utc"]), utc(result["end_exclusive_utc"])
    schedule = swap_policy.schedule(start, end)
    ledger = result["ledger"]
    admissions = [e for e in result["admission_events"] if e["reason"] == "admitted"]
    require(
        [(e["time_utc"], e["direction"]) for e in admissions]
        == [(t["entry_time_utc"], t["direction"]) for t in ledger],
        "admission/ledger mismatch",
    )
    for trade in ledger:
        factor = broker["trade_contract_size"] * trade["volume"]
        born, exited = utc(trade["entry_time_utc"]), utc(trade["exit_time_utc"])
        swap = float(
            schedule.amount(born.value // 10**6, exited.value // 10**6, trade["direction"], factor)
        )
        fee = result["costs"]["commission_per_lot"] * trade["volume"]
        net = trade["direction"] * (trade["exit"] - trade["entry"]) * factor - fee + swap
        require(math.isclose(net, trade["net"], abs_tol=1e-8), "independent net mismatch")
        require(math.isclose(swap, trade["swap_usd"], abs_tol=1e-8), "swap mismatch")
        require(
            trade["risk_pct"] <= trade["admission_cap_pct"] + 1e-8 <= 10 + 1e-8,
            "admission cap mismatch",
        )
    observed_min = min([200.0] + [e["equity_usd"] for e in result["equity"]])
    row = {
        key: result[key]
        for key in (
            "net_usd",
            "final_balance",
            "max_dd_pct",
            "trades",
            "max_admitted_risk_pct",
            "win_rate",
            "realized_rr",
            "profit_factor",
            "rejections",
        )
    }
    row.update(monthly(ledger, start, end))
    row.update(cost_attribution(ledger))
    row.update(blocking(result["admission_events"], ledger, start, end))
    tail_start = max(start, end - pd.Timedelta(days=30))
    tail = [e for e in result["admission_events"] if utc(e["time_utc"]) >= tail_start]
    exposed = any(
        utc(t["entry_time_utc"]) < end and utc(t["exit_time_utc"]) >= tail_start for t in ledger
    )
    row["tail_state"] = (
        "exposed"
        if exposed
        else "risk_cap_only"
        if row["terminal_risk_blockage"]
        else "no_signal"
        if not tail
        else "mixed_reasons"
    )
    row.update(
        min_equity=observed_min,
        bankrupt=observed_min <= 0 or any(t["reason"] == "BANKRUPT" for t in ledger),
        fixed_lot=all(t["volume"] == 0.01 for t in ledger),
        mean_admitted_risk_pct=sum(t["risk_pct"] for t in ledger) / len(ledger) if ledger else None,
    )
    return row


def qualify(rows, controls):
    require(set(rows) == set(controls) == set(VIEWS), "both swap views required")
    gates = {}
    for view in VIEWS:
        row = rows[view]
        gates[view] = dict(
            net=row["net_usd"] > 0 and row["net_usd"] >= controls[view]["net_usd"],
            dd=row["max_dd_pct"] <= 40,
            frequency=row["mean_entries"] >= 15,
            survival=row["min_equity"] > 0 and not row["bankrupt"],
            terminal=not row["terminal_risk_blockage"],
            risk=row["max_admitted_risk_pct"] <= 10 + 1e-8 and row["fixed_lot"],
        )
    return dict(gates=gates, qualified=all(all(g.values()) for g in gates.values()))


def search_rank(identity, rows, controls):
    gates = qualify(rows, controls)["gates"]
    return (
        -int(all(g["survival"] for g in gates.values())),
        -sum(sum(g.values()) for g in gates.values()),
        max(max(0, 15 - r["mean_entries"]) for r in rows.values()),
        -min(r["net_usd"] for r in rows.values()),
        max(r["max_dd_pct"] for r in rows.values()),
        identity,
    )


def winner_rank(identity, rows):
    return (
        -min(r["net_usd"] for r in rows.values()),
        max(r["max_dd_pct"] for r in rows.values()),
        max(r["cost_proxy_per_trade"] for r in rows.values()),
        max(r["mean_admitted_risk_pct"] for r in rows.values()),
        identity,
    )
