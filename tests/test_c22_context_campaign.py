"""Real C22 detector/replay CLI fixtures; no broker, no internal mocks."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

from scripts.research.c22_context_campaign import REPO, NAME, VIEWS, digest
from scripts.research.reward156_search import prepare_candidate
from scripts.research.breakout_logic import replay, Costs
from scripts.research.rollover import SwapPolicy
from tests.test_c22h4_strategy import bars


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True))


class CampaignTests(unittest.TestCase):
    def setUp(self):
        (REPO / "runs").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=REPO / "runs", prefix="context-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baseline, self.output = self.root / "baseline", self.root / "output"
        self.baseline.mkdir()
        from scripts.c22h4.strategy import CONTRACT
        from tests.test_breakout_logic import BROKER

        config = json.loads((REPO / "config/c22h4-demo.json").read_text())
        source_hashes = dict(config["source_hashes"])
        for name in (
            "scripts/research/breakout_replay.py",
            "scripts/research/reward156_campaign.py",
        ):
            source_hashes[name] = digest(REPO / name)
        protocol = dict(
            catalog=[dict(CONTRACT, name=NAME)],
            source_hashes=source_hashes,
            costs=dict(
                base=dict(extra_spread=0.0, slippage=0.0, commission_per_lot=0.0),
                stress=dict(extra_spread=0.2, slippage=0.1, commission_per_lot=0.0),
            ),
        )
        original = dict(
            broker=dict(
                BROKER,
                swap_mode=1,
                swap_long=-10.0,
                swap_short=0.0,
                point=0.001,
                swap_rollover3days=3,
            )
        )
        source = bars()
        input_root = self.baseline / "input"
        input_root.mkdir()
        source.to_csv(input_root / "continuous-bars.csv", index_label="bar_open_utc")
        time = np.array([t.value // 10**6 for t in source.index + pd.Timedelta(minutes=15)])
        bid = source.close.to_numpy()
        # Second quote after final signal ensures executable lifecycle close.
        ticks = [
            np.append(time, time[-1] + 10000),
            np.append(bid, bid[-1]),
            np.append(bid + 0.2, bid[-1] + 0.2),
        ]
        tape = input_root / "continuous-tape"
        tape.mkdir()
        for key, array in zip(("time", "bid", "ask"), ticks):
            np.save(tape / (key + ".npy"), array)
        protocol["start"] = source.index[0].isoformat()
        protocol["end"] = (source.index[-1] + pd.Timedelta(minutes=30)).isoformat()
        manifest = dict(
            broker=original["broker"],
            source_hashes={},
            artifacts={
                str(p.relative_to(input_root)): digest(p)
                for p in input_root.rglob("*")
                if p.is_file()
            },
            costs_status="synthetic fixture; not financial evidence",
        )
        write(input_root / "continuous-manifest.json", manifest)
        protocol["input_manifest_sha256"] = digest(input_root / "continuous-manifest.json")
        protocol["behavior_sha256"] = hashlib.sha256(
            json.dumps(protocol, sort_keys=True).encode()
        ).hexdigest()
        write(self.baseline / "protocol.json", protocol)
        for name in source_hashes:
            target = self.baseline / "source_snapshot" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO / name).read_bytes())
        contract = next(c for c in protocol["catalog"] if c["name"] == NAME)
        frame, rules = prepare_candidate(source, contract)
        for view in VIEWS:
            cost, swap = view.split("-")
            result = replay(
                frame,
                ticks,
                original["broker"],
                rules,
                Costs(**protocol["costs"][cost]),
                start=pd.Timestamp(protocol["start"]),
                end=pd.Timestamp(protocol["end"]),
                swap_policy=SwapPolicy.from_broker(original["broker"]) if swap == "swap" else None,
                capture_events=True,
            )
            path = self.baseline / "cells" / (view + "-" + NAME + ".json")
            write(path, result)
            write(
                self.baseline / "integrity" / (view + "-" + NAME + ".json"),
                dict(
                    behavior_sha256=protocol["behavior_sha256"],
                    result_sha256=digest(path),
                    fresh_full_result_match=True,
                ),
            )
        write(
            self.baseline / "results.json",
            dict(input=manifest, protocol_sha256=digest(self.baseline / "protocol.json")),
        )
        write(
            self.baseline / "COMPLETE.json",
            dict(
                protocol_sha256=digest(self.baseline / "protocol.json"),
                results_sha256=digest(self.baseline / "results.json"),
            ),
        )

    def cli(self, *extra):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.research.c22_context_campaign",
                "--baseline",
                str(self.baseline),
                "--output",
                str(self.output),
                *extra,
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
        )

    def test_partial_resume_complete_and_repeat_preserve_original(self):
        before = {str(p): digest(p) for p in self.baseline.rglob("*") if p.is_file()}
        partial = self.cli("--max-cells", "1")
        self.assertEqual(partial.returncode, 0, partial.stderr)
        self.assertIn("PARTIAL", partial.stdout)
        self.assertFalse((self.output / "COMPLETE.json").exists())
        complete = self.cli()
        self.assertEqual(complete.returncode, 0, complete.stderr)
        self.assertIn("INCONCLUSIVE_FOR_FILTER_SELECTION", complete.stdout)
        substantive = {str(p): digest(p) for p in self.output.rglob("*") if p.is_file()}
        repeat = self.cli()
        self.assertEqual(repeat.returncode, 0, repeat.stderr)
        self.assertEqual(
            substantive, {str(p): digest(p) for p in self.output.rglob("*") if p.is_file()}
        )
        self.assertEqual(
            before, {str(p): digest(p) for p in self.baseline.rglob("*") if p.is_file()}
        )
        self.assertEqual(
            subprocess.run(
                ["git", "check-ignore", str(self.output)], cwd=REPO, capture_output=True
            ).returncode,
            0,
        )

    def test_each_digest_mismatch_blocks_and_removes_completion(self):
        complete = self.cli()
        self.assertEqual(complete.returncode, 0, complete.stderr)
        originals = {p: p.read_bytes() for p in self.output.rglob("*") if p.is_file()}
        cases = [
            self.baseline / "input/continuous-bars.csv",
            self.baseline / "source_snapshot/scripts/research/reward156_search.py",
            self.output / "protocol.json",
            self.output / "checkpoint.json",
            self.output / "base-no_swap/diagnostics.json",
            self.output / "base-no_swap/coverage.json",
            self.output / "base-no_swap/validation.json",
            self.output / "COMPLETE.json",
        ]
        for path in cases:
            with self.subTest(path=path):
                content = path.read_bytes()
                path.write_bytes(content + b" ")
                # Whitespace changes JSON semantics unchanged; digest must still bind artifacts.
                result = self.cli()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("BLOCKED", result.stderr)
                self.assertFalse((self.output / "COMPLETE.json").exists())
                path.write_bytes(content)
                for p, data in originals.items():
                    p.write_bytes(data)

    def test_missing_input_does_not_create_success_marker(self):
        (self.baseline / "input/continuous-tape/time.npy").unlink()
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stderr)
        self.assertFalse((self.output / "COMPLETE.json").exists())

    def test_process_interruption_during_artifact_publication_resumes(self):
        # Inject failure only at filesystem publication boundary. Real detector,
        # replay, annotation and journal construction execute untouched.
        code = """
import os
from pathlib import Path
import scripts.research.c22_context_campaign as campaign
writer = campaign.atomic_json
def interrupt(path, value):
    writer(path, value)
    if path.name == 'diagnostics.json':
        os._exit(137)
campaign.atomic_json = interrupt
campaign.campaign(Path(__import__('sys').argv[1]), Path(__import__('sys').argv[2]))
"""
        interrupted = subprocess.run(
            [sys.executable, "-c", code, str(self.baseline), str(self.output)],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        self.assertEqual(interrupted.returncode, 137, interrupted.stderr)
        self.assertFalse((self.output / "COMPLETE.json").exists())
        self.assertIsNotNone(json.loads((self.output / "checkpoint.json").read_text())["pending"])
        resumed = self.cli()
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertIn("COMPLETE", resumed.stdout)
        self.assertIsNone(json.loads((self.output / "checkpoint.json").read_text())["pending"])

    def test_invalid_checkpoint_type_blocks_and_invalidates_completion(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.output / "checkpoint.json").write_text("null\n")
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"status": "BLOCKED"', result.stderr)
        self.assertFalse((self.output / "COMPLETE.json").exists())

    def test_second_writer_rejected_without_mutating_active_campaign(self):
        import time

        gate, release = self.root / "paused", self.root / "release"
        code = """
import sys,time
from pathlib import Path
import scripts.research.c22_context_campaign as c
baseline,output,gate,release=map(Path,sys.argv[1:])
original=c.atomic_json
paused=False
def writer(path,value):
    global paused
    original(path,value)
    if path.name=='checkpoint.json' and value.get('pending') and not paused:
        paused=True
        gate.write_text('paused')
        while not release.exists(): time.sleep(.01)
c.atomic_json=writer
print(c.campaign(baseline,output,max_cells=1))
"""
        first = subprocess.Popen(
            [
                sys.executable,
                "-c",
                code,
                str(self.baseline),
                str(self.output),
                str(gate),
                str(release),
            ],
            cwd=REPO,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 20
            while not gate.exists() and first.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(gate.exists(), "writer did not reach publication boundary")
            before = {str(p): digest(p) for p in self.output.rglob("*") if p.is_file()}
            second = self.cli()
            after = {str(p): digest(p) for p in self.output.rglob("*") if p.is_file()}
            self.assertNotEqual(second.returncode, 0, second.stdout)
            self.assertIn("campaign already running", second.stderr)
            self.assertEqual(before, after, "rejected writer mutated active evidence")
            release.write_text("resume")
            stdout, stderr = first.communicate(timeout=20)
            self.assertEqual(first.returncode, 0, stderr)
            resumed = self.cli()
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertIn('"status": "COMPLETE"', resumed.stdout)
        finally:
            if first.poll() is None:
                first.kill()
            first.communicate(timeout=10)

    def test_malformed_persisted_types_all_block_and_invalidate_completion(self):
        import copy
        from scripts.research.c22_context_campaign import write_checkpoint

        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = {p: p.read_bytes() for p in self.output.rglob("*") if p.is_file()}
        valid = json.loads((self.output / "checkpoint.json").read_text())
        cases = [("null", None), ("list", []), ("string", "checkpoint")]
        for field, value in (("cells", None), ("artifacts", []), ("pending", [])):
            changed = copy.deepcopy(valid)
            changed[field] = value
            cases.append((field, changed))
        for name, value in cases:
            with self.subTest(name=name):
                for path, content in saved.items():
                    path.write_bytes(content)
                if isinstance(value, dict):
                    write_checkpoint(self.output / "checkpoint.json", value)
                else:
                    (self.output / "checkpoint.json").write_text(json.dumps(value))
                result = self.cli()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('"status": "BLOCKED"', result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse((self.output / "COMPLETE.json").exists())

    def test_lock_released_on_process_death_and_contender_keeps_completion(self):
        import time

        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        gate = self.root / "lock-held"
        code = """
import sys,time
from pathlib import Path
import scripts.research.c22_context_campaign as c
baseline,output,gate=map(Path,sys.argv[1:])
original=c.verify_baseline
def pause(root):
    gate.write_text('owner holds lock')
    while True: time.sleep(.01)
c.verify_baseline=pause
c.campaign(baseline,output)
"""
        first = subprocess.Popen(
            [sys.executable, "-c", code, str(self.baseline), str(self.output), str(gate)],
            cwd=REPO,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 20
            while not gate.exists() and first.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(gate.exists())
            before = {str(p): digest(p) for p in self.output.rglob("*") if p.is_file()}
            second = self.cli()
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("campaign already running", second.stderr)
            self.assertTrue((self.output / "COMPLETE.json").exists())
            self.assertEqual(
                before, {str(p): digest(p) for p in self.output.rglob("*") if p.is_file()}
            )
            first.kill()
            first.communicate(timeout=10)
            resumed = self.cli()
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertIn('"status": "COMPLETE"', resumed.stdout)
        finally:
            if first.poll() is None:
                first.kill()
            first.communicate(timeout=10)
