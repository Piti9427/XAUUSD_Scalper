"""UTC equity evidence is collected before entry gates, never invented later."""

from datetime import datetime, timedelta, timezone
from contextlib import closing, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from scripts.demo_runtime.broker import BrokerView
from scripts.demo_runtime.journal import Journal
from scripts.trial30.runner import Trial30DemoRunner
from tests.demo.test_trial30_demo import Broker, NOW, policy


MIDNIGHT = datetime(2026, 10, 2, tzinfo=timezone.utc)


class BoundaryCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "boundary.sqlite3"
        self.journal = Journal(self.path)
        self.addCleanup(self.journal.close)
        self.view = BrokerView(None, 123, "Exness-Demo", "XAUUSDm", "fixture", self.journal)
        self.account = NS(balance=200.0, equity=197.0)
        self.positions = [NS(identifier=777, type=1, volume=0.01)]
        self.deals = [
            NS(
                ticket=1,
                type=2,
                entry=0,
                volume=0.0,
                position_id=0,
                time_msc=int((MIDNIGHT - timedelta(days=1)).timestamp() * 1000),
                profit=200.0,
                commission=0.0,
                swap=0.0,
                fee=0.0,
            ),
            NS(
                ticket=2,
                type=1,
                entry=0,
                volume=0.01,
                position_id=777,
                time_msc=int((MIDNIGHT - timedelta(minutes=1)).timestamp() * 1000),
                profit=0.0,
                commission=0.0,
                swap=0.0,
                fee=0.0,
            ),
        ]

    def capture(self, **changes):
        args = dict(
            request_started=MIDNIGHT + timedelta(milliseconds=10),
            observed=MIDNIGHT + timedelta(milliseconds=200),
        )
        return self.view.capture_boundary(self.account, **(args | changes))

    def test_persisted_boundary_equity_recovers_later_held_baseline_after_restart(self):
        self.assertTrue(self.capture())
        self.journal.close()
        self.journal = Journal(self.path)
        self.addCleanup(self.journal.close)
        restarted = BrokerView(None, 123, "Exness-Demo", "XAUUSDm", "fixture", self.journal)
        self.account.equity = 150.0
        result = restarted._baseline(
            self.account, self.positions, self.deals, MIDNIGHT + timedelta(seconds=30)
        )
        self.assertEqual(result, 197.0)
        day = self.journal.get("day")
        self.assertEqual(day["source"], "captured_at_utc_boundary")
        self.assertEqual(day["boundary_observed_utc"], "2026-10-02T00:00:00.200000+00:00")
        rows = self.journal.conn.execute("SELECT payload FROM audit_events").fetchall()
        self.assertTrue(any("utc_boundary_mark" in row[0] for row in rows))

    def test_late_missing_or_cross_boundary_read_never_latches_current_equity(self):
        for changes in (
            dict(
                request_started=MIDNIGHT + timedelta(seconds=30),
                observed=MIDNIGHT + timedelta(seconds=31),
            ),
            dict(request_started=MIDNIGHT - timedelta(milliseconds=20)),
            dict(observed=MIDNIGHT + timedelta(seconds=1)),
            dict(observed=MIDNIGHT),
        ):
            with self.subTest(changes=changes):
                self.assertFalse(self.capture(**changes))
                self.assertIsNone(self.journal.get("utc_boundary_mark"))
        with self.assertRaisesRegex(ValueError, "day_start_floating_unknown"):
            self.view._baseline(
                self.account, self.positions, self.deals, MIDNIGHT + timedelta(seconds=30)
            )

    def test_first_proven_mark_is_never_overwritten_by_later_equity(self):
        self.assertTrue(self.capture())
        self.account.equity = 300.0
        self.assertFalse(self.capture(observed=MIDNIGHT + timedelta(milliseconds=800)))
        self.assertEqual(self.journal.get("utc_boundary_mark")["equity"], 197.0)

    def test_previous_day_proof_cannot_reset_a_later_held_midnight_baseline(self):
        self.assertTrue(self.capture())
        self.account.equity = 150.0
        with self.assertRaisesRegex(ValueError, "day_start_floating_unknown"):
            self.view._baseline(
                self.account,
                self.positions,
                self.deals,
                MIDNIGHT + timedelta(days=1, seconds=30),
            )
        self.assertIsNone(self.journal.get("day"))
        self.assertEqual(self.journal.get("utc_boundary_mark")["day"], MIDNIGHT.date().isoformat())

    def test_wrong_account_malformed_or_nonfinite_proof_cannot_supply_baseline(self):
        self.capture()
        original = self.journal.get("utc_boundary_mark")
        for changes in (
            {"account_fingerprint": "other"},
            {"equity": -1.0},
            {"request_started_utc": "2026-10-02T00:00:00"},
            {"source": "restart_equity"},
        ):
            with self.subTest(changes=changes):
                self.journal.put("utc_boundary_mark", original | changes)
                with self.assertRaisesRegex(ValueError, "invalid_boundary_mark"):
                    self.view._baseline(
                        self.account, self.positions, self.deals, MIDNIGHT + timedelta(seconds=30)
                    )
        self.journal.put("utc_boundary_mark", original)
        self.account.equity = float("nan")
        # No new invalid value may replace the first proof.
        self.assertFalse(self.capture())

    def test_public_cycle_captures_verified_equity_even_when_quote_is_stale(self):
        broker = Broker()
        runner = Trial30DemoRunner(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=Path(self.temp.name) / "runner.sqlite3",
            cost_policy=policy(),
            execute=True,
        )
        self.addCleanup(runner.close)
        result = runner.cycle(now=MIDNIGHT + timedelta(milliseconds=20))
        self.assertEqual(result["reason"], "quote_stale")
        mark = runner.journal.get("utc_boundary_mark")
        self.assertIsNotNone(mark)
        self.assertEqual(mark["equity"], 200.0)
        self.assertEqual(mark["account_fingerprint"], runner.fingerprint)
        broker.order_send.assert_not_called()

    def test_public_cycle_sdk_response_after_first_second_cannot_supply_a_boundary_mark(self):
        broker = Broker()
        runner = Trial30DemoRunner(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=Path(self.temp.name) / "slow-sdk.sqlite3",
            cost_policy=policy(),
            execute=True,
        )
        self.addCleanup(runner.close)
        samples = iter([10.0, 11.1])
        with patch(
            "scripts.demo_runtime.runner.time.monotonic", side_effect=lambda: next(samples, 11.1)
        ):
            result = runner.cycle(now=MIDNIGHT + timedelta(milliseconds=20))
        self.assertEqual(result["reason"], "quote_stale")
        self.assertIsNone(runner.journal.get("utc_boundary_mark"))
        broker.order_send.assert_not_called()

    def test_poll_deadline_aligns_to_next_utc_boundary_without_daytime_busy_loop(self):
        from scripts.demo_runtime.boundary import poll_delay

        self.assertAlmostEqual(poll_delay(1.0, MIDNIGHT - timedelta(milliseconds=250)), 0.26)
        self.assertEqual(poll_delay(1.0, MIDNIGHT + timedelta(hours=12)), 1.0)
        self.assertEqual(poll_delay(1.0, MIDNIGHT + timedelta(milliseconds=200)), 1.0)
        with self.assertRaises(ValueError):
            poll_delay(1.0, MIDNIGHT.replace(tzinfo=None))

    def test_malformed_boundary_mark_cannot_stop_active_management_or_proven_close(self):
        broker = Broker()
        runner = Trial30DemoRunner(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=Path(self.temp.name) / "active.sqlite3",
            cost_policy=policy(),
            execute=True,
        )
        self.addCleanup(runner.close)
        self.assertEqual(runner.cycle(now=NOW)["status"], "FILLED")
        original_day = runner.journal.get("day")
        runner.journal.put("utc_boundary_mark", {"version": 1, "source": "malformed-fixture"})
        now = MIDNIGHT + timedelta(milliseconds=20)
        broker.tick.time_msc = int(now.timestamp() * 1000)
        managed = runner.cycle(now=now)
        self.assertEqual(managed["status"], "MANAGING", managed)
        self.assertIsNotNone(runner.journal.get("active"))
        self.assertEqual(runner.journal.get("day"), original_day)
        self.assertEqual(broker.order_send.call_count, 1)
        opening = broker.deals[-1]
        broker.positions = []
        broker.deals.append(
            NS(
                **(
                    vars(opening)
                    | {
                        "ticket": 3,
                        "entry": 1,
                        "type": 0,
                        "profit": -1.0,
                        "time_msc": int(now.timestamp() * 1000),
                        "time": int(now.timestamp()),
                        "comment": "[sl]",
                        "price": broker.tick.ask,
                    }
                )
            )
        )
        broker.account.balance = broker.account.equity = 199.0
        closed = runner.cycle(now=now)
        self.assertEqual(closed["status"], "CLOSED", closed)
        self.assertIsNone(runner.journal.get("active"))
        self.assertFalse(closed["day_start_valid"])
        self.assertEqual(broker.order_send.call_count, 1)
        audit = [
            json.loads(row[0])
            for row in runner.journal.conn.execute("SELECT payload FROM audit_events")
        ]
        self.assertTrue(any(row["kind"] == "BOUNDARY_CAPTURE_BLOCKED" for row in audit))

    def test_cli_timestamps_cycle_after_a_cost_reload_that_crosses_capture_window(self):
        from scripts.demo_runtime import cli

        broker = Broker()
        broker.initialize = Mock(return_value=True)
        broker.shutdown = Mock()
        root = Path(self.temp.name)
        cost = root / "cost.json"
        cost.write_text(json.dumps(policy()))
        journal = root / "cli.sqlite3"
        current = MIDNIGHT + timedelta(milliseconds=20)
        reads = 0
        read_text = Path.read_text

        def delayed_policy_read(path, *args, **kwargs):
            nonlocal current, reads
            if path == cost:
                reads += 1
                if reads == 2:
                    # Initial policy load has completed. The loop reload spans
                    # midnight's first second before any SDK account read.
                    current += timedelta(seconds=2)
            return read_text(path, *args, **kwargs)

        def isolated_runner(**kwargs):
            kwargs["account_guard_dir"] = root / "guard"
            return Trial30DemoRunner(**kwargs)

        with (
            patch.dict(
                "os.environ",
                {
                    "XAUUSD_MT5_LOGIN": "123",
                    "XAUUSD_MT5_SERVER": "Exness-Demo",
                    "XAUUSD_MT5_PASSWORD": "fixture",
                },
                clear=True,
            ),
            patch.object(Path, "read_text", delayed_policy_read),
            patch.object(cli, "clock_now", side_effect=lambda: current),
            redirect_stdout(io.StringIO()),
        ):
            result = cli.main(
                [
                    "--once",
                    "--journal",
                    str(journal),
                    "--cost-policy",
                    str(cost),
                ],
                mt5=broker,
                runner_class=isolated_runner,
            )
        self.assertEqual(result, 1)
        self.assertEqual(reads, 2)
        with closing(sqlite3.connect(journal)) as connection:
            self.assertIsNone(
                connection.execute("SELECT value FROM kv WHERE key='utc_boundary_mark'").fetchone()
            )
            latest = json.loads(
                connection.execute("SELECT value FROM kv WHERE key='last_result'").fetchone()[0]
            )
        self.assertEqual(latest["captured_utc"], current.isoformat())
        self.assertEqual(latest["reason"], "quote_stale")
        broker.order_send.assert_not_called()
        broker.shutdown.assert_called_once()
