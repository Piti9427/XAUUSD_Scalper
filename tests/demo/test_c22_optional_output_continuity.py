"""Optional cache faults retain public financial-cycle and owned-manager truth."""

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from scripts.c22_selected import strategy as selected_strategy
from tests.demo import test_c22_identity_diagnostics as identity_fixtures
from tests.demo.test_c22_selected_runner import SelectedBroker


class OptionalOutputContinuityTests(unittest.TestCase):
    def setUp(self):
        self.helper = identity_fixtures.IdentityDiagnosticsTests()
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)

    def runner(self, sdk, name):
        runner = self.helper.runner(sdk, name)
        runner.cache_output = Path(self.helper.temp.name) / name / "bars.csv"
        runner.strategy.cache_path = runner.cache_output
        return runner

    @staticmethod
    def cycle(runner, now):
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            return runner.cycle(now=now)

    @staticmethod
    def entry_sends(sdk):
        return sum(call.args[0]["action"] == sdk.TRADE_ACTION_DEAL
                   for call in sdk.order_send.call_args_list)

    def assert_operational_failure(self, runner, result, *, code, stage):
        records = result["operational_errors"]
        self.assertEqual(len(records), 1, records)
        self.assertEqual(records[0]["code"], code)
        self.assertEqual(records[0]["stage"], stage)
        self.assertNotIn("private-fixture", json.dumps(records))
        stored = runner.journal.get("last_result")
        self.assertEqual(stored["status"], result["status"])
        self.assertEqual(stored["operational_errors"], records)
        events = [json.loads(row[0]) for row in runner.journal.conn.execute(
            "SELECT payload FROM audit_events WHERE json_extract(payload,'$.kind')="
            "'OPERATIONAL_FAILURE' ORDER BY id")]
        self.assertEqual(events[-1]["financial_status"], result["status"])
        self.assertEqual(events[-1]["diagnostic"], records[0])
        self.assertEqual(events[-1]["correlation_id"],
                         runner.journal.audit_context["correlation_id"])

    def test_export_fault_after_fill_retains_manager_and_no_resend_across_restart(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                sdk = SelectedBroker(direction)
                name = f"fill-export-{direction}"
                runner = self.runner(sdk, name)
                runner.export_cache = Mock(side_effect=OSError("private-fixture-disk-full"))
                first = self.cycle(runner, sdk.now)
                self.assertEqual(first["status"], "FILLED", first)
                self.assert_operational_failure(runner, first, code="cache_export_failed",
                                                stage="cache.export")
                active = deepcopy(runner.journal.get("active"))
                day = deepcopy(runner.journal.get("day"))
                self.assertIsNotNone(active)
                self.assertEqual(len(sdk.positions), 1)
                self.assertEqual(self.entry_sends(sdk), 1)
                following = self.cycle(runner, sdk.now + timedelta(seconds=1))
                self.assertEqual(following["status"], "MANAGING", following)
                self.assert_operational_failure(runner, following, code="cache_export_failed",
                                                stage="cache.export")
                self.assertEqual(runner.journal.get("active"), active)
                self.assertEqual(runner.journal.get("day"), day)
                runner.close()
                restarted = self.runner(sdk, name)
                result = self.cycle(restarted, sdk.now + timedelta(seconds=2))
                self.assertEqual(result["status"], "MANAGING", result)
                self.assertEqual(restarted.journal.get("active"), active)
                self.assertEqual(restarted.journal.get("day"), day)
                self.assertEqual(self.entry_sends(sdk), 1)

    def test_export_fault_after_be_preserves_confirmed_protection_and_broker_close(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                sdk = SelectedBroker(direction)
                runner = self.runner(sdk, f"be-export-{direction}")
                self.assertEqual(self.cycle(runner, sdk.now)["status"], "FILLED")
                sdk.tick.bid += direction * 10
                sdk.tick.ask += direction * 10
                sdk.next_bar()
                runner.export_cache = Mock(side_effect=OSError("private-fixture-export"))
                protected = self.cycle(runner, sdk.now)
                self.assertEqual(protected["status"], "BE_MOVED", protected)
                self.assertEqual(protected["position_protection"], "confirmed")
                self.assert_operational_failure(runner, protected, code="cache_export_failed",
                                                stage="cache.export")
                self.assertEqual(self.entry_sends(sdk), 1)
                self.assertEqual(sdk.order_send.call_count, 2)
                self.assertEqual(self.cycle(runner, sdk.now)["status"], "MANAGING")
                self.assertEqual(sdk.order_send.call_count, 2)
                sdk.now += timedelta(seconds=15)
                sdk.tick.time_msc = int(sdk.now.timestamp() * 1000)
                sdk.send(dict(action=1, position=777, type=1 if direction == 1 else 0,
                              volume=0.01, price=sdk.tick.bid if direction == 1 else sdk.tick.ask))
                closed = self.cycle(runner, sdk.now)
                self.assertEqual(closed["status"], "CLOSED", closed)
                self.assertIsNone(runner.journal.get("active"))
                self.assertEqual(closed["position_protection"], "flat")
                self.assert_operational_failure(runner, closed, code="cache_export_failed",
                                                stage="cache.export")
                self.assertEqual(self.entry_sends(sdk), 1)

    def test_failed_export_skips_checkpoint_and_preserves_previous_valid_cache(self):
        sdk = SelectedBroker()
        runner = self.runner(sdk, "preserve-cache")
        self.assertEqual(self.cycle(runner, sdk.now)["status"], "FILLED")
        prior_csv = runner.cache_output.read_bytes()
        prior_meta = runner.cache_output.with_suffix(".csv.meta.json").read_bytes()
        with patch.object(runner.strategy.cache.bars, "to_csv",
                          side_effect=OSError("private-fixture-disk-full")), \
                patch.object(runner.strategy, "checkpoint", wraps=runner.strategy.checkpoint) as checkpoint:
            # Force a CSV retry without changing any market or financial input.
            runner._cache_export = None
            result = self.cycle(runner, sdk.now + timedelta(seconds=1))
        self.assertEqual(result["status"], "MANAGING", result)
        checkpoint.assert_not_called()
        self.assertEqual(runner.cache_output.read_bytes(), prior_csv)
        self.assertEqual(runner.cache_output.with_suffix(".csv.meta.json").read_bytes(), prior_meta)
        self.assertEqual(self.entry_sends(sdk), 1)

    def test_checkpoint_fault_is_durable_same_cycle_and_retry_restores_seed_provenance(self):
        sdk = SelectedBroker()
        runner = self.runner(sdk, "metadata")
        with patch("scripts.c22_selected.strategy.save_manifest",
                   side_effect=OSError("private-fixture-metadata")):
            first = self.cycle(runner, sdk.now)
        self.assertEqual(first["status"], "FILLED", first)
        self.assertEqual(first["history_seed_status"], "checkpoint_failed")
        self.assertEqual(runner.strategy.history_seed_status, "checkpoint_failed")
        self.assert_operational_failure(runner, first, code="cache_checkpoint_failed",
                                        stage="cache.checkpoint")
        with patch("scripts.c22_selected.strategy.save_manifest",
                   wraps=selected_strategy.save_manifest) as save:
            retried = self.cycle(runner, sdk.now + timedelta(seconds=1))
        self.assertEqual(retried["status"], "MANAGING", retried)
        self.assertEqual(save.call_count, 1)
        self.assertEqual(retried["history_seed_status"], "missing")
        self.assertEqual(runner.strategy.history_seed_status, "missing")
        self.assertNotIn("operational_errors", retried)
        self.assertEqual(self.entry_sends(sdk), 1)

    def test_existing_metadata_survives_checkpoint_fault_and_unexpected_fault_is_isolated(self):
        sdk = SelectedBroker()
        runner = self.runner(sdk, "metadata-existing")
        self.assertEqual(self.cycle(runner, sdk.now)["status"], "FILLED")
        meta = runner.cache_output.with_suffix(".csv.meta.json")
        prior = meta.read_bytes()
        meta.write_bytes(prior)  # A changed file signature requires metadata re-verification.
        with patch("scripts.c22_selected.strategy.save_manifest",
                   side_effect=ValueError("private-fixture-metadata-invalid")):
            result = self.cycle(runner, sdk.now + timedelta(seconds=1))
        self.assertEqual(result["status"], "MANAGING", result)
        self.assertEqual(meta.read_bytes(), prior)
        self.assert_operational_failure(runner, result, code="cache_checkpoint_failed",
                                        stage="cache.checkpoint")
        with patch.object(runner.strategy, "checkpoint",
                          side_effect=RuntimeError("private-fixture-unexpected-metadata")):
            unexpected = self.cycle(runner, sdk.now + timedelta(seconds=2))
        self.assertEqual(unexpected["status"], "MANAGING", unexpected)
        self.assert_operational_failure(runner, unexpected, code="cache_checkpoint_failed",
                                        stage="cache.checkpoint")
        self.assertEqual(self.entry_sends(sdk), 1)

    def test_financial_journal_failure_is_not_swallowed_as_optional_output_failure(self):
        sdk = SelectedBroker()
        runner = self.runner(sdk, "financial")
        self.assertEqual(self.cycle(runner, sdk.now)["status"], "FILLED")
        active = deepcopy(runner.journal.get("active"))
        real_put = runner.journal.put

        def failing_financial_put(key, value):
            if key == "protection_unknown_since":
                raise OSError("private-fixture-financial-write")
            return real_put(key, value)

        runner.export_cache = Mock()
        with patch.object(runner.journal, "put", side_effect=failing_financial_put):
            with self.assertRaises(OSError):
                self.cycle(runner, sdk.now + timedelta(seconds=1))
        runner.export_cache.assert_not_called()
        self.assertEqual(runner.journal.get("active"), active)
        self.assertEqual(self.entry_sends(sdk), 1)
