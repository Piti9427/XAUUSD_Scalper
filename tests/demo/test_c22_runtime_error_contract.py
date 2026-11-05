"""Safe failure attribution and durable operational outcomes through public cycles."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from tests.demo import test_c22_identity_diagnostics as fixtures
from scripts.demo_runtime import cli
from scripts.demo_runtime.diagnostics import failure_record, safe_details, public_reason, RESUME


class RuntimeErrorContractTests(unittest.TestCase):
    def setUp(self):
        self.helper = fixtures.IdentityDiagnosticsTests()
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)

    def runner(self, name):
        sdk = fixtures.SelectedBroker()
        return sdk, self.helper.runner(sdk, name)

    def cycle(self, sdk, runner):
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            return runner.cycle(now=sdk.now)

    def test_distinct_sdk_origins_keep_legacy_reason_and_safe_trace(self):
        failures = []
        for operation, stage in (
            ("account_info", "broker.identity"),
            ("history_deals_get", "broker.history"),
        ):
            with self.subTest(operation=operation):
                sdk, runner = self.runner(operation)
                setattr(sdk, operation, Mock(side_effect=RuntimeError("SECRET-private-SDK-origin")))
                result = self.cycle(sdk, runner)
                self.assertEqual(result["reason"], "RuntimeError")
                failure = result["failure"]
                failures.append(failure)
                self.assertEqual(failure["code"], "runtime_exception")
                self.assertEqual(failure["stage"], stage)
                self.assertTrue(failure["cause_chain"][0]["frames"])
                self.assertEqual(
                    failure["correlation_id"], runner.journal.audit_context["correlation_id"]
                )
                self.assertEqual(runner.journal.get("last_result")["failure"], failure)
                self.assertNotIn("SECRET", json.dumps(result))
                self.assertNotIn("Exness-Demo", json.dumps(failure))
                sdk.order_send.assert_not_called()
        self.assertNotEqual(failures[0]["origin"], failures[1]["origin"])

    def test_unknown_sdk_valueerror_does_not_leak_message_or_become_known_gate(self):
        sdk, runner = self.runner("private-valueerror")
        sdk.account_info = Mock(side_effect=ValueError("password=SECRET-token-url"))
        result = self.cycle(sdk, runner)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "ValueError")
        self.assertEqual(result["failure"]["classification"], "FAULT")
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("password", json.dumps(runner.journal.get("last_result")))
        sdk.order_send.assert_not_called()

    def test_concrete_history_and_first_quote_causes_keep_specific_resume(self):
        for name, operation, expected in (
            ("history", "history_deals_total", "history_unknown"),
            ("first-quote", "copy_ticks_range", "first_quote_unknown"),
        ):
            with self.subTest(name=name):
                sdk, runner = self.runner(name)
                setattr(sdk, operation, Mock(return_value=None))
                result = self.cycle(sdk, runner)
                self.assertEqual(result["reason"], expected)
                item = result["entry_availability"]["known_blockers"][0]
                self.assertEqual(item["code"], expected)
                self.assertNotEqual(item["resume_condition"], "inspect_recorded_runtime_failure")
                self.assertEqual(result["failure"]["classification"], "GATE_BLOCK")
                sdk.order_send.assert_not_called()

    def test_failed_notification_is_durable_without_recursive_outbox_event(self):
        sdk, runner = self.runner("delivery")
        runner.notify = Mock(side_effect=RuntimeError("SECRET-delivery-url-token"))
        result = self.cycle(sdk, runner)
        self.assertEqual(result["status"], "FILLED")
        self.assertEqual(result["notification"], "pending_retry")
        stored = runner.journal.get("last_result")
        self.assertEqual(stored["notification"], "pending_retry")
        self.assertEqual(stored["operational_errors"][0]["stage"], "delivery.lifecycle")
        rows = [
            json.loads(row[0])
            for row in runner.journal.conn.execute(
                "SELECT payload FROM audit_events WHERE json_extract(payload,'$.kind')='OPERATIONAL_FAILURE'"
            )
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["correlation_id"], runner.journal.audit_context["correlation_id"])
        self.assertEqual(rows[0]["financial_status"], "FILLED")
        events = [
            json.loads(row[0]) for row in runner.journal.conn.execute("SELECT payload FROM events")
        ]
        self.assertEqual(len(events), 1)
        self.assertNotEqual(events[0]["kind"], "OPERATIONAL_FAILURE")
        self.assertIsNotNone(runner.journal.get("active"))
        self.assertIsNone(runner.journal.get("selected_last_loss_ms"))
        self.assertNotIn("SECRET", json.dumps(stored) + json.dumps(rows))
        self.assertEqual(sdk.order_send.call_count, 1)

    def test_diagnostic_persistence_failure_uses_independent_safe_fallback(self):
        sdk, runner = self.runner("fallback")
        self.assertEqual(self.cycle(sdk, runner)["status"], "FILLED")
        active = runner.journal.get("active")
        result = dict(status="MANAGING")
        stderr = StringIO()
        with (
            patch.object(runner.journal, "audit", side_effect=OSError("SECRET-db-disk")),
            redirect_stderr(stderr),
        ):
            runner.record_operational_failure(
                result,
                now=sdk.now,
                stage="cache.export",
                error=OSError("SECRET-file-path"),
                code="cache_export_failed",
            )
        self.assertEqual(runner.journal.get("active"), active)
        self.assertEqual(sdk.order_send.call_count, 1)
        fallback = json.loads(stderr.getvalue().splitlines()[-1])
        self.assertEqual(fallback["kind"], "DIAGNOSTIC_FALLBACK")
        self.assertNotIn("SECRET", stderr.getvalue())

    def test_financial_journal_failure_still_propagates_without_send(self):
        sdk, runner = self.runner("financial-write")
        with patch.object(runner.journal, "put", side_effect=OSError("SECRET-financial-write")):
            with self.assertRaises(OSError):
                self.cycle(sdk, runner)
        sdk.order_send.assert_not_called()

    def test_chained_causes_are_bounded_and_exclude_messages_and_locals(self):
        try:
            try:
                raise OSError("SECRET-innermost-path")
            except OSError as cause:
                raise RuntimeError("SECRET-outer-token") from cause
        except RuntimeError as error:
            # A cyclic chain must not hang the manager's diagnostic boundary.
            error.__cause__.__cause__ = error
            result = failure_record(error, stage="broker.history")
        self.assertEqual(
            [item["exception_type"] for item in result["cause_chain"]], ["RuntimeError", "OSError"]
        )
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("locals", json.dumps(result))
        self.assertEqual(result["root_cause_status"], "UNKNOWN")

    def test_untrusted_diagnostic_payload_and_error_string_are_safe(self):
        class BrokenValueError(ValueError):
            def __str__(self):
                raise RuntimeError("SECRET-string-fault")

        self.assertEqual(public_reason(BrokenValueError()), "BrokenValueError")
        detail = safe_details(
            dict(
                stage="SECRET",
                code="SECRET",
                field="password",
                expected={"state": {}},
                observed={"state": "INVALID", "private": "SECRET"},
                password="SECRET",
                exception_class="SECRET url/token",
            )
        )
        self.assertEqual(detail, {"observed": {"state": "INVALID"}})

    def test_existing_runtime_machine_reasons_have_specific_registry_entries(self):
        import ast
        from scripts.demo_runtime.diagnostics import ROOT

        paths = [
            ROOT / "scripts/demo_runtime" / name
            for name in ("broker.py", "runner.py", "admission.py", "lifecycle.py", "boundary.py")
        ]
        paths += [
            ROOT / "scripts/c22_selected/strategy.py",
            ROOT / "scripts/c22_selected/runner.py",
        ]
        codes = set()
        for path in paths:
            for node in ast.walk(ast.parse(path.read_text())):
                if (
                    isinstance(node, ast.Raise)
                    and isinstance(node.exc, ast.Call)
                    and node.exc.args
                    and isinstance(node.exc.args[0], ast.Constant)
                    and isinstance(node.exc.args[0].value, str)
                ):
                    codes.add(node.exc.args[0].value)
        self.assertTrue(codes)
        self.assertEqual(sorted(codes - RESUME.keys()), [])
        for code in codes:
            self.assertNotEqual(RESUME[code][1], "inspect_recorded_runtime_failure", code)

    def test_cost_diagnostic_codes_survive_shared_failure_record(self):
        import ast
        from scripts.demo_runtime.diagnostics import ROOT

        tree = ast.parse((ROOT / "scripts/demo_runtime/costs.py").read_text())
        codes = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            candidate = (
                node.args[2:3]
                if node.func.id == "_diagnose"
                else node.args[:1]
                if node.func.id == "failed"
                else []
            )
            for argument in candidate:
                codes.update(
                    child.value
                    for child in ast.walk(argument)
                    if isinstance(child, ast.Constant)
                    and isinstance(child.value, str)
                    and child.value.startswith("cost_")
                )
        self.assertIn("cost_evidence_source_missing", codes)
        for code in sorted(codes):
            with self.subTest(code=code):
                record = failure_record(
                    ValueError("cost_policy_invalid_or_stale"),
                    stage="admission.check",
                    details=dict(code=code, stage="cost.evidence"),
                )
                self.assertEqual(record["code"], code)
                self.assertEqual(record["details"]["code"], code)


class CliErrorContractTests(unittest.TestCase):
    def invoke(self, folder, broker, factory, *, watch=False):
        root = Path(folder)
        config, cost = root / "config.json", root / "cost.json"
        config.write_text("{}")
        cost.write_text("{}")
        output, errors = StringIO(), StringIO()
        env = {
            "XAUUSD_MT5_LOGIN": "123",
            "XAUUSD_MT5_SERVER": "Exness-Demo",
            "XAUUSD_MT5_PASSWORD": "SECRET",
            "MT5_TERMINAL_PATH": "fixture-terminal",
        }
        with (
            patch.dict("os.environ", env, clear=True),
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            result = cli.main(
                [
                    "--watch" if watch else "--once",
                    "--config",
                    str(config),
                    "--cost-policy",
                    str(cost),
                    "--journal",
                    str(root / "journal.sqlite3"),
                    *(["--max-cycles", "2"] if watch else []),
                ],
                mt5=broker,
                runner_class=factory,
                expected_config={},
            )
        return result, output.getvalue(), errors.getvalue()

    def test_cleanup_failure_preserves_primary_error_and_still_shuts_down(self):
        from tempfile import TemporaryDirectory

        broker, runner = Mock(), Mock()
        broker.initialize.return_value = True
        runner.cycle.side_effect = OSError("SECRET-primary-journal")
        runner.close.side_effect = RuntimeError("SECRET-close")
        with TemporaryDirectory() as folder:
            result, output, errors = self.invoke(folder, broker, Mock(return_value=runner))
        self.assertEqual(result, 1)
        rows = [json.loads(line) for line in output.splitlines()]
        primary = next(row for row in rows if row.get("reason") == "OSError")
        self.assertEqual(primary["failure"]["stage"], "cli.cycle")
        broker.shutdown.assert_called_once()
        self.assertIn("cli.close", errors)
        self.assertNotIn("SECRET", output + errors)

    def test_shutdown_failure_sets_failure_exit_without_erasing_successful_cycle(self):
        from tempfile import TemporaryDirectory

        broker, runner = Mock(), Mock()
        broker.initialize.return_value = True
        broker.shutdown.side_effect = RuntimeError("SECRET-shutdown")
        runner.cycle.return_value = {"status": "WAIT", "reason": "no_signal"}
        with TemporaryDirectory() as folder:
            result, output, errors = self.invoke(folder, broker, Mock(return_value=runner))
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(output.splitlines()[-1])["status"], "WAIT")
        runner.close.assert_called_once()
        self.assertIn("cli.shutdown", errors)
        self.assertNotIn("SECRET", output + errors)

    def test_malformed_startup_config_has_safe_decode_cause_before_sdk(self):
        from tempfile import TemporaryDirectory

        broker = Mock()
        with TemporaryDirectory() as folder:
            config = Path(folder) / "config.json"
            config.write_text('{"password":"SECRET",')
            output = StringIO()
            with redirect_stdout(output):
                result = cli.main(["--once", "--config", str(config)], mt5=broker)
        payload = json.loads(output.getvalue())
        self.assertEqual(result, 2)
        self.assertEqual(payload["reason"], "snapshot_config_mismatch")
        self.assertEqual(payload["failure"]["code"], "config_decode_failed")
        self.assertNotIn("SECRET", output.getvalue())
        broker.initialize.assert_not_called()

    def test_policy_reload_fault_still_runs_owned_manager_and_persists_cause(self):
        helper = fixtures.IdentityDiagnosticsTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        sdk = fixtures.SelectedBroker()
        runner = helper.runner(sdk, "reload")
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            self.assertEqual(runner.cycle(now=sdk.now)["status"], "FILLED")
        sdk.initialize = Mock(return_value=True)
        sdk.shutdown = Mock()
        captured = []
        original_close = runner.close

        def close():
            captured.append(runner.journal.get("last_result"))
            original_close()

        runner.close = Mock(side_effect=close)

        def factory(**kwargs):
            (Path(helper.temp.name) / "cost.json").write_text('{"private":"SECRET",')
            return runner

        with (
            patch("scripts.demo_runtime.runner.time.monotonic", return_value=100),
            patch("scripts.demo_runtime.cli.clock_now", return_value=sdk.now),
        ):
            result, output, errors = self.invoke(helper.temp.name, sdk, factory)
        self.assertEqual(result, 0)
        self.assertEqual(captured[0]["status"], "MANAGING")
        failure = captured[0]["operational_errors"][0]
        self.assertEqual(failure["code"], "cost_policy_reload_failed")
        self.assertEqual(failure["stage"], "cli.policy_reload")
        self.assertEqual(runner.policy, {})
        self.assertEqual(sdk.order_send.call_count, 1)
        sdk.shutdown.assert_called_once()
        self.assertNotIn("SECRET", output + errors)


if __name__ == "__main__":
    unittest.main()
