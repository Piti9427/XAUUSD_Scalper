"""Public candidate CLI: explicit Demo gate, frozen config, safe defaults."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import json
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest

from scripts.ops.mt5_wine_c22h4 import main
from tests.demo.test_c22h4_demo import CandidateBroker
from tests.demo.test_trial30_demo import policy


class CandidateCliTests(unittest.TestCase):
    def test_shadow_reads_market_with_autotrading_disabled_but_execution_blocks(self):
        for execute in (False, True):
            with self.subTest(execute=execute), TemporaryDirectory() as tmp:
                broker = CandidateBroker(1)
                broker.initialize = Mock(return_value=True)
                broker.shutdown = Mock()
                broker.account.trade_allowed = False
                broker.account.trade_expert = False
                broker.terminal_info = Mock(
                    return_value=SimpleNamespace(
                        connected=True, trade_allowed=False, tradeapi_disabled=True
                    )
                )
                cost = Path(tmp) / "cost.json"
                cost.write_text(json.dumps(policy() | {"reviewed_utc": broker.now.isoformat()}))
                output = StringIO()
                with (
                    patch.dict(
                        "os.environ",
                        dict(
                            XAUUSD_MT5_LOGIN="123",
                            XAUUSD_MT5_SERVER="Exness-Demo",
                            XAUUSD_MT5_PASSWORD="fixture",
                            MT5_TERMINAL_PATH=r"C:\C22Demo\terminal64.exe",
                            MT5_ENABLE_DEMO_ORDER_SEND="1",
                        ),
                        clear=True,
                    ),
                    patch("scripts.ops.mt5_wine_trial30.clock_now", return_value=broker.now),
                    redirect_stdout(output),
                ):
                    code = main(
                        [
                            "--once",
                            "--cost-policy",
                            str(cost),
                            "--journal",
                            str(Path(tmp) / "shadow.sqlite3"),
                            *(["--execute"] if execute else []),
                        ],
                        mt5=broker,
                    )
                result = json.loads(output.getvalue().splitlines()[-1])
                if execute:
                    self.assertEqual(code, 1)
                    self.assertEqual(result["reason"], "algo_permissions_required")
                else:
                    self.assertEqual(code, 0)
                    self.assertEqual(result["status"], "SHADOW_ADMIT")
                    self.assertTrue(result["entry_ready"])
                    self.assertFalse(result["execute"])
                    self.assertEqual(result["position_protection"], "flat")
                    self.assertGreater(result["cache_bars"], 0)
                broker.order_send.assert_not_called()

    def test_shadow_keeps_demo_identity_and_connection_gates(self):
        from scripts.c22h4.runner import C22H4DemoRunner

        for failure in ("login", "real", "disconnected"):
            with self.subTest(failure=failure), TemporaryDirectory() as tmp:
                broker = CandidateBroker(1)
                broker.account.trade_expert = False
                broker.terminal_info = Mock(
                    return_value=SimpleNamespace(
                        connected=failure != "disconnected",
                        trade_allowed=False,
                        tradeapi_disabled=True,
                    )
                )
                if failure == "login":
                    broker.account.login = 124
                if failure == "real":
                    broker.account.trade_mode = 2
                runner = C22H4DemoRunner(
                    mt5=broker,
                    expected_login=123,
                    expected_server="Exness-Demo",
                    journal_path=Path(tmp) / "shadow.sqlite3",
                    cost_policy={},
                    execute=False,
                )
                try:
                    result = runner.cycle(now=broker.now)
                    self.assertEqual(result["status"], "BLOCKED")
                    self.assertEqual(
                        result["reason"],
                        "algo_permissions_required"
                        if failure == "disconnected"
                        else "demo_identity_required",
                    )
                    self.assertFalse(result["entry_ready"])
                    broker.order_send.assert_not_called()
                finally:
                    runner.close()

    def test_initialize_timeout_is_configurable_without_enabling_orders(self):
        for timeout, extra in ((10000, []), (90000, ["--initialize-timeout-ms", "90000"])):
            with self.subTest(timeout=timeout), TemporaryDirectory() as tmp:
                cost = Path(tmp) / "cost.json"
                cost.write_text("{}")
                broker = Mock()
                broker.initialize.return_value = False
                broker.last_error.return_value = (-10005, "fixture")
                with (
                    patch.dict(
                        "os.environ",
                        dict(
                            XAUUSD_MT5_LOGIN="123",
                            XAUUSD_MT5_SERVER="Exness-Demo",
                            XAUUSD_MT5_PASSWORD="fixture",
                            MT5_ENABLE_DEMO_ORDER_SEND="1",
                        ),
                        clear=True,
                    ),
                    patch("scripts.c22h4.runner.C22H4DemoRunner") as runner,
                ):
                    self.assertEqual(
                        main(["--once", "--cost-policy", str(cost), *extra], mt5=broker), 1
                    )
                    self.assertEqual(broker.initialize.call_args.kwargs["timeout"], timeout)
                    self.assertFalse(runner.call_args.kwargs["execute"])
                broker.order_send.assert_not_called()
                broker.shutdown.assert_called_once()

    def test_invalid_initialize_timeout_rejected_before_runner_or_broker(self):
        for timeout in ("-1", "0", "999", "120001"):
            with (
                self.subTest(timeout=timeout),
                patch("scripts.c22h4.runner.C22H4DemoRunner") as runner,
            ):
                broker = Mock()
                self.assertEqual(main(["--initialize-timeout-ms", timeout], mt5=broker), 2)
                runner.assert_not_called()
                broker.initialize.assert_not_called()
                broker.shutdown.assert_not_called()
                broker.order_send.assert_not_called()

    def test_execute_requires_env_gate_before_initialize(self):
        broker = Mock()
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(main(["--execute", "--once"], mt5=broker), 2)
        broker.initialize.assert_not_called()

    def test_bad_config_rejected_before_initialize(self):
        broker = Mock()
        with TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.json"
            config.write_text("{}")
            self.assertEqual(main(["--config", str(config)], mt5=broker), 2)
        broker.initialize.assert_not_called()

    def test_once_shadow_has_no_order_send(self):
        broker = CandidateBroker(1)
        broker.initialize = Mock(return_value=True)
        broker.shutdown = Mock()
        with TemporaryDirectory() as tmp:
            cost = Path(tmp) / "cost.json"
            cost.write_text(json.dumps(policy() | {"reviewed_utc": broker.now.isoformat()}))
            with (
                patch.dict(
                    "os.environ",
                    dict(
                        XAUUSD_MT5_LOGIN="123",
                        XAUUSD_MT5_SERVER="Exness-Demo",
                        XAUUSD_MT5_PASSWORD="fixture",
                    ),
                    clear=True,
                ),
                patch("scripts.ops.mt5_wine_trial30.clock_now", return_value=broker.now),
            ):
                self.assertEqual(
                    main(
                        [
                            "--once",
                            "--cost-policy",
                            str(cost),
                            "--journal",
                            str(Path(tmp) / "c22.sqlite3"),
                        ],
                        mt5=broker,
                    ),
                    0,
                )
        broker.order_send.assert_not_called()
        broker.shutdown.assert_called_once()

    def test_second_cli_rejected_before_mt5_initialize_or_shutdown(self):
        from scripts.c22h4.runner import C22H4DemoRunner
        from scripts.ops.mt5_wine_trial30 import ROOT

        broker = CandidateBroker()
        broker.initialize = Mock(return_value=True)
        broker.shutdown = Mock()
        with TemporaryDirectory() as tmp:
            costs = policy() | {"reviewed_utc": broker.now.isoformat()}
            cost = Path(tmp) / "cost.json"
            cost.write_text(json.dumps(costs))
            runner = C22H4DemoRunner(
                mt5=broker,
                expected_login=123,
                expected_server="Exness-Demo",
                journal_path=Path(tmp) / "first.sqlite3",
                cost_policy=costs,
                account_guard_dir=Path(tmp) / "data",
            )
            try:
                with (
                    patch.dict(
                        "os.environ",
                        dict(
                            XAUUSD_MT5_LOGIN="123",
                            XAUUSD_MT5_SERVER="Exness-Demo",
                            XAUUSD_MT5_PASSWORD="fixture",
                        ),
                        clear=True,
                    ),
                    patch("scripts.ops.mt5_wine_trial30.ROOT", Path(tmp)),
                ):
                    self.assertEqual(
                        main(
                            [
                                "--once",
                                "--config",
                                str(ROOT / "config/c22h4-demo.json"),
                                "--journal",
                                str(Path(tmp) / "second.sqlite3"),
                                "--cost-policy",
                                str(cost),
                            ],
                            mt5=broker,
                        ),
                        1,
                    )
                broker.initialize.assert_not_called()
                broker.shutdown.assert_not_called()
            finally:
                runner.close()

    def test_account_guard_cannot_be_redirected_by_environment(self):
        from scripts.ops.mt5_wine_trial30 import ROOT

        broker = Mock()
        broker.initialize.return_value = False
        broker.last_error.return_value = (-1, "fixture")
        with TemporaryDirectory() as tmp:
            cost = Path(tmp) / "cost.json"
            cost.write_text(json.dumps(policy()))
            with (
                patch.dict(
                    "os.environ",
                    dict(
                        XAUUSD_MT5_LOGIN="123",
                        XAUUSD_MT5_SERVER="Exness-Demo",
                        XAUUSD_MT5_PASSWORD="fixture",
                        DEMO_ACCOUNT_GUARD_DIR=tmp,
                    ),
                    clear=True,
                ),
                patch("scripts.c22h4.runner.C22H4DemoRunner") as runner,
            ):
                self.assertEqual(main(["--once", "--cost-policy", str(cost)], mt5=broker), 1)
                self.assertEqual(runner.call_args.kwargs["account_guard_dir"], ROOT / "data")
