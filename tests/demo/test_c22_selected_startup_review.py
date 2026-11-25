"""F2 (2026-11-12): an invalid review at flat startup blocks entries but must not crash-loop the sender.

On the VM a cost-policy expiry made the startup review invalid, the process exited, and systemd
restarted it 13,805 times over 4 days. install_execution_review keeps raising (initial-acceptance
contract); only the CLI now keeps the process alive with admissions blocked.
"""

from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import sqlite3
import unittest

from scripts.c22_selected.__main__ import main
from scripts.c22_selected.execution import canonical_hash
from scripts.c22_selected.runner import SelectedDemoRunner
from tests.demo.test_c22_selected_execution import review_fixture
from tests.demo.test_c22_selected_runner import SelectedBroker, selected_config
from tests.demo.test_demo_containment import policy_v2


class SelectedStartupReviewTests(unittest.TestCase):
    def run_cli(self, *, stale):
        folder = TemporaryDirectory(); self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        broker = SelectedBroker()
        broker.initialize = Mock(return_value=True)
        broker.shutdown = Mock()
        for name in ("swap_mode", "swap_long", "swap_short", "swap_rollover3days"):
            setattr(broker.info, name, 0)
        config, cost = selected_config(), policy_v2(broker.now, broker.info)
        journal, review = root / "journal.sqlite3", root / "review.json"
        prepared = SelectedDemoRunner(mt5=broker, expected_login=123, expected_server="Exness-Demo",
                                      journal_path=journal, account_guard_dir=root, config=config, cost_policy=cost)
        payload = review_fixture(prepared, broker.now)
        if stale:
            payload["readiness"]["captured_utc"] = (broker.now - timedelta(minutes=6)).isoformat()
            payload["readiness_sha256"] = canonical_hash(payload["readiness"])
        review.write_text(json.dumps(payload))
        prepared.close()
        (root / "config.json").write_text(json.dumps(config))
        (root / "cost.json").write_text(json.dumps(cost))

        def runner(**kwargs):
            kwargs["account_guard_dir"] = root
            return SelectedDemoRunner(**kwargs)

        output = StringIO()
        env = {"XAUUSD_MT5_LOGIN": "123", "XAUUSD_MT5_SERVER": "Exness-Demo", "XAUUSD_MT5_PASSWORD": "fixture",
               "MT5_ENABLE_DEMO_ORDER_SEND": "1", "MT5_TERMINAL_PATH": r"C:\C22Demo\terminal64.exe"}
        with patch.dict("os.environ", env, clear=True), \
                patch("scripts.demo_runtime.cli.clock_now", return_value=broker.now), redirect_stdout(output):
            code = main(["--once", "--execute", "--execution-review", str(review), "--config", str(root / "config.json"),
                         "--cost-policy", str(root / "cost.json"), "--journal", str(journal)],
                        mt5=broker, runner_class=runner)
        lines = [json.loads(l) for l in output.getvalue().splitlines() if l.startswith("{")]
        kinds = [json.loads(r[0]).get("kind") for r in
                 sqlite3.connect(journal).execute("SELECT payload FROM audit_events ORDER BY id")]
        return code, lines, broker, kinds

    def test_invalid_review_at_flat_startup_cycles_blocked_instead_of_crashing(self):
        code, lines, broker, kinds = self.run_cli(stale=True)
        last = lines[-1]
        self.assertTrue(last.get("process_alive"), last)               # a real cycle ran
        self.assertEqual(last["failure"]["classification"], "GATE_BLOCK", last)
        self.assertNotEqual(last["failure"]["stage"], "cli.runner_init", last)   # old crash stage
        self.assertEqual(last["status"], "BLOCKED", last)
        self.assertEqual(last["reason"], "selected_execution_review_invalid", last)
        broker.order_send.assert_not_called()
        self.assertIn("EXECUTION_REVIEW_STARTUP_BLOCKED", kinds)

    def test_valid_review_path_is_unchanged(self):
        code, lines, broker, kinds = self.run_cli(stale=False)
        self.assertEqual(code, 0)
        self.assertEqual(lines[-1]["status"], "FILLED", lines[-1])
        self.assertNotIn("EXECUTION_REVIEW_STARTUP_BLOCKED", kinds)


if __name__ == "__main__":
    unittest.main()
