"""Read-only comparisons for broker M15, Bid ticks, and saved reference bars."""

from __future__ import annotations

import math

import pandas as pd

from scripts.pure_b1.decision import round_level
from scripts.pure_b1.quote_time import FRESH_QUOTE, first_tick
from scripts.smc.risk import check_fixed_lot_risk
from scripts.strategy import pure_b1_bars, pure_b1_levels


OHLC = ("open", "high", "low", "close")
INDICATORS = ("rsi", "ema50", "atr")


def ticks_to_m15(ticks: pd.DataFrame) -> pd.DataFrame:
    if ticks.empty or not {"time_msc", "bid", "ask"}.issubset(ticks):
        raise ValueError("Bid/Ask ticks required")
    if not ticks["time_msc"].is_monotonic_increasing:
        raise ValueError("tick time invalid")
    if (
        not ticks[["bid", "ask"]].apply(pd.to_numeric, errors="coerce").notna().all().all()
        or (ticks["bid"] <= 0).any()
        or (ticks["ask"] < ticks["bid"]).any()
    ):
        raise ValueError("invalid Bid/Ask ticks")
    frame = ticks[["time_msc", "bid"]].copy()
    frame["bar_open_utc"] = pd.to_datetime(frame.time_msc, unit="ms", utc=True).dt.floor("15min")
    bars = frame.groupby("bar_open_utc", sort=True).bid.agg(
        open="first", high="max", low="min", close="last"
    )
    return bars[list(OHLC)]


def _validate_bars(frame: pd.DataFrame) -> None:
    if not set(OHLC).issubset(frame):
        raise ValueError("OHLC columns required")
    index = frame.index
    if (
        not isinstance(index, pd.DatetimeIndex)
        or index.tz is None
        or index.has_duplicates
        or not index.is_monotonic_increasing
        or any(stamp.utcoffset().total_seconds() != 0 for stamp in index)
    ):
        raise ValueError("ordered UTC DatetimeIndex required")


def compare_bars(
    broker_bars: pd.DataFrame, reference_bars: pd.DataFrame, *, tolerance: float
) -> dict:
    _validate_bars(broker_bars)
    _validate_bars(reference_bars)
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("invalid price tolerance")
    overlap = broker_bars.index.intersection(reference_bars.index)
    if broker_bars.empty or reference_bars.empty:
        raise ValueError("nonempty bar sets required")
    start = max(broker_bars.index[0], reference_bars.index[0])
    end = min(broker_bars.index[-1], reference_bars.index[-1])
    broker_window = broker_bars.loc[start:end].index if start <= end else broker_bars.index[:0]
    reference_window = (
        reference_bars.loc[start:end].index if start <= end else reference_bars.index[:0]
    )
    broker_only = broker_window.difference(reference_window)
    reference_only = reference_window.difference(broker_window)
    mismatches = []
    mismatch_bars = set()
    maximum = 0.0
    for ts in overlap:
        for field in OHLC:
            left = float(broker_bars.at[ts, field])
            right = float(reference_bars.at[ts, field])
            difference = abs(left - right)
            if not math.isfinite(difference):
                raise ValueError("nonfinite OHLC comparison")
            maximum = max(maximum, difference)
            if difference > tolerance:
                mismatch_bars.add(ts)
                mismatches.append(
                    {
                        "bar_open_utc": ts.isoformat(),
                        "field": field,
                        "broker": left,
                        "reference": right,
                        "abs_diff": difference,
                        "cause": "price_delta",
                    }
                )
    return {
        "status": (
            "INCONCLUSIVE"
            if not len(overlap)
            else "FAIL"
            if mismatches or len(broker_only) or len(reference_only)
            else "PASS"
        ),
        "overlap_bars": len(overlap),
        "broker_only_bars": len(broker_only),
        "reference_only_bars": len(reference_only),
        "broker_only_examples": [ts.isoformat() for ts in broker_only[:30]],
        "reference_only_examples": [ts.isoformat() for ts in reference_only[:30]],
        "mismatch_bars": len(mismatch_bars),
        "max_abs_diff": maximum,
        "mismatches": mismatches,
    }


def _suffix_start(full: pd.DataFrame, tail: pd.DataFrame, tolerance: float):
    start = None
    for ts in tail.index:
        left, right = full.loc[ts], tail.loc[ts]
        if not (bool(left.ready) and bool(right.ready)):
            start = None
            continue
        matched = int(left.direction) == int(right.direction) and all(
            math.isfinite(float(left[field]))
            and math.isfinite(float(right[field]))
            and abs(float(left[field]) - float(right[field])) <= tolerance
            for field in INDICATORS
        )
        if matched:
            if start is None:
                start = ts
        else:
            start = None
    return start


def prove_warmup(bars: pd.DataFrame, *, tolerance: float = 1e-8) -> dict:
    """Prove warmup by comparing full history with a strictly shorter tail.

    A fixed drop of 100 or 500 bars is not proof. The comparison must succeed
    on a suffix that includes the last bar. If no shorter history is available
    or none matches, the parity gate fails closed.
    """
    if len(bars) < 3:
        return {
            "status": "FAIL",
            "proven": False,
            "cause": "warmup_comparison_absent",
            "tolerance": tolerance,
            "method": "full_history_vs_strictly_shorter_tail",
        }
    full = pure_b1_bars(bars)
    comparisons = []
    proven_from = None
    dropped = None
    for start in sorted({1, max(1, len(bars) // 2)}):
        if start <= 0 or start >= len(bars):
            continue
        tail = pure_b1_bars(bars.iloc[start:])
        suffix = _suffix_start(full, tail, tolerance)
        comparisons.append(
            {
                "dropped_prefix_bars": start,
                "tail_bars": len(bars) - start,
                "matched": suffix is not None,
                "proven_from_utc": None if suffix is None else suffix.isoformat(),
            }
        )
        if suffix is not None:
            proven_from = suffix
            dropped = start
            break
    if proven_from is None:
        cause = (
            "warmup_comparison_absent" if not comparisons else "warmup_comparison_failed"
        )
        return {
            "status": "FAIL",
            "proven": False,
            "cause": cause,
            "tolerance": tolerance,
            "comparisons": comparisons,
            "method": "full_history_vs_strictly_shorter_tail",
        }
    return {
        "status": "PASS",
        "proven": True,
        "cause": None,
        "tolerance": tolerance,
        "dropped_prefix_bars": dropped,
        "proven_from_utc": proven_from.isoformat(),
        "comparisons": comparisons,
        "method": "full_history_vs_strictly_shorter_tail",
    }


def compare_signals(broker_bars: pd.DataFrame, reference_bars: pd.DataFrame) -> dict:
    bar_parity = compare_bars(broker_bars, reference_bars, tolerance=0.001)
    warmup = {
        "broker": prove_warmup(broker_bars),
        "reference": prove_warmup(reference_bars),
    }
    mismatches = []
    max_delta = {field: 0.0 for field in INDICATORS}
    comparable = 0
    proven = warmup["broker"]["proven"] and warmup["reference"]["proven"]
    if proven:
        start = max(
            pd.Timestamp(warmup["broker"]["proven_from_utc"]),
            pd.Timestamp(warmup["reference"]["proven_from_utc"]),
        )
        broker = pure_b1_bars(broker_bars)
        reference = pure_b1_bars(reference_bars)
        overlap = broker.index.intersection(reference.index)
        overlap = overlap[overlap >= start]
        for ts in overlap:
            left, right = broker.loc[ts], reference.loc[ts]
            if not bool(left.ready and right.ready):
                continue
            comparable += 1
            for field in max_delta:
                max_delta[field] = max(
                    max_delta[field], abs(float(left[field]) - float(right[field]))
                )
            if int(left.direction) != int(right.direction):
                mismatches.append(
                    {
                        "bar_open_utc": ts.isoformat(),
                        "broker_direction": int(left.direction),
                        "reference_direction": int(right.direction),
                        "cause": "direction_mismatch",
                    }
                )
    drift = any(delta > 1e-6 for delta in max_delta.values())
    if not proven:
        cause = next(
            item["cause"]
            for item in warmup.values()
            if not item["proven"]
        )
        status = "FAIL"
    elif not comparable:
        cause = "warmup_comparison_absent"
        status = "FAIL"
    elif bar_parity["status"] != "PASS" or mismatches or drift:
        cause = "indicator_or_bar_mismatch"
        status = "FAIL"
    else:
        cause = None
        status = "PASS"
    return {
        "status": status,
        "cause": cause,
        "comparable_bars": comparable,
        "indicator_tolerance": 1e-6,
        "signal_mismatches": mismatches,
        "max_indicator_abs_diff": max_delta,
        "warmup": warmup,
        "bar_parity_status": bar_parity["status"],
    }


def _cell(status: str, *, cause: str | None = None, abs_diff=None, broker=None, reference=None):
    cell = {"status": status, "cause": cause}
    if abs_diff is not None:
        cell["abs_diff"] = abs_diff
    if broker is not None:
        cell["broker"] = broker
    if reference is not None:
        cell["reference"] = reference
    return cell


def _quote_for_bar(ticks: pd.DataFrame | None, ts: pd.Timestamp):
    if ticks is None or ticks.empty:
        return None, "quote_timing_unavailable"
    bar_close_ms = int((ts + pd.Timedelta(minutes=15)).value // 10**6)
    times = ticks["time_msc"].to_numpy()
    index, reason = first_tick(times, bar_close_ms, FRESH_QUOTE)
    if index is None:
        if reason == "late_quote":
            raw = int(ticks["time_msc"].searchsorted(bar_close_ms, side="left"))
            if raw < len(times) and int(times[raw]) - bar_close_ms > 15 * 60 * 1000:
                return None, "quote_timing_unavailable"
            return None, "late_quote"
        return None, "quote_timing_unavailable"
    row = ticks.iloc[index]
    return {
        "bid": float(row.bid),
        "ask": float(row.ask),
        "time_msc": int(row.time_msc),
    }, None


def _levels(entry: float, direction: int, atr: float, tick_size: float):
    stop, target = pure_b1_levels(entry, direction, atr)
    return round_level(stop, tick_size, direction), round_level(target, tick_size, direction)


def build_parity_ledger(
    broker_bars: pd.DataFrame,
    reference_bars: pd.DataFrame,
    *,
    ticks: pd.DataFrame | None = None,
    equity_by_bar: dict | None = None,
    cost_policy_verified: bool = False,
    broker_spec: dict | None = None,
    bar_causes: dict | None = None,
    price_tolerance: float = 0.001,
    indicator_tolerance: float = 1e-6,
) -> dict:
    """Per-bar OHLC, indicator, signal, SL/TP, and 10% risk ledger.

    Missing historical equity, quote timing, or a verified cost snapshot is
    blocked. This function does not invent equity or fills. Shadow is not
    passed while any required row is blocked or any mismatch is unexplained.
    """
    _validate_bars(broker_bars)
    _validate_bars(reference_bars)
    warmup = {
        "broker": prove_warmup(broker_bars, tolerance=1e-8),
        "reference": prove_warmup(reference_bars, tolerance=1e-8),
    }
    broker_ind = pure_b1_bars(broker_bars)
    reference_ind = pure_b1_bars(reference_bars)
    start = max(broker_bars.index[0], reference_bars.index[0])
    end = min(broker_bars.index[-1], reference_bars.index[-1])
    broker_window = broker_bars.loc[start:end].index if start <= end else broker_bars.index[:0]
    reference_window = (
        reference_bars.loc[start:end].index if start <= end else reference_bars.index[:0]
    )
    counts = {"match": 0, "mismatch": 0, "blocked": 0}
    by_field = {}
    blocked_causes = set()
    unexplained = 0
    rows = []
    proven_from = None
    if warmup["broker"]["proven"] and warmup["reference"]["proven"]:
        proven_from = max(
            pd.Timestamp(warmup["broker"]["proven_from_utc"]),
            pd.Timestamp(warmup["reference"]["proven_from_utc"]),
        )

    def add(bucket: dict, field: str, cell: dict) -> None:
        bucket[field] = cell
        counts[cell["status"]] += 1
        field_counts = by_field.setdefault(field, {"match": 0, "mismatch": 0, "blocked": 0})
        field_counts[cell["status"]] += 1
        if cell["status"] == "blocked" and cell.get("cause"):
            blocked_causes.add(cell["cause"])
        if cell["status"] == "mismatch" and not cell.get("cause"):
            nonlocal unexplained
            unexplained += 1

    timestamps = broker_window.union(reference_window).sort_values()
    for ts in timestamps:
        fields = {}
        in_broker = ts in broker_bars.index
        in_reference = ts in reference_bars.index
        cause_for_bar = None if bar_causes is None else bar_causes.get(ts.isoformat())
        if not in_broker or not in_reference:
            side = "broker_only_bar" if in_broker else "reference_only_bar"
            cause = cause_for_bar or (
                "not_in_canonical_15_of_15" if side == "broker_only_bar" else side
            )
            add(
                fields,
                "bar",
                _cell("mismatch", cause=cause, broker=in_broker, reference=in_reference),
            )
            rows.append({"bar_open_utc": ts.isoformat(), "fields": fields})
            continue
        for name in OHLC:
            left = float(broker_bars.at[ts, name])
            right = float(reference_bars.at[ts, name])
            difference = abs(left - right)
            if difference > price_tolerance:
                add(
                    fields,
                    name,
                    _cell(
                        "mismatch",
                        cause="price_delta",
                        abs_diff=difference,
                        broker=left,
                        reference=right,
                    ),
                )
            else:
                add(fields, name, _cell("match", abs_diff=difference))
        if proven_from is None or ts < proven_from:
            cause = (
                "warmup_comparison_absent"
                if not warmup["broker"]["proven"] or not warmup["reference"]["proven"]
                else "warmup_unproven"
            )
            if cause == "warmup_comparison_absent":
                blocked_cause = "warmup_comparison_absent"
            else:
                blocked_cause = "warmup_unproven"
            for name in (*INDICATORS, "direction"):
                add(fields, name, _cell("blocked", cause=blocked_cause))
            left_direction = right_direction = 0
        else:
            left = broker_ind.loc[ts]
            right = reference_ind.loc[ts]
            if not (bool(left.ready) and bool(right.ready)):
                for name in (*INDICATORS, "direction"):
                    add(fields, name, _cell("blocked", cause="indicator_not_ready"))
                left_direction = right_direction = 0
            else:
                for name in INDICATORS:
                    difference = abs(float(left[name]) - float(right[name]))
                    if difference > indicator_tolerance:
                        add(
                            fields,
                            name,
                            _cell(
                                "mismatch",
                                cause="indicator_delta",
                                abs_diff=difference,
                                broker=float(left[name]),
                                reference=float(right[name]),
                            ),
                        )
                    else:
                        add(fields, name, _cell("match", abs_diff=difference))
                left_direction = int(left.direction)
                right_direction = int(right.direction)
                if left_direction != right_direction:
                    add(
                        fields,
                        "direction",
                        _cell(
                            "mismatch",
                            cause="direction_mismatch",
                            broker=left_direction,
                            reference=right_direction,
                        ),
                    )
                else:
                    add(
                        fields,
                        "direction",
                        _cell("match", broker=left_direction, reference=right_direction),
                    )
        signal_time = (ts + pd.Timedelta(minutes=15)).isoformat()
        if fields["direction"]["status"] == "match" and left_direction == right_direction:
            add(fields, "signal_timestamp", _cell("match", broker=signal_time, reference=signal_time))
        elif fields["direction"]["status"] == "blocked":
            add(fields, "signal_timestamp", _cell("blocked", cause=fields["direction"]["cause"]))
        else:
            add(
                fields,
                "signal_timestamp",
                _cell(
                    "mismatch",
                    cause="direction_mismatch",
                    broker=signal_time,
                    reference=signal_time,
                ),
            )
        quote, quote_cause = _quote_for_bar(ticks, ts)
        tick_size = None if broker_spec is None else broker_spec.get("tick_size")
        if left_direction == 0 and right_direction == 0 and fields["direction"]["status"] == "match":
            add(fields, "stop", _cell("match", cause="no_signal"))
            add(fields, "target", _cell("match", cause="no_signal"))
        elif fields["direction"]["status"] != "match":
            cause = fields["direction"]["cause"] or "direction_mismatch"
            status = "mismatch" if fields["direction"]["status"] == "mismatch" else "blocked"
            add(fields, "stop", _cell(status, cause=cause))
            add(fields, "target", _cell(status, cause=cause))
        elif quote is None or not tick_size:
            cause = quote_cause or "quote_timing_unavailable"
            add(fields, "stop", _cell("blocked", cause=cause))
            add(fields, "target", _cell("blocked", cause=cause))
        else:
            entry_left = quote["ask"] if left_direction == 1 else quote["bid"]
            entry_right = quote["ask"] if right_direction == 1 else quote["bid"]
            try:
                stop_left, target_left = _levels(
                    entry_left, left_direction, float(broker_ind.at[ts, "atr"]), float(tick_size)
                )
                stop_right, target_right = _levels(
                    entry_right,
                    right_direction,
                    float(reference_ind.at[ts, "atr"]),
                    float(tick_size),
                )
            except (ValueError, KeyError):
                add(fields, "stop", _cell("blocked", cause="level_inputs_invalid"))
                add(fields, "target", _cell("blocked", cause="level_inputs_invalid"))
            else:
                for name, left_price, right_price in (
                    ("stop", stop_left, stop_right),
                    ("target", target_left, target_right),
                ):
                    difference = abs(left_price - right_price)
                    if difference > price_tolerance:
                        add(
                            fields,
                            name,
                            _cell(
                                "mismatch",
                                cause="level_delta",
                                abs_diff=difference,
                                broker=left_price,
                                reference=right_price,
                            ),
                        )
                    else:
                        add(
                            fields,
                            name,
                            _cell("match", abs_diff=difference, broker=left_price, reference=right_price),
                        )
        equity = None if equity_by_bar is None else equity_by_bar.get(ts.isoformat())
        if not cost_policy_verified:
            add(fields, "risk_decision", _cell("blocked", cause="cost_snapshot_unverified"))
        elif equity is None or not math.isfinite(float(equity)) or float(equity) <= 0:
            add(fields, "risk_decision", _cell("blocked", cause="historical_equity_unavailable"))
        elif left_direction == 0 and right_direction == 0 and fields["direction"]["status"] == "match":
            add(fields, "risk_decision", _cell("match", cause="no_signal"))
        elif quote is None or broker_spec is None or fields.get("stop", {}).get("status") != "match":
            add(
                fields,
                "risk_decision",
                _cell("blocked", cause=quote_cause or "quote_timing_unavailable"),
            )
        else:
            entry = quote["ask"] if left_direction == 1 else quote["bid"]
            gate_left = check_fixed_lot_risk(
                equity=float(equity),
                entry_price=entry,
                sl_price=float(fields["stop"]["broker"]),
                contract_size=float(broker_spec["contract_size"]),
                min_lot=float(broker_spec["min_lot"]),
                max_lot=float(broker_spec["max_lot"]),
                lot_step=float(broker_spec["lot_step"]),
                commission_per_lot=broker_spec.get("commission_per_lot"),
                slippage_allowance=broker_spec.get("slippage_allowance"),
                spread_buffer=0.0,
                require_cost_model=True,
            )
            gate_right = check_fixed_lot_risk(
                equity=float(equity),
                entry_price=entry,
                sl_price=float(fields["stop"]["reference"]),
                contract_size=float(broker_spec["contract_size"]),
                min_lot=float(broker_spec["min_lot"]),
                max_lot=float(broker_spec["max_lot"]),
                lot_step=float(broker_spec["lot_step"]),
                commission_per_lot=broker_spec.get("commission_per_lot"),
                slippage_allowance=broker_spec.get("slippage_allowance"),
                spread_buffer=0.0,
                require_cost_model=True,
            )
            if gate_left.is_valid != gate_right.is_valid or gate_left.reason != gate_right.reason:
                add(
                    fields,
                    "risk_decision",
                    _cell(
                        "mismatch",
                        cause="risk_decision_mismatch",
                        broker=gate_left.reason,
                        reference=gate_right.reason,
                    ),
                )
            else:
                add(
                    fields,
                    "risk_decision",
                    _cell("match", broker=gate_left.reason, reference=gate_right.reason),
                )
        rows.append({"bar_open_utc": ts.isoformat(), "fields": fields})

    if unexplained:
        gate = "FAIL"
    elif counts["blocked"]:
        gate = "BLOCKED"
    elif counts["mismatch"]:
        gate = "FAIL"
    elif counts["match"]:
        gate = "PASS"
    else:
        gate = "FAIL"
    return {
        "gate": gate,
        "shadow_passed": gate == "PASS",
        "counts": counts,
        "by_field": by_field,
        "blocked_causes": sorted(blocked_causes),
        "unexplained_mismatches": unexplained,
        "warmup": warmup,
        "quote_rule": FRESH_QUOTE.name,
        "rows": rows,
        "order_api_called": False,
    }
