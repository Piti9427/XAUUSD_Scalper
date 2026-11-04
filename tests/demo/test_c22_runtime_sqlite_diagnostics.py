"""Safe runtime SQLite attribution without changing Journal or caller behavior."""

from contextlib import ExitStack, closing, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.c22_selected import runner as selected_runner
from scripts.demo_runtime import cli, diagnostics, runner as shared_runner
from scripts.demo_runtime.journal import Journal


NOW = datetime(2026, 10, 31, 1, 35, 8, tzinfo=timezone.utc)
PRIVATE = "PRIVATE-fixture /customer/path SELECT hidden FROM private_table"


def sqlite_fault(code=sqlite3.SQLITE_BUSY, name="SQLITE_BUSY"):
    error = sqlite3.OperationalError(PRIVATE)
    error.sqlite_errorcode = code
    error.sqlite_errorname = name
    return error


def commit_failure_journal(error):
    class CommitFailure(sqlite3.Connection):
        fail_next = False

        def __exit__(self, exc_type, exc_value, traceback):
            if self.fail_next:
                self.fail_next = False
                super().__exit__(RuntimeError, RuntimeError("fixture rollback"), None)
                raise error
            return super().__exit__(exc_type, exc_value, traceback)

    connection = sqlite3.connect(":memory:", factory=CommitFailure)
    connection.executescript(
        "CREATE TABLE kv(key TEXT PRIMARY KEY,value TEXT NOT NULL);"
        "CREATE TABLE audit_events(id INTEGER PRIMARY KEY,payload TEXT NOT NULL);"
    )
    block_key = NOW.date().isoformat() + "|quote_stale"
    connection.executemany("INSERT INTO kv VALUES (?,?)", [
        ("active", "null"), ("protection_unknown_since", "null"),
        ("protection_alerted", "false"), ("last_alert_block", json.dumps(block_key)),
        ("last_result", '{"status":"FIXTURE_OLD"}'),
    ])
    connection.commit()
    journal = Journal.__new__(Journal)
    journal.conn, journal.guard = connection, None
    journal.audit_context = {"correlation_id": "fixture-correlation"}
    connection.fail_next = True
    return journal


class RuntimeSqliteDiagnosticsTests(unittest.TestCase):
    def record(self, error, **kwargs):
        return diagnostics.failure_record(error, stage="cli.cycle", now=NOW, **kwargs)

    def assert_private(self, value):
        text = json.dumps(value, allow_nan=False)
        self.assertNotIn("PRIVATE-fixture", text)
        self.assertNotIn("customer/path", text)
        self.assertNotIn("private_table", text)

    def test_runtime_native_codes_preserve_public_envelope_and_exception_identity(self):
        for code, name in ((5, "SQLITE_BUSY"), (13, "SQLITE_FULL"),
                           (10, "SQLITE_IOERR"), (266, "SQLITE_IOERR_READ")):
            with self.subTest(code=code):
                error = sqlite_fault(code, name)
                error.__cause__ = OSError(PRIVATE)
                cause, traceback, attributes = error.__cause__, error.__traceback__, vars(error).copy()
                record = self.record(error, correlation_id="fixture-correlation")
                self.assertEqual(record["details"], {"sqlite_errorcode": code,
                    "sqlite_errorname": name, "sqlite_primary_code": code & 0xff})
                self.assertEqual(record["code"], "runtime_exception")
                self.assertEqual(record["stage"], "cli.cycle")
                self.assertEqual(record["classification"], "FAULT")
                self.assertEqual(record["root_cause_status"], "UNKNOWN")
                self.assertEqual(record["evidence_ref"], "audit-correlation:fixture-correlation")
                self.assertEqual([item["exception_type"] for item in record["cause_chain"]],
                                 ["OperationalError", "OSError"])
                self.assertEqual(vars(error), attributes)
                self.assertIs(error.__cause__, cause)
                self.assertIs(error.__traceback__, traceback)
                self.assert_private(record)

    def test_actual_sqlite_errors_retain_native_extended_codes(self):
        with closing(sqlite3.connect(":memory:")) as connection:
            connection.execute("CREATE TABLE required(value TEXT NOT NULL)")
            for statement, code, name in (
                ("SELECT hidden FROM private_table", 1, "SQLITE_ERROR"),
                ("INSERT INTO required VALUES(NULL)", 1299, "SQLITE_CONSTRAINT_NOTNULL"),
            ):
                with self.subTest(code=code):
                    try:
                        connection.execute(statement)
                    except sqlite3.Error as error:
                        record = self.record(error)
                    else:
                        self.fail("Expected real SQLite fixture error")
                    self.assertEqual(record["details"], {"sqlite_errorcode": code,
                        "sqlite_errorname": name, "sqlite_primary_code": code & 0xff})
                    self.assert_private(record)

    def test_missing_malformed_and_unknown_native_metadata_stays_honest(self):
        errors = [sqlite3.OperationalError(PRIVATE)]
        errors += [sqlite_fault(code) for code in (None, True, "5", -1, 0, 2**80, float("nan"), [])]
        for index, error in enumerate(errors):
            with self.subTest(case=index):
                record = self.record(error)
                self.assertEqual(record["details"], {"sqlite_errorcode": None,
                    "sqlite_errorname": "UNKNOWN", "sqlite_primary_code": None})
                self.assert_private(record)
        record = self.record(sqlite_fault(123456, "SQLITE_UNVERIFIED"))
        self.assertEqual(record["details"], {"sqlite_errorcode": 123456,
            "sqlite_errorname": "UNKNOWN", "sqlite_primary_code": 64})

    def test_mismatched_names_and_external_details_cannot_forge_native_fields(self):
        for name in (PRIVATE, "SQLITE_FULL", "SQLITE_BUSY\n" + PRIVATE, None, object(), 5):
            with self.subTest(name_type=type(name).__name__):
                record = self.record(sqlite_fault(5, name), details={
                    "sqlite_errorcode": 13, "sqlite_errorname": "SQLITE_FULL", "sql": PRIVATE})
                self.assertEqual(record["details"], {"sqlite_errorcode": 5,
                    "sqlite_errorname": "UNKNOWN", "sqlite_primary_code": 5})
                self.assert_private(record)

    def test_faulting_native_properties_cannot_mask_the_original_error(self):
        class Hostile(sqlite3.OperationalError):
            @property
            def sqlite_errorcode(self):
                raise RuntimeError(PRIVATE)

            @property
            def sqlite_errorname(self):
                raise RuntimeError(PRIVATE)

        error = Hostile(PRIVATE)
        record = self.record(error)
        self.assertEqual(record["exception_type"], "Hostile")
        self.assertEqual(record["details"], {"sqlite_errorcode": None,
            "sqlite_errorname": "UNKNOWN", "sqlite_primary_code": None})
        self.assert_private(record)

    def test_non_sqlite_fault_and_known_gate_keep_existing_details_and_classification(self):
        for error, classification in ((OSError(PRIVATE), "FAULT"), (ValueError("quote_stale"), "GATE_BLOCK")):
            with self.subTest(error=type(error).__name__):
                record = self.record(error)
                self.assertEqual(record["details"], {})
                self.assertEqual(record["classification"], classification)
                self.assert_private(record)

    def test_fallback_adds_safe_persistence_fields_without_mutating_record_or_recursing(self):
        record = {"code": "cache_export_failed", "stage": "cache.export"}
        original = dict(record)
        output = StringIO()
        with redirect_stderr(output):
            diagnostics.fallback(record, persistence_error=sqlite_fault(13, "SQLITE_FULL"))
        payload = json.loads(output.getvalue())
        self.assertEqual(record, original)
        self.assertEqual(payload["diagnostic"], original)
        self.assertEqual(payload["kind"], "DIAGNOSTIC_FALLBACK")
        self.assertEqual(payload["persistence_failure"], {"exception_type": "OperationalError",
            "cause_chain": [{"exception_type": "OperationalError", "frames": []}],
            "sqlite_errorcode": 13, "sqlite_errorname": "SQLITE_FULL", "sqlite_primary_code": 13})
        self.assert_private(payload)
        output = StringIO()
        with redirect_stderr(output):
            diagnostics.fallback(record, persistence_error=OSError(PRIVATE))
        self.assertEqual(set(json.loads(output.getvalue())["persistence_failure"]),
                         {"exception_type", "cause_chain"})

    def test_actual_journal_context_exit_keeps_exception_cause_and_rollback(self):
        error = sqlite_fault(13, "SQLITE_FULL")
        error.__cause__ = OSError(PRIVATE)
        journal = commit_failure_journal(error)
        self.addCleanup(journal.close)
        try:
            journal.put("last_result", {"status": "FIXTURE_CHANGED"})
        except sqlite3.OperationalError as observed:
            self.assertIs(observed, error)
            cause, traceback = observed.__cause__, observed.__traceback__
            record = self.record(observed)
            self.assertIs(observed.__cause__, cause)
            self.assertIs(observed.__traceback__, traceback)
        else:
            self.fail("Expected synthetic commit-context failure")
        self.assertEqual(record["origin"]["path"], "scripts/demo_runtime/journal.py")
        self.assertEqual(record["origin"]["function"], "put")
        self.assertEqual(record["details"]["sqlite_errorcode"], 13)
        self.assertEqual(journal.get("last_result"), {"status": "FIXTURE_OLD"})
        self.assertFalse(journal.conn.in_transaction)
        self.assert_private(record)

    def test_current_cycle_to_real_cli_keeps_exit_shutdown_and_no_order(self):
        error, sdk = sqlite_fault(10, "SQLITE_IOERR"), Mock()
        journal = commit_failure_journal(error)
        self.addCleanup(journal.close)
        runner = selected_runner.SelectedDemoRunner.__new__(selected_runner.SelectedDemoRunner)
        runner.journal, runner.account_guard = journal, Mock()
        runner.strategy = SimpleNamespace(snapshot="fixture", diagnostics=lambda: {},
            config={"contract_id": "fixture"}, cooldown_bars=2)
        runner.broker = SimpleNamespace(position_count=None, last_equity=None,
            quote_diagnostics={}, identity_diagnostics={})
        runner.execute = False
        runner._admission = SimpleNamespace(review=None)
        runner.renewal_runtime = None
        runner.health_notify = runner.alert_notify = runner.notify = None
        runner.cache_output = None
        runner.broker_evidence_dir = Path("FIXTURE_MUST_NOT_BE_READ")

        def financial_cycle(_now):
            runner.broker.position_count = 0
            return {"status": "BLOCKED", "reason": "quote_stale"}

        runner._cycle = financial_cycle
        sdk.initialize.return_value = True
        output, errors = StringIO(), StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(Path, "read_text", return_value="{}"))
            stack.enter_context(patch.object(cli, "clock_now", return_value=NOW))
            stack.enter_context(patch("scripts.smc.mt5_init.resolve_mt5_account_kwargs",
                return_value={"login": 123, "server": "fixture-Demo", "password": "PRIVATE-fixture"}))
            stack.enter_context(patch.dict("os.environ", {}, clear=True))
            export = stack.enter_context(patch.object(selected_runner, "export_requested"))
            stack.enter_context(redirect_stdout(output))
            stack.enter_context(redirect_stderr(errors))
            result = cli.main(["--once", "--config", "fixture.json", "--cost-policy", "fixture-policy.json"],
                mt5=sdk, runner_class=Mock(return_value=runner), expected_config={})
        self.assertEqual(result, 1)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["failure"]["stage"], "cli.cycle")
        self.assertEqual(payload["failure"]["code"], "runtime_exception")
        self.assertEqual(payload["failure"]["origin"]["function"], "put")
        self.assertEqual(payload["failure"]["details"]["sqlite_errorcode"], 10)
        self.assertEqual([frame["path"] for frame in payload["failure"]["cause_chain"][0]["frames"]], [
            "scripts/demo_runtime/cli.py", "scripts/c22_selected/runner.py",
            "scripts/demo_runtime/runner.py", "scripts/demo_runtime/journal.py"])
        export.assert_not_called()
        sdk.initialize.assert_called_once()
        sdk.shutdown.assert_called_once()
        sdk.order_send.assert_not_called()
        self.assertIsNone(journal.conn)
        self.assert_private(payload)

    def test_post_export_put_failure_keeps_optional_path_and_native_evidence(self):
        journal = commit_failure_journal(sqlite_fault())
        self.addCleanup(journal.close)
        runner = selected_runner.SelectedDemoRunner.__new__(selected_runner.SelectedDemoRunner)
        runner.journal, runner.mt5 = journal, Mock()
        runner.renewal_runtime = None
        runner.strategy = SimpleNamespace(config={"contract_id": "fixture"}, cooldown_bars=2)
        runner.cache_output = None
        runner.broker_evidence_dir = Path("FIXTURE")
        runner._send_clock = lambda now: now
        receipt = {"status": "CAPTURED", "captured_utc": "2026-10-29T12:47:04+00:00"}
        runner._last_evidence_receipt = receipt
        result = {"status": "BLOCKED", "reason": "quote_stale"}
        with patch.object(shared_runner.DemoRunner, "cycle", return_value=result), \
                patch.object(selected_runner, "export_requested", return_value=receipt) as export:
            actual = runner.cycle(now=NOW)
        export.assert_called_once()
        self.assertEqual(actual["broker_evidence"]["status"], "FAULT")
        failure = actual["operational_errors"][0]
        self.assertEqual(failure["stage"], "evidence.export")
        self.assertEqual(failure["code"], "broker_evidence_export_failed")
        self.assertEqual(failure["details"]["sqlite_errorcode"], 5)
        self.assertEqual(runner._last_evidence_receipt, receipt)
        self.assertEqual(journal.get("last_result")["broker_evidence"]["status"], "FAULT")
        runner.mt5.order_send.assert_not_called()
        self.assert_private(failure)


if __name__ == "__main__":
    unittest.main()
