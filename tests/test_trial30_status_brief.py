"""Operator summary for trial30 journal status."""

import hashlib
import json
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.ops.trial30_status import format_brief, load_report
from test_trial30_demo import policy


def report(**overrides):
    base = dict(
        last_result=dict(
            status="WAIT",
            reason="duplicate_bar",
            execute=True,
            snapshot="RESEARCH-D48-SELL-BE1R-20261001-T030",
        ),
        heartbeat_age_seconds=0.8,
        day={"day": "2026-10-01", "equity": 200.0},
        active=None,
        safety_halt=None,
        broker_events=[],
    )
    base.update(overrides)
    return base


class Trial30StatusBriefTest(unittest.TestCase):
    def test_waiting_watcher_is_short(self):
        text = format_brief(report(), [("watcher", "3527"), ("wine", "3528")])
        self.assertIn("สถานะ: รอ — แท่งนี้ตรวจไปแล้ว", text)
        self.assertIn("โหมดส่งออเดอร์: execution (เปิดส่ง)", text)
        self.assertIn("ความพร้อมรับไม้: ยังไม่ยืนยัน", text)
        self.assertIn("heartbeat ล่าสุด: เมื่อกี้", text)
        self.assertIn("ไม้ที่เปิด: ไม่มี", text)
        self.assertIn("หยุดฉุกเฉิน: ไม่มี", text)
        self.assertIn("equity วันนี้: 200.00 (2026-10-01)", text)
        self.assertIn("เหตุการณ์โบรกเกอร์: ไม่มี", text)
        self.assertIn("โปรเซส: watcher 3527, wine 3528", text)
        self.assertNotIn("opt/homebrew", text)

    def test_stale_open_position_keeps_ticket(self):
        text = format_brief(
            report(
                heartbeat_age_seconds=90,
                active={"status": "FILLED", "ticket": 4808795122, "fill": 4162.791},
                broker_events=[{"kind": "FILLED", "ticket": 4808795122}],
                safety_halt="filled_risk_violation",
            ),
            [],
        )
        self.assertIn("heartbeat ล่าสุด: ค้าง 90 วินาที", text)
        self.assertIn("ไม้ที่เปิด: FILLED ticket 4808795122 ราคา 4162.791", text)
        self.assertIn("หยุดฉุกเฉิน: filled_risk_violation", text)
        self.assertIn("เหตุการณ์โบรกเกอร์: FILLED ticket 4808795122", text)
        self.assertIn("โปรเซส: ไม่ได้รัน", text)

    def load_with_cost(
        self, *, stale=False, execute=True, missing=False, missing_identity=False, last_block=None
    ):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        path = root / "cost.json"
        raw = policy()
        if missing_identity:
            raw["account_fingerprint"] = None
        if not missing:
            path.write_text(json.dumps(raw))
        now = datetime(2026, 10, 3 if stale else 1, 1, tzinfo=timezone.utc)
        conn = sqlite3.connect(root / "journal.sqlite3")
        self.addCleanup(conn.close)
        conn.executescript(
            "CREATE TABLE kv(key TEXT PRIMARY KEY,value TEXT);"
            "CREATE TABLE events(id INTEGER PRIMARY KEY,payload TEXT,sent INTEGER);"
        )
        values = {
            "identity": raw["account_fingerprint"],
            "last_result": report()["last_result"]
            | {
                "captured_utc": now.isoformat(),
                "reason": "no_signal",
                "execute": execute,
            },
        }
        if last_block is not None:
            values["trade_block_note"] = last_block
        conn.executemany(
            "INSERT INTO kv VALUES (?,?)",
            [(key, json.dumps(value)) for key, value in values.items()],
        )
        conn.commit()
        changes = conn.total_changes
        before = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        result = load_report(conn, cost_policy_path=path, now=now)
        self.assertEqual(conn.total_changes, changes)
        if before:
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        return result

    def test_expired_policy_is_visible_even_without_signal_and_is_not_refreshed(self):
        result = self.load_with_cost(stale=True)
        self.assertEqual(result["cost_policy"]["status"], "BLOCKED")
        self.assertEqual(result["entry_readiness"]["reason"], "cost_policy_invalid_or_stale")
        text = format_brief(result, [("watcher", "1")])
        self.assertIn("โหมดส่งออเดอร์: execution (เปิดส่ง)", text)
        self.assertIn("ความพร้อมรับไม้: ไม่พร้อม — cost_policy_invalid_or_stale", text)
        self.assertIn("2026-10-02T00:00:00+00:00", text)

    def test_fresh_local_policy_does_not_claim_broker_order_readiness(self):
        result = self.load_with_cost()
        self.assertEqual(result["cost_policy"]["status"], "VALID")
        self.assertEqual(result["entry_readiness"]["status"], "UNVERIFIED")
        self.assertEqual(result["entry_readiness"]["reason"], "awaiting_signal_and_broker_checks")
        self.assertIn("ความพร้อมรับไม้: ยังไม่ยืนยัน", format_brief(result, []))

    def test_missing_explicit_policy_reports_source_and_blocks_readiness(self):
        result = self.load_with_cost(missing=True)
        self.assertEqual(result["cost_policy"]["source"], "explicit")
        self.assertEqual(result["entry_readiness"]["reason"], "cost_policy_unreadable")

    def test_shadow_with_valid_costs_still_has_no_execution_readiness(self):
        result = self.load_with_cost(execute=False)
        self.assertEqual(result["cost_policy"]["status"], "VALID")
        self.assertEqual(result["entry_readiness"]["reason"], "shadow_mode")
        self.assertIn("โหมดส่งออเดอร์: shadow (ไม่ส่ง)", format_brief(result, []))

    def test_missing_journal_identity_never_attests_cost_file(self):
        result = self.load_with_cost(missing_identity=True)
        self.assertEqual(result["cost_policy"]["status"], "BLOCKED")
        self.assertEqual(result["entry_readiness"]["reason"], "cost_policy_identity_unknown")

    def test_process_scoped_baseline_block_is_history_not_current_readiness(self):
        result = self.load_with_cost(last_block="2026-09-30|day_start_floating_unknown")
        self.assertEqual(result["entry_readiness"]["reason"], "awaiting_signal_and_broker_checks")
        text = format_brief(result, [("watcher", "1")])
        self.assertIn("blocker ล่าสุดที่บันทึก: 2026-09-30 — day_start_floating_unknown", text)
        self.assertIn("baseline equity ต้นวัน UTC ไม่ครบตาม process-scoped policy", text)
        self.assertIn("ความพร้อมรับไม้: ยังไม่ยืนยัน", text)


if __name__ == "__main__":
    unittest.main()
