"""Open historical holdout only after a hash-bound discovery selection lock."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.breakout_logic import Costs, replay
from scripts.research.public_exness_archive import import_month
from scripts.research.reward156_search import cell_gates, prepare_candidate
from scripts.research.reward156_tuning import atomic_json, summary
from scripts.research.rollover import SwapPolicy
from scripts.research.tune_breakout_logic import sha256


def verify_lock(output, winner):
    lock = json.loads((output / "selection-lock.json").read_text())
    contract = json.loads((output / "contract.json").read_text())
    if (
        lock["candidate"] != winner
        or lock["behavior_sha256"] != contract["behavior_sha256"]
        or lock["discovery_results_sha256"] != sha256(output / "discovery-results.json")
    ):
        raise ValueError("holdout selection lock mismatch")
    return lock


def load_holdout(campaign, winner):
    verify_lock(campaign.output, winner)  # before reading any held-out prices
    source = Path(campaign.config["datasets"]["A"]["path"])
    manifest = json.loads((source / "dataset.json").read_text())
    start = pd.Timestamp(manifest["holdout_start"], tz="UTC")
    end = pd.Timestamp(manifest["holdout_end"], tz="UTC")
    if (start, end) != (pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2025-10-01", tz="UTC")):
        raise ValueError("holdout bounds drift")
    root = campaign.output / "holdout-input"
    (root / "discovery").mkdir(parents=True, exist_ok=True)
    items = [i for i in manifest["archives"] if "2025-07" <= i["month"] < "2025-10"]
    if [i["month"] for i in items] != ["2025-07", "2025-08", "2025-09"]:
        raise ValueError("incomplete holdout archive coverage")
    frames, audits = [], []
    for item in items:
        if sha256(source / item["file"]) != item["sha256"]:
            raise ValueError("sealed archive hash changed")
        link = root / item["file"]
        if not link.exists():
            link.symlink_to((source / item["file"]).resolve())
        audit, frame = import_month(root, item)
        audits.append(audit)
        frames.append(frame)
    total = sum(a["ticks"] for a in audits)
    tape = root / "tape"
    tape.mkdir(exist_ok=True)
    for k, dtype in [("time", "int64"), ("bid", "float64"), ("ask", "float64")]:
        target = np.lib.format.open_memmap(
            tape / (k + ".npy"), mode="w+", dtype=dtype, shape=(total,)
        )
        offset = 0
        for item in items:
            with np.load(root / "discovery" / (item["month"] + ".npz")) as month:
                target[offset : offset + len(month[k])] = month[k]
                offset += len(month[k])
        target.flush()
        del target
    held = pd.concat(frames)
    prefix, _, broker = campaign.datasets["A"]
    raw = pd.concat(
        [prefix[["open", "high", "low", "close"]], held[["open", "high", "low", "close"]]]
    )
    if raw.index.has_duplicates or not raw.index.is_monotonic_increasing:
        raise ValueError("holdout chronology overlap")
    atomic_json(
        campaign.output / "holdout-input.json",
        dict(
            archives=audits,
            artifacts={k: sha256(tape / (k + ".npy")) for k in ("time", "bid", "ask")},
            start_utc=start.isoformat(),
            end_exclusive_utc=end.isoformat(),
            indicator_prefix="Dataset A discovery; account starts fresh USD200",
        ),
    )
    ticks = [np.load(tape / (k + ".npy"), mmap_mode="r") for k in ("time", "bid", "ask")]
    return raw, ticks, broker, start, end


def run_holdout(campaign, winner):
    from scripts.research.reward156_campaign import CONTROLS

    raw, ticks, broker, start, end = load_holdout(campaign, winner)
    rows = []
    for c in [*CONTROLS, winner]:
        frame, rules = prepare_candidate(raw, c)
        for cost, options in campaign.config["costs"].items():
            for view in ("no_swap", "swap"):
                key = "-".join(("holdout", cost, view, c["name"]))
                result = campaign.checkpoints.execute(
                    key,
                    lambda: replay(
                        frame,
                        ticks,
                        broker,
                        rules,
                        Costs(**options),
                        start=start,
                        end=end,
                        swap_policy=SwapPolicy.from_broker(broker) if view == "swap" else None,
                        capture_events=True,
                    ),
                    repeat=True,
                )
                metrics = summary(result, frame, start, end)
                metrics["bankrupt"] = any(
                    t["reason"] == "BANKRUPT" for t in result["ledger"]
                ) or any(p["equity_usd"] <= 0 for p in result["equity"])
                row = dict(contract=c["name"], cost=cost, cost_view=view, metrics=metrics)
                if c == winner:
                    peers = [
                        r["metrics"] for r in rows if r["cost"] == cost and r["cost_view"] == view
                    ]
                    if len(peers) != 2:
                        raise ValueError("holdout paired controls missing")
                    row["gates"] = cell_gates(metrics, peers, "holdout", holdout=True)
                rows.append(row)
    passed = all(all(r["gates"].values()) for r in rows if r["contract"] == winner["name"])
    status = "PASSED_HISTORICAL_HOLDOUT_RESEARCH_ONLY" if passed else "FAILED_HOLDOUT_NO_RETUNING"
    atomic_json(campaign.output / "holdout-results.json", dict(rows=rows, status=status))
    return status
