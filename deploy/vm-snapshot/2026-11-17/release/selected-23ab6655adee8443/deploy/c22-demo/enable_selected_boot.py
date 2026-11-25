"""Register reviewed selected services for boot without starting or stopping any."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess


UNITS = ("c22-selected-terminal.service", "c22-selected-execution.service")
OLD_BOOT_UNITS = ("c22-selected-shadow.service", "c22-demo-shadow.service", "c22-demo-execution.service")
SNAPSHOT = "RESEARCH-C22-SELECTED-20261025-26B8"


def boot_plan(release: Path, journal: Path, review_path: Path, *, fingerprint: str,
              unit_directory: Path, now: datetime, run=subprocess.run) -> dict:
    """Require the reviewed, fresh flat manager and exact installed unit bytes."""
    release = release.resolve()
    manifest = json.loads((release / "release-manifest.json").read_text())
    if manifest.get("remote_release") != str(release):
        raise ValueError("release_location_mismatch")
    for name, expected in manifest["files"].items():
        target = (release / name).resolve()
        if not target.is_relative_to(release) or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError("release_integrity_required")
    for name in UNITS:
        expected = manifest["files"][name]
        if hashlib.sha256((unit_directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError("installed_selected_unit_mismatch")
    review_bytes = review_path.read_bytes()
    review = json.loads(review_bytes)
    if (review.get("scope") != "SELECTED_DEMO_ARMED_TRIAL" or review.get("owner_authorized") is not True
            or review["readiness"].get("account_fingerprint") != fingerprint
            or review["readiness"].get("snapshot") != SNAPSHOT):
        raise ValueError("reviewed_selected_demo_required")
    status = run(["systemctl", "show", "c22-selected-execution.service", "--property=ActiveState,WorkingDirectory"],
                 check=True, capture_output=True, text=True)
    values = dict(line.split("=", 1) for line in status.stdout.splitlines() if "=" in line)
    if values.get("ActiveState") != "active" or values.get("WorkingDirectory") != str(release):
        raise ValueError("reviewed_manager_not_running")
    connection = sqlite3.connect(journal.as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("BEGIN")
        state = {key: json.loads(value) for key, value in connection.execute("SELECT key,value FROM kv")}
        latest = state.get("last_result", {})
        stamp = datetime.fromisoformat(latest["captured_utc"])
        if (stamp.tzinfo is None or stamp.utcoffset() != timedelta(0)
                or not timedelta(0) <= now - stamp <= timedelta(seconds=15)
                or state.get("identity") != fingerprint
                or state.get("selected_execution_review_sha256") != hashlib.sha256(review_bytes).hexdigest()
                or state.get("active") is not None
                or state.get("safety_halt") or latest.get("execute") is not True
                or latest.get("snapshot") != SNAPSHOT or latest.get("observed_positions") != 0
                or latest.get("position_protection") != "flat"):
            raise ValueError("fresh_flat_reviewed_manager_required")
    finally:
        connection.close()
    old_loaded = []
    for name in OLD_BOOT_UNITS:
        observed = run(["systemctl", "show", name, "--property=LoadState", "--value"],
                       check=True, capture_output=True, text=True)
        if observed.stdout.strip() != "not-found":
            old_loaded.append(name)
    commands = [["systemctl", "disable", *old_loaded]] if old_loaded else []
    commands.append(["systemctl", "enable", *UNITS])
    return {"version": 1, "mode": "BOOT_REGISTRATION_ONLY", "release": str(release),
            "account_fingerprint": fingerprint, "commands": commands, "starts_or_stops_manager": False}


def apply_plan(plan: dict, *, run=subprocess.run) -> None:
    for command in plan["commands"]:
        # The helper has no start/stop/restart/--now route, including through
        # a caller-supplied plan. Boot metadata cannot kill an owned manager.
        if (len(command) < 3 or command[:2] not in (["systemctl", "enable"], ["systemctl", "disable"])
                or any(argument.startswith("-") for argument in command[2:])):
            raise ValueError("boot_registration_command_invalid")
        allowed = UNITS if command[1] == "enable" else OLD_BOOT_UNITS
        if any(name not in allowed for name in command[2:]):
            raise ValueError("boot_registration_unit_invalid")
    for command in plan["commands"]:
        run(command, check=True, capture_output=True, text=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--fingerprint", required=True)
    parser.add_argument("--unit-directory", type=Path, default=Path("/etc/systemd/system"))
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        plan = boot_plan(arguments.release, arguments.journal.resolve(), arguments.review,
                         fingerprint=arguments.fingerprint, unit_directory=arguments.unit_directory,
                         now=datetime.now(timezone.utc))
        if arguments.apply:
            apply_plan(plan)
        print(json.dumps(plan | {"applied": arguments.apply}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, sqlite3.Error, subprocess.CalledProcessError):
        print(json.dumps({"status": "BLOCKED", "reason": "selected_boot_preflight_failed"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
