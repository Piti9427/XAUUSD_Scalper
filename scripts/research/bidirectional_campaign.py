"""Trial30 challenger research. Two-sided fills and strict scenario improvements."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from itertools import product
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.research.breakout_logic import Rules, Costs, replay
from scripts.research.run_strategy_campaign import write_json
from scripts.research.tune_breakout_logic import load_data, sha256, START, TRAIN_END, END
from scripts.research.public_exness_archive import load_discovery


def candidate_frame(frame, buy_filter, depth, buy_signal="breakout", signal_spec=None):
    """Causal completed-bar signals; default D48 or explicit directional horizons."""
    if buy_filter not in ("off", "ema50", "prior_day", "body", "extreme", "ema_prior"):
        raise ValueError("unknown BUY filter")
    if depth not in (0.0, 0.15):
        raise ValueError("unknown depth")
    if buy_signal not in ("breakout", "lower_wick", "trend_pullback"):
        raise ValueError("unknown BUY setup")
    if signal_spec is not None:
        if buy_signal != "breakout":
            raise ValueError("horizon contract requires breakout setup")
        if set(signal_spec) - {"max_range_atr"} != {"buy_lookback", "sell_lookback", "trend_span"}:
            raise ValueError("unknown signal contract")
        if any(signal_spec[k] not in (12, 24, 48, 96) for k in ("buy_lookback", "sell_lookback")):
            raise ValueError("unsupported horizon")
        if signal_spec["trend_span"] not in (0, 50, 200):
            raise ValueError("unsupported trend span")
        maximum = signal_spec.get("max_range_atr", 0.0)
        if maximum not in (0.0, 6.0, 9.0, 12.0):
            raise ValueError("unsupported range compression")
        frame = frame.copy()
        frame["hh"] = frame.high.rolling(signal_spec["buy_lookback"]).max().shift(1)
        frame["ll"] = frame.low.rolling(signal_spec["sell_lookback"]).min().shift(1)
        frame["direction"] = np.select([frame.close > frame.hh, frame.close < frame.ll], [1, -1], 0)
        if maximum:
            buy_low = frame.low.rolling(signal_spec["buy_lookback"]).min().shift(1)
            sell_high = frame.high.rolling(signal_spec["sell_lookback"]).max().shift(1)
            width = pd.Series(
                np.where(frame.direction == 1, frame.hh - buy_low, sell_high - frame.ll),
                index=frame.index,
            )
            prior_atr = frame.atr.shift(1)
            compressed = (prior_atr > 0) & (width / prior_atr <= maximum)
            frame.loc[~compressed.fillna(False), "direction"] = 0
        if signal_spec["trend_span"]:
            span = signal_spec["trend_span"]
            average = frame.close.ewm(span=span, adjust=False, min_periods=span).mean()
            aligned = (frame.direction * (frame.close - average) > 0) & (
                frame.direction * (average - average.shift(4)) > 0
            )
            frame.loc[~aligned.fillna(False), "direction"] = 0
    result = frame.copy()
    ema = frame.close.ewm(span=50, adjust=False, min_periods=50).mean()
    trend = (frame.close > ema) & (ema > ema.shift(4))
    if buy_signal != "breakout":
        result.loc[result.direction == 1, "direction"] = 0
        trigger = (
            (frame.low < frame.ll) & (frame.close > frame.ll) & (frame.high <= frame.hh)
            if buy_signal == "lower_wick"
            else trend
            & (frame.close.shift(1) < frame.open.shift(1))
            & (frame.close > frame.high.shift(1))
        )
        admitted = trigger.fillna(False) & (frame.direction != -1)
        result.loc[admitted, "direction"] = 1
        result.loc[admitted, "hh"] = (
            frame.ll if buy_signal == "lower_wick" else frame.high.shift(1)
        )[admitted]
    daily = frame.resample("1D").agg({"open": "first", "close": "last"})
    prior = np.sign(daily.close - daily.open).shift(1)
    prior_up = prior.reindex((frame.index + pd.Timedelta(minutes=15)).normalize())
    prior_up.index = frame.index
    span = frame.high - frame.low
    allowed = {
        "off": result.direction == 1,
        "ema50": trend,
        "prior_day": prior_up == 1,
        "body": (span > 0) & (frame.close - frame.open >= span / 2),
        "extreme": (span > 0) & (frame.close >= frame.high - span * 0.2),
        "ema_prior": trend & (prior_up == 1),
    }[buy_filter]
    result.loc[(result.direction == 1) & ~allowed.fillna(False), "direction"] = 0
    if depth:
        boundary = np.where(result.direction == 1, result.hh, result.ll)
        distance = result.direction * (result.close - boundary) / result.atr
        result.loc[distance < depth, "direction"] = 0
    return result


def qualifies_trial30(pair, baseline, min_trades):
    """Require both executed sides, fixed-lot risk and improvement in each scenario."""
    if len(pair) != 2 or len(baseline) != 2:
        return False
    keys = (
        "net_usd",
        "win_rate",
        "realized_rr",
        "max_dd_pct",
        "max_admitted_risk_pct",
        "trades",
        "buy_trades",
        "sell_trades",
    )
    for candidate, parent in zip(pair, baseline):
        if any(candidate.get(k) is None or not math.isfinite(candidate[k]) for k in keys):
            return False
        if any(parent.get(k) is None or not math.isfinite(parent[k]) for k in keys[:4]):
            return False
        if (
            candidate["trades"] < min_trades
            or candidate["buy_trades"] < 1
            or candidate["sell_trades"] < 1
            or not 0 <= candidate["max_admitted_risk_pct"] <= 10
            or not 0 <= candidate["max_dd_pct"] <= min(30, parent["max_dd_pct"])
            or not 0 <= candidate["win_rate"] <= 1
            or candidate["net_usd"] <= max(0, parent["net_usd"])
            or candidate["win_rate"] <= parent["win_rate"]
            or candidate["realized_rr"] <= max(1, parent["realized_rr"])
        ):
            return False
    return True


def metrics(result):
    summary = {k: v for k, v in result.items() if k not in ("ledger", "equity")}
    summary["buy_trades"] = sum(p["direction"] == 1 for p in result["ledger"])
    summary["sell_trades"] = sum(p["direction"] == -1 for p in result["ledger"])
    if summary["buy_trades"] + summary["sell_trades"] != summary["trades"]:
        raise ValueError("ledger direction/count mismatch")
    return summary


def contracts(catalog="quality"):
    """Frozen catalogs; causal signals, admission, reward and protection interactions."""

    def rules(guard, target, protection, activation):
        return asdict(
            Rules(
                entry_guard=guard,
                daily_loss_limit=0.2,
                target_atr=target,
                protect_mode=protection,
                protect_after_r=activation,
            )
        )

    if catalog == "compression":
        return [
            dict(
                hypothesis="prior_range_compression",
                buy_filter="off",
                depth=0.0,
                signal_spec=dict(
                    buy_lookback=buy, sell_lookback=sell, trend_span=trend, max_range_atr=maximum
                ),
                rules=rules(guard, 3.0, protection, 1.0),
            )
            for buy, sell, maximum, trend, guard, protection in product(
                (24, 48, 96),
                (24, 48, 96),
                (6.0, 9.0, 12.0),
                (0, 50),
                ("off", "body_dominant"),
                ("break_even", "candle_trail"),
            )
        ]

    if catalog == "horizon_quality":
        return [
            dict(
                hypothesis="horizon_candle_quality",
                buy_filter="off",
                depth=0.0,
                signal_spec=dict(buy_lookback=buy, sell_lookback=sell, trend_span=0),
                rules=rules(guard, 3.0, protection, activation),
            )
            for buy, sell, guard, protection, activation in product(
                (12, 24, 48, 96),
                (12, 24, 48, 96),
                ("body_dominant", "close_extreme"),
                ("break_even", "candle_trail"),
                (1.0, 1.5),
            )
        ]

    if catalog == "horizons":
        return [
            dict(
                hypothesis="direction_horizons_and_trend",
                buy_filter="off",
                depth=0.0,
                signal_spec=dict(buy_lookback=buy, sell_lookback=sell, trend_span=trend),
                rules=rules("off", target, protection, activation),
            )
            for buy, sell, trend, target, protection, activation in product(
                (12, 24, 48, 96),
                (12, 24, 48, 96),
                (0, 50, 200),
                (3.0, 6.25),
                ("break_even", "candle_trail"),
                (1.0, 1.5),
            )
        ]

    if catalog == "admission":
        return [
            dict(
                hypothesis="selective_buy_admission",
                buy_signal="breakout",
                buy_filter=buy_filter,
                depth=0.0,
                rules=asdict(
                    Rules(
                        buy_pause_drawdown=pause,
                        risk_mode=risk_mode,
                        entry_guard=guard,
                        protect_mode=protection,
                        protect_after_r=1.0,
                        target_atr=target,
                        daily_loss_limit=0.2,
                    )
                ),
            )
            for pause, risk_mode, guard, protection, target, buy_filter in product(
                (0.025, 0.05, 0.10),
                ("static", "drawdown_steps"),
                ("off", "body_dominant"),
                ("break_even", "candle_trail"),
                (3.0, 6.25),
                ("off", "prior_day"),
            )
        ]

    if catalog == "tuning":
        result = []
        for signal, guard, stop, rr, protection, activation in product(
            ("breakout", "lower_wick"),
            ("off", "body_dominant"),
            ("atr", "trigger", "boundary"),
            (1.5, 2.0),
            ("break_even", "candle_trail"),
            (0.5, 1.0),
        ):
            result.append(
                dict(
                    hypothesis="stop_geometry",
                    buy_signal=signal,
                    buy_filter="prior_day",
                    depth=0.0,
                    rules=asdict(
                        Rules(
                            entry_guard=guard,
                            stop_mode=stop,
                            target_rr=rr,
                            daily_loss_limit=0.2,
                            protect_mode=protection,
                            protect_after_r=activation,
                        )
                    ),
                )
            )
        for entry, stop, guard, rr, protection, buy_filter in product(
            ("confirm", "retest"),
            ("atr", "trigger", "boundary"),
            ("off", "body_dominant"),
            (1.5, 2.0),
            ("break_even", "candle_trail"),
            ("off", "prior_day"),
        ):
            result.append(
                dict(
                    hypothesis="entry_timing",
                    buy_signal="breakout",
                    buy_filter=buy_filter,
                    depth=0.0,
                    rules=asdict(
                        Rules(
                            entry_mode=entry,
                            entry_guard=guard,
                            stop_mode=stop,
                            target_rr=rr,
                            daily_loss_limit=0.2,
                            protect_mode=protection,
                            protect_after_r=1.0,
                        )
                    ),
                )
            )
        for entry, failed, stagnant, target, protection, buy_filter in product(
            ("immediate", "confirm"),
            (0, 1, 2),
            (0, 4),
            (3.0, 6.25),
            ("break_even", "candle_trail"),
            ("off", "prior_day"),
        ):
            result.append(
                dict(
                    hypothesis="false_breakout_exit",
                    buy_signal="breakout",
                    buy_filter=buy_filter,
                    depth=0.0,
                    rules=asdict(
                        Rules(
                            entry_mode=entry,
                            failed_closes=failed,
                            stagnant_bars=stagnant,
                            target_atr=target,
                            daily_loss_limit=0.2,
                            protect_mode=protection,
                            protect_after_r=1.0,
                        )
                    ),
                )
            )
        return result

    if catalog == "symmetric":
        return [
            dict(
                buy_signal=signal,
                buy_filter=buy_filter,
                depth=0.0,
                rules=rules(guard, target, protection, activation),
            )
            for guard, signal, buy_filter, target, protection, activation in product(
                ("body_dominant", "close_extreme", "prior_day"),
                ("breakout", "lower_wick"),
                ("off", "prior_day"),
                (3.0, 6.25),
                ("break_even", "candle_trail"),
                (1.0, 1.5),
            )
        ]
    if catalog == "buy_setups":
        return [
            dict(
                buy_signal=signal,
                buy_filter=guard,
                depth=depth,
                rules=rules("off", target, protection, activation),
            )
            for signal, guard, depth, target, protection, activation in product(
                ("lower_wick", "trend_pullback"),
                ("off", "prior_day", "body"),
                (0.0, 0.15),
                (3.0, 6.25),
                ("break_even", "candle_trail"),
                (1.0, 1.5),
            )
        ]
    if catalog != "quality":
        raise ValueError("unknown catalog")
    return [
        dict(
            buy_filter=guard,
            depth=depth,
            rules=rules("off", target, protection, activation),
        )
        for guard, depth, target, protection, activation in product(
            ("off", "ema50", "prior_day", "body", "extreme", "ema_prior"),
            (0.0, 0.15),
            (3.0, 6.25),
            ("break_even", "candle_trail"),
            (1.0, 1.5),
        )
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--resume", action="store_true")
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
    costs = dict(base=Costs(), stress=Costs(extra_spread=0.2, slippage=0.1))
    baseline = Rules(
        entry_guard="sell_only",
        daily_loss_limit=0.2,
        protect_mode="break_even",
        protect_after_r=1.0,
    )
    sources = [
        "scripts/research/bidirectional_campaign.py",
        "scripts/research/breakout_logic.py",
        "scripts/research/tune_breakout_logic.py",
        "scripts/research/public_exness_archive.py",
        "scripts/research/data.py",
        "scripts/research/run_strategy_campaign.py",
        "scripts/strategy.py",
    ]
    protocol = dict(
        version=3,
        catalog=args.catalog,
        baseline_snapshot="RESEARCH-D48-SELL-BE1R-20261001-T030",
        baseline_rules=asdict(baseline),
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
    output = args.output
    if args.resume:
        if json.loads((output / "protocol.json").read_text()) != protocol:
            raise ValueError("resume protocol/source/input mismatch")
    else:
        output.mkdir(parents=True, exist_ok=False)
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
            )
        )
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
                result = replay(prepared, ticks, broker, rules, cost, start=s, end=e)
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
            w: qualifies_trial30(pair, reference[w], 60 if w == "full" else 20)
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
            max(pair[1]["max_dd_pct"] for pair in r["metrics"].values()),
            -r["metrics"]["full"][1]["net_usd"],
            r["trial"],
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
