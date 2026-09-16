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
        if "Failed to log in" in text or "token" in text.lower() and "invalid" in text.lower():
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


def main() -> int:
    smoke_ok = False
    smoke_path = None
    for p in sorted((ROOT / "docs" / "ops").glob("*-exness-smoke.json")):
        smoke_path = str(p.relative_to(ROOT))
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
            if payload.get("ok") is True:
                smoke_ok = True
                break
        except (OSError, json.JSONDecodeError):
            continue

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
            "artifact": smoke_path,
            "blocker_docs": [
                "docs/ops/2026-09-16-mac-live-gate-blocker.md",
                "docs/ops/2026-09-16-mac-wine-initialize-path.json",
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
            "utm_app_present_no_vms": True,
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
