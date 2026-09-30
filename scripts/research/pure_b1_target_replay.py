"""Replay declared Pure B1 signal on saved Exness Bid/Ask ticks; never place orders."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import scripts.research.b1_hybrid_six_month as replay_module
import scripts.strategy as strategy_module
from scripts.pure_b1.cost_policy import DECLARED_SLIPPAGE_PRICE, DECLARED_SPREAD_STRESS_PRICE
from scripts.pure_b1.decision import round_level
from scripts.pure_b1.provenance import module_sha256, sha256_file
from scripts.pure_b1.quote_time import ARCHIVAL_QUOTE, FRESH_QUOTE, first_tick
from scripts.smc.risk import check_fixed_lot_risk
from scripts.strategy import pure_b1_bars, pure_b1_levels

from .b1_final import normalize_price
from .b1_hybrid_six_month import Replay


START = pd.Timestamp("2026-03-28", tz="UTC")
END = pd.Timestamp("2026-09-28", tz="UTC")

SCENARIOS = {
    "archival_spread_only": {
        "quote_rule": ARCHIVAL_QUOTE.name,
        "day_start": "signal_tick_setdefault",
        "day_quota_limit": 99,
        "commission_per_lot": None,
        "hypothetical_fee_r": 0.0,
        "slippage_allowance": 0.0,
        "entry_stress_price": 0.0,
        "apply_swap": False,
        "spread_buffer": 0.0,
        "historical_swap_entitlement": "missing",
        "broker_fills": "missing",
        "expected_standard_demo_result": False,
        "note": "Archival spread-only mechanics, including the 900s first-tick window and signal-tick day-start. Not a Standard Demo expectation.",
    },
    "archival_hypothetical_0_10r_current_spec_swap": {
        "quote_rule": ARCHIVAL_QUOTE.name,
        "day_start": "signal_tick_setdefault",
        "day_quota_limit": 99,
        "commission_per_lot": None,
        "hypothetical_fee_r": 0.1,
        "slippage_allowance": 0.0,
        "entry_stress_price": 0.0,
        "apply_swap": True,
        "spread_buffer": 0.0,
        "historical_swap_entitlement": "missing",
        "broker_fills": "missing",
        "expected_standard_demo_result": False,
        "note": "Hypothetical 0.10R fee plus current-spec swap. Not the expected Standard Demo result. Historical swap entitlement and broker fills stay missing.",
    },
    "standard_no_commission_swap_free_current_policy": {
        "quote_rule": FRESH_QUOTE.name,
        "day_start": "utc_flat_balance_or_first_second_tick",
        "day_quota_limit": None,
        "commission_per_lot": 0.0,
        "commission_source": "Exness published Standard tariff, checked 2026-09-29; not symbol_info",
        "hypothetical_fee_r": 0.0,
        "slippage_allowance": 0.0,
        "entry_stress_price": 0.0,
        "apply_swap": False,
        "swap_label": "swap_free_current_policy_not_historical",
        "spread_buffer": 0.0,
        "historical_swap_entitlement": "missing",
        "broker_fills": "missing",
        "expected_standard_demo_result": False,
        "note": "Labeled Standard/no-commission/swap-free-current-policy. Zero commission has a published-tariff source. Swap-free is not historical entitlement. Fresh 60s/90s quote rule. No 99-signal day quota.",
    },
    "non_swap_free": {
        "quote_rule": FRESH_QUOTE.name,
        "day_start": "utc_flat_balance_or_first_second_tick",
        "day_quota_limit": None,
        "commission_per_lot": 0.0,
        "commission_source": "Exness published Standard tariff, checked 2026-09-29; not symbol_info",
        "hypothetical_fee_r": 0.0,
        "slippage_allowance": 0.0,
        "entry_stress_price": 0.0,
        "apply_swap": True,
        "swap_label": "current_spec_swap_not_historical_entitlement",
        "spread_buffer": 0.0,
        "historical_swap_entitlement": "missing",
        "broker_fills": "missing",
        "expected_standard_demo_result": False,
        "note": "Current symbol swap specification applied as a labeled non-swap-free scenario. Historical swap entitlement was not observed.",
    },
    "slippage_spread_stress": {
        "quote_rule": FRESH_QUOTE.name,
        "day_start": "utc_flat_balance_or_first_second_tick",
        "day_quota_limit": None,
        "commission_per_lot": 0.0,
        "commission_source": "Exness published Standard tariff, checked 2026-09-29; not symbol_info",
        "hypothetical_fee_r": 0.0,
        "slippage_allowance": 0.0,
        "entry_stress_price": DECLARED_SLIPPAGE_PRICE + DECLARED_SPREAD_STRESS_PRICE,
        "apply_swap": False,
        "swap_label": "swap_free_current_policy_not_historical",
        "spread_buffer": 0.0,
        "historical_swap_entitlement": "missing",
        "broker_fills": "missing",
        "expected_standard_demo_result": False,
        "note": "Declared slippage 0.10 plus declared spread stress 0.20, applied once to the Bid/Ask entry. spread_buffer stays 0 because Bid/Ask already includes spread. Not a terminal-certified slippage.",
    },
}

LABELED_SCENARIOS = (
    "standard_no_commission_swap_free_current_policy",
    "non_swap_free",
    "slippage_spread_stress",
)


def _sha256(path):
    return sha256_file(Path(path))


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


def _archival_engine(ticks, broker, spec):
    return Replay(
        *ticks,
        broker,
        cost_scenario=spec["hypothetical_fee_r"] > 0,
        apply_swap=spec["apply_swap"],
        entry_fee_r=spec["hypothetical_fee_r"],
        signal_day_start=True,
        boundary_day_start_only=False,
        day_quota_limit=spec["day_quota_limit"],
    )


def _labeled_engine(ticks, broker, spec):
    return Replay(
        *ticks,
        broker,
        cost_scenario=False,
        apply_swap=spec["apply_swap"],
        entry_fee_r=0.0,
        entry_stress_price=spec["entry_stress_price"],
        signal_day_start=False,
        boundary_day_start_only=True,
        day_quota_limit=None,
        tick_rounder=lambda price, grid, direction: round_level(price, grid, direction),
    )


def _bind_flat_day_start(engine, *, tick_ms, flat_since_ms):
    """Carry a flat simulated balance across UTC midnight. Never use a later loss as the baseline."""
    day = int(tick_ms // 86400000)
    if day in engine.day_start or engine.legs:
        return flat_since_ms
    day_open_ms = day * 86400000
    if flat_since_ms is not None and flat_since_ms <= day_open_ms:
        engine.day_start[day] = float(engine.balance)
    return flat_since_ms


def _mark_flat(engine, flat_since_ms, tick_ms):
    if engine.legs:
        return None
    if flat_since_ms is None and engine.leg_rows:
        return int(pd.Timestamp(engine.leg_rows[-1]["exit_time_utc"]).value // 10**6)
    return flat_since_ms if flat_since_ms is not None else tick_ms


def _result(engine, spec, *, signal_events, cost_risk_rejected, legs, baskets):
    losses = -baskets.loc[baskets.net < 0, "net"].sum() if len(baskets) else 0
    return {
        "scenario": spec["name"],
        "quote_rule": spec["quote_rule"],
        "day_start": spec["day_start"],
        "day_quota_limit": spec["day_quota_limit"],
        "spread_buffer": 0.0,
        "hypothetical_fee_r": spec["hypothetical_fee_r"],
        "entry_stress_price": spec["entry_stress_price"],
        "swap_label": spec.get("swap_label", "disabled" if not spec["apply_swap"] else "current_spec"),
        "historical_swap_entitlement": "missing",
        "broker_fills": "missing",
        "expected_standard_demo_result": False,
        "note": spec["note"],
        "initial_balance": 200.0,
        "final_balance": engine.balance,
        "return_pct": (engine.balance / 200.0 - 1) * 100,
        "basket_count": len(baskets),
        "leg_count": len(legs),
        "recovery_count": engine.recovery_count,
        "signal_events": signal_events,
        "win_rate": float((baskets.net > 0).mean()) if len(baskets) else None,
        "profit_factor": float(baskets.loc[baskets.net > 0, "net"].sum() / losses) if losses else None,
        "max_tick_equity_dd_pct": engine.max_dd * 100,
        "close_reasons": engine.close_reasons,
        "rejections": engine.rejections,
        "cost_inclusive_risk_rejections": cost_risk_rejected,
    }


def replay_target(frame, ticks, broker, *, cost_scenario=None, scenario=None):
    if scenario is None:
        scenario = (
            "archival_hypothetical_0_10r_current_spec_swap"
            if cost_scenario
            else "archival_spread_only"
        )
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown replay scenario: {scenario}")
    spec = dict(SCENARIOS[scenario], name=scenario)
    times, bid, ask = ticks
    archival = spec["day_start"] == "signal_tick_setdefault"
    engine = (
        _archival_engine(ticks, broker, spec) if archival else _labeled_engine(ticks, broker, spec)
    )
    previous = 0
    signal_events = 0
    cost_risk_rejected = 0
    flat_since_ms = int(START.value // 10**6)
    rule = ARCHIVAL_QUOTE if archival else FRESH_QUOTE
    for index in np.flatnonzero(frame.direction.to_numpy() != 0):
        signal_close = frame.index[index] + pd.Timedelta(minutes=15)
        if not START <= signal_close < END:
            continue
        bar_close_ms = int(signal_close.value // 10**6)
        if archival:
            tick_index = int(np.searchsorted(times, bar_close_ms))
            if tick_index >= len(times) or int(times[tick_index]) - bar_close_ms >= 900000:
                engine.rejections["tick_gap"] += 1
                continue
        else:
            tick_index, quote_reason = first_tick(times, bar_close_ms, rule)
            if tick_index is None:
                key = "tick_gap" if quote_reason == "missing_quote" else "late_quote"
                engine.rejections[key] += 1
                continue
        engine.advance(previous, tick_index + 1)
        previous = tick_index + 1
        flat_since_ms = _mark_flat(engine, flat_since_ms, int(times[tick_index]))
        if not archival:
            flat_since_ms = _bind_flat_day_start(
                engine, tick_ms=int(times[tick_index]), flat_since_ms=flat_since_ms
            )
        before = len(engine.legs)
        direction = int(frame.direction.iloc[index])
        atr = float(frame.atr.iloc[index])
        signal_events += 1
        if not engine.legs:
            entry = float(ask[tick_index] if direction == 1 else bid[tick_index])
            entry += direction * float(spec["entry_stress_price"])
            stop, _target = pure_b1_levels(entry, direction, atr)
            if archival:
                stop = normalize_price(stop, engine.grid)
                distance = abs(entry - stop)
                commission = (
                    spec["hypothetical_fee_r"] * distance * broker["trade_contract_size"]
                    if spec["hypothetical_fee_r"]
                    else 0.0
                )
            else:
                if spec.get("commission_per_lot") is None or not str(spec.get("commission_source") or "").strip():
                    cost_risk_rejected += 1
                    continue
                stop = round_level(stop, engine.grid, direction)
                distance = abs(entry - stop)
                commission = float(spec["commission_per_lot"])
            gate = check_fixed_lot_risk(
                equity=engine.equity_at(tick_index),
                entry_price=entry,
                sl_price=stop,
                contract_size=broker["trade_contract_size"],
                min_lot=broker["volume_min"],
                max_lot=broker["volume_max"],
                lot_step=broker["volume_step"],
                commission_per_lot=commission,
                slippage_allowance=float(spec["slippage_allowance"]),
                spread_buffer=0.0,
                require_cost_model=True,
            )
            if not gate.is_valid:
                cost_risk_rejected += 1
                continue
        engine.on_signal(tick_index, direction, 0, atr)
        flat_since_ms = _mark_flat(engine, flat_since_ms, int(times[tick_index]))
        if len(engine.legs) > before:
            leg = engine.legs[-1]
            stop, target = pure_b1_levels(leg.entry, direction, atr)
            rounded_stop = (
                normalize_price(stop, engine.grid)
                if archival
                else round_level(stop, engine.grid, direction)
            )
            rounded_target = (
                normalize_price(target, engine.grid)
                if archival
                else round_level(target, engine.grid, direction)
            )
            if not np.isclose(leg.stop, rounded_stop) or not np.isclose(leg.target, rounded_target):
                raise ValueError("replay engine and Pure B1 levels disagree")
    engine.advance(previous, len(times))
    if engine.legs:
        engine._close_basket(len(times) - 1, "END_OF_SAMPLE")
    legs = pd.DataFrame(engine.leg_rows)
    baskets = pd.DataFrame(engine.basket_rows)
    return _result(
        engine, spec, signal_events=signal_events, cost_risk_rejected=cost_risk_rejected, legs=legs, baskets=baskets
    ), legs, baskets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        choices=tuple(SCENARIOS),
        help="Labeled scenario. Repeat for more than one. Default: the three current-policy scenarios.",
    )
    args = parser.parse_args()
    selected = tuple(args.scenarios or LABELED_SCENARIOS)
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
        "quote_rule": FRESH_QUOTE.name,
        "archival_quote_rule": ARCHIVAL_QUOTE.name,
        "scenarios": list(selected),
        "entry": "scenario-labeled first quote after completed M15; Ask BUY / Bid SELL",
        "start_utc": START.isoformat(),
        "end_exclusive_utc": END.isoformat(),
        "baseline": str(args.baseline),
        "capture": str(args.capture),
        "baseline_manifest_sha256": _sha256(args.baseline / "manifest.json"),
        "capture_manifest_sha256": _sha256(args.capture / "manifest.json"),
        "strategy_sha256": module_sha256(strategy_module),
        "replay_sha256": module_sha256(replay_module),
        "source_sha256": sha256_file(Path(__file__).resolve()),
        "expected_standard_demo_result": False,
        "limitations": [
            "Research replay, no MT5 order approval or notification",
            "Historical commission, slippage, margin approval, swap entitlement, and broker fills are missing",
            "Hypothetical 0.10R fee is not the expected Standard Demo result",
            "Swap-free current policy is not historical entitlement",
            "Slippage and spread stress are declared assumptions, not terminal-certified values",
            "Bid/Ask entry already includes spread; spread_buffer is 0",
        ],
    }
    (args.output / "contract.json").write_text(json.dumps(contract, indent=2))
    results = []
    for name in selected:
        result, legs, baskets = replay_target(frame, ticks, broker, scenario=name)
        legs.to_csv(args.output / f"legs_{name}.csv", index=False)
        baskets.to_csv(args.output / f"baskets_{name}.csv", index=False)
        results.append(result)
        print(
            json.dumps(
                {
                    "scenario": result["scenario"],
                    "return_pct": result["return_pct"],
                    "basket_count": result["basket_count"],
                    "expected_standard_demo_result": False,
                    "order_api_called": False,
                }
            ),
            flush=True,
        )
    (args.output / "results.json").write_text(json.dumps(results, indent=2))
    (args.output / "COMPLETE").write_text(
        "Labeled offline scenarios only. Demo orders and real money remain NO-GO.\n"
    )


if __name__ == "__main__":
    main()
