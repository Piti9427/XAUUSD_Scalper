"""One causal joint BUY48 selector,capacity attribution and daily MTM model.

Research only. No broker/execution/notification API or separate account exists.
"""

import math
import numpy as np
import pandas as pd

from scripts.research.reward156_tuning import closed_h4_ema
from scripts.research.rollover import SwapPolicy


def _utc(value):
    value = pd.Timestamp(value)
    if value.tzinfo is None or value.utcoffset() != pd.Timedelta(0):
        raise ValueError("addon_aware_utc_required")
    return value


def joint_frame(bars, native, *, enabled):
    """Keep full native priority; replace only addon rows' direction/ranges."""
    if type(enabled) is not bool or not bars.index.equals(native.index):
        raise ValueError("addon_exact_frame_identity_required")
    if (
        bars.index.tz is None
        or str(bars.index.tz) != "UTC"
        or bars.index.has_duplicates
        or not bars.index.is_monotonic_increasing
    ):
        raise ValueError("addon_utc_chronology_required")
    if not native.direction.isin((-1, 0, 1)).all():
        raise ValueError("addon_native_direction_invalid")
    if not bars[["open", "high", "low", "close"]].equals(native[["open", "high", "low", "close"]]):
        raise ValueError("addon_native_ohlc_mismatch")
    high = bars.high.rolling(48, min_periods=48).max().shift(1)
    low = bars.low.rolling(48, min_periods=48).min().shift(1)
    average = bars.close.ewm(span=50, adjust=False, min_periods=50).mean()
    macro = closed_h4_ema(bars, 200)
    eligible = (
        (bars.close > high)
        & (bars.close > average)
        & (average > average.shift(4))
        & (bars.close > macro)
    ).fillna(False)
    pick = native.direction.eq(0) & eligible & enabled
    frame = native.copy()
    frame.loc[pick, "direction"] = 1
    frame.loc[pick, "hh"] = high[pick]
    frame.loc[pick, "ll"] = low[pick]
    origin = np.where(native.direction.ne(0), "native", np.where(pick, "addon", "none"))
    witness = pd.DataFrame(
        dict(
            native_direction=native.direction,
            addon_eligible=eligible,
            origin=origin,
            prior_high=high,
            prior_low=low,
            ema50=average,
            macro_ema=macro,
        ),
        index=bars.index,
    )
    return frame, witness


def attribute_joint(result, witness, *, control=None):
    """Match actual context/entry identities; never add counterfactual profits."""
    by_signal = {
        int((stamp + pd.Timedelta(minutes=15)).value // 10**6): row
        for stamp, row in witness.iterrows()
    }
    events = result.get("context_events")
    if not isinstance(events, list):
        raise ValueError("addon_context_events_required")
    annotated = []
    admissions = {}
    for event in events:
        stamp = int(_utc(event["signal_close_utc"]).value // 10**6)
        if stamp not in by_signal:
            raise ValueError("addon_unbound_signal_event")
        row = by_signal[stamp]
        origin = row.origin
        expected = (
            int(row.native_direction) if origin == "native" else 1 if origin == "addon" else 0
        )
        if event["direction"] != expected or not expected:
            raise ValueError("addon_priority_or_signal_mismatch")
        item = dict(event, origin=origin, signal_ms=stamp)
        annotated.append(item)
        if event["reason"] == "admitted":
            key = (int(_utc(event["time_utc"]).value // 10**6), event["direction"])
            if key in admissions:
                raise ValueError("addon_duplicate_admission")
            admissions[key] = item
    entries = []
    previous = None
    for trade in result["ledger"]:
        key = (trade["entry_ms"], trade["direction"])
        if key not in admissions:
            raise ValueError("addon_unbound_entry")
        born = trade["entry_ms"]
        closed = int(_utc(trade["exit_time_utc"]).value // 10**6)
        if previous is not None and born < previous:
            raise ValueError("addon_overlapping_capacity")
        previous = closed
        event = admissions[key]
        entries.append(
            dict(
                entry_ms=born,
                exit_ms=closed,
                direction=trade["direction"],
                signal_ms=event["signal_ms"],
                origin=event["origin"],
                net_usd=trade["net"],
            )
        )
    if len(entries) != len(admissions) or not math.isclose(
        math.fsum(t["net_usd"] for t in entries),
        result["final_balance"] - 200,
        abs_tol=1e-7,
        rel_tol=1e-11,
    ):
        raise ValueError("addon_shared_cash_reconciliation_failed")
    native_signatures = {
        (t["signal_ms"], t["direction"]) for t in entries if t["origin"] == "native"
    }
    missed = []
    extra = []
    if control is not None:
        control_admits = {
            (int(_utc(e["signal_close_utc"]).value // 10**6), e["direction"])
            for e in control["context_events"]
            if e["reason"] == "admitted"
        }
        by_key = {(e["signal_ms"], e["direction"]): e for e in annotated}
        for signature in sorted(control_admits - native_signatures):
            if signature not in by_key:
                raise ValueError("addon_core_missing_context")
            event = by_key[signature]
            time_ms = int(_utc(event["time_utc"]).value // 10**6)
            held = [t for t in entries if t["entry_ms"] < time_ms < t["exit_ms"]]
            boundary = [t for t in entries if t["entry_ms"] == time_ms or t["exit_ms"] == time_ms]
            holder = (
                held[0]["origin"]
                if len(held) == 1
                else "AMBIGUOUS_SAME_MS_BOUNDARY"
                if boundary
                else "NO_STRICT_HELD_WITNESS"
            )
            missed.append(
                dict(
                    signal_close_utc=pd.Timestamp(signature[0], unit="ms", tz="UTC").isoformat(),
                    direction=signature[1],
                    joint_reason=event["reason"],
                    holder=holder,
                )
            )
        extra = [
            dict(signal_ms=k[0], direction=k[1]) for k in sorted(native_signatures - control_admits)
        ]
    contributions = {
        name: math.fsum(t["net_usd"] for t in entries if t["origin"] == name)
        for name in ("native", "addon")
    }
    return dict(
        entries=entries,
        events=annotated,
        closed_net_by_source=contributions,
        missed_control_native=missed,
        extra_joint_native=extra,
        known_busy_with_addon=sum(
            e["joint_reason"] == "busy" and e["holder"] == "addon" for e in missed
        ),
        ambiguous_busy_boundaries=sum(
            e["joint_reason"] == "busy" and e["holder"] == "AMBIGUOUS_SAME_MS_BOUNDARY"
            for e in missed
        ),
        counterfactual_pnl_added=False,
        capacity="ONE_SHARED_POSITION",
    )


def _distribution(values):
    array = np.asarray(values, dtype=float)
    return dict(
        count=len(array),
        positive=int((array > 1e-7).sum()),
        negative=int((array < -1e-7).sum()),
        flat=int((np.abs(array) <= 1e-7).sum()),
        mean_usd=float(array.mean()) if len(array) else None,
        median_usd=float(np.median(array)) if len(array) else None,
        worst_usd=float(array.min()) if len(array) else None,
        best_usd=float(array.max()) if len(array) else None,
    )


def daily_mtm(result, ticks, broker, swap_policy, *, origins):
    """Daily executable-side model with exact original quote age/coverage."""
    if not isinstance(swap_policy, SwapPolicy):
        raise ValueError("addon_daily_modeled_swap_required")
    start = _utc(result["start_utc"])
    requested_end = _utc(result["end_exclusive_utc"])
    times, bid, ask = ticks
    if not len(times) or len(times) != len(bid) or len(times) != len(ask):
        raise ValueError("addon_daily_tape_invalid")
    end = min(requested_end, pd.Timestamp(int(times[-1]) + 1, unit="ms", tz="UTC"))
    if start >= end or result["initial_balance"] != 200:
        raise ValueError("addon_daily_window_invalid")
    trades = result["ledger"]
    ordered = sorted(trades, key=lambda t: t["entry_ms"])
    previous = None
    for trade in ordered:
        born = trade["entry_ms"]
        closed = int(_utc(trade["exit_time_utc"]).value // 10**6)
        if (
            born < int(start.value // 10**6)
            or born > closed
            or (previous is not None and born < previous)
        ):
            raise ValueError("addon_daily_capacity_or_chronology_invalid")
        previous = closed
        if born not in origins or origins[born] not in ("native", "addon"):
            raise ValueError("addon_daily_origin_unknown")
    boundaries = (
        [start]
        + [
            b
            for b in pd.date_range(
                start.normalize() + pd.Timedelta(days=1), end.normalize(), freq="D"
            )
            if b < end
        ]
        + [end]
    )
    schedule = swap_policy.schedule(start, requested_end)
    costs = result["costs"]

    def mark(boundary):
        cutoff = int(boundary.value // 10**6)
        closed = [t for t in trades if int(_utc(t["exit_time_utc"]).value // 10**6) < cutoff]
        cash = 200.0 + math.fsum(t["net"] for t in closed)
        held = [
            t
            for t in trades
            if t["entry_ms"] < cutoff <= int(_utc(t["exit_time_utc"]).value // 10**6)
        ]
        if len(held) > 1:
            raise ValueError("addon_daily_overlapping_capacity")
        if not held:
            return dict(
                equity=cash,
                coverage="FLAT_REALIZED_CASH",
                verified=True,
                quote_utc=None,
                quote_age_seconds=None,
                held=False,
            )
        t = held[0]
        index = int(np.searchsorted(times, cutoff, side="left")) - 1
        if index < 0 or int(times[index]) < t["entry_ms"]:
            return dict(
                equity=None,
                coverage="PRICE_UNKNOWN",
                verified=False,
                quote_utc=None,
                quote_age_seconds=None,
                held=True,
            )
        direction = t["direction"]
        factor = broker["trade_contract_size"] * t["volume"]
        quote = (
            float(bid[index] if direction == 1 else ask[index])
            - direction * costs["extra_spread"] / 2
        )
        if not math.isfinite(quote):
            raise ValueError("addon_daily_quote_nonfinite")
        fee = costs["commission_per_lot"] * t["volume"]
        swap = float(schedule.amount(t["entry_ms"], cutoff - 1, direction, factor))
        equity = cash - fee + direction * (quote - t["entry"]) * factor + swap
        age = (cutoff - 1 - int(times[index])) / 1000
        verified = 0 <= age <= 60
        return dict(
            equity=equity,
            coverage="RECENT_ACTUAL_QUOTE_MODEL" if verified else "STALE_ACTUAL_QUOTE_MODEL",
            verified=verified,
            quote_utc=pd.Timestamp(int(times[index]), unit="ms", tz="UTC").isoformat(),
            quote_age_seconds=age,
            held=True,
        )

    before = dict(
        equity=200.0,
        coverage="INITIAL_CASH",
        verified=True,
        quote_utc=None,
        quote_age_seconds=None,
        held=False,
    )
    rows = []
    for left, right in zip(boundaries, boundaries[1:]):
        after = mark(right)
        born = [t for t in trades if left.value // 10**6 <= t["entry_ms"] < right.value // 10**6]
        closed = [t for t in trades if left <= _utc(t["exit_time_utc"]) < right]
        net = (
            after["equity"] - before["equity"]
            if after["equity"] is not None and before["equity"] is not None
            else None
        )
        if net is not None and not math.isfinite(net):
            raise ValueError("addon_daily_cash_nonfinite")
        rows.append(
            dict(
                start_utc=left.isoformat(),
                end_utc=right.isoformat(),
                full_calendar_day=bool(
                    left == left.normalize() and right - left == pd.Timedelta(days=1)
                ),
                start_equity_usd=before["equity"],
                end_equity_usd=after["equity"],
                net_usd=net,
                start_price_verified=before["verified"],
                end_price_verified=after["verified"],
                end_coverage=after["coverage"],
                end_quote_utc=after["quote_utc"],
                end_quote_age_seconds=after["quote_age_seconds"],
                start_coverage=before["coverage"],
                entries=len(born),
                closes=len(closed),
                native_entries=sum(origins[t["entry_ms"]] == "native" for t in born),
                addon_entries=sum(origins[t["entry_ms"]] == "addon" for t in born),
                no_entry_day=not bool(born),
                held_during_day=any(
                    t["entry_ms"] < right.value // 10**6 and _utc(t["exit_time_utc"]) >= left
                    for t in trades
                ),
            )
        )
        before = after
    known = [r["net_usd"] for r in rows if r["net_usd"] is not None]
    total = math.fsum(known) if len(known) == len(rows) else None
    if total is not None and not math.isclose(
        total, result["final_balance"] - 200.0, abs_tol=1e-7, rel_tol=1e-11
    ):
        raise ValueError("addon_daily_final_cash_mismatch")
    complete = [r for r in rows if r["full_calendar_day"]]
    return dict(
        schema=1,
        days=rows,
        net_reconciliation_usd=total,
        requested_end_utc=requested_end.isoformat(),
        actual_effective_end_utc=end.isoformat(),
        partial_days=sum(not r["full_calendar_day"] for r in rows),
        complete_no_entry_days=sum(r["no_entry_day"] for r in complete),
        complete_held_no_entry_days=sum(
            r["no_entry_day"] and r["held_during_day"] for r in complete
        ),
        unverified_complete_days=sum(
            not (r["start_price_verified"] and r["end_price_verified"]) for r in complete
        ),
        distribution=dict(
            modeled_complete=_distribution(
                [r["net_usd"] for r in complete if r["net_usd"] is not None]
            ),
            verified_complete=_distribution(
                [
                    r["net_usd"]
                    for r in complete
                    if r["net_usd"] is not None
                    and r["start_price_verified"]
                    and r["end_price_verified"]
                ]
            ),
        ),
        qualification="COST_INCONCLUSIVE",
        daily_profit_guaranteed=False,
        mark_convention="last_actual_executable_quote_before_boundary_plus_modeled_swap_through_boundary_minus_1ms",
    )
