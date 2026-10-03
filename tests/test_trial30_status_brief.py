"""Operator summary for trial30 journal status."""

import unittest

from scripts.ops.trial30_status import format_brief


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
        self.assertIn("ส่งออเดอร์: ได้", text)
        self.assertIn("สัญญาณล่าสุด: เมื่อกี้", text)
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
        self.assertIn("สัญญาณล่าสุด: ค้าง 90 วินาที", text)
        self.assertIn("ไม้ที่เปิด: FILLED ticket 4808795122 ราคา 4162.791", text)
        self.assertIn("หยุดฉุกเฉิน: filled_risk_violation", text)
        self.assertIn("เหตุการณ์โบรกเกอร์: FILLED ticket 4808795122", text)
        self.assertIn("โปรเซส: ไม่ได้รัน", text)


if __name__ == "__main__":
    unittest.main()
