"""Causal closed-M15 SMC challenger. No execution or notification dependencies."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.strategy import pure_b1_bars
from scripts.research.reward156_tuning import closed_h4_ema
from scripts.smc.structure import (
    StructureState,
    StructureEventKind,
    apply_close_break,
    find_fractals_5bar,
    measure_displacement,
    detect_fvg,
)
from scripts.smc.types import Direction

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config/smc-challenger.json"
CONTRACT = {
    "version": "smc_m15_v1",
    "research_only": True,
    "initial_equity": 200,
    "volume": 0.01,
    "risk_cap": 0.1,
    "daily_loss_limit": 0.1,
    "max_daily_losses": 1,
    "macro_span": 200,
    "min_body_ratio": 0.45,
    "min_fvg_gap": 0.3,
    "sweep_to_choch_bars": 8,
    "retest_bars": 4,
    "target_rr": 2.0,
    "calendar": "conservative_utc_96_bars_v1",
    "swap_required": True,
    "views": ["base-current-spec-swap", "stress-current-spec-swap"],
}


def validate_config(config):
    """One frozen prototype, not an implicit parameter tuning surface."""
    if not isinstance(config, dict) or set(config) != set(CONTRACT):
        raise ValueError("unknown or missing SMC contract keys")
    if any(type(config[k]) is not type(v) or config[k] != v for k, v in CONTRACT.items()):
        raise ValueError("unsupported SMC contract; version a new research protocol")
    return config


def contract_id(config=CONTRACT):
    validate_config(config)
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


def prepare_signals(bars, config=CONTRACT):
    """Return one row per sealed Bid M15 bar, indexed by bar open UTC."""
    validate_config(config)
    frame = pure_b1_bars(bars)[["open", "high", "low", "close", "atr"]]
    frame["direction"] = 0
    frame["hh"] = frame.high
    frame["ll"] = frame.low
    frame["stop_low"] = np.nan
    frame["stop_high"] = np.nan
    frame["macro_ema"] = closed_h4_ema(bars, config["macro_span"])
    frame = frame.join(liquidity_pools(bars))
    flags_high, flags_low = find_fractals_5bar(bars)
    values = frame[["open", "high", "low", "close"]].to_numpy()
    stamps = frame.index.as_unit("ms").asi8
    columns = {
        "structure_event": ["NONE"] * len(frame),
        "fvg_published": [False] * len(frame),
        "signal_reason": ["no_setup"] * len(frame),
        "setup_id": [""] * len(frame),
        "sweep_utc": [""] * len(frame),
        "choch_utc": [""] * len(frame),
        "fvg_utc": [""] * len(frame),
        "pivot_confirmed_utc": [""] * len(frame),
        "gap_low": [np.nan] * len(frame),
        "gap_high": [np.nan] * len(frame),
    }
    highs, lows, broken = [], [], set()
    state = StructureState.initial()
    pending = None
    cid = contract_id(config)
    directions = np.zeros(len(frame), dtype=int)
    stop_lows, stop_highs = np.full(len(frame), np.nan), np.full(len(frame), np.nan)

    def close_time(i):
        return (frame.index[i] + pd.Timedelta(minutes=15)).isoformat()

    for i, (opened, high, low, closed) in enumerate(values):
        # No setup may cross an absent bar or session boundary gap.
        if i and stamps[i] - stamps[i - 1] != 900000:
            pending = None
        if i >= 4 and stamps[i] - stamps[i - 4] == 3600000:
            pivot = i - 2
            if flags_high[pivot]:
                highs.append((pivot, values[pivot, 1]))
                columns["pivot_confirmed_utc"][i] = close_time(i)
            if flags_low[pivot]:
                lows.append((pivot, values[pivot, 2]))
                columns["pivot_confirmed_utc"][i] = close_time(i)

        # Protected break has priority; otherwise latest unbroken confirmed swing.
        candidates = []
        for side, pivots in ((1, highs), (-1, lows)):
            if pivots:
                pivot, price = pivots[-1]
                if (side, pivot) not in broken and side * (closed - price) > 0:
                    candidates.append((side, pivot, price))
            if state.protected_index is not None and state.protected_price is not None:
                protected = (state.protected_index, state.protected_price)
                wanted = 1 if state.bias.value == "BEARISH" else -1
                if (
                    side == wanted
                    and (side, protected[0]) not in broken
                    and side * (closed - protected[1]) > 0
                ):
                    candidates.insert(0, (side, *protected))
        event_kind, event_side = "NONE", 0
        if candidates:
            side, pivot, price = candidates[0]
            if len(candidates) > 1 and candidates[0][2] != state.protected_price:
                prefer = 1 if closed >= (values[i - 1, 3] if i else opened) else -1
                side, pivot, price = next((c for c in candidates if c[0] == prefer), candidates[0])
            opposites = lows if side == 1 else highs
            between = [(j, p) for j, p in opposites if pivot < j < i]
            state, event = apply_close_break(
                state,
                break_side="above" if side == 1 else "below",
                broken_swing_price=float(price),
                break_index=i,
                opposite_pivots_between=between,
            )
            broken.add((side, pivot))
            event_kind, event_side = event.kind.value, side
        columns["structure_event"][i] = event_kind

        row = frame.iloc[i]
        pools = [
            (name, row[name], row[name + "_published_utc"])
            for name in ("asian_low", "pdl", "asian_high", "pdh")
            if pd.notna(row[name])
        ]
        sweeps = []
        for name, price, publication in pools:
            side = 1 if name in ("asian_low", "pdl") else -1
            if (
                (low < price and closed >= price)
                if side == 1
                else (high > price and closed <= price)
            ):
                sweeps.append((side, name, float(price), publication))
        if len({s[0] for s in sweeps}) > 1:
            pending = None
            columns["signal_reason"][i] = "conflicting_sweeps"
            continue
        if sweeps:
            side, name, price, publication = sweeps[0]
            pending = dict(
                side=side,
                sweep=i,
                wick=low if side == 1 else high,
                pool=name,
                price=price,
                publication=publication,
                choch=None,
                fvg=None,
            )
            columns["signal_reason"][i] = "sweep"
            continue
        if pending is None:
            continue
        side = pending["side"]
        if side * (closed - pending["wick"]) < 0:
            columns["signal_reason"][i] = "wick_invalidated"
            pending = None
            continue
        if pending["choch"] is None:
            age = i - pending["sweep"]
            if age > config["sweep_to_choch_bars"]:
                columns["signal_reason"][i] = "choch_expired"
                pending = None
            elif event_kind == StructureEventKind.CHOCH.value and event_side == side:
                displacement, _, _ = measure_displacement(
                    opened, high, low, closed, config["min_body_ratio"]
                )
                if displacement and side * (closed - opened) > 0:
                    pending["choch"] = i
                    columns["signal_reason"][i] = "choch"
            continue
        if pending["fvg"] is None:
            choch = pending["choch"]
            valid = i == choch + 1 and i >= 2 and stamps[i] - stamps[i - 2] == 1800000
            gap = (
                detect_fvg(
                    bars.iloc[i - 2].to_dict(),
                    bars.iloc[i - 1].to_dict(),
                    bars.iloc[i].to_dict(),
                    Direction.BUY if side == 1 else Direction.SELL,
                    config["min_fvg_gap"],
                )
                if valid
                else (False, 0, 0, 0)
            )
            if not gap[0]:
                columns["signal_reason"][i] = "no_fvg"
                pending = None
                continue
            pending.update(fvg=i, gap_low=gap[2], gap_high=gap[1])
            identity = [
                cid,
                side,
                pending["pool"],
                pending["publication"],
                close_time(pending["sweep"]),
                close_time(choch),
                close_time(i),
            ]
            pending["id"] = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
            columns["fvg_published"][i] = True
            columns["signal_reason"][i] = "fvg"
            continue
        if i - pending["fvg"] > config["retest_bars"]:
            columns["signal_reason"][i] = "retest_expired"
            pending = None
            continue
        if pending["gap_low"] <= closed <= pending["gap_high"]:
            columns["setup_id"][i] = pending["id"]
            for col, key in (("sweep_utc", "sweep"), ("choch_utc", "choch"), ("fvg_utc", "fvg")):
                columns[col][i] = close_time(pending[key])
            columns["gap_low"][i], columns["gap_high"][i] = pending["gap_low"], pending["gap_high"]
            allowed = pd.notna(row.macro_ema) and side * (closed - row.macro_ema) > 0
            columns["signal_reason"][i] = (
                "candidate"
                if allowed
                else "macro_unavailable"
                if pd.isna(row.macro_ema)
                else "macro_blocked"
            )
            if allowed and pd.notna(row.atr) and row.atr > 0:
                directions[i] = side
                stop_lows[i] = pending["wick"] if side == 1 else np.nan
                stop_highs[i] = pending["wick"] if side == -1 else np.nan
            pending = None  # Exactly one attempt; replay rejection cannot revive it.
    frame["direction"], frame["stop_low"], frame["stop_high"] = directions, stop_lows, stop_highs
    for column, data in columns.items():
        frame[column] = data
    return frame


def liquidity_pools(bars):
    """Conservative declared calendar: PDH/PDL requires all96 UTC slots.

    No inferred holidays/rollover gaps. Asian requires all28 slots. A missing
    session disables only that pool. Incomplete most-recent day is never skipped.
    """
    pure_b1_bars(bars)
    out = pd.DataFrame(index=bars.index)
    for name in ("asian_low", "asian_high", "pdl", "pdh"):
        out[name] = np.nan
        out[name + "_published_utc"] = ""
    previous = None
    for day, group in bars.groupby(bars.index.normalize(), sort=True):
        if previous is not None:
            prev_day, prev = previous
            expected = pd.date_range(prev_day, periods=96, freq="15min")
            if prev.index.equals(expected):
                for name, price in (("pdh", prev.high.max()), ("pdl", prev.low.min())):
                    out.loc[group.index, name] = float(price)
                    out.loc[group.index, name + "_published_utc"] = (
                        prev_day + pd.Timedelta(days=1)
                    ).isoformat()
        asian = group.loc[group.index < day + pd.Timedelta(hours=7)]
        if asian.index.equals(pd.date_range(day, periods=28, freq="15min")):
            # A row is observed at its close, including06:45 published07:00.
            available = group.index[
                group.index + pd.Timedelta(minutes=15) >= day + pd.Timedelta(hours=7)
            ]
            for name, price in (("asian_high", asian.high.max()), ("asian_low", asian.low.min())):
                out.loc[available, name] = float(price)
                out.loc[available, name + "_published_utc"] = (
                    day + pd.Timedelta(hours=7)
                ).isoformat()
        previous = day, group
    return out


class SignalCache:
    """Full causal prefix cache; chunk seams never replace sealed observations."""

    def __init__(self, config=CONTRACT):
        self.config = dict(validate_config(config))
        self.bars = None

    def append(self, bars):
        pure_b1_bars(bars)
        bars = bars[["open", "high", "low", "close"]].copy()
        if self.bars is not None:
            old = self.bars
            overlap = old.index.intersection(bars.index)
            covered = old.index[old.index >= bars.index[0]]
            if (
                not covered.isin(bars.index).all()
                or not bars.index[bars.index <= old.index[-1]].isin(old.index).all()
            ):
                raise ValueError("bar cache omitted sealed observations")
            if not old.loc[overlap].equals(bars.loc[overlap]):
                raise ValueError("bar cache divergence")
            bars = pd.concat([old, bars.loc[bars.index > old.index[-1]]])
        self.bars = bars
        return prepare_signals(bars, self.config)
