"""Existing Oracle VM only: refresh read-only evidence, restore shadow, report gaps.

Run manually while flat. No execution mode, policy attestation or order sends.
Keep beside c22h4_readiness.py and broker_probe.py, outside the frozen release.
"""

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import fcntl
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time


def journal_values(path):
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        values = {k: json.loads(v) for k, v in conn.execute("SELECT key,value FROM kv")}
        return values, conn.execute("SELECT count(*) FROM events WHERE sent=0").fetchone()[0]
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", type=datetime.fromisoformat, required=True)
    parser.add_argument("--feed-review", type=Path)
    parser.add_argument(
        "--cost-policy",
        type=Path,
        default=Path("/home/ubuntu/c22-demo/state/cost-policy-runtime.json"),
    )
    args = parser.parse_args(argv)
    if (
        args.since.tzinfo is None
        or args.since.utcoffset() != timedelta(0)
        or args.since >= datetime.now(timezone.utc)
    ):
        parser.error("--since must be a past aware UTC qualification start")
    h = Path.home()
    if h != Path("/home/ubuntu"):
        parser.error("run as ubuntu on the prepared Oracle VM")
    current = h / "c22-demo/current"
    prepared = h / "c22-demo/preparation"
    guard = (prepared / "prepare-market-open.lock").open("a")
    try:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("another preparation probe owns this terminal workflow")
    evidence = h / "c22-oracle-compat-evidence/market-open-preparation"
    run = evidence / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run.mkdir(parents=True, mode=0o700)
    journal = h / "c22-demo/state/c22h4-shadow.sqlite3"
    result = dict(
        captured_utc=datetime.now(timezone.utc).isoformat(),
        execution_authorized=False,
        order_send_called=False,
        shadow_restored=False,
    )
    stopped = False
    env = os.environ.copy()
    try:
        subprocess.run(
            ["sha256sum", "--check", "--status", "release.sha256"], cwd=current, check=True
        )
        for line in (h / "c22-private/c22-backup.env").read_text().splitlines():
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                env[key] = json.loads(value)
        if env.get("WINEPREFIX") != str(h / "c22-qemu-demo._g86ow9b"):
            raise ValueError("unexpected dedicated Wine prefix")
        env["MT5_ENABLE_DEMO_ORDER_SEND"] = "0"
        values, pending = journal_values(journal)
        last = values.get("last_result", {})
        age = (
            datetime.now(timezone.utc) - datetime.fromisoformat(last["captured_utc"])
        ).total_seconds()
        if not (
            0 <= age < 15
            and last.get("execute") is False
            and last.get("observed_positions") == 0
            and last.get("position_protection") == "flat"
            and not values.get("active")
            and not values.get("safety_halt")
            and not pending
        ):
            raise ValueError("fresh flat shadow and reconciled journal required")
        (run / "before.json").write_text(
            json.dumps(dict(last_result=last, pending_outbox=pending), indent=2) + "\n"
        )
        old = evidence / "broker-evidence.json"
        if old.exists():
            shutil.copy2(old, run / "prior-broker-evidence.json")
            old.unlink()  # Derived latest pointer only; archived before removal.
        stopped = True
        subprocess.run(["sudo", "-n", "systemctl", "stop", "c22-demo-shadow.service"], check=True)
        try:
            with (run / "broker-probe.log").open("w") as log:
                probe = subprocess.run(
                    [
                        "xvfb-run",
                        "-a",
                        env["DEMO_WINE_BIN"],
                        env["DEMO_WINDOWS_PYTHON"],
                        "-u",
                        "Z:" + str(prepared / "broker_probe.py").replace("/", "\\"),
                    ],
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=210,  # 90s initialize + 60s history synchronization + overhead
                )
                result["probe_exit"] = probe.returncode
        finally:
            subprocess.run(
                [str(h / "c22-qemu-control/wine-11.0-source/bin/wineserver"), "-k"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            subprocess.run(
                ["sudo", "-n", "systemctl", "start", "c22-demo-shadow.service"], check=True
            )
            stopped = False
            result["shadow_restored"] = True
            restored_at = datetime.now(timezone.utc)
        if result["probe_exit"] or not old.is_file():
            raise ValueError("read-only broker probe failed; old evidence not reused")
        shutil.copy2(old, run / "broker-evidence.json")
        old.chmod(0o600)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            values, _ = journal_values(journal)
            last = values.get("last_result", {})
            if last.get("captured_utc"):
                age = (
                    datetime.now(timezone.utc) - datetime.fromisoformat(last["captured_utc"])
                ).total_seconds()
                if (
                    0 <= age < 5
                    and datetime.fromisoformat(last["captured_utc"]) >= restored_at
                    and last.get("execute") is False
                    and last.get("observed_positions") == 0
                    and last.get("position_protection") == "flat"
                ):
                    break
            time.sleep(2)
        else:
            raise ValueError("shadow did not recover fresh flat observation")
        subprocess.run(
            ["sudo", "-n", "systemctl", "start", "c22-demo-backup.service"], check=True, timeout=120
        )
        meta_path = sorted((h / "c22-demo/backups").glob("demo-*.json"))[-1]
        meta = json.loads(meta_path.read_text())
        backup = meta_path.with_suffix(".sqlite3")
        if not meta.get("restore_verified") or hashlib.sha256(
            backup.read_bytes()
        ).hexdigest() != meta.get("sha256"):
            raise ValueError("backup checksum/restore metadata invalid")
        snapshot = run / "financial-snapshot.sqlite3"
        shutil.copy2(backup, snapshot)
        snapshot.chmod(0o600)
        shutil.copy2(meta_path, run / "backup.json")
        native_env = os.environ.copy()
        native_env["PYTHONPATH"] = str(current)
        checker = subprocess.run(
            [
                "python3",
                str(prepared / "c22h4_readiness.py"),
                "--journal",
                str(snapshot),
                "--broker",
                str(run / "broker-evidence.json"),
                "--parity",
                str(prepared / "broker-parity.json"),
                "--cost-policy",
                str(args.cost_policy),
                "--since",
                args.since.isoformat(),
                "--out",
                str(run / "readiness.json"),
                *(["--feed-review", str(args.feed_review)] if args.feed_review else []),
            ],
            env=native_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        result["readiness_exit"] = checker.returncode
        (run / "readiness-command.log").write_text(checker.stdout + checker.stderr)
        if checker.returncode not in (0, 2) or not (run / "readiness.json").exists():
            raise ValueError("readiness report failed")
        report = json.loads((run / "readiness.json").read_text())
        result.update(
            status=report["status"],
            blockers=report["blockers"],
            backup_sha256=meta["sha256"],
            run=str(run),
        )
        latest = evidence / "latest-readiness.json"
        temp = latest.with_suffix(".json.tmp")
        temp.write_text(json.dumps(report, indent=2) + "\n")
        temp.replace(latest)
    except Exception as exc:
        result.update(status="PREPARATION_FAILED", reason=type(exc).__name__)
        if isinstance(exc, ValueError):
            result["detail"] = str(exc)
    finally:
        if stopped:
            result["shadow_restored"] = (
                subprocess.run(
                    ["sudo", "-n", "systemctl", "start", "c22-demo-shadow.service"]
                ).returncode
                == 0
            )
        (run / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
    return 2 if result.get("status") != "AWAITING_OPERATOR_REVIEW" else 0


if __name__ == "__main__":
    raise SystemExit(main())
