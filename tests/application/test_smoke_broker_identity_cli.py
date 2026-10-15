import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SmokeBrokerIdentityCliTests(unittest.TestCase):
    def test_writes_evidence_json_with_out_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "smoke.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "smoke_broker_identity.py"),
                    "--out",
                    str(out_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertTrue(out_path.is_file())
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("captured_at_utc", payload)
            self.assertIn("infra_verdict", payload)
            self.assertEqual(proc.returncode, 2)
            stdout = json.loads(proc.stdout)
            self.assertEqual(stdout["infra_verdict"], payload["infra_verdict"])


if __name__ == "__main__":
    unittest.main()
