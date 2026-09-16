#!/usr/bin/env python3
"""Emit Issue #1 Gate C/D readiness snapshot from in-repo evidence (no live invent)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _exists(rel: str) -> bool:
    return (ROOT / rel).is_file()


def _gh_auth_ok() -> bool:
    try:
        proc = subprocess.run(
            ["gh", "auth", "status", "-h", "github.com"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        text = (proc.stdout or "") + (proc.stderr or "")
        # Parentheses matter: status text always contains "Token: …".
        if ("Failed to log in" in text) or (
            "token" in text.lower() and "invalid" in text.lower()
        ):
            return False
        # Probe a cheap authenticated call — status text alone can be misleading.
        api = subprocess.run(
            ["gh", "api", "user", "-q", ".login"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return api.returncode == 0 and bool((api.stdout or "").strip())
    except FileNotFoundError:
        return False


def _scenario_software_ok() -> bool | None:
    path = ROOT / "docs" / "ops" / "2026-09-16-issue1-scenario-coverage.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return bool(payload.get("summary", {}).get("software_evidence_complete"))


def _scan_exness_smoke() -> tuple[bool, str | None, str | None]:
    """
    Return (ok, passing_artifact, latest_attempt_artifact).

    Matches both `*-exness-smoke.json` and `*-exness-smoke-*.json` so Mac retry
    evidence is visible without inventing ok:true.
    """
    ops = ROOT / "docs" / "ops"
    candidates = sorted(
        set(ops.glob("*-exness-smoke.json")) | set(ops.glob("*-exness-smoke-*.json")),
        key=lambda p: p.stat().st_mtime,
    )
    latest = str(candidates[-1].relative_to(ROOT)) if candidates else None
    for p in candidates:
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("ok") is True:
            return True, str(p.relative_to(ROOT)), latest
    return False, None, latest


def _utm_app_present() -> bool:
    return Path("/Applications/UTM.app").is_dir()


def main() -> int:
    smoke_ok, smoke_pass, smoke_latest = _scan_exness_smoke()

    host_hunt = "docs/ops/2026-09-16-host-reachability-hunt.json"
    coverage = "docs/ops/2026-09-16-issue1-scenario-coverage.json"
    report = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "gate_b_scenario_software": {
            "artifact": coverage if _exists(coverage) else None,
            "software_evidence_complete": _scenario_software_ok(),
            "note": "Scenarios 1–23 software only; does not close #1",
        },
        "gate_c_exness_smoke": {
            "ok": smoke_ok,
            "artifact": smoke_pass,
            "latest_attempt_artifact": smoke_latest,
            "blocker_docs": [
                "docs/ops/2026-09-16-mac-live-gate-blocker.md",
                "docs/ops/2026-09-16-mac-wine-initialize-path.json",
                "docs/ops/2026-09-16-mac-wine-reprobe-running.json",
                "docs/ops/2026-09-16-exness-smoke-mac-post-split.json",
                "docs/ops/2026-09-16-host-ssh-reprobe.json",
                host_hunt,
            ],
        },
        "gate_c_oracle_soak": {
            "checklist_present": _exists(
                "docs/ops/2026-09-16-oracle-arm64-runtime-checklist.md"
            ),
            "completed_artifact_present": any(
                (ROOT / "docs" / "ops").glob("*-oracle-soak*.json")
            ),
        },
        "gate_d_demo_12w": {
            "protocol_present": _exists(
                "docs/ops/2026-09-16-foundation-demo-12w-protocol.md"
            ),
            "start_artifact_present": any(
                (ROOT / "docs" / "ops").glob("*-demo-12w-start*.json")
            ),
            "note": "Do not invent a start artifact; operator fills after Gates B/C.",
        },
        "operator_blockers": {
            "gh_auth_ok": _gh_auth_ok(),
            "host_reachability_artifact": host_hunt if _exists(host_hunt) else None,
            "utm_app_present": _utm_app_present(),
            "utm_app_present_no_vms": _utm_app_present(),
            "next_action": (
                "Authorize Mac SSH pubkey on Oracle/Windows MT5 host, or run "
                "./scripts/ops/foundation_live_gate.sh there with Exness Demo (hedging). "
                "See ./scripts/ops/issue1_operator_unblock.sh"
            ),
        },
        "issue1_closable": False,
    }
    report["issue1_closable"] = bool(
        report["gate_c_exness_smoke"]["ok"]
        and report["gate_c_oracle_soak"]["completed_artifact_present"]
        and report["gate_d_demo_12w"]["start_artifact_present"]
    )

    out = ROOT / "docs" / "ops" / "2026-09-16-issue1-live-gate-readiness.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["issue1_closable"] else 2


if __name__ == "__main__":
    sys.exit(main())
