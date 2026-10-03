"""Offline single-position breakout experiments; no execution or notification API.

The event loop visits every completed bar and all ticks while a position is
open. Experimental exits fill on the first available quote after close; lateness
blocks new entries, never suppresses a protective exit.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
import math
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Rules:
    failed_closes: int = 0
    reset_after_exit: bool = False
    stagnant_bars: int = 0
    entry_mode: str = "immediate"
    stop_mode: str = "atr"
    protect_mode: str = "off"
    entry_guard: str = "off"
    buy_pause_drawdown: float = 0.0

    risk_mode: str = "static"
    risk_cap: float = 0.10
    daily_loss_limit: float = 0.40
    target_atr: float = 3.0
    min_depth_atr: float = 0.0
    target_rr: float = 0.0
    cooldown_bars: int = 0
    session_mode: str = "all"
    max_daily_losses: int = 0
    protect_after_r: float = 0.5
    stop_atr: float = 2.5
    buy_stop_atr: float | None = None
    buy_target_rr: float | None = None
    buy_protect_mode: str | None = None

    def __post_init__(self):
        if self.buy_protect_mode not in (None, "off", "break_even"):
            raise ValueError("unsupported BUY protection")
        if self.buy_stop_atr is not None and self.buy_stop_atr not in (1.0, 1.5, 2.0, 2.5):
            raise ValueError("unsupported BUY ATR stop multiplier")
        if self.buy_target_rr is not None and self.buy_target_rr not in (1.25, 1.35, 1.5, 2.0):
            raise ValueError("unsupported BUY risk distance target")
        if (
            self.buy_stop_atr is not None or self.buy_target_rr is not None
        ) and self.stop_mode != "atr":
            raise ValueError("BUY exit profile requires ATR stop mode")
        if self.stop_atr not in (1.5, 2.0, 2.5):
            raise ValueError("unsupported ATR stop multiplier")
        if self.protect_after_r not in (0.5, 1.0, 1.5, 2.0):
            raise ValueError("unsupported protection activation")
        if self.cooldown_bars not in (0, 1, 4) or self.max_daily_losses not in (0, 1, 2):
            raise ValueError("unsupported loss circuit")
        if self.session_mode not in ("all", "london_ny"):
            raise ValueError("unsupported UTC session")
        if self.risk_mode not in ("static", "drawdown_steps"):
            raise ValueError("unsupported risk mode")
        if self.risk_cap not in (0.025, 0.05, 0.10):
            raise ValueError("unsupported risk cap")
        if self.daily_loss_limit not in (0.05, 0.10, 0.20, 0.40):
            raise ValueError("unsupported daily limit")
        if self.target_rr not in (0.0, 1.25, 1.35, 1.4, 1.45, 1.5, 2.0, 3.0):
            raise ValueError("unsupported risk distance target")
        if self.target_atr not in (3.0, 6.25):
            raise ValueError("unsupported parent target")
        if self.min_depth_atr not in (0.0, 0.15, 0.20, 0.25):
            raise ValueError("unsupported breakout depth")
        if self.failed_closes not in (0, 1, 2) or self.stagnant_bars not in (0, 4, 8, 16):
            raise ValueError("unsupported research rule")
        if self.entry_mode not in ("immediate", "confirm", "retest", "failed_reverse"):
            raise ValueError("unsupported entry mode")
        if self.stop_mode not in ("atr", "structure", "trigger", "boundary"):
            raise ValueError("unsupported stop mode")
        if self.protect_mode not in ("off", "break_even", "candle_trail", "runner"):
            raise ValueError("unsupported profit protection")
        if self.entry_guard not in (
            "off",
            "buy_only",
            "sell_only",
            "body_dominant",
            "close_extreme",
            "prior_day",
        ):
            raise ValueError("unsupported entry guard")
        if (
            not math.isfinite(self.buy_pause_drawdown)
            or self.buy_pause_drawdown < 0
            or self.buy_pause_drawdown >= 1
        ):
            raise ValueError("unsupported buy pause")


@dataclass(frozen=True)
class Costs:
    extra_spread: float = 0.0  # USD per ounce, divided across both sides
    slippage: float = 0.0  # USD per ounce, each adverse market fill
    commission_per_lot: float = 0.0  # USD round trip, reserved/charged on entry

    def __post_init__(self):
        if any(not math.isfinite(v) or v < 0 for v in asdict(self).values()):
            raise ValueError("costs must be finite and nonnegative")


def features(bars: pd.DataFrame) -> pd.DataFrame:
    frame = bars[["open", "high", "low", "close"]].astype(float).copy()
    frame["hh"] = frame.high.rolling(48).max().shift(1)
    frame["ll"] = frame.low.rolling(48).min().shift(1)
    previous = frame.close.shift()
    frame["atr"] = (
        pd.concat(
            [frame.high - frame.low, (frame.high - previous).abs(), (frame.low - previous).abs()],
            axis=1,
        )
        .max(axis=1)
        .rolling(14)
        .mean()
    )
    frame["direction"] = np.select([frame.close > frame.hh, frame.close < frame.ll], [1, -1], 0)
    return frame


def _entry_signals(frame, mode):
    output = frame.copy()
    output["stop_low"] = frame.low
    output["stop_high"] = frame.high
    output["entry_boundary"] = np.where(frame.direction == 1, frame.hh, frame.ll)
    if mode == "immediate":
        return output
    output["direction"] = 0
    pending = None
    for index, row in enumerate(frame.itertuples()):
        if pending is not None:
            direction, high, low, born, candle_low, candle_high = pending
            boundary = high if direction == 1 else low
            beyond = direction * (row.close - boundary) > 0
            touched = row.low <= boundary if direction == 1 else row.high >= boundary
            reverse = mode == "failed_reverse" and index - born <= 2 and low <= row.close <= high
            if reverse or (mode != "failed_reverse" and beyond and (mode == "confirm" or touched)):
                if reverse:
                    direction = -direction
                output.loc[row.Index, ["direction", "hh", "ll"]] = [direction, high, low]
                output.loc[row.Index, "entry_boundary"] = boundary
                output.loc[row.Index, ["stop_low", "stop_high"]] = [
                    min(candle_low, row.low),
                    max(candle_high, row.high),
                ]
                pending = None
                continue
            expired = index - born >= (2 if mode == "failed_reverse" else 4)
            if (mode != "failed_reverse" and not beyond) or mode == "confirm" or expired:
                pending = None
        if pending is None and row.direction:
            pending = (int(row.direction), row.hh, row.ll, index, row.low, row.high)
    return output


def _level(price, grid, direction):
    units = Decimal(str(price)) / Decimal(str(grid))
    return float(
        units.to_integral_value(rounding=ROUND_FLOOR if direction == 1 else ROUND_CEILING)
        * Decimal(str(grid))
    )


def replay(frame, ticks, broker, rules, costs, *, start, end):
    """Return account metrics and closed trades for one independent $200 window.

    Input frame includes completed OHLC, prior hh/ll, atr and direction.
    No dynamic lot sizing. Quote age is zero at observation; lateness <=90s.
    SL is a trigger, not a guaranteed maximum loss across a price gap.
    """
    if any(x.tzinfo is None or x.utcoffset() != pd.Timedelta(0) for x in (start, end)):
        raise ValueError("window must be aware UTC")
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
        (frame.index + pd.Timedelta(minutes=15)).normalize()
    ).to_numpy()
    all_t, all_b, all_a = ticks
    if not (len(all_t) == len(all_b) == len(all_a)):
        raise ValueError("unequal tick arrays")
    left, right = np.searchsorted(all_t, [start.value // 10**6, end.value // 10**6])
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
    for key in ("trade_contract_size", "trade_tick_size", "leverage", "volume_step"):
        if not math.isfinite(broker[key]) or broker[key] <= 0:
            raise ValueError("invalid broker specification")
    if not (broker["volume_min"] <= 0.01 <= broker["volume_max"]) or not np.isclose(
        0.01 / broker["volume_step"], round(0.01 / broker["volume_step"])
    ):
        raise ValueError("fixed lot is not broker-admissible")
    factor = broker["trade_contract_size"] * 0.01
    fee = costs.commission_per_lot * 0.01
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
        quote = bid[index] if p["direction"] == 1 else ask[index]
        price = p["target"] if reason == "TP" else quote - p["direction"] * costs.slippage
        gross = p["direction"] * (price - p["entry"]) * factor
        net = gross - fee
        if net < 0:
            loss_day = int(times[index] // 86400000)
            daily_losses[loss_day] = daily_losses.get(loss_day, 0) + 1
            cooldown_until_ms = int(times[index]) + rules.cooldown_bars * 900000
        balance += gross
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
            quote = bid[cursor:stop] if p["direction"] == 1 else ask[cursor:stop]
            pnl = p["direction"] * (quote - p["entry"]) * factor
            sl = p["direction"] * (quote - p["stop"]) <= 0
            tp = (p["direction"] * (quote - p["target"]) >= 0) & (not p["target_disabled"])
            hits = np.flatnonzero(sl | tp | (balance + pnl <= 0))
            used = int(hits[0]) + 1 if len(hits) else len(pnl)
            # Observe executable TP value, not a favorable tick overshoot that cannot fill.
            marks = balance + pnl[:used]
            if len(hits) and tp[used - 1] and not sl[used - 1]:
                marks[-1] = balance + p["direction"] * (p["target"] - p["entry"]) * factor
            excursions = marks - p["entry_equity"]
            p["mfe_usd"] = max(p["mfe_usd"], float(np.max(excursions)))
            p["mae_usd"] = min(p["mae_usd"], float(np.min(excursions)))
            observe(marks, times[cursor : cursor + used])
            if len(hits):
                close(
                    cursor + used - 1,
                    "SL" if sl[used - 1] else "TP" if tp[used - 1] else "BANKRUPT",
                )
            cursor += used

    completed = frame.index + pd.Timedelta(minutes=15)
    selected = (completed >= start) & (completed < end)
    stamps = completed[selected].as_unit("ms").asi8
    indices = np.searchsorted(times, stamps)
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
        if position is not None:
            p = position
            # Signal bar precedes entry; never count it as a held bar.
            if stamp > p["entry_ms"]:
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
        if position is not None and stamp > position["entry_ms"] and protect_mode != "off":
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
            rejected["late_quote"] += 1
            continue
        if position is not None:
            rejected["busy"] += 1
            continue
        if reset_range is not None:
            rejected["reset"] += 1
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
            rejected["entry_guard"] += 1
            continue
        if (
            rules.buy_pause_drawdown
            and direction == 1
            and peak > 0
            and (peak - balance) / peak >= rules.buy_pause_drawdown
        ):
            rejected["buy_pause"] += 1
            continue
        day = int(times[index] // 86400000)
        hour = (int(times[index]) % 86400000) / 3600000
        if rules.session_mode == "london_ny" and not (7 <= hour < 11 or 12 <= hour < 17):
            rejected["session"] += 1
            continue
        if int(times[index]) < cooldown_until_ms:
            rejected["cooldown"] += 1
            continue
        if rules.max_daily_losses and daily_losses.get(day, 0) >= rules.max_daily_losses:
            rejected["daily_loss_count"] += 1
            continue
        if flat_since is not None and flat_since <= day * 86400000:
            day_start.setdefault(day, balance)
        if day not in day_start:
            rejected["day_start_unknown"] += 1
            continue
        if balance <= 0:
            rejected["bankrupt"] += 1
            continue
        if day_start[day] - balance >= day_start[day] * rules.daily_loss_limit:
            rejected["daily_loss"] += 1
            continue
        if not all(math.isfinite(v) for v in (row.atr, row.hh, row.ll)) or row.atr <= 0:
            continue
        entry = float(ask[index] if direction == 1 else bid[index]) + direction * costs.slippage
        stop_atr = (
            rules.buy_stop_atr
            if direction == 1 and rules.buy_stop_atr is not None
            else rules.stop_atr
        )
        target_rr = (
            rules.buy_target_rr
            if direction == 1 and rules.buy_target_rr is not None
            else rules.target_rr
        )
        stop = _level(entry - direction * row.atr * stop_atr, broker["trade_tick_size"], direction)
        if rules.stop_mode in ("structure", "trigger"):
            anchor = (
                (row.low if direction == 1 else row.high)
                if rules.stop_mode == "trigger"
                else (row.stop_low if direction == 1 else row.stop_high)
            )
            stop = _level(
                anchor - direction * broker["trade_tick_size"], broker["trade_tick_size"], direction
            )
        if rules.stop_mode == "boundary":
            stop = _level(
                row.entry_boundary - direction * 0.5 * row.atr, broker["trade_tick_size"], direction
            )
        executable = float(bid[index] if direction == 1 else ask[index])
        if not math.isfinite(stop) or direction * (executable - stop) <= 0:
            rejected["invalid_stop"] += 1
            continue
        target_distance = abs(entry - stop) * target_rr if target_rr else row.atr * rules.target_atr
        target = _level(entry + direction * target_distance, broker["trade_tick_size"], direction)
        risk = (abs(entry - stop) + costs.slippage) * factor + fee
        admission_cap = rules.risk_cap
        if rules.risk_mode == "drawdown_steps":
            drawdown = max(0.0, (peak - balance) / peak)
            if drawdown >= 0.15:
                admission_cap = min(admission_cap, 0.025)
            elif drawdown >= 0.10:
                admission_cap = min(admission_cap, 0.05)
        if risk > balance * admission_cap:
            rejected["risk_cap"] += 1
            continue
        if balance - fee <= entry * factor / broker["leverage"]:
            rejected["margin"] += 1
            continue
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
            volume=0.01,
        )
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
    return dict(
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


def dominates(candidate, baseline, stressed, stressed_baseline, *, min_trades):
    """Fail closed; no weighted score can hide deterioration in a required metric."""
    return bool(
        candidate["trades"] >= min_trades
        and stressed["trades"] >= min_trades
        and candidate["realized_rr"] is not None
        and baseline["realized_rr"] is not None
        and candidate["net_usd"] > max(0, baseline["net_usd"])
        and candidate["max_dd_pct"] < baseline["max_dd_pct"]
        and candidate["realized_rr"] > baseline["realized_rr"]
        and stressed["net_usd"] > max(0, stressed_baseline["net_usd"])
        and stressed["max_dd_pct"] <= stressed_baseline["max_dd_pct"]
        and candidate["max_admitted_risk_pct"] <= 10
        and stressed["max_admitted_risk_pct"] <= 10
    )
