"""Offline tick event loop; independent USD200 windows, no execution API."""

from dataclasses import asdict
import math
from typing import Any

import numpy as np
import pandas as pd

from .breakout_entry import _level, prepare_entry
from .breakout_signals import _entry_signals


def replay(
    frame,
    ticks,
    broker,
    rules,
    costs,
    *,
    start,
    end,
    entry_frame=None,
    swap_policy=None,
    capture_events=False,
):
    """Return account metrics and closed trades for one independent $200 window.

    Input frame includes completed OHLC, prior hh/ll, atr and direction.
    Fixed0.01 by default; optional current-equity risk sizing floors broker steps.
    Quote age is zero at observation; lateness <=90s.
    SL is a trigger, not a guaranteed maximum loss across a price gap.
    """
    if any(x.tzinfo is None or x.utcoffset() != pd.Timedelta(0) for x in (start, end)):
        raise ValueError("window must be aware UTC")
    minutes = 15
    if entry_frame is not None:
        if rules.entry_mode != "immediate" or "management_bar" not in entry_frame:
            raise ValueError(
                "M5 entries require immediate prepared triggers and M15 management flags"
            )
        frame = entry_frame
        minutes = 5
    if start >= end or frame.index.tz is None or str(frame.index.tz) != "UTC":
        raise ValueError("invalid window/frame timezone")
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise ValueError("invalid bar chronology")
    # Shift daily direction before mapping, so current/future day cannot influence admission.
    daily = frame.resample("1D").agg({"open": "first", "close": "last"})
    prior = np.sign(daily.close - daily.open).shift(1)
    frame = frame.copy()
    boundary = np.where(frame.direction == 1, frame.hh, frame.ll)
    depth = frame.direction * (frame.close - boundary) / frame.atr
    if rules.min_depth_atr:
        frame.loc[depth < rules.min_depth_atr, "direction"] = 0
    frame = _entry_signals(frame, rules.entry_mode)
    frame["prior_day_direction"] = prior.reindex(
        (frame.index + pd.Timedelta(minutes=minutes)).normalize()
    ).to_numpy()
    all_t, all_b, all_a = ticks
    if not (len(all_t) == len(all_b) == len(all_a)):
        raise ValueError("unequal tick arrays")
    left, right = np.asarray(
        np.searchsorted(
            all_t, np.asarray([start.value // 10**6, end.value // 10**6], dtype=np.int64)
        )
    )
    times = all_t[left:right]
    # Read-only float tapes need no full-window copies for actual-spread replay.
    bid = all_b[left:right]
    ask = all_a[left:right]
    if costs.extra_spread or not np.issubdtype(bid.dtype, np.floating):
        bid = bid - costs.extra_spread / 2
    if costs.extra_spread or not np.issubdtype(ask.dtype, np.floating):
        ask = ask + costs.extra_spread / 2
    if not len(times):
        raise ValueError("invalid ticks")
    # Bound validation temporaries; overlap one timestamp across every chunk seam.
    for cursor in range(0, len(times), 100000):
        stop = cursor + 100000
        b, a = bid[cursor:stop], ask[cursor:stop]
        if (
            (np.diff(times[max(0, cursor - 1) : stop]) < 0).any()
            or not np.isfinite(b).all()
            or not np.isfinite(a).all()
            or (b <= 0).any()
            or (a < b).any()
        ):
            raise ValueError("invalid ticks")
    for key in (
        "trade_contract_size",
        "trade_tick_size",
        "leverage",
        "volume_step",
        "volume_min",
        "volume_max",
    ):
        if not math.isfinite(broker[key]) or broker[key] <= 0:
            raise ValueError("invalid broker specification")
    if broker["volume_min"] > broker["volume_max"]:
        raise ValueError("invalid broker volume bounds")
    if (rules.sizing_mode == "fixed" or rules.buy_sizing_mode == "fixed") and (
        not (broker["volume_min"] <= 0.01 <= broker["volume_max"])
        or not np.isclose(0.01 / broker["volume_step"], round(0.01 / broker["volume_step"]))
    ):
        raise ValueError("fixed lot is not broker-admissible")
    swap_schedule = swap_policy.schedule(start, end) if swap_policy is not None else None
    balance = peak = 200.0
    max_dd = 0.0
    position: dict[str, Any] | None = None
    ledger: list[dict[str, Any]] = []
    equity: list[dict[str, Any]] = []
    rejected = {
        k: 0
        for k in (
            "risk_cap",
            "margin",
            "daily_loss",
            "day_start_unknown",
            "late_quote",
            "busy",
            "reset",
            "bankrupt",
            "invalid_stop",
            "entry_guard",
            "buy_pause",
            "cooldown",
            "session",
            "daily_loss_count",
        )
    }
    rejection_events = []
    admission_events = []

    def event(reason, direction, stamp):
        if capture_events:
            admission_events.append(
                dict(
                    direction=direction,
                    reason=reason,
                    time_utc=pd.Timestamp(stamp, unit="ms", tz="UTC").isoformat(),
                    position_open=position is not None,
                )
            )

    def swap_at(p, stamps):
        if swap_schedule is None:
            return 0.0
        return swap_schedule.amount(
            p["entry_ms"], stamps, p["direction"], broker["trade_contract_size"] * p["volume"]
        )

    def reject(reason, direction, stamp):
        rejected[reason] += 1
        event(reason, direction, stamp)
        if entry_frame is not None:
            rejection_events.append(
                dict(
                    direction=direction,
                    reason=reason,
                    time_utc=pd.Timestamp(stamp, unit="ms", tz="UTC").isoformat(),
                )
            )

    day_start: dict[int, float] = {}
    daily_losses: dict[int, int] = {}
    cooldown_until_ms = 0
    flat_since: int | None = int(start.value // 10**6)
    reset_range = None
    previous = 0
    signal_count = 0

    def observe(marks, stamps):
        nonlocal peak, max_dd
        if not len(marks):
            return
        # Keep segment endpoints/extrema plus UTC midnight marks; all-tick DD stays exact.
        checkpoints = np.unique(
            np.r_[
                0,
                len(marks) - 1,
                np.argmin(marks),
                np.argmax(marks),
                np.flatnonzero(stamps % 86400000 < 1000),
            ]
        )
        for idx in checkpoints:
            equity.append(
                dict(
                    time_utc=pd.Timestamp(int(stamps[idx]), unit="ms", tz="UTC").isoformat(),
                    equity_usd=float(marks[idx]),
                )
            )
        peaks = np.maximum.accumulate(np.r_[peak, marks])[1:]
        max_dd = max(max_dd, float(np.max((peaks - marks) / peaks)))
        peak = max(peak, float(np.max(marks)))
        # Only actual first-second midnight marks establish an open-position baseline.
        midnight = np.flatnonzero(stamps % 86400000 < 1000)
        if len(midnight):
            days, first = np.unique(stamps[midnight] // 86400000, return_index=True)
            for day, idx in zip(days, midnight[first]):
                day_start.setdefault(int(day), float(marks[idx]))

    def close(index, reason):
        nonlocal balance, position, flat_since, reset_range, cooldown_until_ms
        p = position
        assert p is not None
        factor = broker["trade_contract_size"] * p["volume"]
        fee = costs.commission_per_lot * p["volume"]
        quote = bid[index] if p["direction"] == 1 else ask[index]
        price = p["target"] if reason == "TP" else quote - p["direction"] * costs.slippage
        gross = p["direction"] * (price - p["entry"]) * factor
        swap = float(swap_at(p, times[index]))
        net = gross - fee + swap
        if net < 0:
            loss_day = int(times[index] // 86400000)
            daily_losses[loss_day] = daily_losses.get(loss_day, 0) + 1
            cooldown_until_ms = int(times[index]) + rules.cooldown_bars * 900000
        balance += gross + swap
        p.update(
            exit_time_utc=pd.Timestamp(int(times[index]), unit="ms", tz="UTC").isoformat(),
            exit=float(price),
            reason=reason,
            net=float(net),
            net_r=float(net / p["risk_usd"]),
            commission_usd=fee,
            modeled_slippage_usd=costs.slippage * factor * (1 if reason == "TP" else 2),
        )
        p["mfe_usd"] = max(p["mfe_usd"], net)
        if swap_schedule is not None:
            p["swap_usd"] = swap
            p["net_before_swap_usd"] = gross - fee
        p["mae_usd"] = min(p["mae_usd"], net)
        p["quoted_spread_proxy_usd"] = (
            (p["entry_spread"] + float(ask[index] - bid[index])) / 2 * factor
        )
        p["modeled_extra_spread_proxy_usd"] = costs.extra_spread * factor
        p["explicit_cost_attribution_usd"] = (
            fee + p["modeled_slippage_usd"] + p["modeled_extra_spread_proxy_usd"]
        )
        ledger.append(p)
        observe(np.array([balance]), times[index : index + 1])
        reset_range = (p["range_low"], p["range_high"]) if rules.reset_after_exit else None
        flat_since = int(times[index])
        position = None

    def advance(begin, finish):
        nonlocal position
        cursor = begin
        while position is not None and cursor < finish:
            stop = min(cursor + 100000, finish)
            p = position
            factor = broker["trade_contract_size"] * p["volume"]
            quote = bid[cursor:stop] if p["direction"] == 1 else ask[cursor:stop]
            swaps = swap_at(p, times[cursor:stop])
            pnl = p["direction"] * (quote - p["entry"]) * factor + swaps
            sl = p["direction"] * (quote - p["stop"]) <= 0
            tp = (p["direction"] * (quote - p["target"]) >= 0) & (not p["target_disabled"])
            hits = np.flatnonzero(sl | tp | (balance + pnl <= 0))
            deadline = p.get("deadline_index")
            if deadline is not None and cursor <= deadline < stop:
                hits = np.unique(np.r_[hits, deadline - cursor])
            used = int(hits[0]) + 1 if len(hits) else len(pnl)
            # Observe executable TP value, not a favorable tick overshoot that cannot fill.
            marks = balance + pnl[:used]
            if len(hits) and tp[used - 1] and not sl[used - 1]:
                marks[-1] = balance + p["direction"] * (p["target"] - p["entry"]) * factor
                if swap_schedule is not None:
                    marks[-1] += swaps[used - 1]
            excursions = marks - p["entry_equity"]
            p["mfe_usd"] = max(p["mfe_usd"], float(np.max(excursions)))
            p["mae_usd"] = min(p["mae_usd"], float(np.min(excursions)))
            observe(marks, times[cursor : cursor + used])
            if len(hits):
                close(
                    cursor + used - 1,
                    "SL"
                    if sl[used - 1]
                    else "TP"
                    if tp[used - 1]
                    else "HOLD_LIMIT"
                    if deadline == cursor + used - 1
                    else "BANKRUPT",
                )
            cursor += used

    completed = frame.index + pd.Timedelta(minutes=minutes)
    selected = (completed >= start) & (completed < end)
    stamps = completed[selected].as_unit("ms").asi8
    indices = np.asarray(np.searchsorted(times, np.asarray(stamps, dtype=np.int64)))
    for row, stamp, index in zip(frame.loc[selected].itertuples(), stamps, indices):
        stamp, index = int(stamp), int(index)
        if index >= len(times):
            continue
        advance(previous, index + 1)
        previous = index + 1
        fresh = int(times[index]) - stamp <= 90000
        direction = int(row.direction)
        signal_count += bool(direction)
        closed_by_rule = False
        management_bar = entry_frame is None or row.management_bar
        if position is not None:
            p = position
            factor = broker["trade_contract_size"] * p["volume"]
            fee = costs.commission_per_lot * p["volume"]
            # Signal bar precedes entry; never count it as a held bar.
            if management_bar and stamp > p["entry_ms"]:
                p["held_bars"] += 1
                failed = p["direction"] * (row.close - p["boundary"]) < 0
                p["failed_count"] = p["failed_count"] + 1 if failed else 0
                executable = bid[index] if p["direction"] == 1 else ask[index]
                net_now = (
                    p["direction"] * (executable - p["entry"]) * factor
                    - fee
                    - costs.slippage * factor
                )
                if rules.failed_closes and p["failed_count"] >= rules.failed_closes:
                    close(index, "FAILED_BREAKOUT")
                    closed_by_rule = True
                elif rules.stagnant_bars and p["held_bars"] >= rules.stagnant_bars and net_now <= 0:
                    close(index, "STAGNANT")
                    closed_by_rule = True
        protect_mode = (
            rules.buy_protect_mode
            if position is not None
            and position["direction"] == 1
            and rules.buy_protect_mode is not None
            else rules.protect_mode
        )
        if (
            position is not None
            and management_bar
            and stamp > position["entry_ms"]
            and protect_mode != "off"
        ):
            p = position
            executable = float(bid[index] if p["direction"] == 1 else ask[index])
            net_now = (
                p["direction"] * (executable - p["entry"]) * factor - fee - costs.slippage * factor
            )
            if net_now >= rules.protect_after_r * p["risk_usd"]:
                p["protection_active"] = True
            if p["protection_active"]:
                # Round toward protection to cover costs, then require executable clearance.
                break_even = _level(
                    p["entry"] + p["direction"] * (fee / factor + costs.slippage),
                    broker["trade_tick_size"],
                    -p["direction"],
                )
                candidate = break_even
                if protect_mode in ("candle_trail", "runner"):
                    anchor = row.low if p["direction"] == 1 else row.high
                    trail = _level(
                        anchor - p["direction"] * broker["trade_tick_size"],
                        broker["trade_tick_size"],
                        p["direction"],
                    )
                    candidate = (
                        max(break_even, trail) if p["direction"] == 1 else min(break_even, trail)
                    )
                if (
                    p["direction"] * (candidate - p["stop"]) > 0
                    and p["direction"] * (executable - candidate) > 0
                ):
                    p["stop"] = candidate
                    p["stop_updates"] += 1
                    if protect_mode == "runner":
                        p["target_disabled"] = True
        if (
            reset_range is not None
            and not closed_by_rule
            and flat_since is not None
            and stamp > flat_since
        ):
            if reset_range[0] <= row.close <= reset_range[1]:
                reset_range = None
        if not direction or closed_by_rule:
            continue
        if not fresh:
            reject("late_quote", direction, int(times[index]))
            continue
        if position is not None:
            reject("busy", direction, int(times[index]))
            continue
        if reset_range is not None:
            reject("reset", direction, int(times[index]))
            continue
        span = row.high - row.low
        guard_ok = (
            rules.entry_guard == "off"
            or (rules.entry_guard == "buy_only" and direction == 1)
            or (rules.entry_guard == "sell_only" and direction == -1)
            or (
                rules.entry_guard == "body_dominant"
                and span > 0
                and direction * (row.close - row.open) >= span / 2
            )
            or (
                rules.entry_guard == "close_extreme"
                and span > 0
                and (
                    (row.close - row.low >= 0.75 * span)
                    if direction == 1
                    else (row.high - row.close >= 0.75 * span)
                )
            )
            or (rules.entry_guard == "prior_day" and row.prior_day_direction == direction)
        )
        if not guard_ok:
            reject("entry_guard", direction, int(times[index]))
            continue
        if (
            rules.buy_pause_drawdown
            and direction == 1
            and peak > 0
            and (peak - balance) / peak >= rules.buy_pause_drawdown
        ):
            reject("buy_pause", direction, int(times[index]))
            continue
        day = int(times[index] // 86400000)
        hour = (int(times[index]) % 86400000) / 3600000
        if rules.holding_mode == "intraday" and hour >= 20.5:
            reject("session", direction, int(times[index]))
            continue
        if rules.session_mode == "london_ny" and not (7 <= hour < 11 or 12 <= hour < 17):
            reject("session", direction, int(times[index]))
            continue
        if int(times[index]) < cooldown_until_ms:
            reject("cooldown", direction, int(times[index]))
            continue
        if rules.max_daily_losses and daily_losses.get(day, 0) >= rules.max_daily_losses:
            reject("daily_loss_count", direction, int(times[index]))
            continue
        if flat_since is not None and flat_since <= day * 86400000:
            day_start.setdefault(day, balance)
        if day not in day_start:
            reject("day_start_unknown", direction, int(times[index]))
            continue
        if balance <= 0:
            reject("bankrupt", direction, int(times[index]))
            continue
        if day_start[day] - balance >= day_start[day] * rules.daily_loss_limit:
            reject("daily_loss", direction, int(times[index]))
            continue
        if not all(math.isfinite(v) for v in (row.atr, row.hh, row.ll)) or row.atr <= 0:
            continue
        plan = prepare_entry(
            row,
            bid[index],
            ask[index],
            broker,
            rules,
            costs,
            balance,
            peak,
            m5=entry_frame is not None,
        )
        if isinstance(plan, str):
            reject(plan, direction, int(times[index]))
            continue
        entry = plan.entry
        stop = plan.stop
        target = plan.target
        admission_cap = plan.admission_cap
        volume = plan.volume
        factor = plan.factor
        fee = plan.fee
        risk = plan.risk
        event("admitted", direction, int(times[index]))
        position = dict(
            direction=direction,
            entry=entry,
            stop=stop,
            initial_stop=stop,
            stop_updates=0,
            protection_active=False,
            target_disabled=False,
            target=target,
            entry_ms=int(times[index]),
            entry_time_utc=pd.Timestamp(int(times[index]), unit="ms", tz="UTC").isoformat(),
            entry_spread=float(ask[index] - bid[index]),
            entry_equity=balance,
            risk_usd=risk,
            risk_pct=risk / balance * 100,
            admission_cap_pct=admission_cap * 100,
            range_high=float(row.hh),
            range_low=float(row.ll),
            boundary=float(row.entry_boundary),
            held_bars=0,
            failed_count=0,
            mfe_usd=0.0,
            mae_usd=0.0,
            volume=volume,
        )
        if rules.holding_mode != "legacy":
            deadline_ms = (
                day * 86400000 + 74700000
                if rules.holding_mode == "intraday"
                else int(times[index]) + 86400000
            )
            position["deadline_index"] = int(np.searchsorted(times, deadline_ms))
        balance -= fee
        flat_since = None
        # Record spread at entry immediately; exits start with subsequent ticks.
        entry_mark = (
            balance + direction * ((bid[index] if direction == 1 else ask[index]) - entry) * factor
        )
        position["mae_usd"] = min(0.0, entry_mark - position["entry_equity"])
        position["mfe_usd"] = max(0.0, entry_mark - position["entry_equity"])
        observe(np.array([entry_mark]), times[index : index + 1])
    advance(previous, len(times))
    if position is not None:
        close(len(times) - 1, "END_OF_SAMPLE")
    profits = np.array([p["net"] for p in ledger])
    wins, losses = profits[profits > 0], profits[profits < 0]
    rr = float(wins.mean() / -losses.mean()) if len(wins) and len(losses) else None
    result = dict(
        rules=asdict(rules),
        costs=asdict(costs),
        start_utc=start.isoformat(),
        end_exclusive_utc=end.isoformat(),
        initial_balance=200.0,
        final_balance=balance,
        net_usd=balance - 200,
        return_pct=(balance / 200 - 1) * 100,
        max_dd_pct=max_dd * 100,
        trades=len(ledger),
        realized_rr=rr,
        profit_factor=float(wins.sum() / -losses.sum()) if len(losses) else None,
        mean_net_r=float(np.mean([p["net_r"] for p in ledger])) if ledger else None,
        win_rate=float(len(wins) / len(ledger)) if ledger else None,
        max_admitted_risk_pct=max((p["risk_pct"] for p in ledger), default=0),
        commission_usd=sum(p["commission_usd"] for p in ledger),
        modeled_slippage_usd=sum(p["modeled_slippage_usd"] for p in ledger),
        modeled_extra_spread_proxy_usd=sum(p["modeled_extra_spread_proxy_usd"] for p in ledger),
        quoted_spread_proxy_usd=sum(p["quoted_spread_proxy_usd"] for p in ledger),
        explicit_cost_attribution_usd=sum(p["explicit_cost_attribution_usd"] for p in ledger),
        cost_attribution_note="Spread attribution is a two-sided quote proxy, not extra cash deducted or counterfactual PnL difference; TP fill remains at target.",
        signal_count=signal_count,
        rejections=rejected,
        ledger=ledger,
        equity=equity,
    )

    if entry_frame is not None:
        result["rejection_events"] = rejection_events
    if capture_events:
        result["admission_events"] = admission_events
    if swap_schedule is not None:
        result["swap_policy"] = asdict(swap_policy)
        result["swap_usd"] = sum(p["swap_usd"] for p in ledger)
        result["net_before_swap_usd"] = sum(p["net_before_swap_usd"] for p in ledger)
    return result
