#!/usr/bin/env python3
"""Emit JSON evidence bundle for GitHub issue closes (local verification)."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git_head() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _run_unittest(module: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", module, "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {"module": module, "ok": proc.returncode == 0, "returncode": proc.returncode}


def main() -> int:
    suite = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
        cwd=ROOT,
    )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "branch": "feature/smc-v2-hardening",
        "unit_suite_ok": suite.returncode == 0,
        "contracts": [
            _run_unittest("tests.test_s1_s4_mechanical_spec_contract"),
            _run_unittest("tests.test_s1_s4_research_handoff_contract"),
        ],
        "artifacts": {
            "mechanical_spec": "docs/specs/xauusd-s1-s4-mechanical-v1.md",
            "research_handoff": "docs/specs/xauusd-s1-s4-research-handoff-v1.md",
            "issue1_progress": "docs/handoff/2026-09-16-issue1-foundation-progress.md",
            "local_acceptance_audit": "docs/handoff/2026-09-16-issues-3-4-local-acceptance-audit.md",
        },
        "github_close_order": ["#3", "#4", "#2"],
        "issue1_live_gates_open": [
            "Exness Demo identity smoke with MT5",
            "Oracle ARM64 soak evidence",
            "Forward Demo 12-week protocol",
        ],
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["unit_suite_ok"] and all(c["ok"] for c in payload["contracts"]) else 1


if __name__ == "__main__":
    sys.exit(main())
