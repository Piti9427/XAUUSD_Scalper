"""Replay declared Pure B1 signal on saved Exness Bid/Ask ticks; never place orders."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.strategy import pure_b1_bars, pure_b1_levels
from scripts.smc.risk import check_fixed_lot_risk

from .b1_final import normalize_price
from .b1_hybrid_six_month import Replay


START = pd.Timestamp("2026-03-28", tz="UTC")
END = pd.Timestamp("2026-09-28", tz="UTC")


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_inputs(baseline, capture):
    baseline_manifest = json.loads((baseline / "manifest.json").read_text())
    capture_path = capture / "manifest.json"
    if baseline_manifest["capture_manifest_sha256"] != _sha256(capture_path):
        raise ValueError("baseline/capture mismatch")
    if not (baseline / "COMPLETE").exists():
        raise ValueError("baseline incomplete")
    for name, digest in baseline_manifest["artifacts_sha256"].items():
        if _sha256(baseline / name) != digest:
            raise ValueError(f"baseline artifact mismatch: {name}")
    broker_capture = json.loads(capture_path.read_text())
    if broker_capture["symbol"] != "XAUUSDm" or broker_capture["account"]["currency"] != "USD":
        raise ValueError("unexpected broker symbol or account currency")
    bars = pd.read_csv(baseline / "reference_bars.csv")
    bars.index = pd.DatetimeIndex(pd.to_datetime(bars.pop("bar_open_utc"), utc=True))
    frame = pure_b1_bars(bars)
    ticks = [
        np.load(baseline / "tape" / f"{name}.npy", mmap_mode="r") for name in ("time", "bid", "ask")
    ]
    left, right = np.searchsorted(ticks[0], [START.value // 10**6, END.value // 10**6])
    ticks = [values[left:right] for values in ticks]
    broker = dict(broker_capture["symbol_spec"], leverage=broker_capture["account"]["leverage"])
    return frame, ticks, broker


def replay_target(frame, ticks, broker, *, cost_scenario):
    times, bid, ask = ticks
    engine = Replay(times, bid, ask, broker, cost_scenario=cost_scenario)
    previous = 0
    signal_events = 0
    cost_risk_rejected = 0
    for index in np.flatnonzero(frame.direction.to_numpy() != 0):
        signal_close = frame.index[index] + pd.Timedelta(minutes=15)
        if not START <= signal_close < END:
            continue
        tick_index = int(np.searchsorted(times, signal_close.value // 10**6))
        if tick_index >= len(times) or times[tick_index] - signal_close.value // 10**6 >= 900000:
            engine.rejections["tick_gap"] += 1
            continue
        engine.advance(previous, tick_index + 1)
        previous = tick_index + 1
        before = len(engine.legs)
        direction = int(frame.direction.iloc[index])
        atr = float(frame.atr.iloc[index])
        signal_events += 1
        if not engine.legs:
            entry = float(ask[tick_index] if direction == 1 else bid[tick_index])
            stop, _ = pure_b1_levels(entry, direction, atr)
            stop = normalize_price(stop, engine.grid)
            distance = abs(entry - stop)
            cost_per_lot = 0.1 * distance * broker["trade_contract_size"] if cost_scenario else 0.0
            gate = check_fixed_lot_risk(
                equity=engine.equity_at(tick_index),
                entry_price=entry,
                sl_price=stop,
                contract_size=broker["trade_contract_size"],
                min_lot=broker["volume_min"],
                max_lot=broker["volume_max"],
                lot_step=broker["volume_step"],
                commission_per_lot=cost_per_lot,
                slippage_allowance=0.0,
                require_cost_model=True,
            )
            if not gate.is_valid:
                cost_risk_rejected += 1
                continue
        engine.on_signal(tick_index, direction, 0, atr)
        if len(engine.legs) > before:
            leg = engine.legs[-1]
            stop, target = pure_b1_levels(leg.entry, direction, atr)
            if not np.isclose(leg.stop, normalize_price(stop, engine.grid)) or not np.isclose(
                leg.target, normalize_price(target, engine.grid)
            ):
                raise ValueError("replay engine and Pure B1 levels disagree")
    engine.advance(previous, len(times))
    if engine.legs:
        engine._close_basket(len(times) - 1, "END_OF_SAMPLE")
    legs = pd.DataFrame(engine.leg_rows)
    baskets = pd.DataFrame(engine.basket_rows)
    losses = -baskets.loc[baskets.net < 0, "net"].sum() if len(baskets) else 0
    result = {
        "cost_scenario": cost_scenario,
        "initial_balance": 200.0,
        "final_balance": engine.balance,
        "return_pct": (engine.balance / 200.0 - 1) * 100,
        "basket_count": len(baskets),
        "leg_count": len(legs),
        "recovery_count": engine.recovery_count,
        "signal_events": signal_events,
        "win_rate": float((baskets.net > 0).mean()) if len(baskets) else None,
        "profit_factor": float(baskets.loc[baskets.net > 0, "net"].sum() / losses)
        if losses
        else None,
        "max_tick_equity_dd_pct": engine.max_dd * 100,
        "close_reasons": engine.close_reasons,
        "rejections": engine.rejections,
        "cost_inclusive_risk_rejections": cost_risk_rejected,
    }
    return result, legs, baskets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frame, ticks, broker = _load_inputs(args.baseline, args.capture)
    args.output.mkdir(parents=True, exist_ok=False)
    contract = {
        "signal": "Donchian30 strict close + RSI14 EWM span14 in (30,70) + EMA50 EWM span50",
        "atr": "true range rolling mean 14",
        "stop_atr": 2.5,
        "target_atr": 6.25,
        "lot": 0.01,
        "risk_cap_current_equity": 0.10,
        "daily_loss_fraction": 0.40,
        "entry": "first actual tick after completed M15 bar, Ask BUY / Bid SELL",
        "start_utc": START.isoformat(),
        "end_exclusive_utc": END.isoformat(),
        "baseline": str(args.baseline),
        "capture": str(args.capture),
        "baseline_manifest_sha256": _sha256(args.baseline / "manifest.json"),
        "capture_manifest_sha256": _sha256(args.capture / "manifest.json"),
        "strategy_sha256": _sha256(Path("scripts/strategy.py")),
        "replay_sha256": _sha256(Path("scripts/research/b1_hybrid_six_month.py")),
        "source_sha256": _sha256(Path(__file__)),
        "limitations": [
            "Research replay, no MT5 order approval or notification",
            "Historical commission/slippage/margin approval unverified",
            "Cost scenario uses current-spec swap and hypothetical 0.10R fee",
        ],
    }
    (args.output / "contract.json").write_text(json.dumps(contract, indent=2))
    results = []
    for cost_scenario in (False, True):
        result, legs, baskets = replay_target(frame, ticks, broker, cost_scenario=cost_scenario)
        suffix = "archival_cost" if cost_scenario else "spread_only"
        legs.to_csv(args.output / f"legs_{suffix}.csv", index=False)
        baskets.to_csv(args.output / f"baskets_{suffix}.csv", index=False)
        results.append(result)
        print(json.dumps(result), flush=True)
    (args.output / "results.json").write_text(json.dumps(results, indent=2))
    (args.output / "COMPLETE").write_text("Offline historical reconstruction only.\n")


if __name__ == "__main__":
    main()
