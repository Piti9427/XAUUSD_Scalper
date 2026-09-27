"""Regression cases from the 2026-09-27 implementation review; offline only."""

import json
import fcntl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts.b1_outbox import consume
from scripts.research import b1_final_release as release
from tests import test_b1_final_release as fixtures
from tests.test_b1_outbox import RecordingSink, event

close_event = fixtures.close_event


class ReviewRegressions(unittest.TestCase):
    def test_missing_offsetting_closes_fail_reconciliation(self):
        deals = pd.DataFrame(
            {
                "position": [1, 1, 2, 2],
                "entry": [0, 1, 0, 1],
                "volume": [0.01] * 4,
                "type": [0, 1, 0, 1],
                "profit": [0.0, 100.0, 0.0, -100.0],
                "commission": [0.0] * 4,
                "swap": [0.0] * 4,
            }
        )
        self.assertFalse(
            release.reconcile(release.ledger_from_events([]), deals, 1000.0, 1000.0)["passed"]
        )

    def test_reconciliation_checks_identity_not_only_sum(self):
        deals = pd.DataFrame(
            {
                "position": [1, 1, 2, 2],
                "entry": [0, 1, 0, 1],
                "volume": [0.01] * 4,
                "type": [0, 1, 0, 1],
                "profit": [0.0, 100.0, 0.0, -100.0],
                "commission": [0.0] * 4,
                "swap": [0.0] * 4,
            }
        )
        events = [close_event("a", 100.0, 10.0), close_event("b", -100.0, 10.0)]
        for e, pid in zip(events, [1, 2]):
            e["fields"]["position_identifier"] = pid
            e["fields"]["volume"] = 0.01
            e["event_id"] = f"close-{pid}"
        ledger = release.ledger_from_events(events)
        self.assertTrue(release.reconcile(ledger, deals, 1000.0, 1000.0)["passed"])
        events[1]["fields"]["position_identifier"] = 3
        self.assertFalse(
            release.reconcile(release.ledger_from_events(events), deals, 1000.0, 1000.0)["passed"]
        )

    def test_duplicate_signal_fails_parity(self):
        bars = fixtures.ReleaseTests().bars()
        epoch = int(bars.bar_open_epoch.iloc[-1])
        signal = {"type": "SIGNAL", "fields": {"bar_open_utc_epoch": epoch, "direction": 1}}
        self.assertTrue(release.signal_parity(bars, [signal], epoch)["passed"])
        self.assertFalse(release.signal_parity(bars, [signal, signal], epoch)["passed"])

    def test_crash_after_acceptance_becomes_unknown_without_resend(self):
        class CrashSink:
            calls = 0

            def send(self, text):
                self.calls += 1
                raise SystemExit("crash after remote acceptance")

        with tempfile.TemporaryDirectory() as folder:
            events, state = Path(folder) / "events.jsonl", Path(folder) / "state.json"
            events.write_text(json.dumps(event("f", "FILL_CONFIRMED", True)) + "\n")
            sink = CrashSink()
            with self.assertRaises(SystemExit):
                consume(events, state, sink)
            consume(events, state, sink)
            self.assertEqual(sink.calls, 1)
            self.assertEqual(json.loads(state.read_text())["events"]["f"], "DELIVERY_UNKNOWN")

    def test_unknown_exception_after_acceptance_is_not_retried(self):
        class AmbiguousSink:
            calls = 0

            def send(self, text):
                self.calls += 1
                raise RuntimeError("response decoding failed after send")

        with tempfile.TemporaryDirectory() as folder:
            events, state = Path(folder) / "events.jsonl", Path(folder) / "state.json"
            events.write_text(json.dumps(event("f", "FILL_CONFIRMED", True)) + "\n")
            sink = AmbiguousSink()
            consume(events, state, sink)
            consume(events, state, sink)
            self.assertEqual(sink.calls, 1)
            self.assertEqual(json.loads(state.read_text())["events"]["f"], "DELIVERY_UNKNOWN")

    def test_health_requires_trusted_no_incident_no_outbox_loss(self):
        clean = {
            "summary": {
                "trusted": 1,
                "incident": 0,
                "outbox_write_failures": 0,
                "pending_confirmed_events": 0,
            },
            "reconciliation": {"passed": True},
            "signal_parity": {"passed": True},
        }
        self.assertTrue(release.implementation_run_passed(clean))
        for key, value in [
            ("trusted", 0),
            ("incident", 1),
            ("outbox_write_failures", 1),
            ("pending_confirmed_events", 1),
        ]:
            dirty = dict(clean, summary=dict(clean["summary"], **{key: value}))
            self.assertFalse(release.implementation_run_passed(dirty))
        self.assertFalse(release.implementation_run_passed(dict(clean, summary={})))

    def test_consumer_lock_rejects_concurrent_send(self):
        with tempfile.TemporaryDirectory() as folder:
            events, state = Path(folder) / "events.jsonl", Path(folder) / "state.json"
            events.write_text(json.dumps(event("f", "FILL_CONFIRMED", True)) + "\n")
            sink = RecordingSink()
            with Path(str(state) + ".lock").open("a") as owner:
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    consume(events, state, sink)
            self.assertEqual(sink.cards, [])

    def test_failed_state_persistence_never_submits_card(self):
        with tempfile.TemporaryDirectory() as folder:
            events, state = Path(folder) / "events.jsonl", Path(folder) / "state.json"
            events.write_text(json.dumps(event("f", "FILL_CONFIRMED", True)) + "\n")
            sink = RecordingSink()
            with patch("scripts.b1_outbox.save_state", side_effect=OSError("disk unavailable")):
                with self.assertRaises(OSError):
                    consume(events, state, sink)
            self.assertEqual(sink.cards, [])

    def test_missing_chronological_block_cannot_qualify_exit(self):
        base = {
            "trades": 50,
            "total_net_r": 5.0,
            "return_pct": 5.0,
            "expectancy_r": 0.1,
            "profit_factor": 1.2,
            "max_dd_pct": 8.0,
            "hard_stop": False,
            "blocks": {"a": 1.0, "b": 1.0, "c": None},
        }
        variant = dict(
            base, total_net_r=6.0, return_pct=6.0, blocks={"a": 2.0, "b": 2.0, "c": None}
        )
        self.assertFalse(release.exit_gate(base, variant)["passed"])

    def test_duplicate_close_cannot_hide_missing_position(self):
        deals = pd.DataFrame(
            {
                "position": [1, 1, 2, 2],
                "entry": [0, 1, 0, 1],
                "volume": [0.01] * 4,
                "type": [0, 1, 0, 1],
                "profit": [0.0, 100.0, 0.0, 100.0],
                "commission": [0.0] * 4,
                "swap": [0.0] * 4,
            }
        )
        e = close_event("a", 100.0, 10.0)
        e["fields"].update(position_identifier=1, volume=0.01)
        e["event_id"] = "close-1"
        self.assertFalse(
            release.reconcile(release.ledger_from_events([e, e]), deals, 1000.0, 1200.0)["passed"]
        )

    def test_posthoc_reserves_cannot_qualify_replay(self):
        ledger = release.ledger_from_events(
            [close_event("BASE|1|1", 1000.0, 100.0), close_event("BASE|2|1", -500.0, 100.0)]
        )
        variant = release.ledger_from_events(
            [close_event("BE|1|1", 1001.0, 100.0), close_event("BE|2|1", -500.0, 100.0)]
        )
        base_run, variant_run = {"run": "base", "metrics": {}}, {"run": "be", "metrics": {}}
        for key, reserve, adverse in release.SCENARIOS:
            base_run["metrics"][key] = dict(
                release.metrics(ledger, 10000.0, 0.08, False, reserve, adverse),
                blocks={"a": 1.0, "b": 1.0, "c": 1.0},
            )
            variant_run["metrics"][key] = dict(
                release.metrics(variant, 10000.0, 0.07, False, reserve, adverse),
                blocks={"a": 2.0, "b": 2.0, "c": 1.0},
            )
        result = release.compare_exits(base_run, variant_run, ledger, variant)
        self.assertFalse(result["passed_required"])
        self.assertEqual(result["validation_status"], "INCOMPLETE_REPLAY_STRESS")


if __name__ == "__main__":
    unittest.main()
