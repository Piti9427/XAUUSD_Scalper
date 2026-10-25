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


class SelectedCliTests(unittest.TestCase):
    def test_send_mode_rejected_before_broker_initialization(self):
        for argument in ("--execute", "--exec"):
            with self.subTest(argument=argument):
                broker = Mock()
                output = StringIO()
                with patch.dict("os.environ", {"MT5_ENABLE_DEMO_ORDER_SEND": "1"}), redirect_stdout(output):
                    code = main([argument, "--once"], mt5=broker)
                self.assertEqual(code, 2)
                self.assertIn("selected_demo_readiness_pending", output.getvalue())
                broker.initialize.assert_not_called()
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
