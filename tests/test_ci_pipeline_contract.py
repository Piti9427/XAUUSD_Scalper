"""TDD tests verifying the CI/CD and local check pipeline contract."""

import os
from pathlib import Path
import unittest
import pandas as pd
from datetime import datetime, timezone
import yaml

ROOT = Path(__file__).resolve().parents[1]


class TestCIPipelineContract(unittest.TestCase):
    def test_github_workflow_ci_exists_and_valid(self):
        ci_path = ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(ci_path.exists(), f"CI workflow file not found: {ci_path}")

        content = ci_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        self.assertIsInstance(parsed, dict)

        # Triggers
        triggers = parsed.get("on") or parsed.get(True) or {}
        self.assertIn("push", triggers)
        self.assertIn("pull_request", triggers)
        push_branches = triggers["push"].get("branches", [])
        self.assertIn("main", push_branches)
        self.assertIn("develop", push_branches)
        self.assertIn("feature/**", push_branches)

        # Job matrix
        checks_job = parsed.get("jobs", {}).get("checks", {})
        matrix = checks_job.get("strategy", {}).get("matrix", {})
        py_versions = matrix.get("python-version", [])
        self.assertIn("3.10", py_versions)
        self.assertIn("3.11", py_versions)

        # Pipeline steps
        step_commands = [s.get("run", "") for s in checks_job.get("steps", []) if "run" in s]
        all_commands = " ".join(step_commands)

        self.assertIn("compileall", all_commands)
        self.assertIn("test_mt5.py", all_commands)
        self.assertIn("pip check", all_commands)
        self.assertIn("ruff check", all_commands)
        self.assertIn("ruff format --check", all_commands)
        self.assertIn("unittest discover", all_commands)

    def test_makefile_has_required_targets(self):
        makefile_path = ROOT / "Makefile"
        self.assertTrue(makefile_path.exists(), f"Makefile not found: {makefile_path}")

        content = makefile_path.read_text(encoding="utf-8")
        for target in [
            "all:",
            "check:",
            "compile:",
            "deps:",
            "lint:",
            "format:",
            "format-check:",
            "test:",
            "clean:",
        ]:
            self.assertIn(target, content, f"Missing target {target} in Makefile")

    def test_run_checks_script_exists_and_executable(self):
        script_path = ROOT / "scripts" / "run_checks.sh"
        self.assertTrue(script_path.exists(), f"Script not found: {script_path}")
        self.assertTrue(os.access(script_path, os.X_OK), f"Script not executable: {script_path}")

        content = script_path.read_text(encoding="utf-8")
        self.assertIn("compileall", content)
        self.assertIn("test_mt5.py", content)
        self.assertIn("pip check", content)
        self.assertIn("ruff check", content)
        self.assertIn("ruff format --check", content)
        self.assertIn("unittest", content)

    def test_smc_main_defines_and_executes_generate_setup_chart(self):
        """Verify smc_main imports and can safely invoke generate_setup_chart."""
        import smc_main
        from scripts.smc.types import Direction, SetupSignal

        self.assertTrue(
            hasattr(smc_main, "generate_setup_chart"),
            "smc_main must import generate_setup_chart from scripts.smc.chart",
        )
        fn = getattr(smc_main, "generate_setup_chart")
        self.assertTrue(callable(fn))

        # Test safe execution: when called without matplotlib or in test env, returns None or path
        df = pd.DataFrame(
            [
                {
                    "time": datetime.now(timezone.utc),
                    "open": 2000.0,
                    "high": 2005.0,
                    "low": 1995.0,
                    "close": 2002.0,
                }
            ]
        )
        signal = SetupSignal(
            direction=Direction.BUY,
            sweep_price=1995.0,
            sweep_wick=1994.0,
            mss_price=2005.0,
            entry_price=2000.0,
            sl_price=1990.0,
            tp_price=2025.0,
            sl_distance=10.0,
            risk_r=2.5,
            fvg_high=2002.0,
            fvg_low=1998.0,
            reason="CHoCH + FVG",
            timestamp=datetime.now(timezone.utc),
            setup_id="TEST_SIG_1",
        )
        result = fn(df, signal, "/tmp/test_chart.png")
        self.assertTrue(result is None or isinstance(result, str))


if __name__ == "__main__":
    unittest.main()
