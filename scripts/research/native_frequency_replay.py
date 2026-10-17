"""Shared native detector geometry into frozen canonical execution; swap mandatory.

This is modeled tick replay, NOT native Tester execution parity. Canonical BE is
bar/fee-inclusive, fee charged upfront, midnight baseline strict. Keep source pins.
"""

from dataclasses import asdict
import math
from types import FunctionType
import numpy as np
import pandas as pd
from scripts.research.breakout_entry import EntryPlan
from scripts.research.breakout_models import Rules, Costs
from scripts.research.breakout_replay import replay
from scripts.research.smc_challenger_adapter import audit_result, validate_broker, prepared_entries

VIEWS = {
    "base-swap": Costs(commission_per_lot=0.0),
    "cost-stress-swap": Costs(commission_per_lot=40.0),
}
CASES = ("pullback", "session_0600_1200", "session_0700_1300", "session_0800_1400", "c22_tuned")


def native_entry(row, bid, ask, broker, rules, costs, balance, peak, *, m5=False):
    entry = float(ask if row.direction == 1 else bid)
    stop, target = float(row.native_stop), float(row.native_target)
    if not math.isclose(entry, float(row.native_entry), rel_tol=0, abs_tol=1e-10):
        raise ValueError("native first-quote geometry divergence")
    if (
        not all(math.isfinite(x) and x > 0 for x in (entry, stop, target))
        or row.direction * ((bid if row.direction == 1 else ask) - stop) <= 0
    ):
        return "invalid_stop"
    factor = broker["trade_contract_size"] * 0.01
    fee = costs.commission_per_lot * 0.01
    risk = abs(entry - stop) * factor + fee
    if risk > balance * 0.1:
        return "risk_cap"
    if balance - fee <= entry * factor / broker["leverage"]:
        return "margin"
    return EntryPlan(entry, stop, target, 0.1, 0.01, factor, fee, risk)


def replay_case(frame, ticks, broker, *, strategy, view, start, end):
    policy = validate_broker(broker)
    if strategy not in CASES or view not in VIEWS:
        raise ValueError("unknown case/view")
    minutes = 15 if strategy == "c22_tuned" else 5
    needed = {
        "open",
        "high",
        "low",
        "close",
        "atr",
        "direction",
        "native_entry",
        "native_stop",
        "native_target",
    }
    if (
        not needed.issubset(frame)
        or frame.index.tz is None
        or str(frame.index.tz) != "UTC"
        or not frame.index.is_monotonic_increasing
        or frame.index.has_duplicates
    ):
        raise ValueError("invalid native signal frame")
    if (frame.index.as_unit("ms").asi8 % (minutes * 60000)).any():
        raise ValueError("unaligned native signal frame")
    if not frame.direction.isin((-1, 0, 1)).all():
        raise ValueError("invalid direction")
    rules = Rules(
        target_rr=2.0,
        protect_mode="break_even",
        protect_after_r=1.0,
        daily_loss_limit=0.1,
        max_daily_losses=0 if strategy == "c22_tuned" else 1,
    )
    prepared = frame.copy()
    prepared["hh"] = frame.high
    prepared["ll"] = frame.low
    prepared["management_bar"] = True
    bound = FunctionType(
        replay.__code__,
        dict(replay.__globals__, _entry_signals=prepared_entries, prepare_entry=native_entry),
        replay.__name__,
        replay.__defaults__,
        replay.__closure__,
    )
    bound.__kwdefaults__ = replay.__kwdefaults__
    result = bound(
        prepared,
        ticks,
        broker,
        rules,
        VIEWS[view],
        start=start,
        end=end,
        entry_frame=prepared if minutes == 5 else None,
        swap_policy=policy,
        capture_events=True,
        capture_context=True,
    )
    audit_result(result)
    # Canonical replay exposes liquidation evidence, not a bankruptcy flag.
    result["bankrupt"] = bool(
        result["final_balance"] <= 0
        or result["rejections"]["bankrupt"]
        or any(t["reason"] == "BANKRUPT" for t in result["ledger"])
        or any(mark["equity_usd"] <= 0 for mark in result["equity"])
    )
    result["execution_model"] = "CANONICAL_TICK_REPLAY_NOT_NATIVE_TESTER"
    result["native_geometry"] = True
    result["cost_view"] = view
    result["rule_contract"] = asdict(rules)
    return result


def monthly_metrics(result, *, first_quote, last_quote):
    start = pd.Timestamp(result["start_utc"])
    end = pd.Timestamp(result["end_exclusive_utc"])
    months = pd.date_range(
        start.normalize().replace(day=1), end - pd.Timedelta(nanoseconds=1), freq="MS", tz="UTC"
    )
    table = {}
    for stamp in months:
        next_month = stamp + pd.offsets.MonthBegin(1)
        requested_full = bool(stamp >= start and next_month <= end)
        observed_scope = (
            "unobserved"
            if last_quote < stamp or first_quote >= next_month
            else "full"
            if first_quote <= stamp and last_quote >= next_month
            else "partial"
        )
        key = stamp.strftime("%Y-%m")
        table[key] = dict(
            month_utc=key,
            entries=0,
            winners=0,
            cash=0.0,
            requested_full=requested_full,
            observed_scope=observed_scope,
            full=requested_full and observed_scope == "full",
        )
    for trade in result["ledger"]:
        entry = pd.Timestamp(trade["entry_time_utc"]).strftime("%Y-%m")
        exit_month = pd.Timestamp(trade["exit_time_utc"]).strftime("%Y-%m")
        fee = trade["commission_usd"]
        table[entry]["entries"] += 1
        table[entry]["winners"] += int(trade["net"] > 0)
        table[entry]["cash"] -= fee
        table[exit_month]["cash"] += trade["net"] + fee
    full = [r for r in table.values() if r["full"]]
    if not math.isclose(sum(r["cash"] for r in table.values()), result["net_usd"], abs_tol=1e-7):
        raise ValueError("monthly cash mismatch")
    return dict(
        net_usd=result["net_usd"],
        final_balance=result["final_balance"],
        max_dd_pct=result["max_dd_pct"],
        trades=result["trades"],
        win_rate=result["win_rate"],
        profit_factor=result["profit_factor"],
        swap_usd=result["swap_usd"],
        full_months=len(full),
        mean_entries=float(np.mean([r["entries"] for r in full])) if full else 0.0,
        median_month_net=float(np.median([r["cash"] for r in full])) if full else 0.0,
        positive_month_ratio=sum(r["cash"] > 0 for r in full) / len(full) if full else 0.0,
        worst_month_net=min((r["cash"] for r in full), default=0.0),
        months=list(table.values()),
        rejections=result["rejections"],
        bankrupt=result["bankrupt"],
        max_admitted_risk_pct=result["max_admitted_risk_pct"],
    )
