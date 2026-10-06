"""Strict, research-only C22 challengers; frozen Demo detector is never modified."""

import hashlib
import json

import pandas as pd

from scripts.research.campaign_signals import candidate_frame
from scripts.research.reward156_search import prepare_candidate, seeds
from scripts.research.reward156_tuning import closed_h4_ema, prepare_contract

# Insertion order is the predeclared parent/parameter/value search order.
DOMAINS = {
    "rsi_period": (7, 14, 21),
    "rsi_threshold": (25, 30, 35),
    "buy_ema": (50, 0),
    "sell_lookback": (24, 48, 96),
    "sell_ema": (0, 50, 200),
    "macro_span": (200, 100, 0),
    "buy_stop_atr": (1.0, 1.5, 2.0, 2.5),
    "buy_target_rr": (1.35, 1.5, 2.0),
    "buy_protect_mode": ("off", "break_even"),
    "stop_atr": (1.5, 2.0, 2.5),
    "sell_target": ("atr3", "r1.35", "r2"),
    "protect_mode": ("off", "break_even"),
    "daily_loss_limit": (0.1, 0.2),
    "max_daily_losses": (1, 2, 0),
    "cooldown_bars": (0, 2, 4),
    "entry_session": ("all", "avoid_rollover"),
    "risk_mode": ("static", "drawdown_steps"),
}
PINS = dict(strategy="reward156", formula="archived", buy_pause_drawdown=0.0, risk_cap=0.1)


def baseline_config():
    seed = seeds()[2]
    return {key: seed[key] for key in (*PINS, *DOMAINS) if key in seed} | dict(
        buy_ema=50, macro_span=200
    )


def validate(config):
    if not isinstance(config, dict) or set(config) != set(PINS) | set(DOMAINS):
        raise ValueError("unknown or missing candidate config keys")
    for key, value in config.items():
        allowed = DOMAINS.get(key, (PINS.get(key),))
        if not any(type(value) is type(choice) and value == choice for choice in allowed):
            raise ValueError("unsupported candidate value: " + key)


def config_id(config):
    validate(config)
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


def neighbors(config):
    validate(config)
    for key, values in DOMAINS.items():
        for value in values:
            if value != config[key]:
                yield key, value, dict(config, **{key: value})


def next_round(parents, seen, remaining):
    """Deduplicate before execution, truncate only by frozen traversal order."""
    catalog, known = [], set(seen)
    for parent in parents:
        for key, value, config in neighbors(parent):
            identity = config_id(config)
            if identity not in known and len(catalog) < remaining:
                known.add(identity)
                catalog.append(
                    dict(
                        id=identity,
                        parent=config_id(parent),
                        parameter=key,
                        value=value,
                        config=config,
                    )
                )
    return catalog


def prepare(bars, config):
    validate(config)
    # Canonical validation/ATR and rule construction; the old adapter's hardcoded
    # BUY EMA is intentionally not used for challenger signal generation.
    frame, _ = prepare_contract(
        bars, dict(strategy="reward156", macro_span=0, buy_pause_drawdown=0.0)
    )
    frame = candidate_frame(
        frame,
        "off",
        0.0,
        oscillator_spec=dict(
            period=config["rsi_period"],
            threshold=config["rsi_threshold"],
            trend_span=config["buy_ema"],
            side="buy",
            parent_lookback=config["sell_lookback"],
            parent_trend_span=config["sell_ema"],
        ),
        entry_session=config["entry_session"],
    )
    frame["raw_direction"] = frame.direction
    for column in (
        "macro_unavailable",
        "macro_blocked",
        "h4_warmup",
        "h4_incomplete",
        "h4_directional_mismatch",
    ):
        frame[column] = False
    if config["macro_span"]:
        span = config["macro_span"]
        ema = closed_h4_ema(bars, span)
        counts = bars.close.resample("4h", origin="start_day").count()
        published = pd.DataFrame(dict(complete=counts == 16, ready=(counts == 16).cumsum() >= span))
        published.index += pd.Timedelta(hours=4)
        state = published.reindex(bars.index + pd.Timedelta(minutes=15), method="ffill")
        state.index = bars.index
        active = frame.raw_direction != 0
        available = ema.notna()
        allowed = frame.direction * (frame.close - ema) > 0
        frame["macro_unavailable"] = active & ~available
        frame["macro_blocked"] = active & ~allowed
        # Mutually exclusive unavailable reasons: warmup takes precedence until
        # enough complete H4 bars exist; then an incomplete latest H4 fails closed.
        ready = state.ready.eq(True)
        frame["h4_warmup"] = active & ~available & ~ready
        frame["h4_incomplete"] = active & ~available & ready
        frame["h4_directional_mismatch"] = active & available & ~allowed
        frame.loc[~allowed, "direction"] = 0
    _, rules = prepare_candidate(bars, {k: v for k, v in config.items() if k != "buy_ema"})
    return frame, rules
