"""Bounded offline research subprocesses; CPU replay never runs on event loop."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
import math
from pathlib import Path

from scripts.research.tune_breakout_logic import sha256


@dataclass(frozen=True)
class Job:
    command: tuple[str, ...]
    log: Path
    cwd: Path | None = None
    snapshot_root: Path | None = None


def snapshots_ready(root: Path) -> bool:
    """Protocol alone is insufficient; every frozen source must hash correctly."""
    try:
        protocol = json.loads((root / "protocol.json").read_text())
        sources = protocol["source_hashes"]
        return bool(sources) and all(
            sha256(root / "source_snapshot" / source) == digest
            for source, digest in sources.items()
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return False


async def wait_for_snapshots(root: Path, timeout: float = 120) -> None:
    async def wait_ready() -> None:
        while not await asyncio.to_thread(snapshots_ready, root):
            await asyncio.sleep(0.1)

    await asyncio.wait_for(wait_ready(), timeout)


async def _reap(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), 5)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
    await process.wait()


async def _finish(task: asyncio.Task) -> bool:
    # Repeated cancellation must not interrupt spawn settlement or child reaping.
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
            continue
    task.result()
    return cancelled


async def run_child(job: Job, timeout: float = 7200) -> int:
    """Propagate child failure/timeout/cancellation only after child is reaped."""
    job.log.parent.mkdir(parents=True, exist_ok=True)
    with job.log.open("w") as output:
        spawn = asyncio.create_task(
            asyncio.create_subprocess_exec(
                *job.command,
                stdout=output,
                stderr=asyncio.subprocess.STDOUT,
                cwd=job.cwd,
            )
        )
        process = None
        try:
            process = await asyncio.shield(spawn)
            code = await asyncio.wait_for(process.wait(), timeout)
            if code:
                raise RuntimeError(f"child exit {code}: {job.log}")
            return code
        finally:
            cancelled = False
            if process is None:
                cancelled = await _finish(spawn)
                process = spawn.result()
            cancelled = await _finish(asyncio.create_task(_reap(process))) or cancelled
            if cancelled:
                raise asyncio.CancelledError


async def supervise(
    jobs: list[Job],
    *,
    workers: int = 2,
    timeout: float = 7200,
    snapshot_timeout: float = 120,
) -> list[int]:
    """Preserve input result order; first failure cancels and reaps all siblings."""
    if workers < 1 or any(not math.isfinite(v) or v <= 0 for v in (timeout, snapshot_timeout)):
        raise ValueError("positive workers and finite positive timeouts required")
    if any(not job.command for job in jobs) or len({job.log.resolve() for job in jobs}) != len(
        jobs
    ):
        raise ValueError("nonempty commands and unique logs required")
    pending = iter(enumerate(jobs))
    results = [0] * len(jobs)

    async def worker() -> None:
        for index, job in pending:
            if job.snapshot_root is not None:
                await wait_for_snapshots(job.snapshot_root, snapshot_timeout)
            results[index] = await run_child(job, timeout)

    tasks = [asyncio.create_task(worker()) for _ in range(min(workers, len(jobs)))]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if await _finish(asyncio.create_task(_settle(tasks))):
            raise asyncio.CancelledError
    return results


async def _settle(tasks: list[asyncio.Task]) -> None:
    await asyncio.gather(*tasks, return_exceptions=True)


def main(argv: list[str] | None = None) -> list[int]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jobs",
        required=True,
        type=Path,
        help="JSON list: command, log, optional cwd/snapshot_root",
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=7200)
    parser.add_argument("--snapshot-timeout", type=float, default=120)
    args = parser.parse_args(argv)
    records = json.loads(args.jobs.read_text())
    jobs = [
        Job(
            tuple(r["command"]),
            Path(r["log"]),
            Path(r["cwd"]) if r.get("cwd") else None,
            Path(r["snapshot_root"]) if r.get("snapshot_root") else None,
        )
        for r in records
    ]
    codes = asyncio.run(
        supervise(
            jobs, workers=args.workers, timeout=args.timeout, snapshot_timeout=args.snapshot_timeout
        )
    )
    print(json.dumps({"child_exit_codes": codes, "workers": args.workers}))
    return codes


if __name__ == "__main__":
    main()
