"""Hash-bound standalone SMC vs frozen C22; swap in every economic cell."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

from scripts.c22h4.strategy import CONTRACT as C22_CONTRACT, verify_sources
from scripts.research.breakout_models import Costs
from scripts.research.breakout_replay import replay
from scripts.research.c22_context_campaign import (
    BASELINE,
    campaign_lock,
    digest,
    read,
    require,
    verify_baseline,
    write_checkpoint,
)
from scripts.research.c22_frequency_campaign import frozen_parity
from scripts.research.c22_frequency_data import load_bars
from scripts.research.c22_frequency_store import Store
from scripts.research.reward156_search import prepare_candidate
from scripts.research.reward156_tuning import blocking
from scripts.research.smc_challenger_adapter import (
    audit_result,
    replay_signals,
    validate_broker,
    validate_tape,
    swap_debits,
)
from scripts.research.smc_challenger_signals import (
    ROOT,
    DEFAULT_CONFIG,
    CONTRACT,
    contract_id,
    prepare_signals,
    validate_config,
)


def sources():
    paths = {
        ROOT / "scripts/strategy.py",
        ROOT / "scripts/pure_b1/broker_data.py",
        ROOT / "scripts/c22h4/strategy.py",
        ROOT / "scripts/smc/structure.py",
        ROOT / "scripts/smc/types.py",
        ROOT / "config/c22h4-demo.json",
    }
    paths.update((ROOT / "scripts/research").glob("*.py"))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


def native(value):
    """Normalize NumPy scalar results, reject NaN instead of invalid JSON."""
    return json.loads(
        json.dumps(
            value, allow_nan=False, default=lambda v: v.item() if isinstance(v, np.generic) else v
        )
    )


def input_coverage(bars, ticks, start, end):
    times = ticks[0]
    left, right = np.searchsorted(times, [start.value // 10**6, end.value // 10**6])
    require(right > left, "no evaluation quotes")

    def stamp(value):
        return pd.Timestamp(int(value), unit="ms", tz="UTC").isoformat()

    return dict(
        input_first_quote=stamp(times[0]),
        input_last_quote=stamp(times[-1]),
        input_ticks=len(times),
        input_bars=len(bars),
        actual_first_quote=stamp(times[left]),
        actual_last_quote=stamp(times[right - 1]),
        evaluation_ticks=int(right - left),
        prefix_ticks=int(left),
        evaluation_bars=int(
            (
                (bars.index + pd.Timedelta(minutes=15) >= start)
                & (bars.index + pd.Timedelta(minutes=15) < end)
            ).sum()
        ),
        prefix_bars=int((bars.index + pd.Timedelta(minutes=15) < start).sum()),
        bar_gap_count=int((np.diff(bars.index.as_unit("ms").asi8) != 900000).sum()),
        no_gap_filling=True,
    )


def load_input(root, *, fixture=False):
    manifest = read(root / "manifest.json")
    require(manifest.get("schema") == "smc_input_v1", "SMC input manifest version required")
    require(
        manifest.get("kind") == ("synthetic_fixture" if fixture else "historical_discovery"),
        "input kind does not match explicit fixture/research mode",
    )
    require(
        manifest.get("bar_basis") == "UTC_Bid_M1_15_of_15", "completed canonical bar basis required"
    )
    require(manifest.get("calendar") == CONTRACT["calendar"], "pool calendar mismatch")
    required = {"bars.csv", "tape/time.npy", "tape/bid.npy", "tape/ask.npy"}
    require(required.issubset(manifest.get("artifacts", {})), "missing input artifacts")
    for name, expected in manifest["artifacts"].items():
        path = root / name
        require(
            not Path(name).is_absolute()
            and ".." not in Path(name).parts
            and path.resolve().is_relative_to(root.resolve()),
            "unsafe input artifact path",
        )
        require(digest(path) == expected, "input artifact drift: " + name)
    validate_broker(manifest["broker"])
    basis = manifest.get("cost_basis", {})
    require(
        all(
            isinstance(basis.get(k), str) and basis[k].strip()
            for k in ("quote_source", "swap_source", "commission_source")
        ),
        "named cost sources required",
    )
    require(basis.get("slippage_basis") == "declared_assumption", "slippage basis required")
    require(basis.get("commission_unit") == "USD_per_lot_round_trip", "commission unit required")
    require(set(manifest["costs"]) == {"base", "stress"}, "two cost views required")
    for name, spread in (("base", 0.0), ("stress", 0.2)):
        cell = manifest["costs"][name]
        require(
            isinstance(cell, dict)
            and set(cell) == {"extra_spread", "slippage", "commission_per_lot"},
            "explicit cost schema required",
        )
        require(all(type(v) in (int, float) for v in cell.values()), "numeric cost schema required")
        cost = Costs(**manifest["costs"][name])
        require(cost.extra_spread == spread and cost.slippage == 0.1, "SMC cost scenario mismatch")
    start, end = (pd.Timestamp(manifest[k]) for k in ("requested_start_utc", "requested_end_utc"))
    require(
        start.tzinfo is not None
        and end.tzinfo is not None
        and start.utcoffset() == end.utcoffset() == pd.Timedelta(0)
        and start < end,
        "ordered aware UTC evaluation window required",
    )
    require(start == start.normalize(), "start must be UTC midnight for initial offline baseline")
    bars = load_bars(root / "bars.csv")
    ticks = tuple(
        np.load(root / "tape" / (k + ".npy"), mmap_mode="r") for k in ("time", "bid", "ask")
    )
    validate_tape(ticks)
    require((bars.index + pd.Timedelta(minutes=15) <= end).all(), "unsealed/post-cutoff bars")
    require(ticks[0][-1] < end.value // 10**6, "post-cutoff ticks")
    manifest["coverage"] = input_coverage(bars, ticks, start, end)
    manifest["coverage"]["history_role"] = (
        "synthetic_fixture" if fixture else "reused_discovery_not_holdout"
    )
    return manifest, bars, ticks


def archived_input(baseline):
    original, old, hashes = verify_baseline(baseline)
    manifest = dict(
        requested_start_utc=original["start"],
        requested_end_utc=original["end"],
        broker=old["broker"],
        costs={
            "base": dict(
                extra_spread=0.0,
                slippage=0.1,
                commission_per_lot=original["costs"]["base"]["commission_per_lot"],
            ),
            "stress": dict(
                extra_spread=0.2,
                slippage=0.1,
                commission_per_lot=original["costs"]["stress"]["commission_per_lot"],
            ),
        },
        cost_basis=dict(
            quote_source="public Exness archive bound by baseline manifest",
            swap_source="current broker specification, historical entitlement unverified",
            commission_source="archived declared tariff; historical commission unverified",
            slippage_basis="declared_assumption",
            commission_unit="USD_per_lot_round_trip",
        ),
        calendar=CONTRACT["calendar"],
        bar_basis="UTC_Bid_M1_15_of_15",
        coverage={k: old[k] for k in ("first_quote_utc", "last_quote_utc", "ticks", "bars")},
    )
    manifest["coverage"]["history_role"] = "reused_discovery_not_holdout"
    validate_broker(manifest["broker"])
    bars = load_bars(baseline / "input/continuous-bars.csv")
    ticks = tuple(
        np.load(baseline / "input/continuous-tape" / (k + ".npy"), mmap_mode="r")
        for k in ("time", "bid", "ask")
    )
    manifest["coverage"] = input_coverage(
        bars, ticks, pd.Timestamp(original["start"]), pd.Timestamp(original["end"])
    )
    manifest["coverage"]["history_role"] = "reused_discovery_not_holdout"
    return original, manifest, bars, ticks, hashes


def execute(task):
    strategy, view, frame, ticks, manifest, config = task
    start, end = (pd.Timestamp(manifest[k]) for k in ("requested_start_utc", "requested_end_utc"))
    cost = Costs(**manifest["costs"][view.split("-")[0]])
    if strategy == "smc":
        result = replay_signals(
            frame, ticks, manifest["broker"], cost, start=start, end=end, config=config
        )
    else:
        from scripts.research.rollover import SwapPolicy

        _, rules = prepare_candidate(frame[["open", "high", "low", "close"]], C22_CONTRACT)
        result = replay(
            frame,
            ticks,
            manifest["broker"],
            rules,
            cost,
            start=start,
            end=end,
            swap_policy=SwapPolicy.from_broker(manifest["broker"]),
            capture_events=True,
            capture_context=True,
        )
        audit_result(result)
        result["swap_debits"] = swap_debits(result, manifest["broker"])
    return native(result)


def scorecard(result, strategy, view):
    start, end = pd.Timestamp(result["start_utc"]), pd.Timestamp(result["end_exclusive_utc"])
    keys = (
        "net_usd",
        "final_balance",
        "max_dd_pct",
        "trades",
        "profit_factor",
        "win_rate",
        "realized_rr",
        "mean_net_r",
        "max_admitted_risk_pct",
        "signal_count",
        "rejections",
        "commission_usd",
        "modeled_slippage_usd",
        "quoted_spread_proxy_usd",
        "swap_usd",
    )
    row = {k: result[k] for k in keys}
    months = pd.date_range(
        start.normalize().replace(day=1), end.normalize().replace(day=1), freq="MS"
    )
    full = [m for m in months if m >= start and m + pd.DateOffset(months=1) <= end]
    counts = {m.strftime("%Y-%m"): 0 for m in full}
    for p in result["ledger"]:
        key = pd.Timestamp(p["entry_time_utc"]).strftime("%Y-%m")
        if key in counts:
            counts[key] += 1
    row.update(
        strategy=strategy,
        view=view,
        full_month_trade_counts=counts,
        mean_entries_per_full_month=float(np.mean(list(counts.values()))) if counts else None,
        expectancy_usd=result["net_usd"] / result["trades"] if result["trades"] else None,
        realized_losses_above_initial_10pct=sum(
            -p["net"] > p["entry_equity"] * 0.1 for p in result["ledger"]
        ),
        no_quote_events=len(result.get("no_quote_events", [])),
    )
    row.update(blocking(result["admission_events"], result["ledger"], start, end))
    return native(row)


def campaign(
    output,
    *,
    input_root=None,
    baseline=BASELINE,
    config_path=DEFAULT_CONFIG,
    fixture=False,
    workers=2,
    max_cells=4,
):
    output, baseline = Path(output).resolve(), Path(baseline).resolve()
    require(
        output.is_relative_to(ROOT / "runs") and output != ROOT / "runs",
        "output must be under ignored runs/",
    )
    require(type(workers) is int and 1 <= workers <= 2, "workers must be1 or2")
    require(type(max_cells) is int and 0 <= max_cells <= 4, "max_cells must be0..4")
    require(not fixture or input_root is not None, "fixture mode requires explicit synthetic input")
    for root in (baseline, Path(input_root).resolve() if input_root else baseline):
        require(
            not root.is_relative_to(output) and not output.is_relative_to(root),
            "output overlaps input/baseline",
        )
    output.mkdir(parents=True, exist_ok=True)
    with campaign_lock(output):
        try:
            return _campaign(
                output,
                input_root=input_root,
                baseline=baseline,
                config_path=config_path,
                fixture=fixture,
                workers=workers,
                max_cells=max_cells,
            )
        except Exception:
            # A failed revalidation must not leave an old completion claim.
            complete = output / "COMPLETE.json"
            protocol_path = output / "protocol.json"
            owned = (
                protocol_path.exists()
                and read(protocol_path).get("config", {}).get("version") == CONTRACT["version"]
            )
            if complete.exists() and owned:
                complete.unlink()
                checkpoint = output / "checkpoint.json"
                state = read(checkpoint)
                state["artifacts"].pop("COMPLETE.json", None)
                write_checkpoint(checkpoint, state)
            raise


def _campaign(output, *, input_root, baseline, config_path, fixture, workers, max_cells):
    config = validate_config(read(Path(config_path)))
    verify_sources(read(ROOT / "config/c22h4-demo.json"))
    original, archive_hashes = None, {}
    parity_manifest = None
    if input_root is None:
        original, manifest, bars, ticks, archive_hashes = archived_input(baseline)
        input_binding = {"archive_hashes": archive_hashes}
        parity_manifest = manifest
    else:
        input_root = Path(input_root).resolve()
        manifest, bars, ticks = load_input(input_root, fixture=fixture)
        input_binding = {
            "path": str(input_root),
            "manifest_sha256": digest(input_root / "manifest.json"),
        }
        if not fixture:
            original, archived, archive_hashes = verify_baseline(baseline)
            parity_manifest = dict(broker=archived["broker"])
    pins = sources()
    protocol = native(
        dict(
            config=config,
            config_id=contract_id(config),
            manifest=manifest,
            input=input_binding,
            baseline_hashes=archive_hashes,
            source_hashes=pins,
            config_sha256=digest(Path(config_path)),
            runtime=dict(
                python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__
            ),
            cost_status="COST_INCONCLUSIVE",
            fixture=fixture,
            catalog=[dict(strategy=s, view=v) for s in ("c22", "smc") for v in config["views"]],
        )
    )
    store = Store(output, protocol)
    if not fixture:
        frozen_parity(baseline, store, original, parity_manifest)
    smc = prepare_signals(bars, config)
    c22, _ = prepare_candidate(bars, C22_CONTRACT)
    require(c22.macro_blocked is not None, "C22 macro contract missing")
    selected = (
        smc.index + pd.Timedelta(minutes=15) >= pd.Timestamp(manifest["requested_start_utc"])
    ) & (smc.index + pd.Timedelta(minutes=15) < pd.Timestamp(manifest["requested_end_utc"]))
    audit_frame = smc.loc[selected]
    coverage = dict(
        manifest["coverage"],
        h4_unavailable_evaluation_bars=int(audit_frame.macro_ema.isna().sum()),
        atr_unavailable_evaluation_bars=int(audit_frame.atr.isna().sum()),
        unavailable_indicator_evaluation_bars=int(
            (audit_frame.macro_ema.isna() | audit_frame.atr.isna()).sum()
        ),
    )
    funnel = audit_frame.signal_reason.value_counts().to_dict()
    signals = [
        dict(bar_open_utc=t.isoformat(), **row.to_dict())
        for t, row in audit_frame.loc[
            audit_frame.direction != 0,
            ["direction", "setup_id", "sweep_utc", "choch_utc", "fvg_utc", "gap_low", "gap_high"],
        ].iterrows()
    ]
    store.put(
        "signals.json",
        native(
            dict(
                funnel=funnel,
                candidates=signals,
                pool_unavailable_bars=int(audit_frame.asian_low.isna().sum()),
            )
        ),
    )
    written = 0
    for item in protocol["catalog"]:
        key = item["strategy"] + "-" + item["view"]
        if (
            store.get("cells/" + key + ".json") is not None
            and store.get("repeat/" + key + ".json") is not None
        ):
            continue
        if written >= max_cells:
            break
        frame = smc if item["strategy"] == "smc" else c22
        # Workers parallelize fresh repeat, not mutable account state or chunks.
        task = (item["strategy"], item["view"], frame, ticks, manifest, config)
        if workers == 1:
            result, repeated = execute(task), execute(task)
        else:
            # Re-open immutable mmap in workers instead of pickling huge tick arrays.
            with ProcessPoolExecutor(max_workers=workers) as pool:
                root = input_root if input_root is not None else baseline / "input"
                prefix = "" if input_root is not None else "continuous-"
                args = (item["strategy"], item["view"], bars, str(root), prefix, manifest, config)
                futures = [pool.submit(execute_from_disk, args) for _ in range(2)]
                result, repeated = [f.result() for f in futures]
        require(result == repeated, "fresh complete-result mismatch: " + key)
        require(sources() == pins, "source drift during replay")
        store.put("cells/" + key + ".json", result)
        store.put(
            "repeat/" + key + ".json",
            dict(
                fresh_full_result_match=True,
                result_sha256=digest(output / "cells" / (key + ".json")),
            ),
        )
        written += 1
        print(key, "full-result repeat PASS", flush=True)
    rows = []
    for item in protocol["catalog"]:
        key = item["strategy"] + "-" + item["view"]
        result = store.get("cells/" + key + ".json")
        if result is not None:
            proof = store.get("repeat/" + key + ".json")
            require(
                proof is not None
                and proof["fresh_full_result_match"] is True
                and proof["result_sha256"] == digest(output / "cells" / (key + ".json")),
                "missing/mismatched repeat proof",
            )
            rows.append(scorecard(result, item["strategy"], item["view"]))
    require(sources() == pins, "source drift before completion")
    if input_root is not None:
        require(
            digest(input_root / "manifest.json") == input_binding["manifest_sha256"],
            "manifest drift during campaign",
        )
        load_input(input_root, fixture=fixture)
    else:
        for path, expected in archive_hashes.items():
            require(digest(Path(path)) == expected, "archive drift during campaign")
    complete = len(rows) == 4
    summary = native(
        dict(
            status="FIXTURE_COMPLETE"
            if fixture and complete
            else "COMPLETE"
            if complete
            else "PARTIAL",
            scorecard=rows,
            fresh_full_result_match=complete,
            conclusion="DESCRIPTIVE_ONLY_NO_SELECTION",
            cost_status="COST_INCONCLUSIVE",
            coverage=coverage,
            baseline_parity=not fixture,
            protocol_sha256=digest(output / "protocol.json"),
        )
    )
    if complete:
        store.put("COMPLETE.json", summary)
    return summary


def execute_from_disk(args):
    strategy, view, bars, root, prefix, manifest, config = args
    frame = (
        prepare_signals(bars, config)
        if strategy == "smc"
        else prepare_candidate(bars, C22_CONTRACT)[0]
    )
    ticks = tuple(
        np.load(Path(root) / (prefix + "tape") / (k + ".npy"), mmap_mode="r")
        for k in ("time", "bid", "ask")
    )
    return execute((strategy, view, frame, ticks, manifest, config))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument(
        "--fixture", action="store_true", help="explicit synthetic diagnostics only"
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-cells", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        result = campaign(
            args.output,
            input_root=args.input,
            baseline=args.baseline,
            config_path=args.config,
            fixture=args.fixture,
            workers=args.workers,
            max_cells=args.max_cells,
        )
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result["status"] in ("COMPLETE", "FIXTURE_COMPLETE") else 3
    except (ValueError, KeyError, OSError) as exc:
        print(json.dumps(dict(status="BLOCKED", reason=str(exc))), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
