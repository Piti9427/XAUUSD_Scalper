"""Finite Reward156 research catalog, causal signals and profit/survival policy."""

from dataclasses import asdict
from itertools import combinations as pairs
import hashlib
import json

import numpy as np
import pandas as pd

from scripts.research.breakout_logic import Rules
from scripts.research.campaign_signals import candidate_frame
from scripts.research.reward156_tuning import closed_h4_ema, prepare_contract

POLICY = "profit_survival_v2"
GROUPS = {
    "signal": {
        "rsi_period": (7, 14),
        "rsi_threshold": (25, 30, 35),
        "sell_lookback": (24, 48, 96),
        "sell_ema": (0, 50, 200),
        "macro_span": (0, 100, 200),
    },
    "exit": {
        "buy_stop_atr": (1.0, 1.5, 2.0, 2.5),
        "stop_atr": (1.5, 2.0, 2.5),
        "buy_target_rr": (1.35, 1.5, 2.0),
        "sell_target": ("atr3", "r1.35", "r2"),
        "buy_protect_mode": ("off", "break_even"),
        "protect_mode": ("off", "break_even"),
    },
    "circuit": {
        "daily_loss_limit": (0.1, 0.2),
        "max_daily_losses": (0, 1, 2),
        "cooldown_bars": (0, 2, 4),
        "entry_session": ("all", "avoid_rollover"),
        "risk_mode": ("static", "drawdown_steps"),
    },
}


def config_id(candidate):
    behavior = {k: v for k, v in candidate.items() if k not in ("name", "group", "parent")}
    return hashlib.sha256(json.dumps(behavior, sort_keys=True).encode()).hexdigest()[:16]


def seeds():
    common = dict(
        strategy="reward156",
        formula="frozen",
        rsi_period=7,
        rsi_threshold=35,
        sell_lookback=48,
        sell_ema=0,
        macro_span=100,
        buy_pause_drawdown=0.0,
        stop_atr=2.5,
        buy_stop_atr=2.5,
        buy_target_rr=1.35,
        sell_target="r1.35",
        protect_mode="off",
        buy_protect_mode="off",
        daily_loss_limit=0.2,
        max_daily_losses=0,
        cooldown_bars=0,
        entry_session="all",
        risk_mode="static",
        risk_cap=0.1,
    )
    return [
        dict(common, name="reward156_h4_ema100"),
        dict(common, name="reward156_h4_ema200", macro_span=200),
        dict(
            common,
            name="circuit22",
            formula="archived",
            rsi_period=14,
            rsi_threshold=25,
            sell_lookback=96,
            sell_ema=50,
            macro_span=0,
            buy_stop_atr=1.5,
            buy_target_rr=2.0,
            sell_target="atr3",
            protect_mode="break_even",
            daily_loss_limit=0.1,
            max_daily_losses=1,
        ),
        dict(
            common,
            name="fine6",
            formula="archived",
            rsi_period=14,
            rsi_threshold=25,
            sell_lookback=96,
            sell_ema=200,
            macro_span=0,
            buy_stop_atr=1.0,
            buy_target_rr=2.0,
            sell_target="atr3",
            protect_mode="break_even",
            daily_loss_limit=0.1,
            max_daily_losses=1,
        ),
        dict(
            common,
            name="unpaused28",
            formula="archived",
            sell_lookback=24,
            sell_ema=200,
            macro_span=0,
            stop_atr=1.5,
            buy_stop_atr=1.5,
            daily_loss_limit=0.1,
            max_daily_losses=1,
            risk_mode="drawdown_steps",
        ),
    ]


def variants(seed):
    result = []
    for group, domain in GROUPS.items():
        for key, values in domain.items():
            for value in values:
                if value != seed[key]:
                    c = dict(seed, **{key: value}, group=group, parent=config_id(seed))
                    c["name"] = "variant_" + config_id(c)
                    result.append(c)
    if len(result) > 27:
        raise ValueError("one-factor budget exceeded")
    return result


def combinations(seed, chosen):
    by_group = {c["group"]: c for c in chosen}
    if set(by_group) != set(GROUPS):
        raise ValueError("one winner per factor group required")
    result = []
    for groups in [*pairs(GROUPS, 2), tuple(GROUPS)]:
        c = dict(seed)
        for group in groups:
            changed = [k for k in GROUPS[group] if seed[k] != by_group[group][k]]
            if len(changed) != 1:
                raise ValueError("group choice is not one-factor")
            key = changed[0]
            c[key] = by_group[group][key]
        c.update(group="+".join(groups), parent=config_id(seed))
        c["name"] = "combined_" + config_id(c)
        result.append(c)
    return result


def prepare_candidate(bars, contract):
    if contract["strategy"] == "trial30" or "formula" not in contract:
        return prepare_contract(bars, contract)
    # Validation and ATR come from canonical detector. Keep frozen RSI semantics.
    frame, _ = prepare_contract(
        bars, dict(strategy="reward156", macro_span=0, buy_pause_drawdown=0.0)
    )
    lookback = contract["sell_lookback"]
    if contract["formula"] == "archived":
        frame = candidate_frame(
            frame,
            "off",
            0.0,
            oscillator_spec=dict(
                period=contract["rsi_period"],
                threshold=contract["rsi_threshold"],
                trend_span=50,
                side="buy",
                parent_lookback=lookback,
                parent_trend_span=contract["sell_ema"],
            ),
            entry_session=contract["entry_session"],
        )
    elif contract["formula"] == "frozen":
        frame["hh"] = frame.high.rolling(lookback).max().shift(1)
        frame["ll"] = frame.low.rolling(lookback).min().shift(1)
        delta = frame.close.diff()
        gain = delta.clip(lower=0).rolling(contract["rsi_period"]).mean()
        loss = (-delta.clip(upper=0)).rolling(contract["rsi_period"]).mean()
        rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
        rsi = rsi.mask((gain == 0) & (loss == 0), 50.0)
        average = frame.ema50
        threshold = contract["rsi_threshold"]
        buy = (
            (rsi.shift(1) < threshold)
            & (rsi >= threshold)
            & (delta > 0)
            & (frame.close > average)
            & (average > average.shift(4))
        )
        sell = frame.close < frame.ll
        if contract["sell_ema"]:
            ema = frame.close.ewm(
                span=contract["sell_ema"], adjust=False, min_periods=contract["sell_ema"]
            ).mean()
            sell &= (frame.close < ema) & (ema < ema.shift(4))
        frame["direction"] = np.select([sell, buy & ~sell], [-1, 1], 0)
        if contract["entry_session"] == "avoid_rollover":
            frame.loc[(frame.index + pd.Timedelta(minutes=15)).hour >= 21, "direction"] = 0
    else:
        raise ValueError("unknown RSI formula")
    frame["raw_direction"] = frame.direction
    frame["macro_unavailable"] = False
    frame["macro_blocked"] = False
    if contract["macro_span"]:
        ema = closed_h4_ema(bars, contract["macro_span"])
        allowed = ((frame.direction == 1) & (frame.close > ema)) | (
            (frame.direction == -1) & (frame.close < ema)
        )
        frame["macro_unavailable"] = (frame.direction != 0) & ema.isna()
        frame["macro_blocked"] = (frame.direction != 0) & ~allowed
        frame.loc[~allowed, "direction"] = 0
    target = contract["sell_target"]
    rules = Rules(
        stop_atr=contract["stop_atr"],
        buy_stop_atr=contract["buy_stop_atr"],
        target_atr=3.0,
        target_rr=0.0 if target == "atr3" else float(target[1:]),
        buy_target_rr=contract["buy_target_rr"],
        protect_mode=contract["protect_mode"],
        buy_protect_mode=contract["buy_protect_mode"],
        protect_after_r=1.0,
        risk_cap=contract["risk_cap"],
        daily_loss_limit=contract["daily_loss_limit"],
        sizing_mode="fixed",
        buy_pause_drawdown=0.0,
        risk_mode=contract["risk_mode"],
        max_daily_losses=contract["max_daily_losses"],
        cooldown_bars=contract["cooldown_bars"],
    )
    return frame, rules


def cell_gates(metrics, peers, window, *, holdout=False):
    full = window == "full"
    gates = dict(
        net_floor=metrics["net_usd"] > 0
        if holdout
        else metrics["net_usd"] >= (50 if full else -20),
        beats_controls=all(metrics["net_usd"] > p["net_usd"] for p in peers)
        if full or holdout
        else True,
        dd=metrics["max_dd_pct"] <= 45,
        trade_count=metrics["trades"] >= (60 if full and not holdout else 10),
        both_sides=metrics["buy_trades"] > 0 and metrics["sell_trades"] > 0
        if full and not holdout
        else True,
        risk=metrics["max_admitted_risk_pct"] <= 10,
        survival=not metrics["bankrupt"] and metrics["final_balance"] > 0,
        terminal=not metrics["terminal_risk_blockage"],
    )
    # Fresh replay balances can be NumPy scalars; persist portable policy flags.
    return {key: bool(value) for key, value in gates.items()}


def rank(candidate, rows):
    selected = [
        r
        for r in rows
        if r["contract"] == candidate["name"]
        and r["window"] == "full"
        and r["cost_view"] in ("no_swap", "swap")
    ]
    return (
        -sum(all(r["gates"].values()) for r in selected),
        -min(r["metrics"]["net_usd"] for r in selected),
        max(r["metrics"]["max_dd_pct"] for r in selected),
        config_id(candidate),
    )


def serialize_rules(bars, candidate):
    return asdict(prepare_candidate(bars, candidate)[1])


def variant_catalog(chosen, existing):
    """Deduplicate execution while retaining each seed's full factor references."""
    canonical = {config_id(c): c for c in existing}
    generated, references = [], {}
    for seed in chosen:
        refs = []
        for variant in variants(seed):
            identity = config_id(variant)
            if identity not in canonical:
                canonical[identity] = variant
                generated.append(variant)
            # Metadata belongs to this factor experiment; execution name is shared.
            refs.append(dict(variant, name=canonical[identity]["name"]))
        references[config_id(seed)] = refs
    return generated, references
