"""Hash-bound, resumable swap-inclusive C22 context diagnostics. No broker access."""

import argparse
from dataclasses import asdict
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from scripts.research.breakout_logic import Costs, replay
from scripts.research.c22_context import annotate, report
from scripts.research.reward156_search import prepare_candidate, config_id
from scripts.research.reward156_tuning import atomic_json
from scripts.research.rollover import SwapPolicy

REPO = Path(__file__).resolve().parents[2]
BASELINE = REPO / "data/research_output_four_strategy_full_history_2026_10_04"
NAME = "variant_1af968e9ac6a26ea"
SNAPSHOT = "RESEARCH-C22-H4EMA200-20261004"
VIEWS = ("base-swap", "stress-swap")


def read(path):
    value = json.loads(Path(path).read_text())
    require(isinstance(value, dict), "JSON object required: " + str(path))
    return value


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_baseline(root):
    """Bind original artifacts to completion attestations and frozen source bytes."""
    protocol, complete, results = [
        read(root / n) for n in ("protocol.json", "COMPLETE.json", "results.json")
    ]
    require(
        complete["protocol_sha256"] == digest(root / "protocol.json") == results["protocol_sha256"],
        "baseline protocol mismatch",
    )
    require(
        complete["results_sha256"] == digest(root / "results.json"), "baseline results mismatch"
    )
    frozen = {k: v for k, v in protocol.items() if k != "behavior_sha256"}
    require(
        hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest()
        == protocol["behavior_sha256"],
        "baseline behavior mismatch",
    )
    manifest_path = root / "input/continuous-manifest.json"
    manifest = read(manifest_path)
    require(
        protocol["input_manifest_sha256"] == digest(manifest_path), "baseline manifest mismatch"
    )
    require(results["input"] == manifest, "baseline manifest/result mismatch")
    hashes = {}

    def check(path, expected):
        require(digest(path) == expected, "input/source hash mismatch: " + str(path))
        hashes[str(path.resolve())] = expected

    for name in (
        "protocol.json",
        "COMPLETE.json",
        "results.json",
        "input/continuous-manifest.json",
    ):
        path = root / name
        hashes[str(path.resolve())] = digest(path)
    for name, expected in protocol["source_hashes"].items():
        check(root / "source_snapshot" / name, expected)
        # Original snapshots remain immutable. Allow the already-committed output
        # directory migration separately; all trading sources except observation
        # must still match their original bytes.
        if name == "scripts/research/reward156_campaign.py":
            old = (root / "source_snapshot" / name).read_bytes()
            migrated = old.replace(
                b"docs/reviews/reward156-profit-survival-2026-10-04",
                b"runs/reward156-profit-survival-2026-10-04",
            )
            require((REPO / name).read_bytes() in (old, migrated), "campaign source drift")
            hashes[str((REPO / name).resolve())] = digest(REPO / name)
        elif name != "scripts/research/breakout_replay.py":
            check(REPO / name, expected)
    for name, expected in manifest["source_hashes"].items():
        check(REPO / name, expected)
    for name, expected in manifest["artifacts"].items():
        check(root / "input" / name, expected)
    for item in manifest.get("newly_imported_months", []):
        check(root / "input/discovery" / (item["month"] + ".npz"), item["cache_sha256"])
        check(root / "input" / (item["month"] + "-bars.csv"), item["bars_sha256"])
    for view in VIEWS:
        key = view + "-" + NAME
        path = root / "cells" / (key + ".json")
        proof_path = root / "integrity" / (key + ".json")
        proof = read(proof_path)
        require(
            proof["behavior_sha256"] == protocol["behavior_sha256"]
            and proof["fresh_full_result_match"],
            "baseline repeat proof mismatch",
        )
        check(path, proof["result_sha256"])
        hashes[str(proof_path.resolve())] = digest(proof_path)
    return protocol, manifest, hashes


def reconcile(result, broker, witnesses):
    """Independent ledger/cash/risk/equity metric recomputation; no assertions stripped by -O."""
    ledger = result["ledger"]
    nets = [t["net"] for t in ledger]
    wins, losses = [n for n in nets if n > 0], [n for n in nets if n < 0]
    metrics = dict(
        trades=len(nets),
        net_usd=sum(nets),
        final_balance=200 + sum(nets),
        return_pct=sum(nets) / 2,
        win_rate=len(wins) / len(nets) if nets else None,
        profit_factor=sum(wins) / -sum(losses) if losses else None,
        realized_rr=(sum(wins) / len(wins)) / (-sum(losses) / len(losses))
        if wins and losses
        else None,
        mean_net_r=sum(t["net"] / t["risk_usd"] for t in ledger) / len(ledger) if ledger else None,
        max_admitted_risk_pct=max((t["risk_pct"] for t in ledger), default=0),
    )
    equity = np.array([200.0] + [p["equity_usd"] for p in result["equity"]])
    peak = np.maximum.accumulate(equity)
    checkpoint_dd = float(np.max((peak - equity) / peak) * 100)
    metrics["max_dd_pct"] = max(
        ((w["peak"] - w["trough"]) / w["peak"] * 100 for w in witnesses), default=0.0
    )
    require(checkpoint_dd <= metrics["max_dd_pct"] + 1e-8, "drawdown witness mismatch")
    for name, expected in metrics.items():
        actual = result[name]
        require(
            actual is None
            if expected is None
            else actual is not None and math.isclose(actual, expected, abs_tol=1e-8, rel_tol=1e-12),
            "metric mismatch: " + name,
        )
    cash, previous = 200.0, None
    for trade in ledger:
        costs = result["costs"]
        risk = (abs(trade["entry"] - trade["initial_stop"]) + costs["slippage"]) * broker[
            "trade_contract_size"
        ] * 0.01 + costs["commission_per_lot"] * 0.01
        require(
            trade["volume"] == 0.01 and trade["risk_pct"] <= 10 + 1e-8,
            "fixed lot/risk invariant mismatch",
        )
        require(
            math.isclose(risk, trade["risk_usd"], abs_tol=1e-8)
            and math.isclose(cash, trade["entry_equity"], abs_tol=1e-8),
            "ledger risk/cash mismatch",
        )
        born, exit_time = (
            pd.Timestamp(trade["entry_time_utc"]),
            pd.Timestamp(trade["exit_time_utc"]),
        )
        require(born <= exit_time and (previous is None or born >= previous), "ledger overlap")
        previous = exit_time
        cash += trade["net"]
    return metrics


def checkpoint_digest(value):
    return hashlib.sha256(
        json.dumps(
            {k: v for k, v in value.items() if k != "self_sha256"}, sort_keys=True, allow_nan=False
        ).encode()
    ).hexdigest()


def write_checkpoint(path, value):
    value["self_sha256"] = checkpoint_digest(value)
    atomic_json(path, value)


def completion(protocol_path, coverage):
    return dict(
        status="COMPLETE",
        cells=len(VIEWS),
        baseline_parity=True,
        fresh_full_result_match=True,
        conclusion="INCONCLUSIVE_FOR_FILTER_SELECTION",
        coverage_status="EXPLICIT_PERIOD_ATTESTATION"
        if coverage
        else "PERIOD_COVERAGE_UNAVAILABLE",
        protocol_sha256=digest(protocol_path),
    )


@contextmanager
def campaign_lock(output):
    """Persistent inode + OS lock: process death releases ownership, never unlink.

    Failed contenders must leave the active writer's artifacts and completion
    marker alone. Acquire before any validation/recovery/publication mutates them.
    """
    with (output / ".campaign.lock").open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("campaign already running: " + str(output)) from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def campaign(baseline, output, *, coverage_path=None, max_cells=len(VIEWS)):
    baseline, output = Path(baseline).resolve(), Path(output).resolve()
    require(
        output.is_relative_to(REPO / "runs") and output != REPO / "runs",
        "output must be a campaign under ignored runs/",
    )
    require(
        not baseline.is_relative_to(output) and not output.is_relative_to(baseline),
        "output overlaps original evidence",
    )
    output.mkdir(parents=True, exist_ok=True)
    with campaign_lock(output):
        return _campaign_locked(baseline, output, coverage_path=coverage_path, max_cells=max_cells)


def _campaign_locked(baseline, output, *, coverage_path, max_cells):
    complete_path = output / "COMPLETE.json"
    try:
        original, manifest, hashes = verify_baseline(baseline)
        coverage = read(coverage_path) if coverage_path else None
        if coverage_path:
            hashes[str(Path(coverage_path).resolve())] = digest(coverage_path)
        # Conservative transitive superset: all application Python sources.
        sources = {
            str(p.relative_to(REPO)): digest(p) for p in sorted((REPO / "scripts").rglob("*.py"))
        }
        protocol = dict(
            schema=2,
            cost_views=list(VIEWS),
            swap_required=True,
            snapshot=SNAPSHOT,
            variant=NAME,
            baseline=str(baseline),
            original_behavior_sha256=original["behavior_sha256"],
            inputs=hashes,
            instrumentation_sources=sources,
            coverage=coverage,
            formulas="open-context-v1",
            discovery_only=True,
            cost_status=manifest.get("costs_status", "COST_INCONCLUSIVE"),
            runtime=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__),
        )
        path = output / "protocol.json"
        if path.exists():
            require(read(path) == protocol, "resume protocol/source/input mismatch")
        else:
            leftovers = list(output.iterdir())
            require(
                all(p.name in ("protocol.pending", ".campaign.lock") for p in leftovers),
                "unrecognized campaign artifacts",
            )
            for temporary in leftovers:
                if temporary.name == "protocol.pending":
                    temporary.unlink()
            atomic_json(path, protocol)
        checkpoint_path = output / "checkpoint.json"
        checkpoint = (
            read(checkpoint_path)
            if checkpoint_path.exists()
            else dict(artifacts={}, cells=[], pending=None, protocol_sha256=digest(path))
        )
        if checkpoint_path.exists():
            require(
                checkpoint.get("self_sha256") == checkpoint_digest(checkpoint)
                and checkpoint_path.read_bytes()
                == (json.dumps(checkpoint, indent=2, allow_nan=False) + "\n").encode(),
                "checkpoint digest mismatch",
            )
        else:
            write_checkpoint(checkpoint_path, checkpoint)
        require(
            checkpoint.get("protocol_sha256") == digest(path), "resume protocol digest mismatch"
        )
        require(
            set(checkpoint) == {"artifacts", "cells", "pending", "protocol_sha256", "self_sha256"}
            and len(checkpoint["cells"]) == len(set(checkpoint["cells"]))
            and set(checkpoint["cells"]).issubset(VIEWS),
            "invalid checkpoint structure",
        )
        pending = checkpoint["pending"]
        if pending is not None:
            require(
                set(pending) == {"view", "payload", "sha256"}
                and pending["view"] in VIEWS
                and pending["view"] not in checkpoint["cells"],
                "invalid pending cell",
            )
            payload = pending["payload"]
            require(
                set(payload)
                == {
                    f"{pending['view']}/{kind}.json"
                    for kind in ("diagnostics", "coverage", "validation")
                },
                "pending artifact accounting mismatch",
            )
            require(
                hashlib.sha256(
                    json.dumps(payload, sort_keys=True, allow_nan=False).encode()
                ).hexdigest()
                == pending["sha256"],
                "pending payload mismatch",
            )
            for name, value in payload.items():
                target = output / name
                expected_bytes = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
                if target.exists():
                    require(target.read_bytes() == expected_bytes, "pending artifact mismatch")
                else:
                    atomic_json(target, value)
                checkpoint["artifacts"][name] = digest(target)
            checkpoint["cells"].append(pending["view"])
            checkpoint["pending"] = None
            write_checkpoint(checkpoint_path, checkpoint)
        # Atomic writer's named .pending files are owned incomplete bytes, never results.
        temporary_names = {"protocol.pending", "checkpoint.pending", "COMPLETE.pending"} | {
            f"{view}/{kind}.pending"
            for view in VIEWS
            for kind in ("diagnostics", "coverage", "validation")
        }
        for temporary in output.rglob("*.pending"):
            require(
                str(temporary.relative_to(output)) in temporary_names,
                "unrecognized temporary artifact",
            )
            temporary.unlink()
        if complete_path.exists() and "COMPLETE.json" not in checkpoint["artifacts"]:
            expected = completion(path, coverage)
            require(
                len(checkpoint["cells"]) == len(VIEWS)
                and complete_path.read_bytes()
                == (json.dumps(expected, indent=2, allow_nan=False) + "\n").encode(),
                "uncommitted completion mismatch",
            )
            checkpoint["artifacts"]["COMPLETE.json"] = digest(complete_path)
            write_checkpoint(checkpoint_path, checkpoint)
        required_artifacts = {
            f"{view}/{kind}.json"
            for view in checkpoint["cells"]
            for kind in ("diagnostics", "coverage", "validation")
        }
        if "COMPLETE.json" in checkpoint["artifacts"]:
            require(len(checkpoint["cells"]) == len(VIEWS), "premature completion marker")
            required_artifacts.add("COMPLETE.json")
        require(
            set(checkpoint["artifacts"]) == required_artifacts,
            "checkpoint artifact accounting mismatch",
        )
        # Verify every artifact before reuse, including summaries and COMPLETE.
        expected_files = {
            "protocol.json",
            "checkpoint.json",
            ".campaign.lock",
            *checkpoint["artifacts"],
        }
        require(
            not {str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()}
            - expected_files,
            "unrecognized resume artifact",
        )
        for name, expected in checkpoint["artifacts"].items():
            require(digest(output / name) == expected, "resume artifact mismatch: " + name)
        bars = pd.read_csv(baseline / "input/continuous-bars.csv")
        bars.index = pd.DatetimeIndex(pd.to_datetime(bars.pop("bar_open_utc"), utc=True))
        contract = next(c for c in original["catalog"] if c["name"] == NAME)
        require("variant_" + config_id(contract) == NAME, "frozen C22 identity mismatch")
        frame, rules = prepare_candidate(bars, contract)
        ticks = [
            np.load(baseline / "input/continuous-tape" / (key + ".npy"), mmap_mode="r")
            for key in ("time", "bid", "ask")
        ]
        start, end = pd.Timestamp(original["start"]), pd.Timestamp(original["end"])
        count = 0
        for view in VIEWS:
            if view in checkpoint["cells"]:
                continue
            if count >= max_cells:
                break
            cost = view.split("-")[0]
            expected = read(baseline / "cells" / (view + "-" + NAME + ".json"))
            options = Costs(**original["costs"][cost])
            require(expected["rules"] == asdict(rules), "frozen C22 rules mismatch")
            policy = SwapPolicy.from_broker(manifest["broker"])
            observed = replay(
                frame,
                ticks,
                manifest["broker"],
                rules,
                options,
                start=start,
                end=end,
                swap_policy=policy,
                capture_events=True,
                capture_context=True,
            )
            trading = {k: v for k, v in observed.items() if not k.startswith("context_")}
            require(trading == expected, "baseline full-result parity mismatch: " + view)
            rows = annotate(
                frame,
                observed,
                run=output.name,
                scenario=view,
                start=start,
                end=end,
                coverage=coverage,
            )
            summary = report(rows)
            metrics = reconcile(trading, manifest["broker"], observed["context_dd_witnesses"])
            fresh = replay(
                frame,
                ticks,
                manifest["broker"],
                rules,
                options,
                start=start,
                end=end,
                swap_policy=policy,
                capture_events=True,
                capture_context=True,
            )
            require(observed == fresh, "fresh full-result repeat mismatch: " + view)
            repeated = annotate(
                frame,
                fresh,
                run=output.name,
                scenario=view,
                start=start,
                end=end,
                coverage=coverage,
            )
            require(
                rows == repeated and summary == report(repeated), "fresh annotation repeat mismatch"
            )
            artifacts = {
                f"{view}/diagnostics.json": rows,
                f"{view}/coverage.json": summary,
                f"{view}/validation.json": dict(
                    baseline_parity=True,
                    fresh_full_result_match=True,
                    metrics=metrics,
                    drawdown_witnesses=observed["context_dd_witnesses"],
                    baseline_result_sha256=digest(
                        baseline / "cells" / (view + "-" + NAME + ".json")
                    ),
                ),
            }
            checkpoint["pending"] = dict(
                view=view,
                payload=artifacts,
                sha256=hashlib.sha256(
                    json.dumps(artifacts, sort_keys=True, allow_nan=False).encode()
                ).hexdigest(),
            )
            write_checkpoint(checkpoint_path, checkpoint)
            for name, value in artifacts.items():
                atomic_json(output / name, value)
                checkpoint["artifacts"][name] = digest(output / name)
            checkpoint["cells"].append(view)
            checkpoint["pending"] = None
            write_checkpoint(checkpoint_path, checkpoint)
            count += 1
            print(
                view,
                "parity/repeat verified",
                "signals",
                len(rows),
                "trades",
                trading["trades"],
                flush=True,
            )
        if len(checkpoint["cells"]) == len(VIEWS):
            # Recheck all source/input bindings after expensive replay, before completion.
            _, _, final_hashes = verify_baseline(baseline)
            if coverage_path:
                final_hashes[str(Path(coverage_path).resolve())] = digest(coverage_path)
            require(
                final_hashes == hashes and all(digest(REPO / p) == h for p, h in sources.items()),
                "source/input changed during campaign",
            )
            completed = completion(path, coverage)
            atomic_json(complete_path, completed)
            checkpoint["artifacts"]["COMPLETE.json"] = digest(complete_path)
            write_checkpoint(checkpoint_path, checkpoint)
            return completed
        return dict(status="PARTIAL", cells=len(checkpoint["cells"]))
    except Exception:
        # A stale completion marker must never survive failed validation.
        complete_path.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--coverage", type=Path)
    parser.add_argument(
        "--max-cells", type=int, choices=range(1, len(VIEWS) + 1), default=len(VIEWS)
    )
    args = parser.parse_args()
    try:
        result = campaign(
            args.baseline, args.output, coverage_path=args.coverage, max_cells=args.max_cells
        )
    except (
        ValueError,
        OSError,
        KeyError,
        StopIteration,
        TypeError,
        AttributeError,
        IndexError,
        OverflowError,
    ) as error:
        print(json.dumps(dict(status="BLOCKED", reason=str(error))), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
