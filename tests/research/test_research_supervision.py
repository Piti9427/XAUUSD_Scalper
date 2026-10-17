"""Public bounded subprocess lifecycle, with real isolated Python children."""

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from scripts.research.supervision import Job, supervise, wait_for_snapshots


class SupervisionTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_reaps_child_and_cancels_sibling(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            jobs = [
                Job(
                    (
                        sys.executable,
                        "-c",
                        "import os,time; print(os.getpid(), flush=True); time.sleep(30)",
                    ),
                    root / f"{n}.log",
                )
                for n in range(2)
            ]
            with self.assertRaises(asyncio.TimeoutError):
                await supervise(jobs, workers=2, timeout=0.2)
            for path in (root / "0.log", root / "1.log"):
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(path.read_text()), 0)
            self.assertFalse(
                [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
            )

    async def test_worker_bound_and_result_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            code = "import time,json; start=time.monotonic(); time.sleep(.05); print(json.dumps([start,time.monotonic()]))"
            jobs = [Job((sys.executable, "-c", code), root / f"{n}.log") for n in range(5)]
            self.assertEqual(await supervise(jobs), [0] * 5)
            intervals = [json.loads(job.log.read_text()) for job in jobs]
            for start, _ in intervals:
                self.assertLessEqual(sum(a <= start < b for a, b in intervals), 2)

    async def test_failure_reaps_running_sibling_and_does_not_start_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pid_file = root / "pid"
            sleeper = f"import os,time,pathlib; pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)"
            failure = f"import pathlib,time; p=pathlib.Path({str(pid_file)!r});\nwhile not p.exists(): time.sleep(.01)\nraise SystemExit(7)"
            jobs = [
                Job((sys.executable, "-c", c), root / f"{n}.log")
                for n, c in enumerate((sleeper, failure, "print('queued')"))
            ]
            with self.assertRaisesRegex(RuntimeError, "child exit 7"):
                await supervise(jobs)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid_file.read_text()), 0)
            self.assertFalse(jobs[2].log.exists())

    async def test_external_cancellation_reaps_child(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pid_file = root / "pid"
            code = f"import os,time,pathlib; pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)"
            task = asyncio.create_task(supervise([Job((sys.executable, "-c", code), root / "log")]))

            async def ready():
                while not pid_file.exists():
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(ready(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid_file.read_text()), 0)

    @unittest.skipUnless(os.name == "posix", "requires POSIX signals")
    async def test_repeated_cancel_kills_and_reaps_child_ignoring_terminate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pid_file = root / "pid"
            code = f"import os,time,pathlib,signal; signal.signal(signal.SIGTERM,signal.SIG_IGN); pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)"
            task = asyncio.create_task(supervise([Job((sys.executable, "-c", code), root / "log")]))

            async def ready():
                while not pid_file.exists():
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(ready(), 2)
            task.cancel()
            await asyncio.sleep(0.05)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 7)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid_file.read_text()), 0)

    async def test_snapshot_readiness_waits_for_complete_matching_bytes(self):
        import hashlib

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            content = b"frozen implementation"
            (root / "protocol.json").write_text(
                json.dumps({"source_hashes": {"engine.py": hashlib.sha256(content).hexdigest()}})
            )
            task = asyncio.create_task(wait_for_snapshots(root, 2))
            self.addAsyncCleanup(self.cancel_task, task)
            await asyncio.sleep(0.02)
            self.assertFalse(task.done())
            source = root / "source_snapshot/engine.py"
            source.parent.mkdir()
            source.write_bytes(content[:4])
            await asyncio.sleep(0.15)
            self.assertFalse(task.done())
            source.write_bytes(content)
            await task

    @staticmethod
    async def cancel_task(task):
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
