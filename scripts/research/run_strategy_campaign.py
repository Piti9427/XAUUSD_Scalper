"""Bounded discovery campaign on verified Bid/Ask archive; never submits orders.

Resume only identical source/input hashes. Every trial stores protocol, metrics,
trade ledger and account equity checkpoints. Reused tape cannot qualify Demo.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path

from scripts.strategy import pure_b1_bars
from scripts.research.breakout_logic import Costs, Rules, replay
from scripts.research.strategy_campaign import qualifies
from scripts.research.tune_breakout_logic import START, TRAIN_END, END, load_data, sha256

STRESS = Costs(extra_spread=0.20, slippage=0.10)
WINDOWS = {"full": (START, END), "first_half": (START, TRAIN_END), "second_half": (TRAIN_END, END)}


def write_json(path, value):
    """Atomic completion marker; interrupted trial files can be replaced on resume."""
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def candidates():
    """384 unique, predeclared candidates; one hypothesis before combinations."""
    result = []
    for parent, target in (("core", 6.25), ("donchian48", 3.0)):
        seed = Rules(target_atr=target)
        # 48 depth experiments; then 96 delayed/reversal entries; then 48 exit experiments.
        for depth in (0.0, 0.15, 0.20, 0.25):
            for risk in (0.025, 0.05, 0.10):
                for daily in (0.05, 0.10, 0.20, 0.40):
                    result.append(
                        (
                            parent,
                            "depth_and_admission",
                            replace(
                                seed, min_depth_atr=depth, risk_cap=risk, daily_loss_limit=daily
                            ),
                        )
                    )
        for mode in ("confirm", "retest", "failed_reverse"):
            for depth in (0.0, 0.20):
                for risk in (0.025, 0.05):
                    for daily in (0.05, 0.10, 0.20, 0.40):
                        for exit_mode in ("fixed", "failed"):
                            result.append(
                                (
                                    parent,
                                    "delayed_or_failed_entry",
                                    replace(
                                        seed,
                                        entry_mode=mode,
                                        min_depth_atr=depth,
                                        risk_cap=risk,
                                        daily_loss_limit=daily,
                                        failed_closes=int(exit_mode == "failed"),
                                    ),
                                )
                            )
        for mode in ("immediate", "confirm", "retest", "failed_reverse"):
            for risk in (0.025, 0.05, 0.10):
                for exit_mode in ("failed", "stagnant", "trail", "failed_trail"):
                    result.append(
                        (
                            parent,
                            "protective_exit",
                            replace(
                                seed,
                                entry_mode=mode,
                                min_depth_atr=0.15
                                if exit_mode == "failed" and mode != "immediate" and risk != 0.10
                                else 0.0,
                                risk_cap=risk,
                                failed_closes=int(exit_mode in ("failed", "failed_trail")),
                                stagnant_bars=8 if exit_mode == "stagnant" else 0,
                                protect_mode="candle_trail"
                                if exit_mode in ("trail", "failed_trail")
                                else "off",
                            ),
                        )
                    )
    assert len(result) == 384
    assert len({(p, r) for p, _, r in result}) == 384
    return result


def compact(result):
    return {k: v for k, v in result.items() if k not in ("ledger", "equity")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--batches", type=int, default=8, help="1..8 batches, <=48 trials each")
    parser.add_argument("--commission-per-lot", type=float, default=0)
    parser.add_argument(
        "--commission-source", default="archived spread-only assumption; broker fee not verified"
    )
    args = parser.parse_args()
    if not 1 <= args.batches <= 8:
        parser.error("batches must be 1..8")
    base_cost = Costs(commission_per_lot=args.commission_per_lot)
    stress_cost = replace(STRESS, commission_per_lot=args.commission_per_lot)
    print("Auditing raw ticks, canonical bars, broker specification and hashes...", flush=True)
    frame, ticks, broker, audit = load_data()
    core = pure_b1_bars(frame).rename(columns={"hh30": "hh", "ll30": "ll"})
    frames = {"core": core, "donchian48": frame}
    sources = [
        "scripts/research/run_strategy_campaign.py",
        "scripts/research/strategy_campaign.py",
        "scripts/research/breakout_logic.py",
        "scripts/research/tune_breakout_logic.py",
        "scripts/research/data.py",
        "scripts/strategy.py",
    ]
    trials = candidates()
    protocol = dict(
        version=1,
        audit=audit,
        source_hashes={p: sha256(p) for p in sources},
        costs={"base": asdict(base_cost), "stress": asdict(stress_cost)},
        commission_source=args.commission_source,
        swap="not modeled; archived account entitlement and historical swap missing; Demo qualification blocked",
        capital=200,
        lot=0.01,
        broker=broker,
        max_trials=384,
        batch_size=48,
        windows={k: [s.isoformat(), e.isoformat()] for k, (s, e) in WINDOWS.items()},
        selection="discovery only: lower full DD, higher stress net, fewer changed rules, trial id",
        gates="each full/half scenario: profit and WR above both parents, DD below both and <=20%, RR>=1; trades full>=60 halves>=20",
        validation="requires verified >=12 months true Bid/Ask including >=3 months never selected; current184 days reused discovery only",
        execution="completed UTC M15; first quote <=90s; buy Ask sell Bid; SL actual quote with adverse slippage, TP target; exit allowance in admission",
        logic={
            "depth": "originating breakout close minus crossed prior boundary, signed and divided by originating ATR; >=threshold",
            "confirm": "next completed bar close remains beyond frozen boundary, else cancel",
            "retest": "within next4 completed bars low<=upper boundary (buy) or high>=lower (sell), close beyond; cancel on close inside",
            "failed_reverse": "within next2 completed bars close inside frozen [low,high], reverse originating direction; origin parent guards only; expiry cancels",
            "exit": "fixed parent SL2.5ATR/TP; failed1 close across original crossed boundary; stagnant8 bars net<=0; trail after net>=.5 initial cost-inclusiveR at close, low-tick/high+tick with cost-covering break-even, never widen; effective later quote",
            "daily": "block new entries after realized balance drop relative UTC day-start equity; missing midnight equity blocks admission",
        },
        candidates=[dict(parent=p, hypothesis=h, rules=asdict(r)) for p, h, r in trials],
    )
    output = args.output
    if args.resume:
        if json.loads((output / "protocol.json").read_text()) != protocol:
            raise ValueError("resume rejected: protocol/source/input hashes changed")
    else:
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / "protocol.json", protocol)
    baseline_hash_path = output / "baseline-hashes.json"
    baseline_hashes = (
        json.loads(baseline_hash_path.read_text())
        if args.resume and baseline_hash_path.exists()
        else {}
    )
    baselines = {}
    for window, (start, end) in WINDOWS.items():
        path = output / f"baselines-{window}.json"
        if args.resume and path.exists():
            if baseline_hashes.get(path.name) != sha256(path):
                raise ValueError("resume rejected: baseline changed or completion hash missing")
            baselines[window] = json.loads(path.read_text())
            continue
        parents = []
        for parent, target in (("core", 6.25), ("donchian48", 3.0)):
            pair = [
                replay(
                    frames[parent], ticks, broker, Rules(target_atr=target), c, start=start, end=end
                )
                for c in (base_cost, stress_cost)
            ]
            parents.append(pair)
        write_json(path, parents)
        baseline_hashes[path.name] = sha256(path)
        write_json(baseline_hash_path, baseline_hashes)
        baselines[window] = parents
        print(
            f"Baseline {window}: "
            + str(
                [
                    (round(p[0]["net_usd"], 2), round(p[0]["max_dd_pct"], 2), p[0]["trades"])
                    for p in parents
                ]
            ),
            flush=True,
        )
    rows = []
    for number, (parent, hypothesis, rules) in enumerate(trials[: args.batches * 48], 1):
        directory = output / f"trial-{number:03d}"
        marker = directory / "result.json"
        if args.resume and marker.exists():
            completed = json.loads(marker.read_text())
            if any(
                sha256(directory / name) != digest
                for name, digest in completed["artifact_hashes"].items()
            ):
                raise ValueError("resume rejected: trial artifact changed")
            expected_names = {f"{w}-{c}.json" for w in WINDOWS for c in ("base", "stress")}
            if set(completed["artifact_hashes"]) != expected_names:
                raise ValueError("resume rejected: incomplete scenario hashes")
            recovered = {}
            for window in WINDOWS:
                pair = []
                for scenario in ("base", "stress"):
                    artifact = json.loads((directory / f"{window}-{scenario}.json").read_text())
                    if artifact["rules"] != asdict(rules):
                        raise ValueError("resume rejected: rules differ from frozen protocol")
                    pair.append(compact(artifact))
                recovered[window] = pair
            recovered_pass = all(
                qualifies(*pair, baselines[w], min_trades=60 if w == "full" else 20)
                for w, pair in recovered.items()
            )
            if (
                completed["metrics"] != recovered
                or completed["discovery_pass"] != recovered_pass
                or completed["rules"] != asdict(rules)
                or completed["parent"] != parent
                or completed["trial"] != number
                or completed["hypothesis"] != hypothesis
            ):
                raise ValueError(
                    "resume rejected: selection metadata differs from verified artifacts"
                )
            rows.append(completed)
            continue
        directory.mkdir(exist_ok=True)
        metrics = {}
        passed = True
        for window, (start, end) in WINDOWS.items():
            pair = []
            for scenario, cost in (("base", base_cost), ("stress", stress_cost)):
                result = replay(frames[parent], ticks, broker, rules, cost, start=start, end=end)
                write_json(directory / f"{window}-{scenario}.json", result)
                pair.append(compact(result))
            metrics[window] = pair
            passed &= qualifies(*pair, baselines[window], min_trades=60 if window == "full" else 20)
        row = dict(
            trial=number,
            parent=parent,
            hypothesis=hypothesis,
            rules=asdict(rules),
            discovery_pass=passed,
            metrics=metrics,
        )
        row["artifact_hashes"] = {
            p.name: sha256(p)
            for p in sorted(directory.glob("*-base.json")) + sorted(directory.glob("*-stress.json"))
        }
        write_json(marker, row)
        rows.append(row)
        print(
            f"Trial {number}/384 {parent} {hypothesis}: net={metrics['full'][0]['net_usd']:.2f} DD={metrics['full'][0]['max_dd_pct']:.2f} pass={passed}",
            flush=True,
        )
        if number % 48 == 0:
            write_json(output / f"batch-{number // 48:02d}.json", rows[-48:])
    eligible = [r for r in rows if r["discovery_pass"]]
    winner = min(
        eligible,
        key=lambda r: (
            r["metrics"]["full"][0]["max_dd_pct"],
            -r["metrics"]["full"][1]["net_usd"],
            sum(
                v != asdict(Rules(target_atr=r["rules"]["target_atr"]))[k]
                for k, v in r["rules"].items()
            ),
            r["trial"],
        ),
        default=None,
    )
    verdict = dict(
        completed_trials=len(rows),
        campaign_exhausted=len(rows) == 384,
        qualified_discovery=len(eligible),
        frozen_discovery_winner=winner,
        status="AWAITING_UNSEEN_DATA"
        if winner
        else "NO_QUALIFIED_CANDIDATE"
        if len(rows) == 384
        else "DISCOVERY_INCOMPLETE",
        demo_status="BLOCKED",
        missing_evidence=[
            ">=12months nonempty real ticks",
            ">=3months untouched validation with >=30 trades",
            "sourced broker commission and swap",
            "MQL5 real-tick parity and delay testing",
            "shadow >=20trading days and >=30eligible decisions, zero unexplained mismatch",
        ],
    )
    write_json(output / "verdict.json", verdict)
    print(
        json.dumps({k: v for k, v in verdict.items() if k != "frozen_discovery_winner"}), flush=True
    )


if __name__ == "__main__":
    main()
