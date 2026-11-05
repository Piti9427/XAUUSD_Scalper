"""CLI outputs stay new local artifacts, never trading/runtime paths."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.qualification.c22.__main__ import main


class CliTests(unittest.TestCase):
    def test_runtime_output_path_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "runtime-policy.json"
            with self.assertRaises(SystemExit) as caught:
                main(["costs", "--export", str(path), "--out", str(path)])
            self.assertEqual(caught.exception.code, 2)
            self.assertFalse(path.exists())

    def test_cost_command_writes_report_and_refuses_replacement(self):
        root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory(dir=root / "runs") as folder:
            path = Path(folder) / "export.json"
            path.write_text(
                json.dumps({"captured_utc": "2020-01-02T00:00:00Z", "history_deals": []})
            )
            output = Path(folder) / "costs.json"
            self.assertEqual(main(["costs", "--export", str(path), "--out", str(output)]), 0)
            report = json.loads(output.read_text())
            self.assertEqual(report["status"], "COST_INCONCLUSIVE")
            before = output.read_bytes()
            with self.assertRaises(SystemExit):
                main(["costs", "--export", str(path), "--out", str(output)])
            self.assertEqual(output.read_bytes(), before)
