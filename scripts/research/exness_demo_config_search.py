"""Search Pure B1 signal configs on saved Exness Bid/Ask ticks.

Costs are the tape's Bid/Ask spread and the published Standard commission of 0.
No hypothetical 0.10R fee, no added slippage, and no swap accrual: historical
swap entitlement was not observed. Fixed 0.01 lot, 10% equity cap, 40% daily
loss, no recovery. This does not authorize a Demo order.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.pure_b1.decision import round_level
from scripts.pure_b1.quote_time import FRESH_QUOTE, first_tick
from scripts.research.b1_hybrid_six_month import Replay
from scripts.research.pure_b1_target_replay import (
    END,
    START,
    _bind_flat_day_start,
    _load_inputs,
    _mark_flat,
)

SELECT_END = pd.Timestamp("2026-06-28", tz="UTC")
MIN_SELECT_TRADES = 8


def signal_frame(bars: pd.DataFrame, *, donchian: int, rsi_mode: str, use_ema50: bool) -> pd.DataFrame:
    frame = bars[["open", "high", "low", "close"]].astype(float).copy()
    frame["hh"] = frame.high.rolling(donchian).max().shift(1)
    frame["ll"] = frame.low.rolling(donchian).min().shift(1)
    delta = frame.close.diff()
    gain = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
    relative_strength = gain / loss.replace(0, np.nan)
    frame["rsi"] = 100 - 100 / (1 + relative_strength)
    frame["ema50"] = frame.close.ewm(span=50, adjust=False).mean()
    prior_close = frame.close.shift()
    true_range = pd.concat(
        [
            frame.high - frame.low,
            (frame.high - prior_close).abs(),
            (frame.low - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr"] = true_range.rolling(14).mean()
    ready = frame[["hh", "ll", "rsi", "atr"]].notna().all(axis=1)
    if use_ema50:
        ready = ready & frame["ema50"].notna()
    direction = np.zeros(len(frame), dtype=int)
    close = frame.close.to_numpy()
    hh = frame.hh.to_numpy()
    ll = frame.ll.to_numpy()
    rsi = frame.rsi.to_numpy()
    ema50 = frame.ema50.to_numpy()
    ready_np = ready.to_numpy()
    for i in np.flatnonzero(ready_np):
        buy_break = close[i] > hh[i]
        sell_break = close[i] < ll[i]
        if use_ema50:
            buy_break = buy_break and close[i] > ema50[i]
            sell_break = sell_break and close[i] < ema50[i]
        if rsi_mode == "band_30_70":
            buy_break = buy_break and 30 < rsi[i] < 70
            sell_break = sell_break and 30 < rsi[i] < 70
        elif rsi_mode == "archived_75_25":
            buy_break = buy_break and rsi[i] <= 75
            sell_break = sell_break and rsi[i] >= 25
        elif rsi_mode != "off":
            raise ValueError(rsi_mode)
        if buy_break:
            direction[i] = 1
        elif sell_break:
            direction[i] = -1
    frame["direction"] = direction
    return frame


def configs():
    rows = []
    for donchian in (20, 30, 40):
        for rsi_mode in ("band_30_70", "archived_75_25", "off"):
            for use_ema50 in (True, False):
                for target_atr in (6.25, 4.0, 3.0):
                    rows.append(
                        {
                            "donchian": donchian,
                            "rsi_mode": rsi_mode,
                            "use_ema50": use_ema50,
                            "stop_atr": 2.5,
                            "target_atr": target_atr,
                        }
                    )
    return rows


def run_config(bars, ticks, broker, spec, *, start, end):
    frame = signal_frame(
        bars,
        donchian=spec["donchian"],
        rsi_mode=spec["rsi_mode"],
        use_ema50=spec["use_ema50"],
    )
    times, bid, ask = ticks
    engine = Replay(
        times,
        bid,
        ask,
        broker,
        cost_scenario=False,
        apply_swap=False,
        entry_fee_r=0.0,
        entry_stress_price=0.0,
        signal_day_start=False,
        boundary_day_start_only=True,
        day_quota_limit=None,
        tick_rounder=lambda price, grid, direction: round_level(price, grid, direction),
        stop_atr=spec["stop_atr"],
        target_atr=spec["target_atr"],
    )
    previous = 0
    signal_events = 0
    flat_since_ms = int(start.value // 10**6)
    direction = frame.direction.to_numpy()
    atr = frame.atr.to_numpy()
    for index in np.flatnonzero(direction != 0):
        signal_close = frame.index[index] + pd.Timedelta(minutes=15)
        if not start <= signal_close < end:
            continue
        bar_close_ms = int(signal_close.value // 10**6)
        tick_index, quote_reason = first_tick(times, bar_close_ms, FRESH_QUOTE)
        if tick_index is None:
            key = "tick_gap" if quote_reason == "missing_quote" else "late_quote"
            engine.rejections[key] += 1
            continue
        engine.advance(previous, tick_index + 1)
        previous = tick_index + 1
        flat_since_ms = _mark_flat(engine, flat_since_ms, int(times[tick_index]))
        flat_since_ms = _bind_flat_day_start(
            engine, tick_ms=int(times[tick_index]), flat_since_ms=flat_since_ms
        )
        signal_events += 1
        engine.on_signal(tick_index, int(direction[index]), 0, float(atr[index]))
        flat_since_ms = _mark_flat(engine, flat_since_ms, int(times[tick_index]))
    engine.advance(previous, len(times))
    if engine.legs:
        engine._close_basket(len(times) - 1, "END_OF_SAMPLE")
    return {
        **spec,
        "start_utc": start.isoformat(),
        "end_exclusive_utc": end.isoformat(),
        "initial_balance": 200.0,
        "final_balance": engine.balance,
        "return_pct": (engine.balance / 200.0 - 1) * 100,
        "trades": engine.basket_count,
        "recovery_count": engine.recovery_count,
        "signal_events": signal_events,
        "max_tick_equity_dd_pct": engine.max_dd * 100,
        "cost_cap_rejections": engine.rejections["margin_proxy"],
        "daily_loss_rejections": engine.rejections["daily_loss"],
        "late_quote": engine.rejections["late_quote"],
        "commission_per_lot": 0.0,
        "hypothetical_fee_r": 0.0,
        "entry_stress_price": 0.0,
        "apply_swap": False,
        "order_api_called": False,
    }


def _slice_ticks(ticks, start, end):
    times, bid, ask = ticks
    left, right = np.searchsorted(times, [start.value // 10**6, end.value // 10**6])
    return [values[left:right] for values in (times, bid, ask)]


def _rank(rows):
    eligible = [row for row in rows if row["trades"] >= MIN_SELECT_TRADES]
    pool = eligible or rows
    return sorted(
        pool,
        key=lambda row: (row["final_balance"], -row["max_tick_equity_dd_pct"], row["trades"]),
        reverse=True,
    ), bool(eligible)


def main():
    baseline = Path("data/b1_hybrid_baseline_6mo_fixed_2026_09_28")
    capture = Path("data/b1_hybrid_exness_6mo_fixed_2026_09_28")
    output = Path("data/b1_exness_demo_config_search_2026_09_29")
    if output.exists():
        raise SystemExit(f"output exists: {output}")
    bars, ticks, broker = _load_inputs(baseline, capture)
    bars = bars[["open", "high", "low", "close"]]
    core = {
        "donchian": 30,
        "rsi_mode": "band_30_70",
        "use_ema50": True,
        "stop_atr": 2.5,
        "target_atr": 6.25,
    }
    calibration = run_config(bars, ticks, broker, core, start=START, end=END)
    if abs(calibration["final_balance"] - 132.98) > 0.05 or calibration["trades"] != 4:
        raise SystemExit(f"calibration missed the saved Demo replay: {calibration}")
    print(json.dumps({"calibration": "pass", "final_balance": calibration["final_balance"]}), flush=True)

    select_ticks = _slice_ticks(ticks, START, SELECT_END)
    confirm_ticks = _slice_ticks(ticks, SELECT_END, END)
    selected_rows = []
    for spec in configs():
        row = run_config(bars, select_ticks, broker, spec, start=START, end=SELECT_END)
        selected_rows.append(row)
        print(
            json.dumps(
                {
                    "window": "select",
                    "rsi_mode": spec["rsi_mode"],
                    "use_ema50": spec["use_ema50"],
                    "donchian": spec["donchian"],
                    "target_atr": spec["target_atr"],
                    "return_pct": row["return_pct"],
                    "trades": row["trades"],
                }
            ),
            flush=True,
        )
    ranked, used_trade_floor = _rank(selected_rows)
    winner = ranked[0]
    confirmation = run_config(
        bars,
        confirm_ticks,
        broker,
        {key: winner[key] for key in core},
        start=SELECT_END,
        end=END,
    )
    output.mkdir()
    payload = {
        "cost": {
            "spread": "saved Exness Bid/Ask ticks",
            "commission_per_lot": 0.0,
            "commission_source": "published Standard tariff, not a deal ledger",
            "hypothetical_fee_r": 0.0,
            "slippage_added": 0.0,
            "swap_applied": False,
            "historical_swap_entitlement": "missing",
            "broker_fills": "missing",
        },
        "selection": {
            "window": [START.isoformat(), SELECT_END.isoformat()],
            "rule": f"highest final balance with at least {MIN_SELECT_TRADES} trades",
            "trade_floor_met": used_trade_floor,
        },
        "confirmation_window": [SELECT_END.isoformat(), END.isoformat()],
        "calibration": calibration,
        "winner_select": winner,
        "winner_confirm_fresh_200": confirmation,
        "select_ranked": ranked,
        "order_api_called": False,
        "live_execution": "NO-GO",
    }
    (output / "search.json").write_text(json.dumps(payload, indent=2))
    print(
        json.dumps(
            {
                "winner": {key: winner[key] for key in (*core, "return_pct", "trades")},
                "confirm_return_pct": confirmation["return_pct"],
                "confirm_trades": confirmation["trades"],
                "order_api_called": False,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
