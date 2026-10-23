"""Real HTTP client against loopback stand-ins; no remote messages or orders."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest

from scripts.demo_runtime.delivery import HealthDelivery, TelegramDelivery
from scripts.demo_runtime.journal import Journal


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.received = []
        self.mode = "success"
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                owner.received.append((self.path, body))
                if owner.mode == "lost_ack":
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                if owner.mode == "timeout":
                    time.sleep(0.08)
                status = int(owner.mode) if owner.mode in ("429", "503") else 200
                self.send_response(status)
                self.end_headers()
                try:
                    payload = (
                        b"OK"
                        if self.path.startswith("/ping")
                        else b'{"ok":true,"result":{"message_id":1}}'
                    )
                    if owner.mode == "trickle":
                        for byte in payload:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(0.01)
                    else:
                        self.wfile.write(payload)
                except BrokenPipeError:
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_http_failures_preserve_outbox_across_restart_and_keep_event_id(self):
        for mode in ("429", "503", "timeout", "lost_ack"):
            with self.subTest(mode=mode):
                path = Path(self.temp.name) / (mode + ".sqlite3")
                journal = Journal(path)
                journal.event(dict(kind="FILLED", ticket=777))
                notify = TelegramDelivery("fixture", "owner", base_url=self.url, timeout=0.02)
                self.mode = mode
                with self.assertRaises(Exception):
                    journal.flush(notify)
                payload = json.loads(
                    journal.conn.execute("SELECT payload FROM events").fetchone()[0]
                )
                self.assertEqual(journal.conn.execute("SELECT sent FROM events").fetchone()[0], 0)
                journal.close()
                restarted = Journal(path)
                self.mode = "success"
                restarted.flush(TelegramDelivery("fixture", "owner", base_url=self.url))
                self.assertEqual(restarted.conn.execute("SELECT sent FROM events").fetchone()[0], 1)
                last_payload = json.loads(json.loads(self.received[-1][1])["text"])
                self.assertEqual(last_payload["event_id"], payload["event_id"])
                restarted.close()

    def test_health_failure_path_never_reports_normal_heartbeat_for_critical(self):
        health = HealthDelivery(self.url + "/ping", timeout=0.02)
        event = dict(result=dict(status="UNKNOWN", critical=True, position_protection="unknown"))
        health(event)
        self.assertEqual(self.received[-1][0], "/ping/fail")
        for mode in ("429", "503", "timeout", "lost_ack"):
            self.mode = mode
            health = HealthDelivery(self.url + "/ping", timeout=0.02)
            with self.assertRaises(Exception):
                health(event)
        self.mode = "success"
        health = HealthDelivery(self.url + "/ping", timeout=0.02)
        health(event)
        self.assertEqual(self.received[-1][0], "/ping/fail")

    def test_real_http_retry_after_runner_restart_never_resends_order(self):
        from scripts.c22h4.runner import C22H4DemoRunner
        from tests.demo.test_c22h4_demo import CandidateBroker
        from tests.demo.test_trial30_demo import policy

        broker = CandidateBroker(1)
        options = dict(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=Path(self.temp.name) / "runner.sqlite3",
            execute=True,
            cost_policy=policy() | {"reviewed_utc": broker.now.isoformat()},
        )
        runner = C22H4DemoRunner(
            **options, notify=TelegramDelivery("fixture", "owner", base_url=self.url, timeout=0.02)
        )
        self.mode = "lost_ack"
        try:
            first = runner.cycle(now=broker.now)
            self.assertEqual(first["status"], "FILLED")
            self.assertEqual(first["notification"], "pending_retry")
        finally:
            runner.close()
        self.mode = "success"
        restarted = C22H4DemoRunner(
            **options, notify=TelegramDelivery("fixture", "owner", base_url=self.url)
        )
        try:
            self.assertEqual(restarted.cycle(now=broker.now)["status"], "MANAGING")
            self.assertEqual(broker.order_send.call_count, 1)
            self.assertEqual(
                restarted.journal.conn.execute("SELECT sent FROM events").fetchone()[0], 1
            )
        finally:
            restarted.close()

    def test_delivery_backlog_is_bounded_and_health_coalesces_to_latest(self):
        journal = Journal(Path(self.temp.name) / "backlog.sqlite3")
        try:
            for seq in range(20):
                journal.audit("HEALTH", result=dict(seq=seq))
                journal.event(dict(kind="FILLED", ticket=seq))
            journal.event(dict(kind="CRITICAL"))
            health, broker = [], []
            journal.consume("health", health.append, kinds=("HEALTH",), latest=True)
            journal.consume("health", health.append, kinds=("HEALTH",), latest=True)
            self.assertEqual(len(health), 1)
            self.assertEqual(health[0]["result"]["seq"], 19)
            journal.flush(broker.append)
            self.assertEqual(len(broker), 1)
            self.assertEqual(broker[0]["kind"], "CRITICAL")
        finally:
            journal.close()

    def test_trickling_http_cannot_extend_wall_deadline_or_spawn_unbounded_workers(self):
        self.mode = "trickle"
        notify = TelegramDelivery("fixture", "owner", base_url=self.url, timeout=0.02)
        event = dict(event_id="trickle", kind="FILLED")
        started = time.monotonic()
        with self.assertRaises(Exception):
            notify(event)
        self.assertLess(time.monotonic() - started, 0.2)
        worker = notify._worker
        for _ in range(5):
            with self.assertRaises(Exception):
                notify(event)
        self.assertIs(notify._worker, worker)
