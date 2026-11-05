"""Same-sender evidence is optional, fresh and never an execution authority."""

from datetime import timedelta
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.c22_selected.runner import SelectedDemoRunner
from scripts.c22_selected.trial_costs import build_trial_policy
from tests.demo.test_c22_selected_runner import SelectedBroker, selected_config
from tests.demo.test_trial30_demo import policy


class SenderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "evidence"
        self.directory.mkdir()
        self.broker = SelectedBroker()
        self.broker.account.margin_mode = 2
        for key, value in dict(
            currency_profit="USD",
            swap_mode=1,
            swap_long=-490.8,
            swap_short=0.0,
            swap_rollover3days=3,
        ).items():
            setattr(self.broker.info, key, value)

    def runner(self, *, execute=False, enabled=True, journal="selected.sqlite3"):
        costs = policy() | {
            "reviewed_utc": self.broker.now.isoformat(),
            "account_type": "Standard Demo",
        }
        options = {"broker_evidence_dir": self.directory} if enabled else {}
        runner = SelectedDemoRunner(
            mt5=self.broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=self.root / journal,
            config=selected_config(),
            cost_policy=costs,
            execute=execute,
            **options,
        )
        self.addCleanup(runner.close)
        return runner

    def request(self, ident="a" * 32):
        (self.directory / "request.json").write_text(
            json.dumps({"request_id": ident, "requested_utc": self.broker.now.isoformat()})
        )

    def test_one_request_uses_existing_reads_and_packet_builds_regular_swap_policy(self):
        runner = self.runner()
        self.request()
        result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)
        self.assertEqual(result["broker_evidence"]["status"], "CAPTURED", result)
        target = self.directory / ("broker-" + "a" * 32 + ".json")
        raw = target.read_bytes()
        packet = json.loads(raw)
        self.assertEqual(packet["history_deals_total"], len(self.broker.deals))
        self.assertEqual(packet["positions"], 0)
        self.assertFalse(packet["execution_authorized"])
        self.assertFalse(packet["order_send_called"])
        self.assertNotIn("login", packet["account"])
        self.assertNotIn("comment", packet["history_deals"][0])
        self.assertEqual(packet["source"], "existing_sender_reads")
        self.assertEqual(
            result["broker_evidence"]["packet_sha256"], hashlib.sha256(raw).hexdigest()
        )
        sources = {
            k: {
                "source": "https://www.exness.com/standard-accounts/",
                "checked_utc": self.broker.now.isoformat(),
            }
            for k in ("tariff", "swap", "calendar")
        }
        candidate = build_trial_policy(raw, now=self.broker.now, sources=sources)
        self.assertEqual(candidate["swap_entitlement"], "UNKNOWN")
        self.assertEqual(candidate["research_economic_qualification"], "COST_INCONCLUSIVE")
        modified = target.stat().st_mtime_ns
        again = runner.cycle(now=self.broker.now + timedelta(seconds=1))
        self.assertEqual(again["broker_evidence"]["captured_utc"], packet["captured_utc"])
        self.assertEqual(target.stat().st_mtime_ns, modified)
        self.broker.order_send.assert_not_called()

    def test_capture_adds_no_sdk_calls_compared_with_disabled_path(self):
        from unittest.mock import Mock

        methods = (
            "account_info",
            "terminal_info",
            "positions_get",
            "orders_get",
            "history_deals_get",
            "history_deals_total",
            "symbol_info",
            "symbol_info_tick",
            "copy_rates_from_pos",
        )
        for name in methods:
            original = getattr(self.broker, name)
            setattr(self.broker, name, Mock(wraps=original))
        self.request()
        enabled = self.runner()
        enabled.cycle(now=self.broker.now)
        counts = {name: getattr(self.broker, name).call_count for name in methods}
        enabled.close()
        for name in methods:
            getattr(self.broker, name).reset_mock()
        # Same journal/start path and same completed bar; observation must add no SDK reads.
        disabled = self.runner(enabled=False, journal="disabled.sqlite3")
        disabled.cycle(now=self.broker.now)
        self.assertEqual({name: getattr(self.broker, name).call_count for name in methods}, counts)
        self.broker.order_send.assert_not_called()

    def test_native_fill_and_unknown_defer_export_without_changing_send(self):
        for response in ("fill", "unknown"):
            with self.subTest(response=response):
                self.setUp()
                if response == "unknown":
                    self.broker.order_send.side_effect = lambda _: None
                self.request()
                runner = self.runner(execute=True)
                result = runner.cycle(now=self.broker.now)
                self.assertEqual(
                    result["status"], "FILLED" if response == "fill" else "UNKNOWN", result
                )
                self.assertEqual(result["broker_evidence"]["status"], "DEFERRED")
                self.assertEqual(result["broker_evidence"]["reason"], "owned_or_uncertain_exposure")
                self.assertEqual(self.broker.order_send.call_count, 1)
                self.assertEqual(list(self.directory.glob("broker-*.json")), [])
                self.assertIsNotNone(runner.journal.get("active"))
                runner.close()

    def test_incomplete_and_disconnected_reads_never_reuse_previous_snapshot(self):
        runner = self.runner()
        self.request()
        self.assertEqual(runner.cycle(now=self.broker.now)["broker_evidence"]["status"], "CAPTURED")
        self.request("b" * 32)
        self.broker.terminal_info = lambda: type(
            "Terminal", (), {"connected": False, "trade_allowed": True, "tradeapi_disabled": False}
        )()
        result = runner.cycle(now=self.broker.now + timedelta(seconds=1))
        self.assertEqual(result["broker_evidence"]["status"], "DEFERRED")
        self.assertEqual(result["broker_evidence"]["reason"], "broker_reads_incomplete")
        self.assertEqual(list(self.directory.glob("broker-b*.json")), [])
        self.broker.order_send.assert_not_called()

    def test_bad_request_and_write_failure_are_optional_and_retryable(self):
        runner = self.runner()
        self.request("../../invalid")
        result = runner.cycle(now=self.broker.now)
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)
        self.assertEqual(result["broker_evidence"]["status"], "FAULT")
        self.assertEqual(result["operational_errors"][-1]["stage"], "evidence.export")
        self.request()
        with patch(
            "scripts.c22_selected.evidence._write_private", side_effect=OSError("secret value")
        ):
            failure = runner.cycle(now=self.broker.now + timedelta(seconds=1))
        self.assertEqual(failure["status"], "SHADOW_ADMIT", failure)
        self.assertEqual(failure["broker_evidence"]["status"], "FAULT")
        self.assertNotIn("secret value", json.dumps(failure))
        retried = runner.cycle(now=self.broker.now + timedelta(seconds=2))
        self.assertEqual(retried["broker_evidence"]["status"], "CAPTURED", retried)
        self.broker.order_send.assert_not_called()

    def test_unreconciled_history_or_pending_orders_defer_without_inventing_proof(self):
        for failure in ("cash", "volume", "orders", "empty", "halt"):
            with self.subTest(failure=failure):
                self.setUp()
                self.request()
                runner = self.runner()
                if failure == "cash":
                    self.broker.account.balance += 2
                    self.broker.account.equity += 2
                elif failure == "volume":
                    self.broker.closed_loss(self.broker.tick.time_msc - 3600000)
                    self.broker.deals.pop()
                elif failure == "orders":
                    self.broker.orders = [object()]
                elif failure == "empty":
                    self.broker.deals = []
                else:
                    runner.journal.put("safety_halt", {"reason": "UNKNOWN"})
                result = runner.cycle(now=self.broker.now)
                self.assertEqual(result["broker_evidence"]["status"], "DEFERRED", result)
                self.assertEqual(list(self.directory.glob("broker-*.json")), [])
                self.broker.order_send.assert_not_called()
                runner.close()

    def test_restart_retains_original_capture_time_and_never_turns_old_packet_fresh(self):
        self.request()
        runner = self.runner()
        first = runner.cycle(now=self.broker.now)["broker_evidence"]
        raw = (self.directory / ("broker-" + "a" * 32 + ".json")).read_bytes()
        runner.close()
        restored = self.runner()
        now = self.broker.now + timedelta(minutes=6)
        receipt = restored.cycle(now=now)["broker_evidence"]
        self.assertEqual(receipt["captured_utc"], first["captured_utc"])
        self.assertFalse(receipt["fresh_for_generation"])
        self.assertEqual(receipt["packet_sha256"], first["packet_sha256"])
        self.assertEqual((self.directory / ("broker-" + "a" * 32 + ".json")).read_bytes(), raw)
        sources = {
            k: {
                "source": "https://www.exness.com/standard-accounts/",
                "checked_utc": now.isoformat(),
            }
            for k in ("tariff", "swap", "calendar")
        }
        with self.assertRaisesRegex(ValueError, "fresh_broker_evidence_required"):
            build_trial_policy(raw, now=now, sources=sources)
        self.broker.order_send.assert_not_called()

    def test_request_after_read_start_and_slow_cycle_cannot_claim_fresh_capture(self):
        from scripts.c22_selected.evidence import export_requested

        runner = self.runner()
        runner.cycle(now=self.broker.now)
        self.request()
        request = self.directory / "request.json"
        value = json.loads(request.read_text())
        value["requested_utc"] = (self.broker.now + timedelta(seconds=1)).isoformat()
        request.write_text(json.dumps(value))
        late = export_requested(
            runner,
            self.directory,
            runner._evidence_snapshot,
            now=self.broker.now + timedelta(seconds=2),
        )
        self.assertEqual(late["reason"], "await_next_complete_read_cycle")
        self.request()
        stale = export_requested(
            runner,
            self.directory,
            runner._evidence_snapshot,
            now=self.broker.now + timedelta(minutes=5, seconds=1),
        )
        self.assertEqual(stale["reason"], "evidence_read_window_stale")
        self.assertEqual(list(self.directory.glob("broker-*.json")), [])
        self.broker.order_send.assert_not_called()

    def test_changed_release_never_relabels_prior_packet_as_current_evidence(self):
        self.request()
        runner = self.runner()
        self.assertEqual(runner.cycle(now=self.broker.now)["broker_evidence"]["status"], "CAPTURED")
        target = self.directory / ("broker-" + "a" * 32 + ".json")
        before = target.read_bytes()
        runner.release_hash = "changed"
        result = runner.cycle(now=self.broker.now + timedelta(seconds=1))
        self.assertEqual(result["broker_evidence"]["reason"], "evidence_packet_context_mismatch")
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(result["status"], "SHADOW_ADMIT")
        self.broker.order_send.assert_not_called()
