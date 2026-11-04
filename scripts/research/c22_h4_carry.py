"""Owner-selected H4 B research adapter and bounded offline campaign.

Only macro availability changes. Frozen replay/accounting sources stay intact.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import sys

import numpy as np
import pandas as pd

from scripts.research import c22_risk_campaign as parent_engine
from scripts.research.breakout_models import Costs, Rules
from scripts.research.c22_loop_store import load_summary
from scripts.research.c22_matrix_tuning import closing_recovery
from scripts.research.c22_performance_campaign import (
    INPUT,
    ROOT,
    SEED,
    VIEWS,
    diagnostics,
    qualifies,
    read,
    sha,
    write,
)
from scripts.research.reward156_tuning import closed_h4_ema

ALGORITHM = "c22_strict_h4_carry_v1"
BASE = "26b8bcd69e043653"
GUARDS = ("raw", "cent")
PARENT = ROOT / "runs/c22-risk-closure-2026-10-26"
PARENT_PROTOCOL_SHA = "a104009031a88558cc07d21a6beb485f79d3aa17e4d0046217c55122f670700b"
SPEC = ROOT / "specs/c22-h4-carry-2026-10-30.md"
TEST = ROOT / "tests/research/test_c22_h4_carry.py"
VERIFIER = ROOT / "scripts/research/c22_h4_carry_verify.py"
VERIFIER_TEST = ROOT / "tests/research/test_c22_h4_carry_verify.py"
AUDIT = ROOT / "runs/c22-real-data-audit-2026-10-24/run_audit_v2.py"
DEFAULT_OUT = ROOT / "runs/c22-h4-carry-2026-10-30"
POLICY = dict(
    schema=1,
    source="strict_16_complete_M15_per_UTC_calendar_H4",
    ema_span=200,
    ema_adjust=False,
    ema_min_periods=200,
    publication="H4_open_plus_4h",
    decision="M15_open_plus_15min",
    max_age_hours_exclusive=8,
    age_clock="elapsed_UTC_no_session_subtraction",
    missing_bucket="no_new_close_no_EMA_update_no_age_reset",
    unknown_session="cause_unknown_retained_carry_permitted_only_inside_bound",
    direction="native_raw_direction_before_macro_mask",
)


def h4_context(bars):
    """Reuse canonical EMA values, carrying only already-published full H4s."""
    strict = closed_h4_ema(bars, 200)
    decisions = bars.index + pd.Timedelta(minutes=15)
    at_boundary = decisions == decisions.floor("4h")
    events = pd.Series(strict.to_numpy()[at_boundary], index=decisions[at_boundary]).dropna()
    values = events.reindex(decisions, method="ffill")
    published = pd.Series(events.index, index=events.index).reindex(decisions, method="ffill")
    age = (pd.Series(decisions, index=decisions) - published) / pd.Timedelta(hours=1)
    available = values.notna() & age.ge(0) & age.lt(8)
    carried = available & strict.isna().to_numpy()
    return pd.DataFrame(
        dict(
            macro_ema=values.where(available).to_numpy(),
            source_end_utc=published.array,
            age_hours=age.to_numpy(),
            carried=carried.to_numpy(),
            status=np.select(
                [available & carried, available, published.isna()],
                ["CARRIED_CAUSE_UNKNOWN", "CURRENT_STRICT_H4", "WARMUP"],
                default="EXPIRED",
            ),
        ),
        index=bars.index,
    )


def carry_frame(bars, native, *, enabled):
    """Apply selected macro to raw direction; disabled output is exact native."""
    if type(enabled) is not bool or not bars.index.equals(native.index):
        raise ValueError("h4_exact_frame_identity_required")
    if not native.raw_direction.isin((-1, 0, 1)).all():
        raise ValueError("h4_native_raw_direction_invalid")
    if not bars[["open", "high", "low", "close"]].equals(native[["open", "high", "low", "close"]]):
        raise ValueError("h4_native_ohlc_mismatch")
    if not enabled:
        return native.copy(), None
    context = h4_context(bars)
    result = native.copy()
    active = result.raw_direction.ne(0)
    available = context.macro_ema.notna()
    allowed = result.raw_direction * (result.close - context.macro_ema) > 0
    result["direction"] = result.raw_direction.where(allowed, 0)
    result["macro_unavailable"] = active & ~available
    result["macro_blocked"] = active & ~allowed
    result["h4_warmup"] = active & ~available & context.source_end_utc.isna()
    result["h4_incomplete"] = active & ~available & context.source_end_utc.notna()
    result["h4_directional_mismatch"] = active & available & ~allowed
    return result, context


def catalog(native_rules):
    descriptor = dict(
        algorithm=ALGORITHM, native_rules=native_rules, signal_seed=read(SEED), h4_policy=POLICY
    )
    identity = hashlib.sha256(json.dumps(descriptor, sort_keys=True).encode()).hexdigest()[:16]
    return dict(
        schema=1,
        algorithm=ALGORITHM,
        finite_domain=2,
        profiles=[
            dict(name=BASE, label="Native26b8", carry=False),
            dict(
                name=identity, label="B-strict-H4-carry-under8h", carry=True, descriptor=descriptor
            ),
        ],
    )


def loaded_repo_sources():
    """Include every loaded repository Python origin, including package init."""
    paths = {AUDIT, Path(__file__).resolve()}
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name:
            path = Path(name).resolve()
            if path.suffix == ".pyc":
                path = Path(importlib.util.source_from_cache(str(path)))
            if path.is_file() and path.is_relative_to(ROOT):
                paths.add(path)
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(paths)}


def runtime_versions():
    return dict(
        python=platform.python_version(),
        numpy=np.__version__,
        pandas=pd.__version__,
        executable_sha256=sha(Path(sys.executable).resolve()),
    )


def loaded_runtime_sources():
    """Bind loaded origins outside the repository too; never silently omit them."""
    paths = set()
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name:
            path = Path(name).resolve()
            if path.suffix == ".pyc":
                path = Path(importlib.util.source_from_cache(str(path)))
            if path.is_file() and not path.is_relative_to(ROOT):
                paths.add(path)
    return {str(path): sha(path) for path in sorted(paths)}


def load_audit():
    spec = importlib.util.spec_from_file_location("h4_carry_accounting_audit", AUDIT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def warm_dependencies(protocol):
    """Exercise tiny synthetic accounting before pinning lazy runtime origins."""
    audit = load_audit()
    cent = parent_engine._cent_replay()
    # Independent reconstruction uses this lazy NumPy helper after the cells.
    # Warm its actual assertion path before pinning audit dependencies too.
    importlib.import_module("numpy.testing").assert_allclose([1.0], [1.0])
    index = pd.to_datetime(
        ["2026-04-07T23:30Z", "2026-04-07T23:45Z", "2026-04-08T00:00Z"], utc=True
    )
    frame = pd.DataFrame(
        dict(
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            hh=100.0,
            ll=95.0,
            atr=1.0,
            direction=[1, 0, 0],
            raw_direction=[1, 0, 0],
        ),
        index=index,
    )
    times = (
        pd.to_datetime(["2026-04-07T23:45Z", "2026-04-08T00:00Z", "2026-04-08T00:15Z"], utc=True)
        .as_unit("ms")
        .asi8
    )
    bid = np.array([100.0, 100.0, 98.0])
    ticks = times, bid, bid + 0.2
    swap = parent_engine.SwapPolicy.from_broker(protocol["broker"])
    if swap is None:
        raise ValueError("modeled_swap_required_for_dependency_warmup")
    h4_context(frame)
    for guard in GUARDS:
        for view in VIEWS:
            costs = Costs(**protocol["views"][view])
            result = (cent if guard == "cent" else parent_engine.replay)(
                frame,
                ticks,
                protocol["broker"],
                Rules(**protocol["native_rules"]),
                costs,
                start=index[0].normalize(),
                end=pd.Timestamp("2026-04-08T00:16Z"),
                swap_policy=swap,
                capture_events=True,
                capture_context=True,
            )
            audit.independent_audit(result, protocol["broker"], costs)
            metrics = audit.metrics(result)
            metrics["min_observed_equity"] = min(
                [200.0] + [row["equity_usd"] for row in result["equity"]]
            )
            dx = diagnostics(result, "2026-04-08T00:15:00+00:00")
            dx["actual_closing_recovery"] = closing_recovery(result, "2026-04-08T00:15:00+00:00")
            load_summary(dict(metrics=metrics, diagnostics=dx))


def check_loaded(protocol):
    for name, digest in loaded_repo_sources().items():
        if protocol["sources"].get(name) != digest:
            raise ValueError("unpinned_or_changed_loaded_dependency: " + name)
    for name, digest in loaded_runtime_sources().items():
        if protocol["runtime_sources"].get(name) != digest:
            raise ValueError("unpinned_or_changed_runtime_dependency: " + name)


def safe_out(out, *, resume_empty_freeze=False):
    if type(resume_empty_freeze) is not bool:
        raise ValueError("explicit_boolean_empty_freeze_review_required")
    out = Path(out).resolve()
    runs = (ROOT / "runs").resolve()
    if out.parent != runs:
        raise ValueError("research_output_must_be_a_dedicated_runs_child")
    for protected in (INPUT.resolve(), PARENT.resolve()):
        if out == protected or out.is_relative_to(protected) or protected.is_relative_to(out):
            raise ValueError("research_output_overlaps_immutable_inputs_or_parent")
    if out.exists():
        if not out.is_dir():
            raise ValueError("research_output_is_not_a_directory")
        entries = list(out.iterdir())
        if entries:
            lock = out / "campaign.lock"
            if (resume_empty_freeze and entries == [lock] and not lock.is_symlink()
                    and lock.is_file() and lock.stat().st_size == 0 and lock.stat().st_nlink == 1):
                return out
            path = out / "protocol.json"
            if not path.is_file() or path.is_symlink():
                raise ValueError("nonempty_unrelated_campaign_destination")
            try:
                protocol = read(path)
                if (
                    protocol["algorithm"] != ALGORITHM
                    or protocol["policy"] != POLICY
                    or protocol["baseline_id"] != BASE
                    or protocol["execution_authorized"] is not False
                ):
                    raise ValueError("different_campaign")
                validate(protocol, out)
            except (AssertionError, KeyError, OSError, TypeError, ValueError):
                raise ValueError("unrelated_or_invalid_campaign_destination") from None
    return out


def plan():
    if sha(PARENT / "protocol.json") != PARENT_PROTOCOL_SHA:
        raise ValueError("parent_protocol_drift")
    prior = read(PARENT / "protocol.json")
    assert read(PARENT / "FINAL.json")["status"] == "VERIFIED_COMPLETE"
    assert read(PARENT / "independent-verification.json")["status"] == "PASS"
    for name, digest in prior["sources"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("inherited_source_drift: " + name)
    assert prior["native_rules_id"] == BASE
    assert set(prior["views"]) == set(VIEWS) == {"base", "stress", "fee"}
    assert sha(INPUT / "manifest.json") == prior["input_manifest_sha256"]
    for view in VIEWS:
        for guard in GUARDS:
            parent_engine._reference(prior, view, guard)
    warm_dependencies(prior)
    # Independent audit dependencies are part of the pre-outcome source closure.
    importlib.import_module("scripts.research.c22_h4_carry_verify")
    # np.load's structured-dtype header path loads this lazily at worker init.
    importlib.import_module("numpy.rec")
    sources = dict(prior["sources"], **loaded_repo_sources())
    for path in (Path(__file__).resolve(), SPEC, TEST, VERIFIER, VERIFIER_TEST, SEED):
        sources[str(path.relative_to(ROOT))] = sha(path)
    cats = catalog(prior["native_rules"])
    return dict(
        **{
            key: prior[key]
            for key in (
                "broker",
                "views",
                "start",
                "end",
                "original_floors",
                "native_rules",
                "input_hashes",
                "input_manifest_sha256",
                "references",
            )
        },
        schema=1,
        algorithm=ALGORITHM,
        sources=sources,
        policy=POLICY,
        runtime_versions=runtime_versions(),
        runtime_sources=loaded_runtime_sources(),
        dependency_warmup="tiny_synthetic_six_view_swap_accounting_only_no_historical_cells",
        initial_balance=200.0,
        input_stats={
            name: dict(
                bytes=(INPUT / name).stat().st_size, mtime_ns=(INPUT / name).stat().st_mtime_ns
            )
            for name in prior["input_hashes"]
        },
        native_rules_id=BASE,
        baseline_id=BASE,
        candidate_id=cats["profiles"][1]["name"],
        finite_domain=2,
        expected_paths=12,
        expected_selected_repeats=6,
        holdout=False,
        cost_status="COST_INCONCLUSIVE",
        real_money="PROHIBITED",
        execution_authorized=False,
        ranking="max raw base net,raw stress net,lower worst6 DD;native wins ties",
        improvement="all6matched_native_nets_preserved_and_strict_raw_base_increase",
        repeat_policy="selected_profit_all_six_fresh",
        parent={
            name: dict(
                path=str((PARENT / filename).relative_to(ROOT)), sha256=sha(PARENT / filename)
            )
            for name, filename in (
                ("protocol", "protocol.json"),
                ("audit", "independent-verification.json"),
                ("final", "FINAL.json"),
            )
        },
    ), cats


def validate(protocol, out, *, inputs=False):
    assert protocol["algorithm"] == ALGORITHM and protocol["policy"] == POLICY
    assert protocol["execution_authorized"] is False and protocol["expected_paths"] == 12
    assert protocol["runtime_versions"] == runtime_versions()
    for name, digest in protocol["runtime_sources"].items():
        if sha(Path(name)) != digest:
            raise ValueError("runtime_dependency_drift: " + name)
    for name, digest in protocol["sources"].items():
        if sha(ROOT / name) != digest or sha(out / "source_snapshot" / name) != digest:
            raise ValueError("source_or_snapshot_drift: " + name)
    for record in protocol["parent"].values():
        assert sha(ROOT / record["path"]) == record["sha256"]
    assert sha(INPUT / "manifest.json") == protocol["input_manifest_sha256"]
    for name, expected in protocol["input_stats"].items():
        path = INPUT / name
        assert dict(bytes=path.stat().st_size, mtime_ns=path.stat().st_mtime_ns) == expected, (
            "input_metadata_drift: " + name
        )
    assert sha(out / "catalog.json") == protocol["catalog_sha256"]
    assert read(out / "catalog.json") == catalog(protocol["native_rules"])
    if inputs:
        for name, digest in protocol["input_hashes"].items():
            assert sha(INPUT / name) == digest, "input_drift: " + name
    check_loaded(protocol)


def _freeze_locked(out):
    """Internal caller already validated destination and holds campaign lock."""
    if (out / "protocol.json").exists():
        protocol = read(out / "protocol.json")
        load_audit()
        validate(protocol, out, inputs=True)
        return protocol
    protocol, cats = plan()
    if any(
        (out / name).exists()
        for name in ("catalog.json", "source_snapshot", "protocol.json.pending")
    ):
        raise ValueError("partial_source_freeze_requires_review")
    for name, digest in protocol["input_hashes"].items():
        assert sha(INPUT / name) == digest, "input_drift: " + name
    assert shutil.disk_usage(out.parent).free >= 2 * 1024**3, "insufficient_disk"
    out.mkdir(parents=True, exist_ok=True)
    write(out / "catalog.json", cats)
    for name in protocol["sources"]:
        target = out / "source_snapshot" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    protocol.update(
        frozen_utc=datetime.now(timezone.utc).isoformat(), catalog_sha256=sha(out / "catalog.json")
    )
    write(out / "protocol.json", protocol)
    validate(protocol, out)
    return protocol


def freeze(out, *, resume_empty_freeze=False):
    out = safe_out(out, resume_empty_freeze=resume_empty_freeze)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Recheck after locking: a newly created unrelated artifact must not
        # turn a reviewed empty destination into a writable campaign.
        safe_out(out, resume_empty_freeze=True)
        return _freeze_locked(out)


def choose(protocol, summaries):
    eligible = [
        name
        for name, rows in summaries.items()
        if all(
            qualifies(
                {view: rows[guard][view]["metrics"] for view in VIEWS},
                protocol["original_floors"][guard],
            )
            for guard in GUARDS
        )
    ]
    assert BASE in eligible
    native = summaries[BASE]
    eligible = [
        name
        for name in eligible
        if name == BASE
        or (
            all(
                summaries[name][g][v]["metrics"]["net_usd"]
                >= native[g][v]["metrics"]["net_usd"] - 1e-7
                for g in GUARDS
                for v in VIEWS
            )
            and summaries[name]["raw"]["base"]["metrics"]["net_usd"]
            > native["raw"]["base"]["metrics"]["net_usd"] + 1e-7
        )
    ]

    def rank(name):
        rows = summaries[name]
        return (
            -rows["raw"]["base"]["metrics"]["net_usd"],
            -rows["raw"]["stress"]["metrics"]["net_usd"],
            max(rows[g][v]["metrics"]["max_dd_pct"] for g in GUARDS for v in VIEWS),
            name != BASE,
        )

    return min(eligible, key=rank), sorted(eligible)


def context_records(frame, context, native):
    if context is None:
        return []
    records = []
    for stamp, row in context.loc[frame.raw_direction.ne(0)].iterrows():
        records.append(
            dict(
                signal_close_utc=(stamp + pd.Timedelta(minutes=15)).isoformat(),
                source_end_utc=None
                if pd.isna(row.source_end_utc)
                else row.source_end_utc.isoformat(),
                age_hours=None if pd.isna(row.age_hours) else float(row.age_hours),
                carried=bool(row.carried),
                status=row.status,
                macro_ema=None if pd.isna(row.macro_ema) else float(row.macro_ema),
                raw_direction=int(frame.at[stamp, "raw_direction"]),
                native_direction=int(native.at[stamp, "direction"]),
                candidate_direction=int(frame.at[stamp, "direction"]),
            )
        )
    return records


def run(out):
    """Resume immutable cells under one lock; never implicitly freeze or deploy."""
    out = safe_out(out)
    if not (out / "protocol.json").exists():
        raise ValueError("reviewed_source_freeze_required_before_run")
    with (out / "campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        load_audit()
        protocol = read(out / "protocol.json")
        validate(protocol, out, inputs=True)
        parent_engine.init_worker(protocol, out)
        check_loaded(protocol)
        state = parent_engine._WORKER
        bars = state["frame"][["open", "high", "low", "close"]]
        profiles = read(out / "catalog.json")["profiles"]
        summaries = {}

        def execute(profile, view, guard, folder):
            key = f"{profile['name']}-{view}-{guard}"
            if (out / (folder + "-integrity") / (key + ".json")).exists():
                value = parent_engine.read_cell(out, key, folder)
                assert value["protocol_sha256"] == sha(out / "protocol.json")
                assert value["profile"] == profile
                assert value["result"]["rules"] == protocol["native_rules"]
                if not profile["carry"]:
                    assert (
                        value["result"] == parent_engine._reference(protocol, view, guard)["result"]
                    )
                return value
            target = out / folder / (key + ".json.gz")
            pending = target.with_suffix(".pending")
            if target.exists() or pending.exists():
                raise ValueError("unreconciled_cell_artifact: " + key)
            validate(protocol, out)
            assert shutil.disk_usage(out).free >= 2 * 1024**3, "insufficient_disk"
            frame, context = carry_frame(bars, state["frame"], enabled=profile["carry"])
            result = (state["cent"] if guard == "cent" else parent_engine.replay)(
                frame,
                state["ticks"],
                protocol["broker"],
                Rules(**protocol["native_rules"]),
                Costs(**protocol["views"][view]),
                start=pd.Timestamp(protocol["start"]),
                end=pd.Timestamp(protocol["end"]),
                swap_policy=state["swap"],
                capture_events=True,
                capture_context=True,
            )
            assert result.get("swap_policy") is not None
            if not profile["carry"]:
                assert result == parent_engine._reference(protocol, view, guard)["result"], (
                    "native_control_parity_failure"
                )
            checks = state["audit"].independent_audit(
                result, protocol["broker"], Costs(**protocol["views"][view])
            )
            metrics = state["audit"].metrics(result)
            minimum = min([200.0] + [row["equity_usd"] for row in result["equity"]])
            metrics.update(
                min_observed_equity=minimum,
                survival=bool(
                    minimum > 0
                    and result["final_balance"] > 0
                    and not result["rejections"]["bankrupt"]
                ),
            )
            dx = diagnostics(result, state["last_quote"])
            dx["actual_closing_recovery"] = closing_recovery(result, state["last_quote"])
            value = dict(
                protocol_sha256=sha(out / "protocol.json"),
                profile=profile,
                view=view,
                guard=guard,
                result=result,
                metrics=metrics,
                diagnostics=dx,
                checks=checks,
                h4_context=context_records(frame, context, state["frame"]),
            )
            value["summary"] = load_summary(value)
            if folder == "repeats":
                original = parent_engine.read_cell(out, key)
                assert all(
                    value[k] == original[k]
                    for k in ("result", "metrics", "diagnostics", "summary", "h4_context")
                )
            check_loaded(protocol)
            target.parent.mkdir(parents=True, exist_ok=True)
            assert shutil.disk_usage(out).free >= 2 * 1024**3, "insufficient_disk"
            with pending.open("wb") as stream:
                with gzip.GzipFile(
                    filename="", mode="wb", compresslevel=1, fileobj=stream, mtime=0
                ) as zipped:
                    zipped.write(json.dumps(value, allow_nan=False, separators=(",", ":")).encode())
            pending.replace(target)
            write(
                out / (folder + "-integrity") / (key + ".json"),
                dict(path=str(target.relative_to(ROOT)), sha256=sha(target), origin="new"),
            )
            print(folder, key, flush=True)
            return value

        for profile in profiles:
            for guard in GUARDS:
                for view in VIEWS:
                    value = execute(profile, view, guard, "cells")
                    summaries.setdefault(profile["name"], {}).setdefault(guard, {})[view] = value[
                        "summary"
                    ]
                    write(
                        out / "checkpoint.json",
                        dict(
                            status="PARTIAL",
                            summaries=summaries,
                            evaluated_paths=sum(
                                len(v) for row in summaries.values() for v in row.values()
                            ),
                        ),
                    )
        selected, eligible = choose(protocol, summaries)
        profile = next(row for row in profiles if row["name"] == selected)
        for guard in GUARDS:
            for view in VIEWS:
                execute(profile, view, guard, "repeats")
        validate(protocol, out)
        value = dict(
            status="MATRIX_EVALUATED_AWAITING_INDEPENDENT_H4_AND_TICK_AUDIT",
            evaluated_paths=12,
            fresh_repeats=6,
            selected=selected,
            qualified=eligible,
            summaries=summaries,
        )
        write(out / "results.json", value)
        paths = [out / name for name in ("protocol.json", "catalog.json", "results.json")]
        paths += list((out / "cells-integrity").glob("*.json")) + list(
            (out / "repeats-integrity").glob("*.json")
        )
        write(
            out / "COMPLETE.json",
            dict(
                status=value["status"],
                paths=12,
                fresh_repeats=6,
                selected=selected,
                artifacts={str(p.relative_to(out)): sha(p) for p in paths},
            ),
        )
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "freeze", "run", "check"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--resume-empty-freeze", action="store_true",
                        help="Reviewed retry of a failed freeze containing only its empty lock")
    args = parser.parse_args()
    if args.resume_empty_freeze and args.command != "freeze":
        parser.error("--resume-empty-freeze applies only to explicit freeze")
    if args.command == "preflight":
        protocol, cats = plan()
        print(
            json.dumps(
                dict(
                    status="UNFROZEN_PREFLIGHT_ONLY",
                    candidate_id=protocol["candidate_id"],
                    sources=len(protocol["sources"]),
                    loaded_sources=loaded_repo_sources(),
                    catalog=cats,
                ),
                indent=2,
            )
        )
    elif args.command == "freeze":
        print(
            json.dumps(
                dict(
                    status="FROZEN_NO_ECONOMIC_CELLS", candidate_id=freeze(
                        args.out, resume_empty_freeze=args.resume_empty_freeze
                    )["candidate_id"]
                )
            )
        )
    elif args.command == "check":
        load_audit()
        validate(read(args.out / "protocol.json"), args.out)
        print("SOURCE_AND_METADATA_PASS")
    else:
        print(json.dumps(run(args.out), indent=2))


if __name__ == "__main__":
    main()
