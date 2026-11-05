"""Public offline detector and persisted entry-geometry parity seam."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
import pandas as pd

from scripts.c22_selected.parity import run_parity
from scripts.c22_selected.strategy import CANDIDATE_ID, ROOT
from tests.demo.test_c22_selected_strategy import EXPECTED_RULES, signal_bars


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def campaign_fixture(directory, *, wrong_stop=False):
    source = signal_bars(-1)
    bars = directory / "input/bars.csv"
    bars.parent.mkdir(parents=True)
    source.rename_axis("bar_open_utc").to_csv(bars)
    closed = source.index[-1] + pd.Timedelta(minutes=15)
    stamp = int(closed.timestamp() * 1000) + 288
    tape = bars.parent / "tape"
    tape.mkdir()
    for name, values in (
        ("time", np.array([stamp], dtype="int64")),
        ("bid", np.array([100.2])),
        ("ask", np.array([100.4])),
    ):
        np.save(tape / (name + ".npy"), values)
    out = directory / "campaign"
    views = {
        "base": {"extra_spread": 0.0, "slippage": 0.0, "commission_per_lot": 0.0},
        "stress": {"extra_spread": 0.2, "slippage": 0.1, "commission_per_lot": 0.0},
        "fee": {"extra_spread": 0.2, "slippage": 0.1, "commission_per_lot": 7},
    }
    protocol = {
        "broker": {
            "trade_tick_size": 0.001,
            "trade_contract_size": 100.0,
            "volume_min": 0.01,
            "volume_max": 200.0,
            "volume_step": 0.01,
            "leverage": 1000,
        },
        "views": views,
        "sources": {},
        "input_hashes": {"bars.csv": sha(bars)}
        | {f"tape/{name}.npy": sha(tape / (name + ".npy")) for name in ("time", "bid", "ask")},
    }
    write_json(out / "protocol.json", protocol)
    artifacts = {"protocol.json": sha(out / "protocol.json")}
    audited = {}
    payload_hashes = {}
    expected = {
        "base": (100.2, 103.149, 96.219, 2.949),
        "stress": (100.0, 102.949, 96.019, 3.049),
        "fee": (100.0, 102.949, 96.019, 3.119),
    }
    for guard in ("raw", "cent"):
        for view, cost in views.items():
            entry, stop, target, risk = expected[view]
            if wrong_stop and guard == "cent" and view == "fee":
                stop += 0.001
            entry_time = pd.Timestamp(stamp, unit="ms", tz="UTC").isoformat()
            ledger = {
                "direction": -1,
                "entry": entry,
                "initial_stop": stop,
                "target": target,
                "entry_ms": stamp,
                "entry_time_utc": entry_time,
                "entry_equity": 200.0,
                "risk_usd": risk,
                "volume": 0.01,
            }
            cell = {
                "case": {"name": CANDIDATE_ID, "rules": EXPECTED_RULES},
                "view": view,
                "guard": guard,
                "result": {
                    "rules": EXPECTED_RULES,
                    "costs": cost,
                    "ledger": [ledger],
                    "context_events": [
                        {
                            "direction": -1,
                            "reason": "admitted",
                            "time_utc": entry_time,
                            "signal_close_utc": closed.isoformat(),
                        }
                    ],
                },
            }
            key = f"{CANDIDATE_ID}-{view}-{guard}"
            payload = out / "cells" / (key + ".json")
            write_json(payload, cell)
            proof = out / "cells-integrity" / (key + ".json")
            write_json(
                proof,
                {"path": str(payload.relative_to(ROOT)), "sha256": sha(payload), "origin": "new"},
            )
            artifacts[str(payload.relative_to(out))] = sha(payload)
            artifacts[str(proof.relative_to(out))] = sha(proof)
            audited[str(proof.relative_to(ROOT))] = sha(proof)
            payload_hashes[str(payload.relative_to(ROOT))] = sha(payload)
    write_json(
        out / "COMPLETE.json",
        {
            "status": "EXHAUSTIVE_COMPLETE",
            "selected": {"profit": CANDIDATE_ID, "repair": CANDIDATE_ID},
            "artifacts": artifacts,
        },
    )
    write_json(
        out / "independent-verification.json",
        {
            "status": "PASS",
            "selected": {"profit": CANDIDATE_ID, "repair": CANDIDATE_ID},
            "parent_completion_sha256": sha(out / "COMPLETE.json"),
            "audited_cells": audited,
            "payload_hashes": payload_hashes,
        },
    )
    return bars, out


class SelectedParityTests(unittest.TestCase):
    def test_matching_six_paths_is_price_agreement_without_broker_qualification(self):
        with TemporaryDirectory(dir=ROOT / "runs") as folder:
            bars, campaign = campaign_fixture(Path(folder))
            report = run_parity(bars, campaign)
            self.assertEqual(report["status"], "PRICE_DETECTOR_PARITY_PASS")
            self.assertEqual(report["coverage"]["geometry_entries_compared"], 6)
            self.assertEqual(report["coverage"]["cost_guard_paths"], 6)
            self.assertFalse(report["execution_authorized"])
            self.assertFalse(report["data"]["broker_fill_parity"])
            self.assertFalse(report["data"]["economic_replay_performed"])
            self.assertEqual(
                report["data"]["lifecycle_context_scope"], "NOT_TESTED_BY_PRICE_PARITY"
            )

    def test_cent_geometry_difference_is_not_substituted_from_raw(self):
        with TemporaryDirectory(dir=ROOT / "runs") as folder:
            bars, campaign = campaign_fixture(Path(folder), wrong_stop=True)
            report = run_parity(bars, campaign)
            self.assertEqual(report["status"], "PARITY_FAIL")
            self.assertTrue(
                any(
                    issue.get("field") == "initial_stop" and issue.get("guard") == "cent"
                    for issue in report["data"]["mismatches"]
                )
            )
