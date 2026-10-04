"""Recompute campaign acceptance from hash-bound replay artifacts and catalogs."""

import hashlib
import json
import math
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((ROOT / name).read_text())


def key(row):
    return (
        "-".join(row[k] for k in ("dataset", "window", "cost", "cost_view", "contract")) + ".json"
    )


def main():
    if not __debug__:
        raise RuntimeError("Artifact verification requires assertions enabled; do not use -O")
    from dataclasses import asdict, replace
    from scripts.research.breakout_logic import Costs
    from scripts.research.reward156_campaign import CONTROLS
    from scripts.research.reward156_search import (
        cell_gates,
        config_id,
        variants,
        variant_catalog,
        combinations,
        rank,
        GROUPS,
        prepare_candidate,
    )
    from scripts.research.reward156_tuning import summary
    from scripts.research.rollover import SwapPolicy

    complete, contract, results, decision = [
        read(n) for n in ("COMPLETE.json", "contract.json", "results.json", "verdict.json")
    ]
    config = contract["config"]
    config_path = REPO / "config/reward156-profit-survival.json"
    assert digest(config_path) == contract["config_sha256"]
    assert json.loads(config_path.read_text()) == config
    frozen = {k: v for k, v in contract.items() if k != "behavior_sha256"}
    assert (
        hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
        == contract["behavior_sha256"]
    )
    assert complete["behavior_sha256"] == contract["behavior_sha256"]
    assert complete["results_sha256"] == digest(ROOT / "results.json")
    assert decision == results["verdict"]
    assert decision["selected"] == complete["selected"]
    assert decision["holdout"] == complete["holdout"]
    for source, expected in contract["sources"].items():
        assert digest(REPO / source) == expected, source
        assert digest(ROOT / "source_snapshot" / source) == expected, source
    plan = REPO / ".cursor/plans/long-term_macro_gate_99f085f3.plan.md"
    assert (
        hashlib.sha256(plan.read_text().split("---", 2)[2].encode()).hexdigest()
        == contract["plan_spec_sha256"]
    )
    raw = {}
    brokers = {}
    manifests = {}
    for name, expected in contract["datasets"].items():
        root = REPO / config["datasets"][name]["path"]
        assert digest(root / "dataset.json") == expected, name
        manifest = json.loads((root / "dataset.json").read_text())
        audit = read("input-" + name + ".json")
        assert audit["dataset_sha256"] == expected
        assert audit["artifacts"] == manifest["artifacts"]
        assert (audit["start_utc"], audit["end_utc"]) == (
            manifest["discovery_start"],
            manifest["discovery_end"],
        )
        assert audit["holdout_prices_accessed"] is False
        for artifact, expected in manifest["artifacts"].items():
            assert digest(root / artifact) == expected, artifact
        for archive in manifest["imported_months"]:
            assert digest(root / archive["file"]) == archive["sha256"]
        frame = pd.read_csv(root / "discovery/bars.csv")
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.pop("bar_open_utc"), utc=True))
        raw[name], brokers[name], manifests[name] = frame, manifest["broker"], manifest

    seed_catalog = read("seed-catalog.json")
    assert seed_catalog == config["seeds"]
    catalog = list(seed_catalog)
    for filename in ("one-factor-catalog.json", "combination-catalog.json"):
        if (ROOT / filename).exists():
            catalog += read(filename)
    assert len(catalog) == complete["evaluated_candidates"] and len(catalog) <= 67
    assert len({config_id(c) for c in catalog}) == len(catalog)
    candidates = {c["name"]: c for c in [*CONTROLS, *catalog]}
    paths = list((ROOT / "cells").glob("*.json"))
    assert len(paths) == complete["cells"]
    replay_results = {}
    repeated = set()
    trade_count = 0
    for path in paths:
        proof = read("integrity/" + path.name)
        assert proof["behavior_sha256"] == contract["behavior_sha256"]
        assert proof["result_sha256"] == digest(path), path.name
        if proof["fresh_full_result_match"]:
            repeated.add(path.name)
        result = json.loads(path.read_text())
        ledger = result["ledger"]
        assert math.isclose(sum(t["net"] for t in ledger), result["net_usd"], abs_tol=1e-8)
        assert math.isclose(200 + result["net_usd"], result["final_balance"], abs_tol=1e-8)
        assert result["initial_balance"] == 200
        assert all(t["volume"] == 0.01 and t["risk_pct"] <= 10 + 1e-8 for t in ledger)
        initial_equity = 200.0
        previous_exit = None
        broker = brokers["A" if path.name.startswith("holdout-") else path.name.split("-")[0]]
        for trade in ledger:
            factor = broker["trade_contract_size"] * trade["volume"]
            fee = result["costs"]["commission_per_lot"] * trade["volume"]
            expected_risk = (
                abs(trade["entry"] - trade["initial_stop"]) + result["costs"]["slippage"]
            ) * factor + fee
            assert math.isclose(trade["risk_usd"], expected_risk, abs_tol=1e-8)
            assert math.isclose(trade["entry_equity"], initial_equity, abs_tol=1e-8)
            assert math.isclose(
                trade["risk_pct"], expected_risk / initial_equity * 100, abs_tol=1e-8
            )
            assert (
                trade["risk_pct"] <= trade["admission_cap_pct"] + 1e-8
                and trade["admission_cap_pct"] <= 10
            )
            born, exit_time = (
                pd.Timestamp(trade["entry_time_utc"]),
                pd.Timestamp(trade["exit_time_utc"]),
            )
            assert born <= exit_time and (previous_exit is None or born >= previous_exit)
            previous_exit = exit_time
            initial_equity += trade["net"]
        if "swap_usd" in result:
            assert math.isclose(
                sum(t["swap_usd"] for t in ledger), result["swap_usd"], abs_tol=1e-8
            )
            assert math.isclose(
                result["net_before_swap_usd"] + result["swap_usd"], result["net_usd"], abs_tol=1e-8
            )
        assert result["rules"]["risk_cap"] == 0.1 and result["rules"]["sizing_mode"] == "fixed"
        assert all(p["time_utc"].endswith("+00:00") for p in result["equity"])
        replay_results[path.name] = result
        trade_count += len(ledger)
    assert len(repeated) == complete["fresh_full_result_matches"]

    frames = {}
    rows = results["rows"]
    seen = set()

    def metrics_for(result, frame, start, end):
        metrics = summary(result, frame, start, end)
        metrics["bankrupt"] = any(t["reason"] == "BANKRUPT" for t in result["ledger"]) or any(
            p["equity_usd"] <= 0 for p in result["equity"]
        )
        return metrics

    for row in rows:
        filename = key(row)
        assert filename not in seen, filename
        seen.add(filename)
        result = replay_results[filename]
        name, ds = row["dataset"], config["datasets"][row["dataset"]]
        start, split, end = [pd.Timestamp(ds[k], tz="UTC") for k in ("start", "split", "end")]
        bounds = {"full": (start, end), "first_half": (start, split), "second_half": (split, end)}
        start, end = bounds[row["window"]]
        assert row["start_utc"] == result["start_utc"] == start.isoformat()
        assert row["end_exclusive_utc"] == result["end_exclusive_utc"] == end.isoformat()
        candidate = candidates[row["contract"]]
        assert row["config_id"] == config_id(candidate)
        cache = (name, row["contract"])
        if cache not in frames:
            frames[cache] = prepare_candidate(raw[name], candidate)
        frame, rules = frames[cache]
        assert result["rules"] == asdict(rules)
        assert result["costs"] == asdict(Costs(**config["costs"][row["cost"]]))
        if row["cost_view"] == "no_swap":
            assert "swap_policy" not in result
        else:
            policy = SwapPolicy.from_broker(brokers[name])
            factor = {"swap": 1.0, "swap_0.5": 0.5, "swap_1.5": 1.5}[row["cost_view"]]
            assert result["swap_policy"] == asdict(
                replace(
                    policy,
                    long_points=policy.long_points * factor,
                    short_points=policy.short_points * factor,
                )
            )
        assert row["metrics"] == metrics_for(result, frame, start, end), filename
        if row["contract"] not in ("trial30", "reward156_original"):
            peers = [
                p["metrics"]
                for p in rows
                if p["contract"] in ("trial30", "reward156_original")
                and all(p[k] == row[k] for k in ("dataset", "window", "cost", "cost_view"))
            ]
            assert len(peers) == 2
            assert row["gates"] == cell_gates(row["metrics"], peers, row["window"])
            assert all(type(v) is bool for v in row["gates"].values())

    aggregates = []
    for candidate in catalog:
        cells = [
            r
            for r in rows
            if r["contract"] == candidate["name"]
            and r["window"] == "full"
            and r["cost_view"] in ("no_swap", "swap")
        ]
        aggregates.append(
            dict(
                name=candidate["name"],
                config_id=config_id(candidate),
                passing_continuous=sum(all(r["gates"].values()) for r in cells),
                worst_net=min(r["metrics"]["net_usd"] for r in cells),
                worst_dd=max(r["metrics"]["max_dd_pct"] for r in cells),
                failed_gates={g: sum(not r["gates"][g] for r in cells) for g in cells[0]["gates"]},
            )
        )
    assert aggregates == results["candidates"]
    baseline = read("baseline-matrix.json")
    assert len(baseline) == 64 and {r["contract"] for r in baseline} == {
        "trial30",
        "reward156_original",
    }
    assert baseline == [r for r in rows if r["contract"] in ("trial30", "reward156_original")]
    old_cells = REPO / "docs/reviews/reward156-tuning-2026-10-04/cells"
    baseline_parity = 0
    for row in baseline:
        assert key(row) in repeated
        if row["cost_view"] in ("no_swap", "swap"):
            assert replay_results[key(row)] == json.loads((old_cells / key(row)).read_text())
            baseline_parity += 1
    assert baseline_parity == 48

    def qualifies(c, windows=("full",), views=("no_swap", "swap")):
        cells = [
            r
            for r in rows
            if r["contract"] == c["name"] and r["window"] in windows and r["cost_view"] in views
        ]
        return len(cells) == 2 * len(windows) * 2 * len(views) and all(
            all(r["gates"].values()) for r in cells
        )

    def passing_final(c):
        return qualifies(c, ("full", "first_half", "second_half")) and qualifies(
            c, views=("swap_0.5", "swap_1.5")
        )

    seed_finalists = sorted(
        [c for c in seed_catalog if qualifies(c)], key=lambda c: rank(c, rows)[1:]
    )[:6]
    seed_winners = [c for c in seed_finalists if passing_final(c)]
    chosen_path = ROOT / "chosen-seeds.json"
    if seed_winners:
        assert not chosen_path.exists()
        finalists = seed_finalists
    else:
        assert chosen_path.exists()
        chosen = read("chosen-seeds.json")
        assert chosen == sorted(seed_catalog, key=lambda c: rank(c, rows))[:2]
        refs = read("one-factor-references.json")
        generated, expected_refs = variant_catalog(chosen, seed_catalog)
        assert generated == read("one-factor-catalog.json")
        assert refs == expected_refs
        existing = {config_id(c): c for c in catalog}
        initial_ids = {config_id(c) for c in seed_catalog + read("one-factor-catalog.json")}
        expected_combinations = []
        for seed in chosen:
            experiments = refs[config_id(seed)]
            assert {config_id(c) for c in experiments} == {config_id(c) for c in variants(seed)}
            assert len(experiments) <= 27
            for c in experiments:
                assert c["name"] == existing[config_id(c)]["name"]
            winners = [
                min([c for c in experiments if c["group"] == group], key=lambda c: rank(c, rows))
                for group in GROUPS
            ]
            for c in combinations(seed, winners):
                if config_id(c) not in initial_ids:
                    expected_combinations.append(c)
                    initial_ids.add(config_id(c))
        assert read("combination-catalog.json") == expected_combinations
        extra = sorted(
            [c for c in catalog if qualifies(c) and c not in seed_finalists],
            key=lambda c: rank(c, rows)[1:],
        )[: 6 - len(seed_finalists)]
        finalists = seed_finalists + extra
    assert decision["finalists"] == [c["name"] for c in finalists] and len(finalists) <= 6
    winners = sorted([c for c in finalists if passing_final(c)], key=lambda c: rank(c, rows)[1:])
    selected = winners[0]["name"] if winners else None
    assert selected == decision["selected"]
    expected = set()
    for c in [*CONTROLS, *catalog]:
        is_final = c in CONTROLS or c in finalists
        windows = ("full", "first_half", "second_half") if is_final else ("full",)
        for ds in config["datasets"]:
            for window in windows:
                for cost in config["costs"]:
                    for view in ("no_swap", "swap"):
                        expected.add("-".join((ds, window, cost, view, c["name"])) + ".json")
            if is_final:
                for cost in config["costs"]:
                    for view in ("swap_0.5", "swap_1.5"):
                        expected.add("-".join((ds, "full", cost, view, c["name"])) + ".json")
        if is_final:
            assert {p for p in expected if p.endswith("-" + c["name"] + ".json")} <= repeated
    assert seen == expected

    holdout_expected = set()
    if selected:
        from scripts.research.reward156_holdout import verify_lock

        winner = candidates[selected]
        verify_lock(ROOT, winner)
        discovery = read("discovery-results.json")
        assert discovery["rows"] == rows and discovery["verdict"]["selected"] == selected
        holdout = read("holdout-results.json")
        audit = read("holdout-input.json")
        manifest = manifests["A"]
        source = REPO / config["datasets"]["A"]["path"]
        items = [i for i in manifest["archives"] if "2025-07" <= i["month"] < "2025-10"]
        assert len(items) == len(audit["archives"]) == 3
        for item, imported in zip(items, audit["archives"]):
            assert all(item[k] == imported[k] for k in item)
            assert digest(source / item["file"]) == item["sha256"]
            assert (
                digest(ROOT / "holdout-input/discovery" / (item["month"] + ".npz"))
                == imported["cache_sha256"]
            )
        for k, expected_digest in audit["artifacts"].items():
            assert digest(ROOT / "holdout-input/tape" / (k + ".npy")) == expected_digest
        # Rebuild canonical prefix from preserved quoted heldout tape, no re-selection.
        import numpy as np
        from scripts.research.data import bars as aggregate_bars

        arrays = [
            np.load(ROOT / "holdout-input/tape" / (k + ".npy"), mmap_mode="r")
            for k in ("time", "bid", "ask")
        ]
        t, b, _ = arrays
        minute = t // 60000
        first = np.r_[0, np.flatnonzero(np.diff(minute)) + 1]
        last = np.r_[first[1:] - 1, len(t) - 1]
        held = aggregate_bars(
            pd.DataFrame(
                dict(
                    bid_open=b[first],
                    bid_high=np.maximum.reduceat(b, first),
                    bid_low=np.minimum.reduceat(b, first),
                    bid_close=b[last],
                ),
                index=pd.to_datetime(minute[first] * 60000, unit="ms", utc=True),
            )
        )
        full = pd.concat(
            [raw["A"][["open", "high", "low", "close"]], held[["open", "high", "low", "close"]]]
        )
        start, end = pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2025-10-01", tz="UTC")
        assert (
            audit["start_utc"] == start.isoformat()
            and audit["end_exclusive_utc"] == end.isoformat()
        )
        assert len(holdout["rows"]) == 12
        wanted_holdout = {
            "-".join(("holdout", cost, view, name)) + ".json"
            for name in ("trial30", "reward156_original", selected)
            for cost in config["costs"]
            for view in ("no_swap", "swap")
        }
        for row in holdout["rows"]:
            filename = (
                "-".join(("holdout", row["cost"], row["cost_view"], row["contract"])) + ".json"
            )
            assert filename not in holdout_expected and filename in repeated
            holdout_expected.add(filename)
            result = replay_results[filename]
            frame, rules = prepare_candidate(full, candidates[row["contract"]])
            assert result["rules"] == asdict(rules)
            assert result["costs"] == asdict(Costs(**config["costs"][row["cost"]]))
            assert (
                result["start_utc"] == start.isoformat()
                and result["end_exclusive_utc"] == end.isoformat()
            )
            assert row["metrics"] == metrics_for(result, frame, start, end)
            if row["cost_view"] == "no_swap":
                assert "swap_policy" not in result
            else:
                assert result["swap_policy"] == asdict(SwapPolicy.from_broker(brokers["A"]))
            if row["contract"] == selected:
                peers = [
                    p["metrics"]
                    for p in holdout["rows"]
                    if p["contract"] in ("trial30", "reward156_original")
                    and all(p[k] == row[k] for k in ("cost", "cost_view"))
                ]
                assert len(peers) == 2
                assert row["gates"] == cell_gates(row["metrics"], peers, "holdout", holdout=True)
        assert holdout_expected == wanted_holdout
        passed = all(all(r["gates"].values()) for r in holdout["rows"] if r["contract"] == selected)
        expected_status = (
            "PASSED_HISTORICAL_HOLDOUT_RESEARCH_ONLY" if passed else "FAILED_HOLDOUT_NO_RETUNING"
        )
        assert decision["holdout"] == holdout["status"] == expected_status
    else:
        assert decision["holdout"] == "NOT_OPENED_NO_QUALIFIER"
        assert not (ROOT / "selection-lock.json").exists() and not (ROOT / "holdout-input").exists()
    assert set(replay_results) == seen | holdout_expected
    checks = read("checks.json")
    assert checks["unittest"]["exit_code"] == 0
    assert checks["unittest"]["log_sha256"] == digest(ROOT / "unittest.log")
    assert all(checks[k]["exit_code"] == 0 for k in ("lint", "compile"))
    assert checks["review"]["standards_remaining"] == checks["review"]["spec_remaining"] == 0
    consumed = {p.name: digest(p) for p in ROOT.glob("*.json") if p.name != "validation.json"}
    audit = dict(
        behavior_sha256=contract["behavior_sha256"],
        consumed_artifact_sha256=consumed,
        verifier_sha256=digest(Path(__file__)),
        summarizer_sha256=digest(ROOT / "summarize_campaign.py"),
        cells=len(paths),
        fresh_full_result_matches=len(repeated),
        reconciled_trades=trade_count,
        source_and_dataset_hashes_match=True,
        row_metrics_recomputed=True,
        gates_recomputed=True,
        adaptive_catalog_recomputed=True,
        finalist_selection_recomputed=True,
        v1_control_full_result_matches=baseline_parity,
        candidate_budget=len(catalog),
        selected=selected,
        status="VERIFIED",
    )
    (ROOT / "validation.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({k: v for k, v in audit.items() if k != "consumed_artifact_sha256"}, indent=2))


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    main()
