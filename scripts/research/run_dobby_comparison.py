"""Frozen-protocol offline Dobby-vs-C22 evaluation; never starts a trading host."""

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

from scripts.research.breakout_models import Costs
from scripts.research.breakout_replay import replay as c22_replay
from scripts.research.dobby_replay import DobbyRules, replay as dobby_replay
from scripts.research.reward156_campaign import Checkpoints
from scripts.research.reward156_search import prepare_candidate
from scripts.research.reward156_tuning import atomic_json
from scripts.research.rollover import SwapPolicy
from scripts.research.tune_breakout_logic import sha256

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data/research_output_four_strategy_full_history_2026_10_04/input"
SOURCES = [
    "scripts/research/run_dobby_comparison.py",
    "scripts/research/dobby_replay.py",
    "scripts/research/breakout_replay.py",
    "scripts/research/breakout_models.py",
    "scripts/research/breakout_entry.py",
    "scripts/research/breakout_signals.py",
    "scripts/research/reward156_search.py",
    "scripts/research/reward156_tuning.py",
    "scripts/research/reward156_campaign.py",
    "scripts/research/rollover.py",
    "scripts/research/campaign_signals.py",
    "scripts/research/breakout_logic.py",
    "scripts/strategy.py",
    "config/c22h4-demo.json",
    "tests/research/test_dobby_replay.py",
]


def read(path):
    return json.loads(Path(path).read_text())


def verify_cash(result):
    ledger = result["ledger"]
    if not np.isclose(sum(t["net"] for t in ledger), result["net_usd"], atol=1e-7, rtol=0):
        raise ValueError("ledger/cash mismatch")
    if not np.isclose(200 + result["net_usd"], result["final_balance"], atol=1e-7, rtol=0):
        raise ValueError("balance mismatch")
    if not np.isclose(sum(t["swap_usd"] for t in ledger), result["swap_usd"], atol=1e-7, rtol=0):
        raise ValueError("swap mismatch")
    previous = None
    balance = 200.0
    for row in ledger:
        if not np.isclose(balance, row["entry_equity"], atol=1e-7, rtol=0):
            raise ValueError("equity path mismatch")
        born, closed = pd.Timestamp(row["entry_time_utc"]), pd.Timestamp(row["exit_time_utc"])
        if born > closed or (previous is not None and previous > born):
            raise ValueError("basket/position overlap")
        previous = closed
        balance += row["net"]


def summarize(result):
    ledger = result["ledger"]
    monthly = {}
    for trade in ledger:
        month = trade["exit_time_utc"][:7]
        monthly[month] = monthly.get(month, 0.0) + trade["net"]
    return dict(
        **{
            k: result[k]
            for k in (
                "net_usd",
                "final_balance",
                "return_pct",
                "max_dd_pct",
                "trades",
                "win_rate",
                "profit_factor",
                "realized_rr",
                "swap_usd",
                "commission_usd",
            )
        },
        legs=result.get("legs", result["trades"]),
        bankrupt=result.get("bankrupt", False) or any(t["reason"] == "BANKRUPT" for t in ledger),
        buy_baskets=sum(t["direction"] == 1 for t in ledger),
        sell_baskets=sum(t["direction"] == -1 for t in ledger),
        forced_exits=sum(t["reason"] == "END_OF_SAMPLE" for t in ledger),
        maximum_loss_usd=min((t["net"] for t in ledger), default=0),
        longest_hours=max(
            (
                (
                    pd.Timestamp(t["exit_time_utc"]) - pd.Timestamp(t["entry_time_utc"])
                ).total_seconds()
                / 3600
                for t in ledger
            ),
            default=0,
        ),
        monthly_net_usd=monthly,
        max_margin_utilization=result.get("max_margin_utilization"),
        max_basket_target_risk_pct=result.get("max_basket_target_risk_pct"),
        max_admitted_risk_pct=result.get("max_admitted_risk_pct"),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runs/dobby-vs-c22-2026-10-18")
    args = parser.parse_args(argv)
    out = args.output.resolve()
    if ROOT / "runs" not in out.parents:
        raise ValueError("machine evidence must be under runs")
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = INPUT / "continuous-manifest.json"
    manifest = read(manifest_path)
    broker = manifest["broker"]
    policy = SwapPolicy.from_broker(broker)  # Missing/unsupported metadata blocks.
    config = read(ROOT / "config/c22h4-demo.json")
    for path, expected in config["source_hashes"].items():
        if sha256(ROOT / path) != expected:
            raise ValueError("C22 source drift: " + path)
    costs = dict(
        base=Costs(),
        stress=Costs(extra_spread=0.2, slippage=0.1),
        fee_sensitivity=Costs(extra_spread=0.2, slippage=0.1, commission_per_lot=7),
    )
    windows = dict(
        full=("2024-09-01T00:00:00Z", "2026-10-03T00:00:00Z"),
        earlier=("2024-09-01T00:00:00Z", "2025-10-01T00:00:00Z"),
        later=("2025-10-01T00:00:00Z", "2026-10-03T00:00:00Z"),
    )
    protocol = dict(
        schema=1,
        purpose="Owner-authorized reconstructed Dobby martingale research comparison; no live adoption",
        initial_equity=200,
        initial_equity_per_window=True,
        monthly_resets=False,
        input_manifest_sha256=sha256(manifest_path),
        input_artifact_hashes=manifest["artifacts"],
        input_first_quote=manifest["first_quote_utc"],
        input_last_quote=manifest["last_quote_utc"],
        ticks=manifest["ticks"],
        bars=manifest["bars"],
        broker=broker,
        swap_policy=asdict(policy),
        views={name: asdict(c) for name, c in costs.items()},
        windows=windows,
        c22_contract=config["contract"],
        dobby_rules=asdict(DobbyRules()),
        reconstructed_assumptions=[
            "User paste incomplete; not compiled original EA or MT5-iRSI parity claim.",
            "One same-direction basket; no first-entry admission while any owned basket exists.",
            "TP/SL management then grid runs every observed tick before Monday/spread/daily-entry gates; one grid leg per tick.",
            "RSI14 uses mean-seeded Wilder smoothing on shared completed UTC Bid M15; strict <30 BUY, >70 SELL.",
            "Only completed 15-M1 bars feed both detectors; missing closed bar blocks Dobby initial entry in that slot.",
            "Initial entries retry within forming M15 slot until spread/margin pass; last_bar consumed only on fill.",
            "Grid extrema use actual modeled fills; lot uses original floor/min/max normalization. No C22 cap imposed on Dobby.",
            "Round-trip commission reserved per leg at entry; mark includes observed Bid/Ask spread and accrued swap; adverse slippage on each market fill.",
            "One losing basket SL per server day; persistent continuous simulation, no restart-counter resets.",
            "Primary calendar assumes server UTC; sensitivity offsets +2/+3 hours on full base/stress, stored times always UTC.",
            "Swap is snapshot points mode long -567.4/short 0, UTC-midnight preceding-business-day calendar, Wednesday triple. Not historical broker attestation.",
            "Used margin is entry notional/leverage; additional leg rejected if free equity insufficient. No unverified broker stop-out threshold invented.",
            "Record margin utilization above 100%; such witnesses are broker-model inconclusive. Equity<=0 liquidates and stops.",
            "Basket close fills all legs at observed quote with slippage; no latency, rejection, partial-fill, disconnection or real broker guarantee.",
            "Force remaining position/basket closed at last observed quote, disclosed END_OF_SAMPLE.",
        ],
        selection=dict(
            rule="Retain C22 unless Dobby is solvent, net-positive and strictly more profitable with no greater tick-equity DD in ALL nine matched window/cost cells. Calendar sensitivities must not reverse full-window comparison. Otherwise no demonstrated robust replacement.",
            minimum_baskets_each_cell=30,
            live_eligibility="Independent: original Dobby violates fixed-lot/single-position/10% contract; research ranking never authorizes runtime replacement.",
        ),
        evidence_status="RETROSPECTIVE / RECONSTRUCTED / COST_INCONCLUSIVE; all history previously research-exposed, no untouched holdout or live profitability claim",
        runtime=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__),
        source_hashes={p: sha256(ROOT / p) for p in SOURCES},
    )
    frozen = out / "protocol.json"
    if frozen.exists() and read(frozen) != json.loads(json.dumps(protocol)):
        raise ValueError("resume source/protocol drift")
    atomic_json(frozen, protocol)
    digest = sha256(frozen)
    for path in SOURCES:
        snapshot = out / "source_snapshot" / path
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            shutil.copyfile(ROOT / path, snapshot)
    # Validate actual tape and original source archive hashes before evaluating.
    checked = {}
    for group, base in ((manifest["artifacts"], INPUT), (manifest["source_hashes"], ROOT)):
        for path, expected in group.items():
            actual = sha256(base / path)
            if actual != expected:
                raise ValueError("input drift: " + path)
            checked[str(base / path)] = actual
    atomic_json(out / "input-verification.json", checked)
    print("Verified", len(checked), "input artifacts", flush=True)
    bars = pd.read_csv(INPUT / "continuous-bars.csv")
    bars.index = pd.DatetimeIndex(pd.to_datetime(bars.pop("bar_open_utc"), utc=True))
    ticks = [
        np.load(INPUT / "continuous-tape" / (key + ".npy"), mmap_mode="r")
        for key in ("time", "bid", "ask")
    ]
    c22_frame, c22_rules = prepare_candidate(bars, config["contract"])
    cache, rows = Checkpoints(out, digest), []
    cases = [
        (strategy, window, view, 0)
        for strategy in ("c22", "dobby")
        for window in windows
        for view in costs
    ]
    cases += [("dobby", "full", view, offset) for offset in (2, 3) for view in ("base", "stress")]
    for strategy, window, view, offset in cases:
        key = f"{strategy}-{window}-{view}-utc{offset:+d}-swap"
        start, end = [pd.Timestamp(value) for value in windows[window]]

        def execute():
            if strategy == "c22":
                return c22_replay(
                    c22_frame,
                    ticks,
                    broker,
                    c22_rules,
                    costs[view],
                    start=start,
                    end=end,
                    swap_policy=policy,
                )
            return dobby_replay(
                bars,
                ticks,
                broker,
                replace(DobbyRules(), server_offset_hours=offset),
                costs[view],
                start=start,
                end=end,
                swap_policy=policy,
            )

        result = cache.execute(key, execute, repeat=True)
        verify_cash(result)
        metric = summarize(result)
        row = dict(
            case=key,
            strategy=strategy,
            window=window,
            view=view,
            server_offset_hours=offset,
            metrics=metric,
        )
        rows.append(row)
        atomic_json(out / "results.json", dict(protocol_sha256=digest, rows=rows))
        print(
            key,
            "net",
            round(metric["net_usd"], 2),
            "DD",
            round(metric["max_dd_pct"], 2),
            "baskets/positions",
            metric["trades"],
            "fresh repeat matched",
            flush=True,
        )
    primary = [r for r in rows if r["server_offset_hours"] == 0]
    failures = []
    for challenger in [r for r in rows if r["strategy"] == "dobby"]:
        control = next(
            r
            for r in primary
            if r["strategy"] == "c22"
            and r["window"] == challenger["window"]
            and r["view"] == challenger["view"]
        )
        c, d = control["metrics"], challenger["metrics"]
        reasons = []
        if d["bankrupt"]:
            reasons.append("insolvent")
        if d["net_usd"] <= max(0, c["net_usd"]):
            reasons.append("net_not_superior_positive")
        if d["max_dd_pct"] > c["max_dd_pct"]:
            reasons.append("drawdown_worse")
        if d["trades"] < protocol["selection"]["minimum_baskets_each_cell"]:
            reasons.append("insufficient_baskets")
        if d["max_margin_utilization"] > 1:
            reasons.append("broker_margin_model_inconclusive")
        if reasons:
            failures.append(dict(case=challenger["case"], reasons=reasons))
    decision = dict(
        research_selection="retain_c22" if failures else "dobby_research_challenger",
        failures=failures,
        live_replacement_authorized=False,
        evidence_status=protocol["evidence_status"],
    )
    atomic_json(out / "decision.json", decision)
    pd.DataFrame(
        [
            dict(
                case=r["case"],
                strategy=r["strategy"],
                window=r["window"],
                view=r["view"],
                server_offset_hours=r["server_offset_hours"],
                **{k: v for k, v in r["metrics"].items() if k != "monthly_net_usd"},
            )
            for r in rows
        ]
    ).to_csv(out / "summary.csv", index=False)
    proofs = [read(p) for p in (out / "integrity").glob("*.json")]
    if len(proofs) != len(cases) or not all(p["fresh_full_result_match"] for p in proofs):
        raise ValueError("incomplete fresh repeat evidence")
    for path, expected in protocol["source_hashes"].items():
        if sha256(ROOT / path) != expected:
            raise ValueError("source changed during run")
    atomic_json(
        out / "COMPLETE.json",
        dict(
            cells=len(cases),
            fresh_full_result_matches=len(proofs),
            protocol_sha256=digest,
            result_sha256=sha256(out / "results.json"),
            decision=decision,
            real_broker_calls=0,
            no_swap_economic_cells=0,
        ),
    )
    print(json.dumps(decision), flush=True)


if __name__ == "__main__":
    main()
