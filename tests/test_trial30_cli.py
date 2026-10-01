"""Public CLI gates: execution must be explicit, Demo, and target-bound."""

from unittest.mock import patch, Mock
from tempfile import TemporaryDirectory
from pathlib import Path
import json
import unittest

from scripts.ops.mt5_wine_trial30 import main
from test_trial30_demo import Broker, policy


class Trial30CliTests(unittest.TestCase):
    def test_execute_requires_explicit_env_gate_before_mt5_initialization(self):
        broker = Mock()
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(main(["--execute", "--once"], mt5=broker), 2)
        broker.initialize.assert_not_called()

    def test_once_shadow_runs_target_demo_cycle_without_order_send(self):
        broker = Broker()
        broker.initialize = Mock(return_value=True)
        broker.shutdown = Mock()
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
                    ),
                    clear=True,
                ),
                patch(
                    "scripts.ops.mt5_wine_trial30.clock_now",
                    return_value=__import__("test_trial30_demo").NOW,
                ),
            ):
                self.assertEqual(
                    main(
                        [
                            "--once",
                            "--cost-policy",
                            str(cost),
                            "--journal",
                            str(Path(tmp) / "state.sqlite3"),
                        ],
                        mt5=broker,
                    ),
                    0,
                )
        broker.order_send.assert_not_called()
        broker.shutdown.assert_called_once()

    def test_real_account_rejected_even_when_order_env_gate_is_enabled(self):
        broker = Broker()
        broker.account.trade_mode = 2
        broker.initialize = Mock(return_value=True)
        broker.shutdown = Mock()
        with TemporaryDirectory() as tmp:
            cost = Path(tmp) / "cost.json"
            cost.write_text(json.dumps(policy()))
            env = dict(
                MT5_ENABLE_DEMO_ORDER_SEND="1",
                XAUUSD_MT5_LOGIN="123",
                XAUUSD_MT5_SERVER="Exness-Demo",
                XAUUSD_MT5_PASSWORD="fixture",
            )
            with (
                patch.dict("os.environ", env, clear=True),
                patch(
                    "scripts.ops.mt5_wine_trial30.clock_now",
                    return_value=__import__("test_trial30_demo").NOW,
                ),
            ):
                self.assertEqual(
                    main(
                        [
                            "--once",
                            "--execute",
                            "--cost-policy",
                            str(cost),
                            "--journal",
                            str(Path(tmp) / "state.sqlite3"),
                        ],
                        mt5=broker,
                    ),
                    1,
                )
        broker.order_send.assert_not_called()

    def test_modified_snapshot_config_rejected_before_mt5_initialization(self):
        broker = Mock()
        with TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.json"
            config.write_text(json.dumps({"snapshot": "other", "volume": 1.0}))
            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(main(["--once", "--config", str(config)], mt5=broker), 2)
        broker.initialize.assert_not_called()
