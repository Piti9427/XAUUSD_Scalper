"""Selected candidate CLI cannot send before its own readiness review."""

from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.c22_selected.__main__ import main
from tests.demo.test_c22_selected_runner import selected_config
from tests.demo.test_c22_selected_execution import review_fixture
from tests.demo.test_c22_selected_runner import SelectedBroker
from tests.demo.test_demo_containment import policy_v2
from scripts.c22_selected.runner import SelectedDemoRunner


class SelectedCliTests(unittest.TestCase):
    def test_reviewed_explicit_execute_reaches_shared_demo_fill(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            broker = SelectedBroker()
            broker.initialize = Mock(return_value=True)
            broker.shutdown = Mock()
            for name in ("swap_mode", "swap_long", "swap_short", "swap_rollover3days"):
                setattr(broker.info, name, 0)
            config, cost = selected_config(), policy_v2(broker.now, broker.info)
            journal, review = root / "journal.sqlite3", root / "review.json"
            prepared = SelectedDemoRunner(
                mt5=broker,
                expected_login=123,
                expected_server="Exness-Demo",
                journal_path=journal,
                account_guard_dir=root,
                config=config,
                cost_policy=cost,
            )
            review.write_text(json.dumps(review_fixture(prepared, broker.now)))
            prepared.close()
            (root / "config.json").write_text(json.dumps(config))
            (root / "cost.json").write_text(json.dumps(cost))

            def runner(**kwargs):
                kwargs["account_guard_dir"] = root
                return SelectedDemoRunner(**kwargs)

            output = StringIO()
            with (
                patch.dict(
                    "os.environ",
                    {
                        "XAUUSD_MT5_LOGIN": "123",
                        "XAUUSD_MT5_SERVER": "Exness-Demo",
                        "XAUUSD_MT5_PASSWORD": "fixture",
                        "MT5_ENABLE_DEMO_ORDER_SEND": "1",
                        "MT5_TERMINAL_PATH": r"C:\C22Demo\terminal64.exe",
                    },
                    clear=True,
                ),
                patch("scripts.demo_runtime.cli.clock_now", return_value=broker.now),
                redirect_stdout(output),
            ):
                code = main(
                    [
                        "--once",
                        "--execute",
                        "--execution-review",
                        str(review),
                        "--config",
                        str(root / "config.json"),
                        "--cost-policy",
                        str(root / "cost.json"),
                        "--journal",
                        str(journal),
                    ],
                    mt5=broker,
                    runner_class=runner,
                )
            self.assertEqual(code, 0, output.getvalue())
            result = json.loads(output.getvalue().splitlines()[-1])
            self.assertEqual(result["status"], "FILLED", result)
            self.assertTrue(result["execute"])
            broker.order_send.assert_called_once()
            broker.shutdown.assert_called_once()

    def test_send_mode_rejected_before_broker_initialization(self):
        for argument in ("--execute", "--exec", "--e", "--ex", "--exe"):
            with self.subTest(argument=argument):
                broker = Mock()
                output = StringIO()
                with (
                    patch.dict("os.environ", {"MT5_ENABLE_DEMO_ORDER_SEND": "1"}),
                    redirect_stdout(output),
                ):
                    code = main([argument, "--once"], mt5=broker)
                self.assertEqual(code, 2)
                self.assertIn("selected_demo_readiness_pending", output.getvalue())
                broker.initialize.assert_not_called()
                broker.order_send.assert_not_called()

    def test_inherited_send_environment_alone_stays_shadow(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config.json").write_text(json.dumps(selected_config()))
            (root / "cost.json").write_text("{}")
            broker, runner = Mock(), Mock()
            broker.initialize.return_value = True
            runner.return_value.cycle.return_value = {"status": "WAIT", "execute": False}
            with (
                patch.dict(
                    "os.environ",
                    {
                        "XAUUSD_MT5_LOGIN": "123",
                        "XAUUSD_MT5_SERVER": "Exness-Demo",
                        "XAUUSD_MT5_PASSWORD": "fixture",
                        "MT5_ENABLE_DEMO_ORDER_SEND": "1",
                    },
                    clear=True,
                ),
                redirect_stdout(StringIO()),
            ):
                code = main(
                    [
                        "--once",
                        "--config",
                        str(root / "config.json"),
                        "--cost-policy",
                        str(root / "cost.json"),
                        "--journal",
                        str(root / "journal.sqlite3"),
                    ],
                    mt5=broker,
                    runner_class=runner,
                )
            self.assertEqual(code, 0)
            self.assertFalse(runner.call_args.kwargs["execute"])
            broker.order_send.assert_not_called()

    def test_verify_sources_runs_without_credentials_or_broker(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(selected_config()))
            broker = Mock()
            output = StringIO()
            with patch.dict("os.environ", {}, clear=True), redirect_stdout(output):
                code = main(["--verify-sources", "--config", str(path)], mt5=broker)
            self.assertEqual(code, 0)
            self.assertIn("CONFIG_SOURCES_VERIFIED", output.getvalue())
            broker.initialize.assert_not_called()
            broker.order_send.assert_not_called()
