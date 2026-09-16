"""Issue #1 live-gate readiness CLI — never invents smoke PASS."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Issue1LiveGateReadinessTests(unittest.TestCase):
    def test_emits_not_closable_without_live_artifacts(self):
        script = ROOT / "scripts" / "ops" / "issue1_live_gate_readiness.py"
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["issue1_closable"])
        self.assertFalse(payload["gate_c_exness_smoke"]["ok"])
        self.assertTrue(payload["gate_d_demo_12w"]["protocol_present"])
        out = ROOT / "docs" / "ops" / "2026-09-16-issue1-live-gate-readiness.json"
        self.assertTrue(out.is_file())
        disk = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(disk["issue1_closable"], False)


if __name__ == "__main__":
    unittest.main()
