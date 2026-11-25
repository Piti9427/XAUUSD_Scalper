"""Read-only prospective fixed-lot Demo evidence; never economic qualification."""

import argparse
from collections import Counter
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3


def report(conn, *, since=None, until=None):
    cohorts = {}
    for (raw,) in conn.execute("SELECT payload FROM audit_events ORDER BY id"):
        event = json.loads(raw)
        captured = datetime.fromisoformat(event["utc"])
        if (since is not None and captured < since) or (until is not None and captured >= until):
            continue
        release, config = event.get("release_hash"), event.get("config_hash")
        if not release or not config:
            continue
        key = release + ":" + config
        active = event.get("active") or {}
        if event["kind"] == "LIFECYCLE":
            key = active.get("cohort_id") or "legacy_unattributed"
        row = cohorts.setdefault(
            key,
            dict(
                cohort_id=key,
                source="Demo broker fills",
                trades=0,
                net_pnl=0.0,
                gross_wins=0.0,
                gross_losses=0.0,
                equity_samples=0,
                observed_equity_drawdown_pct=0.0,
                blockers=Counter(),
                containment_reasons=Counter(),
                safety_closures=0,
                safety_net_pnl=0.0,
                request_latency_ms=[],
                signal_to_fill_ms=[],
                unknown_cycles=0,
                shadow_admissions=0,
                signals=0,
                requests=0,
                data_completeness="INCONCLUSIVE",
                costs="COST_INCONCLUSIVE",
                profitability="INCONCLUSIVE",
                real_money="PROHIBITED",
            ),
        )
        if event["kind"] == "LIFECYCLE" and event["event"]["kind"] in ("CLOSED", "SAFETY_CLOSED"):
            net = float(event["event"]["net"])
            row["trades"] += 1
            row["net_pnl"] += net
            row["gross_wins"] += max(0, net)
            row["gross_losses"] += max(0, -net)
            if event["event"]["kind"] == "SAFETY_CLOSED":
                row["safety_closures"] += 1
                row["safety_net_pnl"] += net
                row["containment_reasons"][event["event"].get("reason", "unknown")] += 1
        if event["kind"] == "LIFECYCLE" and event["event"]["kind"] == "FILLED":
            latency = event["event"].get("signal_to_fill_ms")
            if latency is not None:
                row["signal_to_fill_ms"].append(latency)
        if event["kind"] == "RESPONSE" and "elapsed_ms" in event:
            row["request_latency_ms"].append(event["elapsed_ms"])
        if event["kind"] == "SIGNAL" and event.get("direction") in (-1, 1):
            row["signals"] += 1
        if event["kind"] == "REQUEST":
            row["requests"] += 1
        if event["kind"] == "CYCLE":
            result = event["result"]
            if result["status"] == "BLOCKED":
                row["blockers"][result.get("reason", "unknown")] += 1
            row["unknown_cycles"] += result.get("position_protection") == "unknown"
            row["shadow_admissions"] += result["status"] == "SHADOW_ADMIT"
            equity = event.get("equity")
            if equity is not None:
                row["equity_samples"] += 1
                peak = max(row.get("_peak", equity), equity)
                row["_peak"] = peak
                row["observed_equity_drawdown_pct"] = max(
                    row["observed_equity_drawdown_pct"], (peak - equity) / peak * 100
                )
    for row in cohorts.values():
        row.pop("_peak", None)
        for metric in ("request_latency_ms", "signal_to_fill_ms"):
            samples = sorted(row[metric])
            row[metric] = dict(
                count=len(samples),
                max=max(samples) if samples else None,
                median=samples[len(samples) // 2] if samples else None,
            )
        row["expectancy_usd"] = row["net_pnl"] / row["trades"] if row["trades"] else None
        row["profit_factor"] = (
            row["gross_wins"] / row["gross_losses"] if row["gross_losses"] else None
        )
    return dict(
        cohorts=list(cohorts.values()),
        since_utc=since.isoformat() if since else None,
        until_utc=until.isoformat() if until else None,
        limitations=[
            "Observed sampled equity drawdown, not continuous tick drawdown",
            "Blocker counts are cycles, not independent missed signals",
            "48h shadow and 7 Demo days are operational gates only",
            "No simulated outcomes mixed with broker fills; no profitability qualification",
        ],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--since", type=datetime.fromisoformat)
    parser.add_argument("--until", type=datetime.fromisoformat)
    args = parser.parse_args(argv)
    if any(
        t is not None and (t.tzinfo is None or t.utcoffset() != timedelta(0))
        for t in (args.since, args.until)
    ):
        parser.error("report window must be aware UTC")
    if args.since and args.until and args.until <= args.since:
        parser.error("--until must be after --since")
    conn = sqlite3.connect(args.journal.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        result = report(conn, since=args.since, until=args.until)
    finally:
        conn.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
