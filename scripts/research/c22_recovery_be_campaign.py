"""Two-profile preregistered OFFLINE campaign; frozen parent files stay intact."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import argparse
import fcntl
import gzip
import inspect
import json
from pathlib import Path
import shutil

import pandas as pd

from scripts.research import c22_risk_campaign as parent_engine
from scripts.research.breakout_models import Costs, Rules
from scripts.research.c22_loop_store import load_summary
from scripts.research.c22_matrix_tuning import closing_recovery
from scripts.research.c22_performance_campaign import (
    INPUT,
    ROOT,
    VIEWS,
    diagnostics,
    qualifies,
    read,
    sha,
    write,
)
from scripts.research.c22_recovery_be_replay import replay

PARENT = ROOT / "runs/c22-risk-closure-2026-10-26"
PREREG = ROOT / "runs/c22-issue-closure-2026-10-28/research"
DEFAULT_OUT = ROOT / "runs/c22-recovery-be-2026-10-28"
ALGORITHM = "c22_recovery_netbe_v1"
BASE = "26b8bcd69e043653"
B2 = "b7431d3dc4c30161"
GUARDS = ("raw", "cent")


def validate(protocol, out, *, inputs=True):
    assert protocol["algorithm"] == ALGORITHM and protocol["expected_paths"] == 12
    assert protocol["holdout"] is False and protocol["execution_authorized"] is False
    for name, digest in protocol["sources"].items():
        assert sha(ROOT / name) == digest, "source drift: " + name
        assert sha(out / "source_snapshot" / name) == digest, "snapshot drift: " + name
    for record in protocol["parent"].values():
        assert sha(ROOT / record["path"]) == record["sha256"], "parent drift"
    assert sha(INPUT / "manifest.json") == protocol["input_manifest_sha256"]
    if inputs:
        for name, digest in protocol["input_hashes"].items():
            assert sha(INPUT / name) == digest, "input drift: " + name
    assert sha(out / "catalog.json") == protocol["catalog_sha256"]
    cats = read(out / "catalog.json")
    assert cats["algorithm"] == ALGORITHM and cats["finite_domain"] == 2
    assert [p["name"] for p in cats["profiles"]] == [BASE, B2]
    assert cats == read(PREREG / "next-risk-catalog.json")


def freeze(out):
    out = Path(out).resolve()
    assert out.is_relative_to(ROOT / "runs")
    if (out / "protocol.json").exists():
        p = read(out / "protocol.json")
        validate(p, out)
        return p
    prior = read(PARENT / "protocol.json")
    assert read(PARENT / "FINAL.json")["status"] == "VERIFIED_COMPLETE"
    assert read(PARENT / "independent-verification.json")["status"] == "PASS"
    pre = read(PREREG / "preregistration-final-freeze.json")
    for name, digest in pre["sources"].items():
        assert sha(ROOT / name) == digest
    sources = dict(prior["sources"])
    for name in (
        "scripts/research/c22_recovery_be_campaign.py",
        "scripts/research/c22_recovery_be_verify.py",
        "scripts/research/c22_recovery_be_replay.py",
        "tests/research/test_c22_recovery_be_replay.py",
        "tests/research/test_c22_recovery_be_audit.py",
        "specs/c22-next-risk-2026-10-28.md",
    ):
        sources[name] = sha(ROOT / name)
    out.mkdir(parents=True, exist_ok=True)
    cats = read(PREREG / "next-risk-catalog.json")
    write(out / "catalog.json", cats)
    p = {
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
    }
    p.update(
        algorithm=ALGORITHM,
        schema=1,
        finite_domain=2,
        expected_paths=12,
        baseline_id=BASE,
        candidate_id=B2,
        sources=sources,
        catalog_sha256=sha(out / "catalog.json"),
        frozen_utc=datetime.now(timezone.utc).isoformat(),
        holdout=False,
        cost_status="COST_INCONCLUSIVE",
        execution_authorized=False,
        ranking="max raw base net,raw stress net,lower worst6 DD;native wins ties",
        repeat_policy="selected_profit_all_six_fresh",
        parent={
            key: dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
            for key, path in [
                ("protocol", PARENT / "protocol.json"),
                ("audit", PARENT / "independent-verification.json"),
                ("final", PARENT / "FINAL.json"),
                ("prereg", PREREG / "preregistration-final-freeze.json"),
            ]
        },
    )
    for name, digest in sources.items():
        assert sha(ROOT / name) == digest
        target = out / "source_snapshot" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    write(out / "protocol.json", p)
    validate(p, out)
    return p


def cent_replay():
    source = inspect.getsource(replay)
    assert source.count("if net < 0:") == 1

    def loss(net):
        return Decimal(str(float(net))).quantize(Decimal(".01"), rounding=ROUND_HALF_UP) < 0

    scope = dict(replay.__globals__, _cent_loss=loss)
    exec(
        compile(source.replace("if net < 0:", "if _cent_loss(net):"), "<recovery-cent>", "exec"),
        scope,
    )
    return scope["replay"]


def cell(out, key, folder="cells"):
    assert folder in ("cells", "repeats")
    proof = read(out / (folder + "-integrity") / (key + ".json"))
    path = (ROOT / proof["path"]).resolve()
    assert path == (out / folder / (key + ".json.gz")).resolve() and sha(path) == proof["sha256"]
    with gzip.open(path, "rt") as stream:
        result = json.load(stream)
    assert key == f"{result['profile']['name']}-{result['view']}-{result['guard']}"
    return result


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

    def rank(name):
        rows = summaries[name]
        return (
            -rows["raw"]["base"]["metrics"]["net_usd"],
            -rows["raw"]["stress"]["metrics"]["net_usd"],
            max(rows[g][v]["metrics"]["max_dd_pct"] for g in GUARDS for v in VIEWS),
            name != BASE,
        )

    return min(eligible, key=rank), sorted(eligible)


def run(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    with (out / "campaign.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        protocol = freeze(out)
        profiles = read(out / "catalog.json")["profiles"]
        parent_engine.init_worker(protocol, out)
        # Reuse only the frozen parent's data/accounting preparation, not its
        # replay or selection. Exactly one process owns this campaign lock.
        state = parent_engine._WORKER
        cent = cent_replay()
        summaries = {}

        def execute(profile, view, guard, folder):
            key = f"{profile['name']}-{view}-{guard}"
            if (out / (folder + "-integrity") / (key + ".json")).exists():
                return cell(out, key, folder)
            assert shutil.disk_usage(out).free >= 2 * 1024**3, "insufficient disk"
            result = (cent if guard == "cent" else replay)(
                state["frame"],
                state["ticks"],
                protocol["broker"],
                Rules(**protocol["native_rules"]),
                Costs(**protocol["views"][view]),
                start=pd.Timestamp(protocol["start"]),
                end=pd.Timestamp(protocol["end"]),
                swap_policy=state["swap"],
                capture_events=True,
                capture_context=True,
                recovery_be=profile["name"] == B2,
            )
            assert result.get("swap_policy") is not None
            if profile["name"] == BASE:
                reference = parent_engine._reference(protocol, view, guard)
                assert result == reference["result"], "native control parity failure"
            checks = state["audit"].independent_audit(
                result, protocol["broker"], Costs(**protocol["views"][view])
            )
            metrics = state["audit"].metrics(result)
            minimum = min([200.0] + [x["equity_usd"] for x in result["equity"]])
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
                profile=profile,
                view=view,
                guard=guard,
                result=result,
                metrics=metrics,
                diagnostics=dx,
                checks=checks,
            )
            value["summary"] = load_summary(value)
            if folder == "repeats":
                original = cell(out, key)
                assert all(
                    value[k] == original[k] for k in ("result", "metrics", "diagnostics", "summary")
                ), "fresh repeat drift"
            target = out / folder / (key + ".json.gz")
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".pending")
            with temporary.open("wb") as stream:
                with gzip.GzipFile(
                    filename="", mode="wb", compresslevel=1, fileobj=stream, mtime=0
                ) as zipped:
                    zipped.write(json.dumps(value, allow_nan=False, separators=(",", ":")).encode())
            temporary.replace(target)
            write(
                out / (folder + "-integrity") / (key + ".json"),
                dict(path=str(target.relative_to(ROOT)), sha256=sha(target), origin="new"),
            )
            print(
                folder,
                key,
                "net",
                round(metrics["net_usd"], 4),
                "DD",
                round(metrics["max_dd_pct"], 4),
                flush=True,
            )
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
                            expected_paths=12,
                            evaluated_paths=sum(
                                len(v) for x in summaries.values() for v in x.values()
                            ),
                            summaries=summaries,
                        ),
                    )
        selected, eligible = choose(protocol, summaries)
        profile = next(p for p in profiles if p["name"] == selected)
        for guard in GUARDS:
            for view in VIEWS:
                execute(profile, view, guard, "repeats")
        validate(protocol, out)
        value = dict(
            status="MATRIX_EVALUATED_AWAITING_AUDIT",
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
                artifacts={str(p.relative_to(out)): sha(p) for p in paths},
            ),
        )
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--freeze-only", action="store_true")
    args = parser.parse_args()
    if args.freeze_only:
        freeze(args.out)
    else:
        run(args.out)


if __name__ == "__main__":
    main()
