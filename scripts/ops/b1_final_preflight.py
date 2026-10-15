"""B1-FINAL Standard Demo preflight and affordability report.

`evaluate` is pure: it turns a read-only broker snapshot (written by
`b1_final_preflight_probe.py` under Wine) into a sanitized report. It never
changes balance, risk or symbol and never calls an order API.
"""

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

B1_MAGIC = 26092701
TARGET_SYMBOL = "XAUUSDm"
HYPOTHETICAL_DEPOSIT = 100.0
FRESH_HWM_RISK = 0.01
REQUIRED_SPEC = (
    "name",
    "trade_mode",
    "volume_min",
    "volume_step",
    "volume_max",
    "trade_tick_size",
    "point",
    "currency_profit",
)
ACCOUNT_TRADE_MODE_DEMO = 0
ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 2
SYMBOL_TRADE_MODE_FULL = 4
MAX_TICK_AGE_SEC = 60


def _floor_volume(raw, step, maximum):
    return math.floor(min(raw, maximum) / step + 1e-10) * step


def _rows(equity, margin_free, spec, stops, fee_per_lot, reserve_r):
    """Same admission arithmetic as CB1Engine::TryEntry: loss*(1+reserve) + fees per lot."""
    budget = equity * FRESH_HWM_RISK
    rows = []
    for stop in stops:
        per_lot = stop["loss_1lot"] * (1 + reserve_r) + fee_per_lot
        volume = round(_floor_volume(budget / per_lot, spec["volume_step"], spec["volume_max"]), 8)
        row = {
            "stop": stop["label"],
            "stop_distance": stop["distance"],
            "risk_pct": FRESH_HWM_RISK,
            "risk_budget": budget,
            "raw_volume": budget / per_lot,
            "normalized_volume": 0.0,
            "minimum_lot_risk": per_lot * spec["volume_min"],
            "volume_risk": 0.0,
        }
        if volume < spec["volume_min"] - 1e-12:
            row["outcome"] = "RISK_BELOW_MINIMUM_LOT"
        elif per_lot * volume > budget + 1e-9:
            row["outcome"] = "RISK_BUDGET_EXCEEDED"
        elif stop["margin_1lot"] * volume > margin_free:
            row.update(
                normalized_volume=volume,
                volume_risk=per_lot * volume,
                outcome="INSUFFICIENT_MARGIN",
            )
        else:
            row.update(normalized_volume=volume, volume_risk=per_lot * volume, outcome="ADMIT")
        rows.append(row)
    return rows


def _verdict(rows):
    median = next((r for r in rows if r["stop"] == "median"), None)
    if median is None:
        return "UNVERIFIED_NO_MEDIAN_STOP"
    return "ACCOUNT_FEASIBLE_AT_MEDIAN_STOP" if median["outcome"] == "ADMIT" else "ACCOUNT_BLOCKED"


def utc_offset_status(snapshot, expected_offset_sec):
    """Offset is observable only from a fresh tick: the server-minus-UTC gap must sit on a 15-minute grid."""
    server, now = snapshot.get("server_tick_epoch"), snapshot.get("probe_utc_epoch")
    if (
        server is None
        and snapshot.get("tick", {}).get("time_msc")
        and snapshot.get("created_at_utc")
    ):
        server = snapshot["tick"]["time_msc"] // 1000
        now = int(datetime.fromisoformat(snapshot["created_at_utc"]).timestamp())
    if server is None or now is None:
        return "UNVERIFIED_NO_FRESH_TICK"
    gap = server - now
    offset = round(gap / 900) * 900
    if abs(gap - offset) > MAX_TICK_AGE_SEC or abs(offset) > 14 * 3600:
        return "UNVERIFIED_NO_FRESH_TICK"
    return "VERIFIED" if offset == expected_offset_sec else "MISMATCH"


def evaluate(
    snapshot,
    commission_per_lot=0.0,
    exit_fee_per_lot=0.0,
    admission_reserve_r=0.0,
    expected_utc_offset_sec=0,
):
    sanitized = json.dumps(snapshot, sort_keys=True, default=str).encode()
    report = {
        "strategy": "B1-FINAL",
        "target_symbol": TARGET_SYMBOL,
        "snapshot_created_at_utc": snapshot.get("created_at_utc"),
        "snapshot_sha256": hashlib.sha256(sanitized).hexdigest(),
        "order_api_called": False,
        "account_qualified": False,
        "blocking_reasons": [],
        "scenarios": [],
        "sizing_inputs": {
            "commission_per_lot": commission_per_lot,
            "exit_fee_per_lot": exit_fee_per_lot,
            "admission_reserve_r": admission_reserve_r,
        },
        "expected_utc_offset_sec": expected_utc_offset_sec,
    }
    if snapshot.get("order_api_called") is not False:
        report["status"] = "INVALID_PROBE"
        return report
    if not snapshot.get("initialized"):
        report["status"] = "UNVERIFIED"
        report["connection_error"] = (snapshot.get("last_error") or [None])[0]
        return report
    reasons = report["blocking_reasons"]
    account = snapshot.get("account") or {}
    spec = snapshot.get("symbol_spec") or {}
    if snapshot.get("identity_match") is not True:
        reasons.append("ACCOUNT_IDENTITY_MISMATCH")
    if account.get("trade_mode") != ACCOUNT_TRADE_MODE_DEMO:
        reasons.append(
            "REAL_ACCOUNT_REJECTED" if account.get("trade_mode") == 2 else "NOT_DEMO_ACCOUNT"
        )
    if account.get("margin_mode") != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING:
        reasons.append("NOT_HEDGING")
    spec_complete = all(spec.get(k) is not None for k in REQUIRED_SPEC)
    if not spec_complete:
        reasons.append("SPECIFICATION_MISSING")
    elif spec["name"] != TARGET_SYMBOL:
        reasons.append("SYMBOL_MISMATCH")
    elif spec["trade_mode"] != SYMBOL_TRADE_MODE_FULL:
        reasons.append("SYMBOL_NOT_FULLY_TRADABLE")
    elif spec["currency_profit"] != account.get("currency"):
        reasons.append("PROFIT_CURRENCY_MISMATCH")
    if any(x.get("magic") != B1_MAGIC for x in snapshot.get("exposure") or []):
        reasons.append("FOREIGN_EXPOSURE")
    report["utc_offset_status"] = utc_offset_status(snapshot, expected_utc_offset_sec)
    if report["utc_offset_status"] == "MISMATCH":
        reasons.append("UTC_OFFSET_MISMATCH")
    stops = snapshot.get("stops") or []
    if not stops or any(
        not (s.get("loss_1lot", 0) > 0 and s.get("margin_1lot", 0) > 0) for s in stops
    ):
        reasons.append("BROKER_CALCULATION_MISSING")
    if reasons:
        report["status"] = "BLOCKED"
        return report
    report["status"] = "VERIFIED"
    report["account_currency"] = account["currency"]
    report["specification"] = {
        k: spec.get(k)
        for k in REQUIRED_SPEC + ("trade_stops_level", "trade_freeze_level", "filling_mode")
    }
    for name, equity, margin_free, source in (
        ("actual_demo_equity", account["equity"], account["margin_free"], "broker_snapshot"),
        (
            "hypothetical_100_usd",
            HYPOTHETICAL_DEPOSIT,
            HYPOTHETICAL_DEPOSIT,
            "hypothetical_research_deposit",
        ),
    ):
        rows = _rows(
            equity,
            margin_free,
            spec,
            stops,
            commission_per_lot + exit_fee_per_lot,
            admission_reserve_r,
        )
        report["scenarios"].append(
            {
                "scenario": name,
                "equity": equity,
                "equity_source": source,
                "rows": rows,
                "verdict": _verdict(rows),
            }
        )
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--commission-per-lot", type=float, default=0.0)
    p.add_argument("--exit-fee-per-lot", type=float, default=0.0)
    p.add_argument("--admission-reserve-r", type=float, default=0.0)
    p.add_argument("--expected-utc-offset-sec", type=int, default=0)
    args = p.parse_args()
    if args.output.exists():
        p.error("output exists")
    report = evaluate(
        json.loads(args.snapshot.read_text()),
        args.commission_per_lot,
        args.exit_fee_per_lot,
        args.admission_reserve_r,
        args.expected_utc_offset_sec,
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {k: report[k] for k in ("status", "blocking_reasons")}
            | {"verdicts": {s["scenario"]: s["verdict"] for s in report["scenarios"]}}
        )
    )
    raise SystemExit(0 if report["status"] == "VERIFIED" else 1)


if __name__ == "__main__":
    main()
