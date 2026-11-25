"""Config-driven paired research only; no broker, execution or notification APIs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np

import pandas as pd

from scripts.strategy import reward156_bars, trial30_bars
from scripts.research.breakout_logic import Costs, Rules, replay
from scripts.research.public_exness_archive import load_discovery
from scripts.research.rollover import SwapPolicy
from scripts.research.tune_breakout_logic import sha256

DEFAULT_CONFIG = Path("config/reward156-tuning.json")
DEFAULT_OUTPUT = Path("docs/reviews/reward156-tuning-2026-10-04")
SOURCES = [
    "scripts/research/reward156_tuning.py",
    "scripts/research/rollover.py",
    "scripts/research/breakout_replay.py",
    "scripts/research/breakout_logic.py",
    "scripts/research/breakout_models.py",
    "scripts/research/breakout_entry.py",
    "scripts/research/breakout_signals.py",
    "scripts/research/public_exness_archive.py",
    "scripts/research/tune_breakout_logic.py",
    "scripts/research/data.py",
    "scripts/strategy.py",
    "config/trial30-demo.json",
    "config/reward156-demo.json",
]


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    pending.replace(path)


def closed_h4_ema(bars, span):
    """Publish complete H4 close EMA only at its close time; no future mapping."""
    if span < 1 or bars.index.tz is None or str(bars.index.tz) != "UTC":
        raise ValueError("positive span and UTC bars required")
    if bars.index.has_duplicates or not bars.index.is_monotonic_increasing:
        raise ValueError("invalid H4 input chronology")
    if (bars.index.as_unit("ms").asi8 % 900000).any():
        raise ValueError("unaligned M15 input")
    h4 = bars.close.resample("4h", origin="start_day", label="left", closed="left").agg(
        ["last", "count"]
    )
    valid = h4["count"] == 16
    ema = h4.loc[valid, "last"].ewm(span=span, adjust=False, min_periods=span).mean()
    published = ema.reindex(h4.index)  # latest incomplete bucket must fail closed
    published.index += pd.Timedelta(hours=4)
    decisions = bars.index + pd.Timedelta(minutes=15)
    mapped = published.reindex(decisions, method="ffill")
    mapped.index = bars.index
    return mapped.rename("macro_ema")


def prepare_contract(bars, contract):
    detector = {"trial30": trial30_bars, "reward156": reward156_bars}[contract["strategy"]]
    frame = detector(bars)
    frame["hh"] = bars.high.rolling(48).max().shift(1)
    frame["ll"] = bars.low.rolling(48).min().shift(1)
    frame["raw_direction"] = frame.direction
    frame["macro_unavailable"] = False
    frame["macro_blocked"] = False
    span = contract["macro_span"]
    if span:
        ema = closed_h4_ema(bars, span)
        allowed = ((frame.direction == 1) & (frame.close > ema)) | (
            (frame.direction == -1) & (frame.close < ema)
        )
        frame["macro_unavailable"] = (frame.direction != 0) & ema.isna()
        frame["macro_blocked"] = (frame.direction != 0) & ~allowed
        frame.loc[~allowed, "direction"] = 0
    trial = contract["strategy"] == "trial30"
    rules = Rules(
        stop_atr=2.5,
        target_atr=3.0,
        target_rr=0.0 if trial else 1.35,
        protect_mode="break_even" if trial else "off",
        protect_after_r=1.0,
        risk_cap=0.10,
        daily_loss_limit=0.20,
        sizing_mode="fixed",
        buy_pause_drawdown=contract["buy_pause_drawdown"],
    )
    return frame, rules


def blocking(events, ledger, start, end):
    by_day = {}
    for event in events:
        day = pd.Timestamp(event["time_utc"]).normalize()
        by_day.setdefault(day, []).append(event)
    intervals = [
        (pd.Timestamp(t["entry_time_utc"]), pd.Timestamp(t["exit_time_utc"])) for t in ledger
    ]
    blocked = []
    for day, group in sorted(by_day.items()):
        overlaps = any(a < day + pd.Timedelta(days=1) and b >= day for a, b in intervals)
        if not overlaps and all(
            e["reason"] == "risk_cap" and not e["position_open"] for e in group
        ):
            blocked.append(day)
    longest = run = 0
    previous = None
    for day in blocked:
        run = run + 1 if previous is not None and day - previous == pd.Timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    tail_start = max(start, end - pd.Timedelta(days=30))
    tail = [e for e in events if pd.Timestamp(e["time_utc"]) >= tail_start]
    tail_exposed = any(a < end and b >= tail_start for a, b in intervals)
    terminal = bool(tail and not tail_exposed and all(e["reason"] == "risk_cap" for e in tail))
    admissions = [pd.Timestamp(e["time_utc"]) for e in events if e["reason"] == "admitted"]
    return dict(
        risk_blocked_days=len(blocked),
        longest_risk_blocked_calendar_streak=longest,
        terminal_risk_blockage=terminal,
        terminal_inactivity_days=(end - max(admissions, default=start)).total_seconds() / 86400,
        tail_no_signal=not bool(tail),
    )


def summary(result, frame, start, end):
    selected = (frame.index + pd.Timedelta(minutes=15) >= start) & (
        frame.index + pd.Timedelta(minutes=15) < end
    )
    trades = result["ledger"]
    row = {
        k: result[k]
        for k in (
            "net_usd",
            "final_balance",
            "max_dd_pct",
            "trades",
            "win_rate",
            "realized_rr",
            "profit_factor",
            "max_admitted_risk_pct",
            "rejections",
        )
    }
    row.update(
        swap_usd=result.get("swap_usd", 0.0),
        net_before_swap_usd=result.get("net_before_swap_usd", result["net_usd"]),
        buy_trades=sum(t["direction"] == 1 for t in trades),
        sell_trades=sum(t["direction"] == -1 for t in trades),
        forced_exits=sum(t["reason"] == "END_OF_SAMPLE" for t in trades),
        macro_blocked=int(frame.loc[selected, "macro_blocked"].sum()),
        macro_unavailable=int(frame.loc[selected, "macro_unavailable"].sum()),
    )
    row.update(blocking(result["admission_events"], trades, start, end))
    return row


def improves(candidate, original):
    return bool(
        candidate["net_usd"] > max(0, original["net_usd"])
        and candidate["max_dd_pct"] <= 35
        and candidate["max_admitted_risk_pct"] <= 10
        and not candidate["terminal_risk_blockage"]
    )


def qualifies(candidate, trial, minimum):
    metrics = ("win_rate", "realized_rr")
    if any(candidate[k] is None or trial[k] is None for k in metrics):
        return False
    return bool(
        improves(candidate, trial)
        and candidate["trades"] >= minimum
        and candidate["buy_trades"] >= 1
        and candidate["sell_trades"] >= 1
        and candidate["win_rate"] > trial["win_rate"]
        and candidate["realized_rr"] > max(1.0, trial["realized_rr"])
    )


def verdict(rows, catalog):
    results = {}
    for contract in catalog[2:]:
        name = contract["name"]
        continuous = [
            r
            for r in rows
            if r["contract"] == name and r["window"] == "full" and r["cost_view"] == "swap"
        ]
        cells = [r for r in rows if r["contract"] == name and r["cost_view"] == "swap"]
        comparisons = []
        for row in cells:

            def peer(name):
                return next(
                    r["metrics"]
                    for r in rows
                    if r["contract"] == name
                    and all(r[k] == row[k] for k in ("dataset", "window", "cost", "cost_view"))
                )

            comparisons.append(
                dict(
                    dataset=row["dataset"],
                    window=row["window"],
                    cost=row["cost"],
                    improves_original=improves(row["metrics"], peer("reward156_original")),
                    qualifies_trial30=qualifies(
                        row["metrics"], peer("trial30"), 60 if row["window"] == "full" else 10
                    ),
                )
            )
        improvement = len(continuous) == 4 and all(
            c["improves_original"] for c in comparisons if c["window"] == "full"
        )
        qualification = (
            improvement and len(cells) == 12 and all(c["qualifies_trial30"] for c in comparisons)
        )
        results[name] = dict(
            improves_reward156=improvement,
            qualifies_vs_trial30=qualification,
            worst_continuous_dd=max((r["metrics"]["max_dd_pct"] for r in continuous), default=None),
            minimum_continuous_net=min((r["metrics"]["net_usd"] for r in continuous), default=None),
            cells=comparisons,
        )
    winners = [c["name"] for c in catalog[2:] if results[c["name"]]["qualifies_vs_trial30"]]
    winners.sort(
        key=lambda n: (results[n]["worst_continuous_dd"], -results[n]["minimum_continuous_net"])
    )
    return dict(
        candidates=results,
        selected=winners[0] if winners else None,
        holdout="ELIGIBLE_LOCK_SELECTION_BEFORE_OPENING" if winners else "NOT_OPENED_NO_QUALIFIER",
        demo="UNCHANGED_TRIAL30",
        real_money="NO_GO",
        costs="COST_INCONCLUSIVE",
    )


def validate_config(config):
    if (
        config["research_only"] is not True
        or config["initial_equity"] != 200
        or config["volume"] != 0.01
        or config["risk_cap"] != 0.1
        or config["daily_loss_limit"] != 0.2
    ):
        raise ValueError("research/account/risk pins changed")
    trial = json.loads(Path("config/trial30-demo.json").read_text())
    reward = json.loads(Path("config/reward156-demo.json").read_text())
    for live in (trial, reward):
        for key in ("symbol", "volume", "sl_atr", "risk_cap", "daily_loss_limit"):
            expected = dict(
                symbol="XAUUSDm", volume=0.01, sl_atr=2.5, risk_cap=0.1, daily_loss_limit=0.2
            )[key]
            if live[key] != expected:
                raise ValueError("runtime contract drift: " + key)
    if reward["target_rr"] != 1.35 or reward["buy_pause_drawdown"] != 0.05:
        raise ValueError("Reward156 exit/pause drift")
    if (
        reward["rsi_period"],
        reward["rsi_threshold"],
        reward["ema_span"],
        reward["donchian"],
        reward["atr"],
    ) != (7, 35, 50, 48, 14):
        raise ValueError("Reward156 detector drift")
    if trial["donchian"] != 48 or trial["atr"] != 14:
        raise ValueError("trial30 detector drift")
    if trial["tp_atr"] != 3 or trial["protect_after_r"] != 1 or trial["side"] != "SELL":
        raise ValueError("trial30 exit/protection drift")
    if len(config["contracts"]) != 5 or len({c["name"] for c in config["contracts"]}) != 5:
        raise ValueError("expected five independent contracts")
    expected = [
        ("trial30", "trial30", 0.0, 0),
        ("reward156_original", "reward156", 0.05, 0),
        ("reward156_no_pause", "reward156", 0.0, 0),
        ("reward156_h4_ema100", "reward156", 0.0, 100),
        ("reward156_h4_ema200", "reward156", 0.0, 200),
    ]
    actual = [
        (c["name"], c["strategy"], c["buy_pause_drawdown"], c["macro_span"])
        for c in config["contracts"]
    ]
    if actual != expected:
        raise ValueError("frozen catalog drift; declare a new protocol before expanding")


def report(output, rows, decision, filename="report.md"):
    lines = [
        "# Reward156 paired research tuning",
        "",
        "All cells: independent USD200 / fixed0.01 / risk10% / daily20%. No Demo change.",
        "A: full10months and reset5month halves. B: full12months and reset6month halves.",
        "Swap: current-spec sensitivity at quoted ticks, assumed UTC rollover; COST_INCONCLUSIVE.",
        "Net-before-swap is attribution on swap path; no_swap is independently replayed counterfactual.",
        "",
        "| Dataset/window | Cost/view | Contract | Net USD | Swap USD | DD % | WR % | RR | BUY/SELL | Risk blocked days |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        m = r["metrics"]
        wr = "n/a" if m["win_rate"] is None else f"{m['win_rate'] * 100:.2f}"
        rr = "n/a" if m["realized_rr"] is None else f"{m['realized_rr']:.4f}"
        lines.append(
            f"| {r['dataset']}/{r['window']} | {r['cost']}/{r['cost_view']} | {r['contract']} | {m['net_usd']:.2f} | {m['swap_usd']:.2f} | {m['max_dd_pct']:.2f} | {wr} | {rr} | {m['buy_trades']}/{m['sell_trades']} | {m['risk_blocked_days']} |"
        )
    lines += [
        "",
        "## Frozen verdict",
        "",
        "```json",
        json.dumps(decision, indent=2),
        "```",
        "",
        "A/B in-sample reused discovery; no prospective/live fill parity. Sealed Jul-Sep2025 not loaded.",
        "No optimization beyond registered three candidates. Passing research does not authorize execution.",
    ]
    (output / filename).write_text("\n".join(lines) + "\n")
    csv_rows = []
    for r in rows:
        flat = {k: v for k, v in r.items() if k != "metrics"}
        flat.update({k: v for k, v in r["metrics"].items() if k != "rejections"})
        flat.update({"rejected_" + k: v for k, v in r["metrics"]["rejections"].items()})
        csv_rows.append(flat)
    pd.DataFrame(csv_rows).to_csv(output / filename.replace(".md", ".csv"), index=False)


def run(config_path, output, repeat):
    if not repeat:
        raise ValueError("frozen protocol requires --repeat for every complete result")
    config = json.loads(config_path.read_text())
    validate_config(config)
    output.mkdir(parents=True, exist_ok=True)
    source_hashes = {p: sha256(p) for p in SOURCES}
    contract = dict(
        runtime=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__),
        config=config,
        config_sha256=sha256(config_path),
        sources=source_hashes,
        datasets={
            name: sha256(Path(ds["path"]) / "dataset.json")
            for name, ds in config["datasets"].items()
        },
        swap_calendar="preceding-business-day UTC midnight; Wednesday triple; no weekend double charge",
        plan_sha256=sha256(".cursor/plans/long-term_macro_gate_99f085f3.plan.md"),
        plan_spec_sha256=hashlib.sha256(
            Path(".cursor/plans/long-term_macro_gate_99f085f3.plan.md")
            .read_text()
            .split("---", 2)[2]
            .encode()
        ).hexdigest(),
    )
    # Plan todo status changes are operational metadata, not a resume behavior change.
    behavior = {k: v for k, v in contract.items() if k != "plan_sha256"}
    digest = hashlib.sha256(json.dumps(behavior, sort_keys=True).encode()).hexdigest()
    contract["behavior_sha256"] = digest
    contract_path = output / "contract.json"
    if contract_path.exists():
        if json.loads(contract_path.read_text())["behavior_sha256"] != digest:
            raise ValueError("checkpoint contract/source/input drift; use a new output folder")
    else:
        atomic_json(contract_path, contract)
    for name, digest_value in source_hashes.items():
        snapshot = output / "source_snapshot" / name
        if snapshot.exists():
            if sha256(snapshot) != digest_value:
                raise ValueError("source snapshot drift")
        else:
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(name, snapshot)
    # Load once; both strategies use same object references and verified environment.
    datasets = {}
    for name, ds in config["datasets"].items():
        frame, ticks, broker, audit = load_discovery(Path(ds["path"]))
        if audit["start_utc"] != ds["start"] or audit["end_utc"] != ds["end"]:
            raise ValueError("requested discovery bounds disagree with manifest")
        datasets[name] = (frame, ticks, broker)
        atomic_json(output / f"input-{name}.json", audit)
        print(f"Loaded {name}: {len(frame)} bars / {len(ticks[0]):,} ticks", flush=True)
    rows = []
    for phase, catalog in (
        ("baseline", config["contracts"][:2]),
        ("tuning", config["contracts"][2:]),
    ):
        for name, ds in config["datasets"].items():
            raw, ticks, broker = datasets[name]
            bounds = [pd.Timestamp(ds[k], tz="UTC") for k in ("start", "split", "end")]
            windows = [
                ("full", bounds[0], bounds[2]),
                ("first_half", bounds[0], bounds[1]),
                ("second_half", bounds[1], bounds[2]),
            ]
            policy = SwapPolicy.from_broker(broker)
            for candidate in catalog:
                frame, rules = prepare_contract(raw, candidate)
                for window, start, end in windows:
                    for cost_name, cost_config in config["costs"].items():
                        costs = Costs(**cost_config)
                        for cost_view in ("no_swap", "swap"):
                            key = f"{name}-{window}-{cost_name}-{cost_view}-{candidate['name']}"
                            path = output / "cells" / (key + ".json")

                            def execute():
                                return replay(
                                    frame,
                                    ticks,
                                    broker,
                                    rules,
                                    costs,
                                    start=start,
                                    end=end,
                                    swap_policy=policy if cost_view == "swap" else None,
                                    capture_events=True,
                                )

                            result = json.loads(path.read_text()) if path.exists() else execute()
                            if not path.exists():
                                atomic_json(path, result)
                            proof = output / "repeats" / (key + ".json")
                            if proof.exists():
                                attestation = json.loads(proof.read_text())
                                if (
                                    attestation["behavior_sha256"] != digest
                                    or attestation["result_sha256"] != sha256(path)
                                    or attestation["status"] != "FULL_RESULT_MATCH"
                                ):
                                    raise ValueError("checkpoint/repeat integrity mismatch: " + key)
                            if repeat and not proof.exists():
                                fresh = execute()
                                if fresh != result:
                                    raise ValueError("complete-result repeat mismatch: " + key)
                                atomic_json(
                                    proof,
                                    dict(
                                        behavior_sha256=digest,
                                        result_sha256=sha256(path),
                                        status="FULL_RESULT_MATCH",
                                    ),
                                )
                            row = dict(
                                dataset=name,
                                window=window,
                                start_utc=start.isoformat(),
                                end_exclusive_utc=end.isoformat(),
                                cost=cost_name,
                                cost_view=cost_view,
                                contract=candidate["name"],
                                metrics=summary(result, frame, start, end),
                            )
                            rows.append(row)
                            print(
                                f"{key}: net={row['metrics']['net_usd']:.2f} DD={row['metrics']['max_dd_pct']:.2f} trades={row['metrics']['trades']}",
                                flush=True,
                            )
        atomic_json(
            output / (phase + "-matrix.json"),
            [r for r in rows if r["contract"] in {c["name"] for c in catalog}],
        )
        if phase == "baseline":
            report(output, rows, dict(status="BASELINE_COMPLETE_BEFORE_TUNING"), "baseline.md")
    decision = verdict(rows, config["contracts"])
    proofs = len(list((output / "repeats").glob("*.json")))
    if proofs != len(rows):
        raise ValueError("repeat proof count differs from matrix cells")
    atomic_json(
        output / "results.json",
        dict(
            rows=rows,
            verdict=decision,
            repeat_required=repeat,
            cells=len(rows),
            captured_utc=datetime.now(timezone.utc).isoformat(),
        ),
    )
    report(output, rows, decision)
    atomic_json(
        output / "COMPLETE.json",
        dict(
            behavior_sha256=digest,
            cells=len(rows),
            fresh_full_result_matches=proofs,
            report_sha256=sha256(output / "report.md"),
            results_sha256=sha256(output / "results.json"),
        ),
    )
    print(json.dumps(decision, indent=2), flush=True)
    return decision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--repeat", action="store_true", help="fresh COMPLETE result repeat of every cell"
    )
    args = parser.parse_args()
    run(args.config, args.output, args.repeat)


if __name__ == "__main__":
    main()
