"""Explain existing identity gates without retries, extra reads or weaker checks."""

from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from scripts.c22_selected.runner import SelectedDemoRunner
from tests.demo.test_c22_selected_runner import SelectedBroker, selected_config
from tests.demo.test_trial30_demo import policy


class IdentityDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def runner(self, sdk, name="identity", *, execute=True):
        costs = policy() | {
            "reviewed_utc": sdk.now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        }
        runner = SelectedDemoRunner(
            mt5=sdk,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=Path(self.temp.name) / name / "journal.sqlite3",
            config=selected_config(),
            cost_policy=costs,
            execute=execute,
        )
        self.addCleanup(runner.close)
        return runner

    @staticmethod
    def terminal(**changes):
        return NS(**(dict(connected=True, trade_allowed=True, tradeapi_disabled=False) | changes))

    def test_disconnected_cycle_reports_specific_flags_and_recovers_without_resend(self):
        sdk = SelectedBroker()
        sdk.account_info = Mock(wraps=sdk.account_info)
        sdk.terminal_info = Mock(return_value=self.terminal(connected=False))
        runner = self.runner(sdk)
        frame = Mock(wraps=runner.strategy.frame)
        runner.strategy.frame = frame
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100.0):
            blocked = runner.cycle(now=sdk.now)
        self.assertEqual(blocked["reason"], "algo_permissions_required")
        self.assertEqual(blocked["identity_blockers"], ["terminal_disconnected"])
        self.assertIs(blocked["identity_terminal_connected"], False)
        self.assertIs(blocked["identity_account_trade_allowed"], True)
        self.assertEqual(sdk.account_info.call_count, 1)
        self.assertEqual(sdk.terminal_info.call_count, 1)
        frame.assert_not_called()
        sdk.order_check.assert_not_called()
        sdk.order_send.assert_not_called()
        self.assertIsNone(runner.journal.get("active"))

        sdk.terminal_info.return_value = self.terminal()
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100.0):
            filled = runner.cycle(now=sdk.now + timedelta(seconds=1))
            managing = runner.cycle(now=sdk.now + timedelta(seconds=2))
        self.assertEqual(filled["status"], "FILLED", filled)
        self.assertEqual(managing["status"], "MANAGING", managing)
        self.assertEqual(sdk.order_send.call_count, 1)
        self.assertEqual(runner.broker.identity_diagnostics["identity_blockers"], [])
        self.assertIsNone(runner.journal.get("selected_last_loss_ms"))

    def test_each_permission_denial_preserves_gate_and_whitelists_evidence(self):
        cases = (
            ("missing_terminal", {}, {}, ["terminal_missing"]),
            ("disconnected", {"connected": False}, {}, ["terminal_disconnected"]),
            ("terminal_trade", {"trade_allowed": False}, {}, ["terminal_trade_disabled"]),
            ("external_api", {"tradeapi_disabled": True}, {}, ["external_trade_api_disabled"]),
            ("account_trade", {}, {"trade_allowed": False}, ["account_trade_disabled"]),
            ("account_expert", {}, {"trade_expert": False}, ["account_expert_disabled"]),
            (
                "combined",
                {"trade_allowed": False, "tradeapi_disabled": True},
                {"trade_expert": False},
                [
                    "terminal_trade_disabled",
                    "external_trade_api_disabled",
                    "account_expert_disabled",
                ],
            ),
        )
        expected_keys = {
            "identity_account_present",
            "identity_terminal_present",
            "identity_require_trade_permissions",
            "identity_terminal_connected",
            "identity_terminal_trade_allowed",
            "identity_terminal_tradeapi_disabled",
            "identity_account_trade_allowed",
            "identity_account_trade_expert",
            "identity_blockers",
        }
        for name, terminal, account, blockers in cases:
            with self.subTest(name=name):
                sdk = SelectedBroker()
                sdk.account.password = "sensitive-fixture-do-not-log"
                for key, value in account.items():
                    setattr(sdk.account, key, value)
                sdk.account_info = Mock(wraps=sdk.account_info)
                sdk.terminal_info = Mock(
                    return_value=None if name == "missing_terminal" else self.terminal(**terminal)
                )
                runner = self.runner(sdk, name)
                result = runner.cycle(now=sdk.now)
                self.assertEqual(result["reason"], "algo_permissions_required")
                self.assertEqual(result["identity_blockers"], blockers)
                self.assertEqual(
                    {key for key in result if key.startswith("identity_")}, expected_keys
                )
                self.assertEqual(sdk.account_info.call_count, 1)
                self.assertEqual(sdk.terminal_info.call_count, 1)
                text = json.dumps(result, allow_nan=False)
                for sensitive in ("sensitive-fixture-do-not-log", "Exness-Demo", "password"):
                    self.assertNotIn(sensitive, text)
                sdk.order_send.assert_not_called()
                self.assertIsNone(runner.journal.get("active"))

    def test_missing_or_wrong_demo_identity_is_not_a_permission_bypass(self):
        for name in ("missing", "wrong_login", "real_account"):
            with self.subTest(name=name):
                sdk = SelectedBroker()
                if name == "wrong_login":
                    sdk.account.login = 999
                elif name == "real_account":
                    sdk.account.trade_mode = 2
                else:
                    sdk.account_info = Mock(return_value=None)
                runner = self.runner(sdk, name)
                result = runner.cycle(now=sdk.now)
                self.assertEqual(result["reason"], "demo_identity_required")
                self.assertEqual(
                    result["identity_blockers"],
                    ["account_missing" if name == "missing" else "demo_identity_mismatch"],
                )
                self.assertIs(result["identity_account_present"], name != "missing")
                sdk.order_send.assert_not_called()

    def test_identity_diagnostics_are_reset_before_next_cycle(self):
        sdk = SelectedBroker()
        sdk.terminal_info = Mock(return_value=self.terminal(connected=False))
        runner = self.runner(sdk)
        first = runner.cycle(now=sdk.now)
        self.assertEqual(first["identity_blockers"], ["terminal_disconnected"])
        sdk.account_info = Mock(side_effect=RuntimeError("fixture SDK read failed"))
        now = sdk.now + timedelta(seconds=1)
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100.0):
            second = runner.cycle(now=now)
        self.assertEqual(second["reason"], "RuntimeError")
        self.assertEqual(
            runner.broker.identity_diagnostics,
            dict(
                account_read_request_started_utc=now.isoformat(),
                account_read_observed_utc=None,
            ),
        )
        self.assertEqual(second["account_read_request_started_utc"], now.isoformat())
        self.assertIsNone(second["account_read_observed_utc"])
        self.assertIsNone(runner.broker.account_observation)
        self.assertNotIn("day_start_valid", second)
        self.assertNotIn("day_start_reason", second)
        self.assertFalse(any(key.startswith("identity_") for key in second))
        sdk.account_info.assert_called_once()
        self.assertEqual(sdk.terminal_info.call_count, 1)
        sdk.order_send.assert_not_called()

    def test_active_close_read_does_not_require_trading_permission(self):
        sdk = SelectedBroker()
        runner = self.runner(sdk)
        self.assertEqual(runner.cycle(now=sdk.now)["status"], "FILLED")
        sdk.now += timedelta(seconds=1)
        sdk.send(dict(action=1, position=777, type=0, volume=0.01, price=sdk.tick.ask))
        sdk.account.trade_allowed = False
        sdk.account.trade_expert = False
        sdk.terminal_info = Mock(
            return_value=self.terminal(trade_allowed=False, tradeapi_disabled=True)
        )
        closed = runner.cycle(now=sdk.now)
        self.assertEqual(closed["status"], "CLOSED", closed)
        self.assertIs(
            runner.broker.identity_diagnostics["identity_require_trade_permissions"], False
        )
        self.assertEqual(runner.broker.identity_diagnostics["identity_blockers"], [])
        self.assertIsNone(runner.journal.get("active"))
        self.assertEqual(sdk.order_send.call_count, 1)

    def test_read_only_identity_still_rejects_a_disconnected_terminal(self):
        sdk = SelectedBroker()
        sdk.terminal_info = Mock(return_value=self.terminal(connected=False))
        runner = self.runner(sdk)
        with self.assertRaisesRegex(ValueError, "algo_permissions_required"):
            runner.broker.identity(require_trade_permissions=False)
        self.assertEqual(
            runner.broker.identity_diagnostics["identity_blockers"], ["terminal_disconnected"]
        )
        sdk.order_send.assert_not_called()

    def test_optional_diagnostic_field_failure_cannot_block_read_only_identity(self):
        class AccountWithUnavailablePermission(NS):
            @property
            def trade_expert(self):
                raise RuntimeError("optional fixture field unavailable")

        sdk = SelectedBroker()
        sdk.account = AccountWithUnavailablePermission(
            **{key: value for key, value in vars(sdk.account).items() if key != "trade_expert"}
        )
        runner = self.runner(sdk)
        self.assertIs(runner.broker.identity(require_trade_permissions=False), sdk.account)
        self.assertIsNone(runner.broker.identity_diagnostics["identity_account_trade_expert"])
        self.assertEqual(runner.broker.identity_diagnostics["identity_blockers"], [])
        with self.assertRaisesRegex(RuntimeError, "optional fixture field unavailable"):
            runner.broker.identity(require_trade_permissions=True)
        sdk.order_send.assert_not_called()

    def test_disconnected_optional_flag_errors_do_not_mask_original_blocker(self):
        class DisconnectedTerminal(NS):
            @property
            def trade_allowed(self):
                raise RuntimeError("trade_allowed unavailable during reconnect")

            @property
            def tradeapi_disabled(self):
                raise RuntimeError("tradeapi_disabled unavailable during reconnect")

        sdk = SelectedBroker()
        sdk.terminal_info = Mock(return_value=DisconnectedTerminal(connected=False))
        runner = self.runner(sdk)
        result = runner.cycle(now=sdk.now)
        self.assertEqual(result["reason"], "algo_permissions_required")
        self.assertEqual(result["identity_blockers"], ["terminal_disconnected"])
        self.assertIsNone(result["identity_terminal_trade_allowed"])
        self.assertIsNone(result["identity_terminal_tradeapi_disabled"])
        self.assertEqual(sdk.terminal_info.call_count, 1)
        sdk.order_check.assert_not_called()
        sdk.order_send.assert_not_called()

    def test_unknown_connection_flag_stays_blocked_without_fabricated_boolean(self):
        sdk = SelectedBroker()
        sdk.terminal_info = Mock(return_value=self.terminal(connected=None))
        runner = self.runner(sdk)
        result = runner.cycle(now=sdk.now)
        self.assertEqual(result["reason"], "algo_permissions_required")
        self.assertIsNone(result["identity_terminal_connected"])
        self.assertEqual(result["identity_blockers"], ["permission_check_failed"])
        self.assertEqual(sdk.terminal_info.call_count, 1)
        sdk.order_send.assert_not_called()

    def test_capital_and_journal_failures_remain_blocked_without_logging_values(self):
        for name, reason in (
            ("capital", "invalid_capital"),
            ("journal", "journal_account_mismatch"),
        ):
            with self.subTest(name=name):
                sdk = SelectedBroker()
                runner = self.runner(sdk, name)
                if name == "capital":
                    sdk.account.equity = float("nan")
                else:
                    runner.journal.put("identity", "sensitive-foreign-account-binding")
                result = runner.cycle(now=sdk.now)
                self.assertEqual(result["reason"], reason)
                self.assertEqual(result["identity_blockers"], [reason])
                self.assertNotIn("sensitive-foreign-account-binding", json.dumps(result))
                json.dumps(result, allow_nan=False)
                self.assertIsNone(runner.journal.get("active"))
                sdk.order_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
