"""Trial30 challenger research. Two-sided fills and strict scenario improvements."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.research.breakout_logic import Rules, Costs, replay
from scripts.research.campaign_signals import candidate_frame as candidate_frame
from scripts.research.campaign_qualification import qualifies_trial30 as qualifies_trial30, metrics
from scripts.research.campaign_catalogs import contracts as contracts
from scripts.research.run_strategy_campaign import write_json
from scripts.research.tune_breakout_logic import load_data, sha256, START, TRAIN_END, END
from scripts.research.public_exness_archive import load_discovery
from scripts.research.m5_retest import build_m5, retest_frame


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--require-calendar-year", action="store_true")
    parser.add_argument(
        "--qualification-policy", choices=("strict_v1", "profit_dd_v2"), default="strict_v1"
    )
    parser.add_argument(
        "--catalog",
        choices=(
            "quality",
            "buy_setups",
            "symmetric",
            "tuning",
            "admission",
            "horizons",
            "horizon_quality",
            "compression",
            "oscillator",
            "hybrid_oscillator",
            "hybrid_admission",
            "hybrid_invalidation",
            "hybrid_reward",
            "hybrid_reward_session",
            "hybrid_reward_admission",
            "hybrid_reward_quality",
            "hybrid_reward_geometry",
            "hybrid_atr_stop",
            "hybrid_parent_horizon",
            "hybrid_parent_trend",
            "hybrid_parent_quality",
            "hybrid_parent_reward_fine",
            "hybrid_parent_reward_pause",
            "hybrid_parent_risk",
            "hybrid_parent_atr",
            "hybrid_parent_protection",
            "hybrid_parent_invalidation",
            "annual_bidirectional",
            "annual_risk",
            "annual_confirmation",
            "annual_hybrid_unpaused",
            "annual_sessions",
            "annual_directional",
            "annual_directional_trend",
            "annual_directional_circuit",
            "annual_directional_fine",
            "annual_fast_quality",
            "annual_short_sell",
            "annual_sizing",
            "annual_short_buy",
            "annual_m5_intraday",
            "annual_m5_bounded24",
            "annual_m5_hybrid",
            "annual_m5_hybrid_quality",
            "annual_m5_directional_sizing",
            "annual_m5_atr_reward",
        ),
        default="quality",
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    catalog = contracts(args.catalog)
    total = len(catalog)
    if len({json.dumps(c, sort_keys=True) for c in catalog}) != total:
        raise ValueError("duplicate frozen contract")
    limit = total if args.limit is None else args.limit
    if not 1 <= limit <= total:
        parser.error(f"limit must be 1..{total}")
    print("Auditing source and actual Bid/Ask inputs...", flush=True)
    if args.dataset:
        frame, ticks, broker, audit = load_discovery(args.dataset)
        start = pd.Timestamp(audit["start_utc"], tz="UTC")
        end = pd.Timestamp(audit["end_utc"], tz="UTC")
        middle = (start + (end - start) / 2).normalize()
        windows = dict(full=(start, end), first_half=(start, middle), second_half=(middle, end))
    else:
        frame, ticks, broker, audit = load_data()
        windows = dict(
            full=(START, END), first_half=(START, TRAIN_END), second_half=(TRAIN_END, END)
        )
    annual_coverage = None
    if args.require_calendar_year:
        start, end = windows["full"]
        if end - start < pd.Timedelta(days=365):
            raise ValueError("annual research requires at least 365 calendar days")
        if args.dataset is None:
            raise ValueError("annual research requires an audited monthly dataset")
        metadata_path = args.dataset / "dataset.json"
        if sha256(metadata_path) != audit["dataset_sha256"]:
            raise ValueError("annual dataset metadata changed after loading")
        metadata = json.loads(metadata_path.read_text())
        expected = list(pd.date_range(start, end, freq="MS", inclusive="left"))
        imported = metadata["imported_months"]
        if (
            start.day != 1
            or end.day != 1
            or len(expected) < 12
            or [item["month"] for item in imported] != [m.strftime("%Y-%m") for m in expected]
        ):
            raise ValueError("annual research requires every audited calendar month in order")
        for month, item in zip(expected, imported):
            following = month + pd.offsets.MonthBegin(1)
            low, high = np.asarray(
                np.searchsorted(
                    ticks[0],
                    np.asarray([month.value // 10**6, following.value // 10**6], dtype=np.int64),
                )
            )
            bars = frame.loc[(frame.index >= month) & (frame.index < following)]
            if (
                high - low != item["ticks"]
                or item["ticks"] <= 0
                or len(bars) != item["canonical_bars"]
                or len(bars) == 0
            ):
                raise ValueError("annual research monthly tick/bar coverage mismatch")
        if sum(item["ticks"] for item in imported) != len(ticks[0]):
            raise ValueError("annual research contains ticks outside declared months")
        annual_coverage = dict(
            minimum_calendar_days=365,
            calendar_days=(end - start).days,
            verified_months=[item["month"] for item in imported],
            monthly_ticks=[item["ticks"] for item in imported],
            monthly_canonical_bars=[item["canonical_bars"] for item in imported],
        )
    costs = dict(base=Costs(), stress=Costs(extra_spread=0.2, slippage=0.1))
    m5 = None
    if args.catalog.startswith("annual_m5_"):
        m5 = build_m5(ticks, args.output / "m5_input", audit["dataset_sha256"])
        audit["m5_manifest"] = json.loads((args.output / "m5_input/manifest.json").read_text())
    baseline = Rules(
        entry_guard="sell_only",
        daily_loss_limit=0.2,
        protect_mode="break_even",
        protect_after_r=1.0,
    )
    sources = [
        "scripts/research/bidirectional_campaign.py",
        "scripts/research/breakout_logic.py",
        "scripts/research/breakout_models.py",
        "scripts/research/breakout_signals.py",
        "scripts/research/breakout_entry.py",
        "scripts/research/breakout_replay.py",
        "scripts/research/campaign_signals.py",
        "scripts/research/campaign_qualification.py",
        "scripts/research/campaign_catalogs.py",
        "scripts/research/catalog_common.py",
        "scripts/research/catalog_m5.py",
        "scripts/research/catalog_annual.py",
        "scripts/research/catalog_parent.py",
        "scripts/research/catalog_hybrid.py",
        "scripts/research/catalog_basic.py",
        "scripts/research/tune_breakout_logic.py",
        "scripts/research/public_exness_archive.py",
        "scripts/research/data.py",
        "scripts/research/run_strategy_campaign.py",
        "scripts/strategy.py",
    ]
    if m5 is not None:
        sources.append("scripts/research/m5_retest.py")
    protocol = dict(
        version=3,
        catalog=args.catalog,
        baseline_snapshot="RESEARCH-D48-SELL-BE1R-20261001-T030",
        baseline_rules=asdict(baseline),
        baseline_rr_policy="zero_reference_only_when_all_executed_baseline_trades_are_losses; candidateRR>1; undefined_otherwise_reject",
        candidates=catalog,
        windows={k: [s.isoformat(), e.isoformat()] for k, (s, e) in windows.items()},
        costs={k: asdict(v) for k, v in costs.items()},
        broker=broker,
        audit=audit,
        source_hashes={p: sha256(p) for p in sources},
        gates="Each full/half base/stress: net, WR, RR strictly above trial30; DD<=trial30 and<=30%; risk<=10%; both executed sides; trades>=60 full,>=20 halves",
        selection="lowest worst-window stress DD, highest full stress net, trial id",
        limitations="Reused discovery, no untouched validation; commission0 assumed, swap not modeled; no MT5 or notification APIs; not runtime authorization",
    )
    if args.qualification_policy == "profit_dd_v2":
        protocol.update(
            qualification_policy="profit_dd_v2",
            baseline_rr_policy="reported_only; no RR or WR superiority gate",
            gates="Each full/half base/stress: net>max(0,trial30); DD<=trial30 and<=30%; risk<=20%; both executed sides; trades>=60 full,>=20 halves",
            selection="highest full stress net, lowest worst-scenario DD, trial id",
        )
    if annual_coverage is not None:
        protocol["annual_coverage"] = annual_coverage
    output = args.output
    if args.resume:
        if json.loads((output / "protocol.json").read_text()) != protocol:
            raise ValueError("resume protocol/source/input mismatch")
    else:
        if m5 is None:
            output.mkdir(parents=True, exist_ok=False)
        elif (output / "protocol.json").exists():
            raise ValueError("campaign exists; use --resume")
        write_json(output / "protocol.json", protocol)
    for path, digest in protocol["source_hashes"].items():
        content = Path(path).read_bytes()
        if sha256(path) != digest:
            raise ValueError("source changed during freeze")
        snapshot = output / "source_snapshot" / path
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.exists() and snapshot.read_bytes() != content:
            raise ValueError("source snapshot mismatch")
        snapshot.write_bytes(content)

    verified_scenarios = 0
    entry_cache = {}

    def evaluate(directory, rules, candidate):
        nonlocal verified_scenarios
        directory.mkdir(exist_ok=True)
        marker = directory / "result.json"
        names = [f"{w}-{c}.json" for w in windows for c in costs]
        prepared = (
            frame
            if candidate is None
            else candidate_frame(
                frame,
                candidate["buy_filter"],
                candidate["depth"],
                candidate.get("buy_signal", "breakout"),
                candidate.get("signal_spec"),
                candidate.get("oscillator_spec"),
                candidate.get("entry_session", "all"),
            )
        )
        if candidate is not None and "hybrid_buy_horizon" in candidate:
            h = candidate["hybrid_buy_horizon"]
            buys = candidate_frame(
                frame, "off", 0, signal_spec=dict(buy_lookback=h, sell_lookback=h, trend_span=50)
            )
            sells = candidate_frame(
                frame,
                "off",
                0,
                oscillator_spec=dict(
                    period=14,
                    threshold=25,
                    trend_span=50,
                    side="buy",
                    parent_lookback=candidate["hybrid_sell_horizon"],
                    parent_trend_span=200,
                ),
                sell_filter=candidate.get("sell_filter", "off"),
            )
            prepared = sells.copy()
            long = (buys.direction == 1) & (sells.direction != -1)
            prepared["direction"] = np.select([sells.direction == -1, long], [-1, 1], 0)
            prepared.loc[long, ["hh", "ll"]] = buys.loc[long, ["hh", "ll"]]
        entry_kwargs = {}
        if candidate is not None and "m5_ttl" in candidate:
            cache_key = json.dumps(
                {
                    k: candidate.get(k)
                    for k in (
                        "signal_spec",
                        "oscillator_spec",
                        "m5_ttl",
                        "m5_buy_only",
                        "hybrid_buy_horizon",
                        "hybrid_sell_horizon",
                        "sell_filter",
                    )
                },
                sort_keys=True,
            )
            if cache_key not in entry_cache:
                entry_cache[cache_key] = retest_frame(
                    prepared, m5, candidate["m5_ttl"], buy_only=candidate.get("m5_buy_only", False)
                )
            entry_kwargs["entry_frame"] = entry_cache[cache_key]
        if args.resume and marker.exists():
            previous = json.loads(marker.read_text())
            if set(previous["artifact_hashes"]) != set(names):
                raise ValueError("resume artifact set mismatch")
            if any(sha256(directory / n) != previous["artifact_hashes"][n] for n in names):
                raise ValueError("resume artifact hash mismatch")
            summary: dict[str, list[dict[str, Any]]] = {}
            for w in windows:
                summary[w] = []
                for c in costs:
                    result = json.loads((directory / f"{w}-{c}.json").read_text())
                    if (
                        result["rules"] != asdict(rules)
                        or result["costs"] != asdict(costs[c])
                        or result["start_utc"] != windows[w][0].isoformat()
                        or result["end_exclusive_utc"] != windows[w][1].isoformat()
                    ):
                        raise ValueError("resume artifact contract mismatch")
                    fresh = replay(
                        prepared,
                        ticks,
                        broker,
                        rules,
                        costs[c],
                        start=windows[w][0],
                        end=windows[w][1],
                        **entry_kwargs,
                    )
                    if fresh != result:
                        raise ValueError("resume artifact differs from authoritative fresh replay")
                    verified_scenarios += 1
                    summary[w].append(metrics(result))
            if previous["metrics"] != summary or previous["candidate"] != candidate:
                raise ValueError("resume artifact selection metadata mismatch")
            return summary
        summary = {}
        for w, (s, e) in windows.items():
            summary[w] = []
            for c, cost in costs.items():
                result = replay(
                    prepared, ticks, broker, rules, cost, start=s, end=e, **entry_kwargs
                )
                write_json(directory / f"{w}-{c}.json", result)
                summary[w].append(metrics(result))
        write_json(
            marker,
            dict(
                candidate=candidate,
                metrics=summary,
                artifact_hashes={n: sha256(directory / n) for n in names},
            ),
        )
        return summary

    reference = evaluate(output / "baseline", baseline, None)
    print(
        "Baseline: "
        + json.dumps(
            {w: [(p["net_usd"], p["max_dd_pct"]) for p in pair] for w, pair in reference.items()}
        ),
        flush=True,
    )
    rows = []
    for number, candidate in enumerate(catalog[:limit], 1):
        summary = evaluate(output / f"trial-{number:03d}", Rules(**candidate["rules"]), candidate)
        passes = {
            w: qualifies_trial30(
                pair,
                reference[w],
                60 if w == "full" else 20,
                **(
                    {"policy": args.qualification_policy}
                    if args.qualification_policy != "strict_v1"
                    else {}
                ),
            )
            for w, pair in summary.items()
        }
        row = dict(
            trial=number,
            candidate=candidate,
            metrics=summary,
            window_pass=passes,
            discovery_pass=all(passes.values()),
        )
        rows.append(row)
        print(
            f"Trial {number}/{total} full net={summary['full'][0]['net_usd']:.2f} "
            f"DD={summary['full'][0]['max_dd_pct']:.2f} pass={row['discovery_pass']}",
            flush=True,
        )
        write_json(output / "progress.json", dict(completed_trials=number, last=row))
    eligible = [r for r in rows if r["discovery_pass"]]
    leader = min(
        eligible,
        key=lambda r: (
            (
                -r["metrics"]["full"][1]["net_usd"],
                max(m["max_dd_pct"] for pair in r["metrics"].values() for m in pair),
                r["trial"],
            )
            if args.qualification_policy == "profit_dd_v2"
            else (
                max(pair[1]["max_dd_pct"] for pair in r["metrics"].values()),
                -r["metrics"]["full"][1]["net_usd"],
                r["trial"],
            )
        ),
        default=None,
    )
    exhausted = len(rows) == total
    winner = leader if exhausted else None
    verdict = dict(
        completed_trials=len(rows),
        total_contracts=total,
        verified_scenarios=verified_scenarios,
        verification="FRESH_REPLAY_MATCH"
        if verified_scenarios == 6 * (len(rows) + 1)
        else "PARTIAL_FRESH_REPLAY"
        if verified_scenarios
        else "INITIAL_REPLAY",
        qualified_discovery=len(eligible),
        campaign_exhausted=exhausted,
        frozen_discovery_winner=winner,
        provisional_leader=leader if not exhausted else None,
        status="AWAITING_INDEPENDENT_VALIDATION"
        if winner
        else "NO_QUALIFIED_CANDIDATE"
        if exhausted
        else "DISCOVERY_INCOMPLETE",
        deployment="UNCHANGED",
        rows=rows,
    )
    if args.qualification_policy == "profit_dd_v2":
        verdict["qualification_policy"] = args.qualification_policy
        verdict["cost_validation"] = (
            "COST_INCONCLUSIVE: historical commission0 assumed; swap omitted"
        )
        if winner:
            verdict["status"] = "COST_INCONCLUSIVE"
    write_json(output / "verdict.json", verdict)
    print(
        json.dumps(
            {k: v for k, v in verdict.items() if k not in ("rows", "frozen_discovery_winner")}
        ),
        flush=True,
    )
    return verdict


if __name__ == "__main__":
    main()
