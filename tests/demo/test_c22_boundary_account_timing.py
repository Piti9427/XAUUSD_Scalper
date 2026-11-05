"""Account response timing stays independent of later identity validation latency."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.c22_selected.runner import SelectedDemoRunner
from scripts.demo_runtime.boundary import read_mark
from scripts.demo_runtime.journal import Journal
from scripts.trial30.runner import Trial30DemoRunner
from tests.demo.test_trial30_demo import Broker, policy

MIDNIGHT = datetime(2026, 10, 2, tzinfo=timezone.utc)
EXPECTED_START = "2026-10-02T00:00:00.020000+00:00"
EXPECTED_RETURN = "2026-10-02T00:00:00.040000+00:00"


@contextmanager
def timing_fixture(
    *,
    account_delay=0.02,
    terminal_delay=1.1,
    missing=False,
    wrong_account=False,
    disconnected=False,
    invalid_capital=False,
    terminal_exception=False,
    capture_write_failure=False,
    account_exception=False,
    runner_class=Trial30DemoRunner,
):
    clock = [10.0]
    broker = Broker()
    broker.account.equity = 197.0
    if wrong_account:
        broker.account.login = 999
    if invalid_capital:
        broker.account.equity = float("nan")
    timeline = []

    def account_read():
        timeline.append("account_request")
        if account_exception:
            raise RuntimeError("fixture_account_read_failure")
        clock[0] += account_delay
        timeline.append("account_return")
        return None if missing else broker.account

    def terminal_read():
        timeline.append("terminal_request")
        clock[0] += terminal_delay
        timeline.append("terminal_return")
        if terminal_exception:
            raise RuntimeError("fixture_terminal_read_failure")
        return SimpleNamespace(
            connected=not disconnected, trade_allowed=True, tradeapi_disabled=False
        )

    broker.account_info = Mock(side_effect=account_read)
    broker.terminal_info = Mock(side_effect=terminal_read)
    with TemporaryDirectory(prefix="midnight-proposal-") as temp:
        path = Path(temp) / "journal.sqlite3"
        runner = runner_class(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=path,
            cost_policy=policy(),
            execute=True,
        )
        original_put = runner.journal.put
        proof_attempts = []

        def put(key, value):
            if key == "utc_boundary_mark":
                timeline.append("proof_persist")
                proof_attempts.append(
                    {
                        "terminal_complete": "terminal_return" in timeline,
                        "identity_journal_bound": runner.journal.get("identity")
                        == runner.fingerprint,
                        "value": dict(value),
                    }
                )
                if capture_write_failure:
                    raise OSError("fixture_boundary_write_failure")
            return original_put(key, value)

        runner.journal.put = put
        try:
            with patch("scripts.demo_runtime.runner.time.monotonic", side_effect=lambda: clock[0]):
                result = runner.cycle(now=MIDNIGHT + timedelta(milliseconds=20))
            broker.order_send.assert_not_called()
            yield {
                "runner": runner,
                "broker": broker,
                "path": path,
                "clock": clock,
                "timeline": timeline,
                "proof_attempts": proof_attempts,
                "result": result,
            }
        finally:
            runner.close()


class TimingRegressionControlTests(unittest.TestCase):
    def assert_single_read_no_proof(self, case):
        self.assertIsNone(case["runner"].journal.get("utc_boundary_mark"))
        self.assertIsNone(case["runner"].journal.get("day"))
        self.assertEqual(case["broker"].account_info.call_count, 1)
        self.assertEqual(case["broker"].terminal_info.call_count, 1)
        self.assertEqual(case["proof_attempts"], [])
        case["broker"].order_send.assert_not_called()

    def test_fast_account_slow_terminal_preserves_first_second_and_restart(self):
        with timing_fixture() as case:
            mark = case["runner"].journal.get("utc_boundary_mark")
            self.assertIsNotNone(mark)
            self.assertEqual(mark["request_started_utc"], EXPECTED_START)
            self.assertEqual(mark["observed_utc"], EXPECTED_RETURN)
            self.assertEqual(mark["equity"], 197.0)
            self.assertEqual(len(case["proof_attempts"]), 1)
            self.assertTrue(case["proof_attempts"][0]["terminal_complete"])
            self.assertTrue(case["proof_attempts"][0]["identity_journal_bound"])
            self.assertLess(
                case["timeline"].index("terminal_return"), case["timeline"].index("proof_persist")
            )
            self.assertEqual(case["broker"].account_info.call_count, 1)
            self.assertEqual(case["broker"].terminal_info.call_count, 1)
            case["runner"].close()
            restarted = Journal(case["path"])
            try:
                retained = read_mark(
                    restarted,
                    fingerprint=case["runner"].fingerprint,
                    day=MIDNIGHT.date().isoformat(),
                )
                self.assertEqual(retained, mark)
                self.assertEqual(retained["observed_utc"], EXPECTED_RETURN)
            finally:
                restarted.close()

    def test_slow_account_remains_no_proof(self):
        with timing_fixture(account_delay=1.1, terminal_delay=0.02) as case:
            self.assert_single_read_no_proof(case)

    def test_wrong_account_never_persists_prevalidation_proof(self):
        with timing_fixture(wrong_account=True) as case:
            self.assertEqual(case["result"]["reason"], "demo_identity_required")
            self.assert_single_read_no_proof(case)

    def test_disconnected_terminal_never_persists_prevalidation_proof(self):
        with timing_fixture(disconnected=True) as case:
            self.assertEqual(case["result"]["reason"], "algo_permissions_required")
            self.assert_single_read_no_proof(case)

    def test_missing_account_remains_no_proof(self):
        with timing_fixture(missing=True) as case:
            self.assertEqual(case["result"]["reason"], "demo_identity_required")
            self.assert_single_read_no_proof(case)

    def test_invalid_capital_never_persists_prevalidation_proof(self):
        with timing_fixture(invalid_capital=True) as case:
            self.assertEqual(case["result"]["reason"], "invalid_capital")
            self.assert_single_read_no_proof(case)

    def test_terminal_exception_never_persists_prevalidation_proof(self):
        with timing_fixture(terminal_exception=True) as case:
            self.assert_single_read_no_proof(case)


class CandidatePersistenceTests(unittest.TestCase):
    def test_exit_day_validity_is_not_relabelled_by_current_cycle_diagnostics(self):
        for current_valid, exit_valid in ((True, False), (False, True), (False, False)):
            with (
                self.subTest(current_valid=current_valid, exit_valid=exit_valid),
                timing_fixture() as case,
            ):
                runner = case["runner"]
                runner.journal.put("active", {"request": {"magic": runner.strategy.magic}})
                runner.broker._baseline = Mock(
                    return_value=197.0,
                    side_effect=None if current_valid else ValueError("day_start_floating_unknown"),
                )
                runner._lifecycle.reconcile_closed = Mock(
                    return_value=dict(
                        status="CLOSED",
                        day_start_valid=exit_valid,
                        day_start_day="2026-10-01",
                        day_start_source="captured_at_utc_boundary",
                    )
                )
                with patch("scripts.demo_runtime.runner.time.monotonic", return_value=30.0):
                    result = runner.cycle(now=MIDNIGHT + timedelta(seconds=30))
                for payload in (result, runner.journal.get("last_result")):
                    self.assertEqual(payload["status"], "CLOSED")
                    self.assertIs(payload["day_start_valid"], exit_valid)
                    self.assertEqual(payload["day_start_day"], "2026-10-01")
                    self.assertNotIn("day_start_reason", payload)
                runner.broker._baseline.assert_called_once()
                self.assertEqual(case["broker"].account_info.call_count, 2)
                case["broker"].order_send.assert_not_called()

    def assert_times_retained_as_diagnostics_only(self, case):
        self.assertIsNone(case["runner"].journal.get("utc_boundary_mark"))
        self.assertIsNone(case["runner"].journal.get("day"))
        self.assertEqual(case["result"]["account_read_request_started_utc"], EXPECTED_START)
        self.assertEqual(case["result"]["account_read_observed_utc"], EXPECTED_RETURN)
        case["runner"].close()
        restarted = Journal(case["path"])
        try:
            result = restarted.get("last_result")
            self.assertEqual(result["account_read_request_started_utc"], EXPECTED_START)
            self.assertEqual(result["account_read_observed_utc"], EXPECTED_RETURN)
            self.assertIsNone(
                read_mark(
                    restarted,
                    fingerprint=case["runner"].fingerprint,
                    day=MIDNIGHT.date().isoformat(),
                )
            )
        finally:
            restarted.close()

    def test_terminal_failure_preserves_return_timestamps_after_restart_without_proof(self):
        with timing_fixture(terminal_exception=True) as case:
            self.assert_times_retained_as_diagnostics_only(case)
            self.assertEqual(case["proof_attempts"], [])

    def test_capture_write_failure_preserves_return_timestamps_after_restart_without_proof(self):
        with timing_fixture(capture_write_failure=True) as case:
            self.assert_times_retained_as_diagnostics_only(case)
            self.assertEqual(len(case["proof_attempts"]), 1)
            self.assertTrue(case["proof_attempts"][0]["terminal_complete"])
            self.assertTrue(case["proof_attempts"][0]["identity_journal_bound"])
            self.assertEqual(case["broker"].account_info.call_count, 1)

    def test_later_failed_identity_never_reuses_or_redates_prior_observation(self):
        with timing_fixture() as case:
            mark = case["runner"].journal.get("utc_boundary_mark")
            self.assertIsNotNone(mark)
            case["broker"].account_info = Mock(return_value=None)
            with patch("scripts.demo_runtime.runner.time.monotonic", side_effect=lambda: 20.0):
                result = case["runner"].cycle(now=MIDNIGHT + timedelta(days=1, milliseconds=20))
            self.assertEqual(result["reason"], "demo_identity_required")
            self.assertEqual(case["runner"].journal.get("utc_boundary_mark"), mark)
            self.assertIsNone(case["runner"].broker.account_observation)
            self.assertIsNone(
                read_mark(
                    case["runner"].journal,
                    fingerprint=case["runner"].fingerprint,
                    day=(MIDNIGHT + timedelta(days=1)).date().isoformat(),
                )
            )
            self.assertEqual(case["broker"].account_info.call_count, 1)
            case["broker"].order_send.assert_not_called()


class SelectedAccountTimingTests(unittest.TestCase):
    def test_held_selected_position_keeps_management_and_uses_only_genuine_restart_proof(self):
        from tests.demo.test_c22_selected_runner import SelectedBroker, selected_config

        for account_delay, captured in ((0.02, True), (1.1, False)):
            with self.subTest(account_delay=account_delay), TemporaryDirectory() as directory:
                broker = SelectedBroker()
                costs = policy() | {
                    "reviewed_utc": broker.now.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ).isoformat()
                }
                path = Path(directory) / "held-selected.sqlite3"
                runner = SelectedDemoRunner(
                    mt5=broker,
                    expected_login=123,
                    expected_server="Exness-Demo",
                    journal_path=path,
                    config=selected_config(),
                    cost_policy=costs,
                    execute=True,
                )
                self.addCleanup(runner.close)
                opened = runner.cycle(now=broker.now)
                self.assertEqual(opened["status"], "FILLED", opened)
                midnight = (broker.now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                now = midnight + timedelta(milliseconds=20)
                broker.tick.time_msc = int(now.timestamp() * 1000)
                broker.account.equity = 197.0
                clock = [10.0]

                def account_read():
                    clock[0] += account_delay
                    return broker.account

                def terminal_read():
                    clock[0] += 1.1
                    return SimpleNamespace(
                        connected=True, trade_allowed=True, tradeapi_disabled=False
                    )

                broker.account_info = Mock(side_effect=account_read)
                broker.terminal_info = Mock(side_effect=terminal_read)
                with patch(
                    "scripts.demo_runtime.runner.time.monotonic", side_effect=lambda: clock[0]
                ):
                    managed = runner.cycle(now=now)
                self.assertEqual(managed["status"], "MANAGING", managed)
                self.assertIsNotNone(runner.journal.get("active"))
                self.assertEqual(broker.order_send.call_count, 1)
                # A later mutation identity check clears broker diagnostics;
                # public/persistent results must retain the original read.
                expected = dict(
                    account_read_request_started_utc=now.isoformat(),
                    account_read_observed_utc=(now + timedelta(seconds=account_delay)).isoformat(),
                    day_start_valid=captured,
                )
                if not captured:
                    expected["day_start_reason"] = "day_start_floating_unknown"
                for payload in (managed, runner.journal.get("last_result")):
                    for key, value in expected.items():
                        self.assertEqual(payload.get(key), value, (key, payload))
                    if captured:
                        self.assertNotIn("day_start_reason", payload)
                self.assertEqual(broker.account_info.call_count, 2)
                self.assertEqual(broker.terminal_info.call_count, 2)
                mark = runner.journal.get("utc_boundary_mark")
                self.assertEqual(mark is not None, captured)
                broker.account_info = Mock(return_value=None)
                next_now = now + timedelta(days=1)
                with patch("scripts.demo_runtime.runner.time.monotonic", return_value=30.0):
                    invalid = runner.cycle(now=next_now)
                for payload in (invalid, runner.journal.get("last_result")):
                    self.assertEqual(payload["reason"], "demo_identity_required")
                    self.assertEqual(
                        payload["account_read_request_started_utc"], next_now.isoformat()
                    )
                    self.assertEqual(payload["account_read_observed_utc"], next_now.isoformat())
                    self.assertNotIn("day_start_valid", payload)
                    self.assertNotIn("day_start_reason", payload)
                self.assertEqual(runner.journal.get("utc_boundary_mark"), mark)
                runner.close()
                restarted = SelectedDemoRunner(
                    mt5=broker,
                    expected_login=123,
                    expected_server="Exness-Demo",
                    journal_path=path,
                    config=selected_config(),
                    cost_policy=costs,
                    execute=True,
                )
                self.addCleanup(restarted.close)
                broker.account.equity = 150.0
                if captured:
                    baseline = restarted.broker._baseline(
                        broker.account,
                        broker.positions,
                        broker.deals,
                        midnight + timedelta(seconds=30),
                    )
                    self.assertEqual(baseline, 197.0)
                    self.assertEqual(restarted.journal.get("utc_boundary_mark"), mark)
                    self.assertEqual(
                        mark["observed_utc"], (midnight + timedelta(milliseconds=40)).isoformat()
                    )
                else:
                    with self.assertRaisesRegex(ValueError, "day_start_floating_unknown"):
                        restarted.broker._baseline(
                            broker.account,
                            broker.positions,
                            broker.deals,
                            midnight + timedelta(seconds=30),
                        )
                    self.assertIsNone(restarted.journal.get("utc_boundary_mark"))
                self.assertEqual(broker.order_send.call_count, 1)

    def test_selected_public_cycle_retains_actual_first_second_account_return(self):
        with timing_fixture(runner_class=SelectedDemoRunner) as case:
            self.assertIsInstance(case["runner"], SelectedDemoRunner)
            mark = case["runner"].journal.get("utc_boundary_mark")
            self.assertIsNotNone(mark)
            self.assertEqual(mark["request_started_utc"], EXPECTED_START)
            self.assertEqual(mark["observed_utc"], EXPECTED_RETURN)
            self.assertEqual(mark["account_fingerprint"], case["runner"].fingerprint)
            self.assertEqual(case["broker"].account_info.call_count, 1)
            self.assertEqual(case["broker"].terminal_info.call_count, 1)
            self.assertTrue(case["proof_attempts"][0]["terminal_complete"])
            self.assertTrue(case["proof_attempts"][0]["identity_journal_bound"])
            case["broker"].order_send.assert_not_called()

    def test_selected_public_cycle_rejects_slow_account_return(self):
        with timing_fixture(
            account_delay=1.1, terminal_delay=0.02, runner_class=SelectedDemoRunner
        ) as case:
            self.assertIsInstance(case["runner"], SelectedDemoRunner)
            self.assertIsNone(case["runner"].journal.get("utc_boundary_mark"))
            self.assertEqual(case["proof_attempts"], [])
            self.assertEqual(case["broker"].account_info.call_count, 1)
            case["broker"].order_send.assert_not_called()

    def test_account_return_at_exact_window_end_remains_no_proof(self):
        with timing_fixture(account_delay=0.98, terminal_delay=0.02) as case:
            self.assertIsNone(case["runner"].journal.get("utc_boundary_mark"))
            self.assertIsNone(case["runner"].journal.get("day"))
            self.assertEqual(case["proof_attempts"], [])
            self.assertEqual(case["broker"].account_info.call_count, 1)
            case["broker"].order_send.assert_not_called()

    def test_account_read_exception_has_no_fabricated_return_time_or_proof(self):
        with timing_fixture(account_exception=True) as case:
            self.assertIsNone(case["runner"].journal.get("utc_boundary_mark"))
            self.assertIsNone(case["runner"].journal.get("day"))
            self.assertEqual(case["result"]["account_read_request_started_utc"], EXPECTED_START)
            self.assertIsNone(case["result"]["account_read_observed_utc"])
            self.assertIsNone(case["runner"].broker.account_observation)
            self.assertEqual(case["proof_attempts"], [])
            self.assertEqual(case["broker"].account_info.call_count, 1)
            self.assertEqual(case["broker"].terminal_info.call_count, 0)
            case["broker"].order_send.assert_not_called()
