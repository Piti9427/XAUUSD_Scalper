"""Public candidate CLI: explicit Demo gate, frozen config, safe defaults."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
import json
import unittest

from scripts.ops.mt5_wine_c22h4 import main
from test_c22h4_demo import CandidateBroker
from test_trial30_demo import policy


class CandidateCliTests(unittest.TestCase):
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
                account_guard_dir=ROOT / "data",
            )
            try:
                with patch.dict(
                    "os.environ",
                    dict(
                        XAUUSD_MT5_LOGIN="123",
                        XAUUSD_MT5_SERVER="Exness-Demo",
                        XAUUSD_MT5_PASSWORD="fixture",
                    ),
                    clear=True,
                ):
                    self.assertEqual(
                        main(
                            [
                                "--once",
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
