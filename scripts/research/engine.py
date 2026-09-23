"""M1 executable-side simulation; R denominated in original stop distance."""

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Costs:
    units: float = 1.0  # 1 oz price exposure, NOT an asserted broker lot specification
    commission_per_unit_roundtrip: float = 0.0
    slippage: float = 0.0  # scenario price-distance, not measured broker slippage
    swap_per_unit_night: float = 0.0  # scenario; no broker triple-day calendar implied

    def __post_init__(self):
        values = tuple(self.__dict__.values())
        if not all(np.isfinite(v) for v in values) or self.units <= 0:
            raise ValueError("Invalid costs/exposure")
        if any(v < 0 for v in values[1:]):
            raise ValueError("Costs must be nonnegative")


def first_exit(a, start, direction, stop, target):
    """Opening gaps precede intraminute range; stop wins unresolved OHLC collisions."""
    for k in range(start, len(a), 1440):
        block = a[k : k + 1440]
        o, h, low_prices, c = block.T
        stops = low_prices <= stop if direction == 1 else h >= stop
        targets = h >= target if direction == 1 else low_prices <= target
        hits = np.flatnonzero(stops | targets)
        if len(hits):
            j = int(hits[0])
            opened = o[j]
            if direction * (opened - stop) <= 0:
                return k + j, opened, "SL_GAP"
            if direction * (opened - target) >= 0:
                return (
                    k + j,
                    target,
                    "TP_OPEN",
                )  # no favorable limit-price improvement assumed
            if stops[j]:
                return k + j, stop, "SL"
            return k + j, target, "TP"
    return len(a) - 1, a[-1, 3], "END_OF_SAMPLE"


def simulate(m1, f, signal, spec, costs=Costs(), native=False, delay_minutes=0):
    if delay_minutes < 0:
        raise ValueError("Negative delay")
    idx = m1.index
    bid = m1[[f"bid_{x}" for x in ("open", "high", "low", "close")]].to_numpy()
    ask = m1[[f"ask_{x}" for x in ("open", "high", "low", "close")]].to_numpy()
    trades = []
    busy_until = -1
    balance = peak = max_dd = 0.0
    for i in np.flatnonzero(signal.direction.to_numpy()):
        if native and f.regime.iloc[i] == "sideway":
            continue
        d = int(signal.direction.iloc[i])
        available = f.index[i] + pd.Timedelta(minutes=spec.timeframe + delay_minutes)
        start = int(idx.searchsorted(available))
        if start >= len(idx) or idx[start] != available or start <= busy_until:
            continue
        opening, closing = (ask, bid) if d == 1 else (bid, ask)
        risk = float(f.atr.iloc[i]) * (spec.sl if native else 2.0)
        rr = spec.tp if native else 2.0
        if not np.isfinite(risk) or risk <= 0:
            continue
        limit = signal.limit.iloc[i]
        if spec.entry != "market":
            if not np.isfinite(limit):
                continue
            expiry = available + pd.Timedelta(minutes=4 * spec.timeframe)
            end = idx.searchsorted(expiry)
            block = opening[start:end]
            hits = np.flatnonzero(
                block[:, 2] <= limit if d == 1 else block[:, 1] >= limit
            )
            busy_until = end - 1  # pending order reserves exposure even if never filled
            if not len(hits):
                continue
            entry_index = start + int(hits[0])
            # Worse of opening/limit is limit for a resting order; no positive improvement.
            entry = float(limit)
            at_open = d * (opening[entry_index, 0] - limit) <= 0
        else:
            entry_index = start
            entry = float(opening[start, 0] + d * costs.slippage)
            at_open = True
        stop, target = entry - d * risk, entry + d * risk * rr
        # A range-filled limit cannot claim a TP before its unknown fill time.
        if not at_open:
            a = closing[entry_index]
            stop_hit = a[2] <= stop if d == 1 else a[1] >= stop
            if stop_hit:
                exit_index, exit_price, reason = (
                    entry_index,
                    min(stop, a[0]) if d == 1 else max(stop, a[0]),
                    "SL_FILL_AMBIGUOUS",
                )
            elif entry_index + 1 < len(idx):
                exit_index, exit_price, reason = first_exit(
                    closing, entry_index + 1, d, stop, target
                )
            else:
                exit_index, exit_price, reason = entry_index, a[3], "END_OF_SAMPLE"
        else:
            exit_index, exit_price, reason = first_exit(
                closing, entry_index, d, stop, target
            )
        if not reason.startswith("TP"):
            exit_price -= d * costs.slippage
        nights = max(0, (idx[exit_index].date() - idx[entry_index].date()).days)
        fees = costs.units * (
            costs.commission_per_unit_roundtrip + costs.swap_per_unit_night * nights
        )
        gross = d * (exit_price - entry) * costs.units
        net = gross - fees
        # M1-close marked equity, then actual exit. Never use the exit bar's post-exit close.
        marks = (
            balance
            + d * (closing[entry_index:exit_index, 3] - entry) * costs.units
            - costs.units * costs.commission_per_unit_roundtrip
        )
        if costs.swap_per_unit_night:
            accrued_nights = (
                idx[entry_index:exit_index].normalize() - idx[entry_index].normalize()
            ).days
            marks -= (
                np.asarray(accrued_nights) * costs.units * costs.swap_per_unit_night
            )
        marks = np.append(marks, balance + net)
        peaks = np.maximum.accumulate(np.r_[peak, marks])[1:]
        max_dd = max(max_dd, float(np.max(peaks - marks)))
        peak = max(peak, float(np.max(marks)))
        # Range-filled orders have unknown entry-minute extrema too.
        path = closing[entry_index if at_open else entry_index + 1 : exit_index]
        adverse = (
            d * (path[:, 2 if d == 1 else 1] - entry) if len(path) else np.array([0.0])
        )
        favorable = (
            d * (path[:, 1 if d == 1 else 2] - entry) if len(path) else np.array([0.0])
        )
        balance += net
        busy_until = exit_index
        trades.append(
            {
                "entry_time": idx[entry_index],
                "exit_time": idx[exit_index],
                "signal_time": f.index[i] + pd.Timedelta(minutes=spec.timeframe),
                "direction": d,
                "entry": entry,
                "exit": exit_price,
                "stop": stop,
                "target": target,
                "risk": risk,
                "gross": gross,
                "fees": fees,
                "net": net,
                "r": net / (risk * costs.units),
                "reason": reason,
                "regime": f.regime.iloc[i],
                "mae_r_before_exit_minute": min(0.0, float(adverse.min()) / risk),
                "mfe_r_before_exit_minute": max(0.0, float(favorable.max()) / risk),
            }
        )
    columns = [
        "entry_time",
        "exit_time",
        "signal_time",
        "direction",
        "entry",
        "exit",
        "stop",
        "target",
        "risk",
        "gross",
        "fees",
        "net",
        "r",
        "reason",
        "regime",
        "mae_r_before_exit_minute",
        "mfe_r_before_exit_minute",
    ]
    return pd.DataFrame(trades, columns=columns), max_dd


def metrics(trades, equity_dd=None):
    if trades.empty:
        return {
            "trades": 0,
            "net": 0.0,
            "total_r": 0.0,
            "expectancy_r": None,
            "pf": None,
            "win_rate": None,
            "max_closed_dd": 0.0,
            "max_equity_dd": equity_dd,
            "recovery": None,
            "max_loss_streak": 0,
            "long_pf": None,
            "short_pf": None,
            "avg_trade": None,
        }
    values = trades.net.to_numpy(float)

    def pf(v):
        losses = -v[v < 0].sum()
        return float(v[v > 0].sum() / losses) if losses else None

    equity = np.r_[0, np.cumsum(values)]
    dd = float(np.max(np.maximum.accumulate(equity) - equity))
    streak = longest = 0
    for v in values:
        streak = streak + 1 if v < 0 else 0
        longest = max(longest, streak)
    return {
        "trades": len(values),
        "net": float(values.sum()),
        "total_r": float(trades.r.sum()),
        "expectancy_r": float(trades.r.mean()),
        "pf": pf(values),
        "win_rate": float((values > 0).mean()),
        "max_closed_dd": dd,
        "max_equity_dd": equity_dd,
        "recovery": float(values.sum() / equity_dd) if equity_dd else None,
        "max_loss_streak": longest,
        "long_pf": pf(values[trades.direction == 1]),
        "short_pf": pf(values[trades.direction == -1]),
        "avg_trade": float(values.mean()),
    }
