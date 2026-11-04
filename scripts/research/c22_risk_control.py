"""Local offline campaign launcher/status; no scheduling, broker or deployment."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from scripts.research.c22_risk_campaign import DEFAULT_OUT, ROOT, _safe_out
from scripts.research.c22_performance_campaign import read, write


def status(out):
    out = _safe_out(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "campaign.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = False
        except BlockingIOError:
            locked = True
    launch = read(out / "launch.json") if (out / "launch.json").exists() else None
    alive = False
    if launch:
        try:
            os.kill(launch["pid"], 0)
            command = subprocess.check_output(["ps", "-p", str(launch["pid"]), "-o", "command="], text=True)
            alive = "scripts.research.c22_risk_campaign" in command
        except (ProcessLookupError, subprocess.CalledProcessError):
            pass
    checkpoint = read(out / "checkpoint.json") if (out / "checkpoint.json").exists() else {}
    log = out / "execution.log"
    return dict(captured_utc=datetime.now(timezone.utc).isoformat(), running=alive,
        exclusive_lock_held=locked, disk_free_bytes=shutil.disk_usage(out).free,
        evaluated_paths=checkpoint.get("evaluated_paths", 0), expected_paths=72,
        completed_profiles=checkpoint.get("completed_profiles", 0),
        complete=(out / "COMPLETE.json").exists(), audited=(out / "independent-verification.json").exists(),
        launch=launch, recent_log=log.read_text(errors="replace")[-1800:] if log.exists() else "")


def start(out, workers):
    out = _safe_out(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "launch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = status(out)
        if current["running"] or current["exclusive_lock_held"] or current["complete"]:
            return current
        assert current["disk_free_bytes"] > 2 * 1024**3, "Insufficient disk"
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT)
        with (out / "execution.log").open("ab") as log:
            process = subprocess.Popen([sys.executable, "-u", "-m", "scripts.research.c22_risk_campaign",
                "--out", str(out), "--workers", str(workers)], cwd=ROOT, env=environment,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        write(out / "launch.json", dict(pid=process.pid, workers=workers,
            started_utc=datetime.now(timezone.utc).isoformat(), offline_only=True))
        return status(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "start"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    print(json.dumps(status(args.out) if args.action == "status" else start(args.out, args.workers), indent=2))


if __name__ == "__main__":
    main()
