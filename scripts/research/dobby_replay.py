"""Offline reconstructed Dobby basket replay. No broker API or execution entrypoint.

Missing EA branches are explicit: one same-direction basket, management before
entry filters, one grid leg per tick, UTC calendar by default. Full-lifecycle
round-trip commission is reserved on entry, matching the C22 research engine.
"""

from dataclasses import asdict, dataclass
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DobbyRules:
    rsi_period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0
    initial_lot: float = 0.01
    multiplier: float = 2.0
    max_legs: int = 4
    grid_points: int = 3000
    basket_tp: float = 8.0
    basket_sl: float = 55.0
    skip_monday: bool = True
    max_daily_sl: int = 1
    max_spread_points: int = 500
    server_offset_hours: int = 0

    def __post_init__(self):
        values = asdict(self)
        if not all(math.isfinite(float(v)) for v in values.values()):
            raise ValueError("nonfinite rules")
        if self.rsi_period < 1 or self.max_legs < 1 or self.initial_lot <= 0:
            raise ValueError("invalid rules")
        if self.basket_tp <= 0 or self.basket_sl <= 0 or self.grid_points <= 0:
            raise ValueError("invalid money/grid rules")


def wilder_rsi(close, period=14):
    """Mean-seeded Wilder smoothing; flat seed=50, zero loss with gain=100."""
    prices = np.asarray(close, dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0).any() or period < 1:
        raise ValueError("invalid RSI prices/period")
    out = np.full(len(prices), np.nan)
    if len(prices) <= period:
        return out
    delta = np.diff(prices)
    gain = np.maximum(delta[:period], 0).mean()
    loss = np.maximum(-delta[:period], 0).mean()
    for i in range(period, len(prices)):
        if i > period:
            gain = (gain * (period - 1) + max(delta[i - 1], 0)) / period
            loss = (loss * (period - 1) + max(-delta[i - 1], 0)) / period
        out[i] = 100 - 100 / (1 + gain / loss) if loss else (100 if gain else 50)
    return out


def replay(bars, ticks, broker, rules, costs, *, start, end, swap_policy, scalar=False):
    """Vectorized event search, or scalar oracle using identical event/accounting rules.

    Gross floating PnL plus accrued swap minus reserved commission determines
    basket exits. Actual closing slippage is then charged. Margin rejection never
    increases lot. Unknown real stop-out/latency/rejection behavior is not modeled.
    """
    if swap_policy is None:
        raise ValueError("modeled swap required")
    if start.tzinfo is None or end.tzinfo is None or start.utcoffset() or end.utcoffset():
        raise ValueError("aware UTC required")
    if start >= end or str(bars.index.tz) != "UTC" or bars.index.has_duplicates:
        raise ValueError("invalid window/bars")
    if not bars.index.is_monotonic_increasing:
        raise ValueError("unordered bars")
    for key in (
        "point",
        "trade_contract_size",
        "volume_min",
        "volume_max",
        "volume_step",
        "leverage",
    ):
        if not math.isfinite(broker[key]) or broker[key] <= 0:
            raise ValueError("invalid broker spec")
    all_t, all_b, all_a = ticks
    if len(all_t) != len(all_b) or len(all_t) != len(all_a):
        raise ValueError("unequal ticks")
    left, right = np.searchsorted(all_t, [start.value // 10**6, end.value // 10**6])
    times, bids, asks = all_t[left:right], all_b[left:right], all_a[left:right]
    if not len(times):
        raise ValueError("empty ticks")
    for i in range(0, len(times), 100000):
        b, a = bids[i : i + 100000], asks[i : i + 100000]
        if (
            (np.diff(times[max(0, i - 1) : i + 100000]) < 0).any()
            or not np.isfinite(b).all()
            or not np.isfinite(a).all()
            or (b <= 0).any()
            or (a < b).any()
        ):
            raise ValueError("invalid ticks")
    schedule = swap_policy.schedule(start, end)
    values = wilder_rsi(bars.close.to_numpy(), rules.rsi_period)
    signal = pd.Series(
        np.where(values < rules.oversold, 1, np.where(values > rules.overbought, -1, 0)),
        index=bars.index + pd.Timedelta(minutes=15),
    )
    slots = np.arange(
        times[0] // 900000 * 900000, times[-1] // 900000 * 900000 + 900001, 900000, dtype=np.int64
    )
    edges = np.searchsorted(times, slots)
    directions = signal.reindex(
        pd.to_datetime(slots[:-1], unit="ms", utc=True), fill_value=0
    ).to_numpy()
    balance = peak = 200.0
    max_dd = 0.0
    basket = None
    ledger, equity, leg_events = [], [], []
    daily_sl = {}
    last_entry_slot = None
    max_margin_utilization = 0.0
    rejected = dict(margin=0, spread=0, monday=0, daily_sl=0)
    contract = broker["trade_contract_size"]
    slip, spread = costs.slippage, costs.extra_spread / 2
    offset = rules.server_offset_hours * 3600000

    def iso(stamp):
        return pd.Timestamp(int(stamp), unit="ms", tz="UTC").isoformat()

    def day_of(stamp):
        return (int(stamp) + offset) // 86400000

    def quotes(i, stop=None):
        if stop is None:
            return float(bids[i] - spread), float(asks[i] + spread)
        return bids[i:stop] - spread, asks[i:stop] + spread

    def observe(marks, stamps):
        nonlocal peak, max_dd
        marks, stamps = np.atleast_1d(marks), np.atleast_1d(stamps)
        peaks = np.maximum.accumulate(np.r_[peak, marks])[1:]
        max_dd = max(max_dd, float(np.max((peaks - marks) / peaks)))
        peak = max(peak, float(np.max(marks)))
        worst = int(np.argmax((peaks - marks) / peaks))
        for i in np.unique(
            [0, len(marks) - 1, int(np.argmin(marks)), int(np.argmax(marks)), worst]
        ):
            equity.append(dict(time_utc=iso(stamps[i]), equity_usd=float(marks[i])))

    def pnl(i, stop=None):
        b, a = quotes(i, stop)
        stamps = times[i] if stop is None else times[i:stop]
        executable = b if basket["direction"] == 1 else a
        gross = (
            basket["direction"]
            * (executable * basket["volume"] - basket["weighted_entry"])
            * contract
        )
        swap = sum(
            schedule.amount(leg["entry_ms"], stamps, basket["direction"], leg["volume"] * contract)
            for leg in basket["legs"]
        )
        return gross, swap

    def close(i, reason):
        nonlocal basket, balance
        gross, swap = (float(x) for x in pnl(i))
        gross -= slip * basket["volume"] * contract
        balance += gross + swap
        net = balance - basket["entry_equity"]
        b, a = quotes(i)
        exit_price = b - slip if basket["direction"] == 1 else a + slip
        record = dict(
            direction=basket["direction"],
            exit_price=exit_price,
            entry_time_utc=iso(basket["entry_ms"]),
            exit_time_utc=iso(times[i]),
            entry_equity=basket["entry_equity"],
            final_balance=balance,
            net=net,
            profit=gross,
            swap_usd=swap,
            commission_usd=basket["commission"],
            reason=reason,
            volume=basket["volume"],
            legs=basket["legs"],
            target_risk_pct=rules.basket_sl / basket["entry_equity"] * 100,
        )
        ledger.append(record)
        if reason == "BASKET_SL":
            day = day_of(times[i])
            daily_sl[day] = daily_sl.get(day, 0) + 1
        observe(balance, times[i])
        basket = None

    def lot_for(previous):
        desired = rules.initial_lot if previous is None else previous * rules.multiplier
        value = math.floor((desired + 1e-12) / broker["volume_step"]) * broker["volume_step"]
        return round(min(broker["volume_max"], max(broker["volume_min"], value)), 2)

    def add(i, direction):
        nonlocal basket, balance
        b, a = quotes(i)
        lot = lot_for(None if basket is None else basket["legs"][-1]["volume"])
        fill = a + slip if direction == 1 else b - slip
        if basket is None:
            basket = dict(
                direction=direction,
                entry_equity=balance,
                entry_ms=int(times[i]),
                legs=[],
                volume=0.0,
                weighted_entry=0.0,
                commission=0.0,
                margin=0.0,
            )
        fee = lot * costs.commission_per_lot
        leg = dict(
            entry_ms=int(times[i]),
            entry_time_utc=iso(times[i]),
            volume=lot,
            fill=fill,
            commission_usd=fee,
        )
        basket["legs"].append(leg)
        basket["volume"] += lot
        basket["weighted_entry"] += fill * lot
        basket["commission"] += fee
        basket["margin"] += fill * lot * contract / broker["leverage"]
        balance -= fee
        leg_events.append(dict(basket=len(ledger), direction=direction, **leg))
        gross, swap = pnl(i)
        observe(balance + gross + swap, times[i])

    for slot, begin, finish, direction in zip(slots[:-1], edges[:-1], edges[1:], directions):
        cursor, stop = int(begin), int(finish)
        while cursor < stop:
            if balance <= 0 and basket is None:
                break
            if basket is None:
                day = day_of(times[cursor])
                if not direction or last_entry_slot == slot:
                    break
                if rules.skip_monday and (day + 3) % 7 == 0:
                    rejected["monday"] += 1
                    break
                if daily_sl.get(day, 0) >= rules.max_daily_sl:
                    rejected["daily_sl"] += 1
                    break
                b, a = quotes(cursor, stop)
                lot = lot_for(None)
                entry = a + slip if direction == 1 else b - slip
                valid = ((a - b) / broker["point"] <= rules.max_spread_points + 1e-8) & (
                    entry * lot * contract / broker["leverage"] + costs.commission_per_lot * lot
                    <= balance
                )
                eligible = np.flatnonzero(valid)
                if not len(eligible):
                    rejected[
                        "spread"
                        if ((a - b) / broker["point"] > rules.max_spread_points).all()
                        else "margin"
                    ] += 1
                    break
                cursor += int(eligible[0])
                add(cursor, int(direction))
                last_entry_slot = slot
                cursor += 1
                continue
            scan_end = cursor + 1 if scalar else stop
            gross, swap = pnl(cursor, scan_end)
            net = gross + swap - basket["commission"]
            marks = balance + gross + swap
            b, a = quotes(cursor, scan_end)
            tp, sl, ruin = net >= rules.basket_tp, net <= -rules.basket_sl, marks <= 0
            grid = np.zeros(scan_end - cursor, dtype=bool)
            if len(basket["legs"]) < rules.max_legs:
                quote = a if basket["direction"] == 1 else b
                extremum = (min if basket["direction"] == 1 else max)(
                    leg["fill"] for leg in basket["legs"]
                )
                adverse = (
                    basket["direction"] * (quote - extremum) <= -rules.grid_points * broker["point"]
                )
                lot = lot_for(basket["legs"][-1]["volume"])
                fill = quote + basket["direction"] * slip
                affordable = (
                    fill * lot * contract / broker["leverage"] + lot * costs.commission_per_lot
                    <= marks - basket["margin"]
                )
                grid = adverse & affordable
            hits = np.flatnonzero(tp | sl | ruin | grid)
            count = int(hits[0]) + 1 if len(hits) else scan_end - cursor
            observe(marks[:count], times[cursor : cursor + count])
            positive = marks[:count] > 0
            if positive.any():
                max_margin_utilization = max(
                    max_margin_utilization,
                    float(np.max(basket["margin"] / marks[:count][positive])),
                )
            if not len(hits):
                cursor = scan_end
                continue
            cursor += int(hits[0])
            hit = int(hits[0])
            if ruin[hit] or sl[hit] or tp[hit]:
                close(cursor, "BANKRUPT" if ruin[hit] else "BASKET_SL" if sl[hit] else "BASKET_TP")
            else:
                add(cursor, basket["direction"])
            cursor += 1
    if basket is not None:
        close(len(times) - 1, "END_OF_SAMPLE")
    nets = np.array([t["net"] for t in ledger])
    wins, losses = nets[nets > 0], nets[nets < 0]
    return dict(
        strategy="dobby_reconstructed",
        rules=asdict(rules),
        costs=asdict(costs),
        swap_policy=asdict(swap_policy),
        initial_balance=200.0,
        final_balance=balance,
        net_usd=balance - 200,
        return_pct=(balance / 200 - 1) * 100,
        max_dd_pct=max_dd * 100,
        trades=len(ledger),
        legs=len(leg_events),
        win_rate=float(len(wins) / len(ledger)) if ledger else None,
        profit_factor=float(wins.sum() / -losses.sum()) if len(losses) else None,
        realized_rr=float(wins.mean() / -losses.mean()) if len(wins) and len(losses) else None,
        swap_usd=sum(t["swap_usd"] for t in ledger),
        commission_usd=sum(t["commission_usd"] for t in ledger),
        bankrupt=balance <= 0 or any(t["reason"] == "BANKRUPT" for t in ledger),
        max_margin_utilization=max_margin_utilization,
        max_basket_target_risk_pct=max((t["target_risk_pct"] for t in ledger), default=0),
        rejected=rejected,
        ledger=ledger,
        equity=equity,
        leg_events=leg_events,
    )
