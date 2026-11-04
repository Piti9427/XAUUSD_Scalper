"""Terminal launch refusals retain safe causes without executing a terminal."""

from contextlib import redirect_stderr, redirect_stdout
import errno
import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "selected_terminal_diagnostics", ROOT / "deploy/c22-demo/launch_selected_terminal.py"
)
LAUNCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAUNCHER)
VALID_CONFIG = (
    "[Experts]\nEnabled=1\nAllowLiveTrading=1\nAllowDllImport=0\nAccount=1\nProfile=1\n"
)
PRIVATE_MARKER = "FIXTURE_PRIVATE_MUST_NOT_APPEAR"


class SelectedTerminalDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(dir=ROOT / "runs")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.release = self.root / "release"
        self.prefix = self.home / "c22-qemu-demo._g86ow9b"
        terminal = self.prefix / "drive_c/tools/mt5-c22-demo"
        charts = terminal / "MQL5/Profiles/Charts"
        charts.mkdir(parents=True)
        self.chart = charts / "fixture.chr"
        self.chart.write_text("<chart></chart>")
        (terminal / "terminal64.exe").write_bytes(b"non-executable fixture")
        self.wine = self.home / "fixture-wine"
        self.wine.write_bytes(b"non-executable fixture")
        self.environment_file = self.home / "c22-private/c22-backup.env"
        self.environment_file.parent.mkdir()
        self.environment_file.write_text("\n".join(
            key + "=" + json.dumps(value)
            for key, value in {
                "WINEPREFIX": str(self.prefix), "DEMO_WINE_BIN": str(self.wine),
                "FIXTURE_SECRET": PRIVATE_MARKER, "MT5_ENABLE_DEMO_ORDER_SEND": "1",
            }.items()
        ))
        self.config = self.release / "deploy/c22-demo/c22-selected-terminal-execution.ini"
        self.config.parent.mkdir(parents=True)
        self.config.write_text(VALID_CONFIG)

    def invoke(self, *, exec_error=None, preflight_error=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(Path, "home", return_value=self.home), patch.object(
            LAUNCHER, "__file__", str(self.config.parent / "launch_selected_terminal.py")
        ), patch.dict(LAUNCHER.os.environ, {}, clear=True), patch.object(
            LAUNCHER.os, "execvpe", side_effect=exec_error
        ) as execute, redirect_stdout(stdout), redirect_stderr(stderr):
            if preflight_error is None:
                result = LAUNCHER.main()
            else:
                with patch.object(LAUNCHER, "launch_options", side_effect=preflight_error):
                    result = LAUNCHER.main()
        raw = stdout.getvalue()
        self.assertNotIn(PRIVATE_MARKER, raw + stderr.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        return result, json.loads(raw) if raw else None, execute

    def test_distinct_guard_causes_keep_existing_envelope_and_never_execute(self):
        cases = (
            ("prefix", "dedicated_terminal_prefix_required"),
            ("ea", "attached_ea_blocks_terminal"),
            ("permissions", "terminal_permission_config_invalid"),
        )
        original = self.environment_file.read_text()
        for mutation, code in cases:
            with self.subTest(mutation=mutation):
                self.environment_file.write_text(original)
                self.chart.write_text("<chart></chart>")
                self.config.write_text(VALID_CONFIG)
                if mutation == "prefix":
                    self.environment_file.write_text('WINEPREFIX="/fixture/wrong-prefix"\n')
                elif mutation == "ea":
                    self.chart.write_text("<expert>fixture</expert>")
                else:
                    self.config.write_text("[Experts]\nEnabled=0\n")
                result, payload, execute = self.invoke()
                self.assertEqual(result, 2)
                self.assertEqual(payload["status"], "BLOCKED")
                self.assertEqual(payload["reason"], "selected_terminal_preflight_failed")
                self.assertEqual(payload["failure"]["code"], code)
                self.assertEqual(payload["failure"]["stage"], "terminal.preflight")
                execute.assert_not_called()

    def test_real_ini_parser_failures_report_safe_cause_and_refuse_exec(self):
        for content, kind in (
            (PRIVATE_MARKER + "\n", "MissingSectionHeaderError"),
            ("[Experts]\nEnabled=1\n" + PRIVATE_MARKER + "\n", "ParsingError"),
            ("[Experts]\nEnabled=1\nEnabled=1\n", "DuplicateOptionError"),
        ):
            with self.subTest(kind=kind):
                self.config.write_text(content)
                result, payload, execute = self.invoke()
                self.assertEqual(result, 2)
                self.assertEqual(payload["reason"], "selected_terminal_preflight_failed")
                self.assertEqual(payload["failure"]["code"], "terminal_permission_config_parse_failed")
                self.assertEqual(payload["failure"]["exception_type"], kind)
                execute.assert_not_called()

    def test_exec_os_failures_report_errno_once_without_retry_or_raw_path(self):
        for number, kind in ((errno.ENOENT, "FileNotFoundError"), (errno.EACCES, "PermissionError")):
            with self.subTest(number=number):
                failure = OSError(number, PRIVATE_MARKER, "/fixture/" + PRIVATE_MARKER)
                result, payload, execute = self.invoke(exec_error=failure)
                self.assertEqual(result, 1)
                self.assertEqual(payload["status"], "BLOCKED")
                self.assertEqual(payload["reason"], "selected_terminal_exec_failed")
                self.assertEqual(payload["failure"]["stage"], "terminal.exec")
                self.assertEqual(payload["failure"]["code"], "terminal_exec_os_error")
                self.assertEqual(payload["failure"]["exception_type"], kind)
                self.assertEqual(payload["failure"]["errno"], number)
                execute.assert_called_once()
                self.assertEqual(execute.call_args.args[2]["MT5_ENABLE_DEMO_ORDER_SEND"], "0")

    def test_malformed_environment_json_is_safe_and_never_executes(self):
        self.environment_file.write_text('FIXTURE_SECRET="' + PRIVATE_MARKER + '\n')
        result, payload, execute = self.invoke()
        self.assertEqual(result, 2)
        self.assertEqual(payload["failure"]["code"], "terminal_environment_invalid")
        self.assertEqual(payload["failure"]["exception_type"], "JSONDecodeError")
        execute.assert_not_called()

    def test_unrecognized_value_and_key_causes_never_echo_exception_arguments(self):
        for failure, code in (
            (ValueError(PRIVATE_MARKER), "terminal_preflight_value_error"),
            (KeyError(PRIVATE_MARKER), "terminal_preflight_key_error"),
        ):
            with self.subTest(code=code):
                result, payload, execute = self.invoke(preflight_error=failure)
                self.assertEqual(result, 2)
                self.assertEqual(payload["failure"]["code"], code)
                execute.assert_not_called()

    def test_preflight_io_failure_exposes_errno_without_private_filename(self):
        result, payload, execute = self.invoke(
            preflight_error=PermissionError(errno.EACCES, PRIVATE_MARKER, PRIVATE_MARKER)
        )
        self.assertEqual(result, 2)
        self.assertEqual(payload["failure"]["code"], "terminal_preflight_io_failed")
        self.assertEqual(payload["failure"]["errno"], errno.EACCES)
        execute.assert_not_called()

    def test_valid_launch_preserves_direct_exec_arguments_and_order_gate(self):
        result, payload, execute = self.invoke()
        self.assertEqual(result, 0)
        self.assertIsNone(payload)
        execute.assert_called_once()
        file, arguments, environment = execute.call_args.args
        self.assertEqual(file, "/usr/bin/xvfb-run")
        self.assertEqual(arguments[:4], [file, "-a", str(self.wine), LAUNCHER.WINDOWS_TERMINAL])
        self.assertEqual(arguments[4], "/portable")
        self.assertTrue(arguments[5].startswith("/config:Z:"))
        self.assertEqual(environment["MT5_ENABLE_DEMO_ORDER_SEND"], "0")
        self.assertNotIn("--execute", arguments)

    def test_interrupt_is_not_converted_to_a_normal_refusal(self):
        with self.assertRaises(KeyboardInterrupt):
            self.invoke(preflight_error=KeyboardInterrupt())


if __name__ == "__main__":
    unittest.main()
