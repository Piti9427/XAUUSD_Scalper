"""SMC frames into immutable canonical tick replay; mandatory modeled swap."""

from __future__ import annotations

from decimal import Decimal
import math
from types import FunctionType

import numpy as np
import pandas as pd

from scripts.strategy import pure_b1_bars
from scripts.research.breakout_models import Costs, Rules
from scripts.research.breakout_replay import replay
from scripts.research.rollover import SwapPolicy
from scripts.research.smc_challenger_signals import CONTRACT, validate_config


def prepared_entries(frame, mode):
    """Keep causal sweep anchors; canonical immediate transform overwrites them."""
    if mode != "immediate":
        raise ValueError("SMC supports prepared immediate entries only")
    output = frame.copy()
    output["entry_boundary"] = np.where(frame.direction == 1, frame.hh, frame.ll)
    return output


def prepared_replay(*args, **kwargs):
    """Reuse exact event-loop bytecode with an isolated entry-transform binding.

    No source copy, monkeypatch or shared global mutation. Frozen replay has no
    prepared-M15 seam; a private globals dictionary injects only that pure seam.
    Defaults/keyword defaults remain canonical. Differential tests guard reuse.
    """
    bound = FunctionType(
        replay.__code__,
        dict(replay.__globals__, _entry_signals=prepared_entries),
        replay.__name__,
        replay.__defaults__,
        replay.__closure__,
    )
    bound.__kwdefaults__ = replay.__kwdefaults__
    return bound(*args, **kwargs)


def smc_rules(config=CONTRACT):
    validate_config(config)
    return Rules(
        stop_mode="structure",
        target_rr=config["target_rr"],
        risk_cap=config["risk_cap"],
        daily_loss_limit=config["daily_loss_limit"],
        max_daily_losses=config["max_daily_losses"],
        entry_mode="immediate",
        protect_mode="off",
        entry_guard="off",
        sizing_mode="fixed",
        buy_pause_drawdown=0.0,
        risk_mode="static",
        min_depth_atr=0.0,
        failed_closes=0,
        reset_after_exit=False,
        stagnant_bars=0,
        cooldown_bars=0,
        session_mode="all",
        holding_mode="legacy",
    )


def validate_broker(broker):
    required = (
        "swap_mode",
        "swap_long",
        "swap_short",
        "point",
        "swap_rollover3days",
        "trade_tick_size",
        "trade_contract_size",
        "volume_min",
        "volume_max",
        "volume_step",
        "leverage",
    )
    if not isinstance(broker, dict) or any(k not in broker for k in required):
        raise ValueError("missing broker/swap metadata")
    if any(type(broker[k]) not in (int, float) or not math.isfinite(broker[k]) for k in required):
        raise ValueError("invalid broker/swap metadata")
    if broker["swap_mode"] != 1 or broker["swap_rollover3days"] not in (1, 2, 3, 4, 5):
        raise ValueError("unsupported swap mode/calendar")
    for key in required[3:]:
        if broker[key] <= 0:
            raise ValueError("nonpositive broker metadata")
    return SwapPolicy.from_broker(broker)


def validate_tape(ticks):
    if len(ticks) != 3:
        raise ValueError("time/bid/ask tape required")
    times, bid, ask = ticks
    if not len(times) or not (len(times) == len(bid) == len(ask)):
        raise ValueError("empty/unequal tape")
    if any(np.ndim(a) != 1 for a in ticks) or not np.issubdtype(times.dtype, np.integer):
        raise ValueError("one-dimensional epoch millisecond tape required")
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
            raise ValueError("invalid tick chronology/quotes")


def replay_signals(frame, ticks, broker, costs, *, start, end, config=CONTRACT):
    """Replay a causal signal frame on one scenario's first post-close quotes.

    Quote spread is read only at the execution instant; no later tick determines
    the candidate. SELL Bid wick becomes Ask-side anchor including stress spread.
    """
    validate_config(config)
    policy = validate_broker(broker)
    if not isinstance(costs, Costs):
        raise ValueError("explicit validated cost scenario required")
    validate_tape(ticks)
    pure_b1_bars(frame)
    needed = {"atr", "hh", "ll", "direction", "stop_low", "stop_high", "setup_id"}
    if not needed.issubset(frame.columns) or not frame.direction.isin((-1, 0, 1)).all():
        raise ValueError("invalid SMC replay frame")
    active = frame.loc[frame.direction != 0]
    if active.setup_id.eq("").any() or active.setup_id.duplicated().any():
        raise ValueError("missing/duplicate setup identity")
    adapted = frame.copy()
    times, bid, ask = ticks
    left, right = np.searchsorted(times, [start.value // 10**6, end.value // 10**6])
    missing = []
    for stamp, row in active.iterrows():
        closed = stamp + pd.Timedelta(minutes=15)
        if not start <= closed < end:
            continue
        anchor = row.stop_low if row.direction == 1 else row.stop_high
        if not math.isfinite(anchor) or anchor <= 0 or not math.isfinite(row.atr) or row.atr <= 0:
            raise ValueError("invalid SMC stop/ATR")
        index = int(np.searchsorted(times, closed.value // 10**6))
        if index < left or index >= right:
            missing.append(
                dict(
                    signal_close_utc=closed.isoformat(),
                    direction=int(row.direction),
                    reason="no_quote",
                    setup_id=row.setup_id,
                )
            )
            continue
        if row.direction == -1:
            spread = (
                Decimal(str(float(ask[index])))
                - Decimal(str(float(bid[index])))
                + Decimal(str(costs.extra_spread))
            )
            adapted.loc[stamp, "stop_high"] = float(Decimal(str(anchor)) + spread)
    result = prepared_replay(
        adapted,
        ticks,
        broker,
        smc_rules(config),
        costs,
        start=start,
        end=end,
        swap_policy=policy,
        capture_events=True,
        capture_context=True,
    )
    result["no_quote_events"] = missing
    result["signal_count"] += len(missing)  # Canonical replay omits beyond-tape candidates.
    audit_result(result)
    result["swap_debits"] = swap_debits(result, broker)
    return result


def swap_debits(result, broker):
    """Auditable rollover attribution, including explicit zero-rate short charges."""
    policy = validate_broker(broker)
    schedule = policy.schedule(
        pd.Timestamp(result["start_utc"]), pd.Timestamp(result["end_exclusive_utc"])
    )
    charges = []
    for trade in result["ledger"]:
        entry = pd.Timestamp(trade["entry_time_utc"]).value // 10**6
        exit_ms = pd.Timestamp(trade["exit_time_utc"]).value // 10**6
        stamps = schedule.times[(schedule.times > entry) & (schedule.times <= exit_ms)]
        accrued = schedule.amount(
            entry, stamps, trade["direction"], broker["trade_contract_size"] * trade["volume"]
        )
        amounts = np.diff(np.r_[0.0, accrued])
        for stamp, amount in zip(stamps, amounts):
            charges.append(
                dict(
                    entry_time_utc=trade["entry_time_utc"],
                    rollover_utc=pd.Timestamp(int(stamp), unit="ms", tz="UTC").isoformat(),
                    direction=trade["direction"],
                    amount_usd=float(amount),
                )
            )
    if not math.isclose(sum(c["amount_usd"] for c in charges), result["swap_usd"], abs_tol=1e-7):
        raise ValueError("swap debit attribution mismatch")
    return charges


def audit_result(result):
    """Cashflow, fixed lot, single-position and initial risk contract checks."""
    ledger = result["ledger"]
    if not math.isclose(sum(p["net"] for p in ledger), result["net_usd"], abs_tol=1e-7):
        raise ValueError("ledger cashflow mismatch")
    previous_exit = None
    for trade in ledger:
        entry, exit_time = (
            pd.Timestamp(trade["entry_time_utc"]),
            pd.Timestamp(trade["exit_time_utc"]),
        )
        if trade["volume"] != 0.01 or trade["risk_usd"] > trade["entry_equity"] * 0.1 + 1e-9:
            raise ValueError("trade volume/risk contract violation")
        if entry > exit_time or (previous_exit is not None and entry < previous_exit):
            raise ValueError("overlapping/reversed trade lifecycle")
        if "swap_usd" not in trade:
            raise ValueError("missing modeled swap ledger")
        previous_exit = exit_time
