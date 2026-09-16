"""Issue #1 live-gate readiness CLI — never invents smoke PASS."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


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
        self.assertIsNone(payload["gate_c_exness_smoke"]["artifact"])
        # Failed Mac attempts must remain visible without inventing ok:true.
        latest = payload["gate_c_exness_smoke"].get("latest_attempt_artifact")
        self.assertTrue(latest is None or "exness-smoke" in latest)
        self.assertTrue(payload["gate_d_demo_12w"]["protocol_present"])
        self.assertIn("foundation_live_gate.sh", payload["operator_blockers"]["next_action"])
        out = ROOT / "docs" / "ops" / "2026-09-16-issue1-live-gate-readiness.json"
        self.assertTrue(out.is_file())
        disk = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(disk["issue1_closable"], False)

    def test_scan_exness_smoke_prefers_newest_mtime(self):
        from scripts.ops import issue1_live_gate_readiness as mod

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_ops = root / "docs" / "ops"
            docs_ops.mkdir(parents=True)
            older = docs_ops / "aaaa-exness-smoke-old.json"
            newer = docs_ops / "zzzz-exness-smoke-new.json"
            older.write_text(json.dumps({"ok": False}), encoding="utf-8")
            time.sleep(0.02)
            newer.write_text(json.dumps({"ok": False}), encoding="utf-8")
            with mock.patch.object(mod, "ROOT", root):
                ok, passing, latest = mod._scan_exness_smoke()
            self.assertFalse(ok)
            self.assertIsNone(passing)
            self.assertTrue(str(latest).endswith(newer.name))

    def test_mac_gate_c_probe_fails_closed_without_mt5_package(self):
        script = ROOT / "scripts" / "ops" / "issue1_mac_gate_c_probe.py"
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("missing", payload.get("package", ""))
        artifact = ROOT / "docs" / "ops" / "2026-09-16-exness-smoke-mac-probe.json"
        self.assertTrue(artifact.is_file())


if __name__ == "__main__":
    unittest.main()
