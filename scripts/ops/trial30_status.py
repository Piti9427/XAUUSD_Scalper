"""Read-only local trial30 status; no Wine/broker APIs or secrets."""

import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
from datetime import datetime, timezone


STATUS_TEXT = {
    "WAIT": "รอ",
    "BLOCKED": "รับไม้ใหม่ไม่ได้",
    "FILLED": "มีไม้เปิด",
    "CLOSED": "ปิดไม้แล้ว",
    "UNKNOWN": "รอโบรกเกอร์ยืนยัน",
    "REJECTED": "คำสั่งถูกปฏิเสธ",
    "SHADOW_ADMIT": "ผ่านเกต แต่ไม่ได้ส่งออเดอร์",
    "STOPPED": "หยุดแล้ว",
}
REASON_TEXT = {
    "duplicate_bar": "แท่งนี้ตรวจไปแล้ว",
    "no_sell_signal": "ไม่มีสัญญาณ SELL",
    "foreign_exposure": "มีไม้หรือออเดอร์ที่บอทไม่ได้เป็นเจ้าของ",
    "safety_halt": "หยุดฉุกเฉินค้างอยู่",
    "another trial30 writer owns journal": "มี watcher อีกตัวถือ journal อยู่",
}


def load_report(conn: sqlite3.Connection) -> dict:
    values = {key: json.loads(value) for key, value in conn.execute("SELECT key,value FROM kv")}
    active = values.get("active")
    result = values.get("last_result", {})
    stamp = result.get("captured_utc")
    age = (
        (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds()
        if stamp
        else None
    )
    return dict(
        last_result=result,
        heartbeat_age_seconds=age,
        day=values.get("day"),
        active={
            k: active.get(k)
            for k in ("status", "ticket", "position_id", "fill", "risk", "be_done")
        }
        if active
        else None,
        safety_halt=values.get("safety_halt"),
        broker_events=[
            json.loads(row[0])
            for row in conn.execute("SELECT payload FROM events ORDER BY id DESC LIMIT 10")
        ],
    )


def watcher_processes() -> list[tuple[str, str]] | None:
    try:
        found = subprocess.run(
            ["pgrep", "-fl", "run_trial30_wine|mt5_wine_trial30"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if found.returncode not in (0, 1):
        return None
    rows = []
    for line in found.stdout.splitlines():
        if "/bin/zsh" in line:
            continue
        pid, _, command = line.partition(" ")
        if not pid.isdigit() or not command:
            continue
        role = "wine" if "mt5_wine_trial30" in command else "watcher"
        rows.append((role, pid))
    return rows


def format_brief(report: dict, processes: list[tuple[str, str]] | None) -> str:
    result = report.get("last_result") or {}
    status = str(result.get("status") or "UNKNOWN")
    reason = result.get("reason")
    status_text = STATUS_TEXT.get(status, status)
    if reason:
        status_text += " — " + REASON_TEXT.get(str(reason), str(reason))
    age = report.get("heartbeat_age_seconds")
    if age is None:
        beat = "ไม่มี"
    elif age < 15:
        beat = "เมื่อกี้" if age < 1 else f"{round(age)} วินาทีที่แล้ว"
    else:
        beat = f"ค้าง {round(age)} วินาที"
    active = report.get("active")
    if not active:
        position = "ไม่มี"
    else:
        position = str(active.get("status") or "มีไม้")
        if active.get("ticket") is not None:
            position += f" ticket {active['ticket']}"
        if active.get("fill") is not None:
            position += f" ราคา {active['fill']}"
    halt = report.get("safety_halt") or "ไม่มี"
    day = report.get("day") or {}
    equity = day.get("equity")
    equity_text = "ไม่ทราบ" if equity is None else f"{float(equity):.2f}"
    day_name = day.get("day") or "ไม่ทราบ"
    events = report.get("broker_events") or []
    if not events:
        event_text = "ไม่มี"
    else:
        shown = []
        for event in events[:3]:
            piece = str(event.get("kind") or "event")
            if event.get("ticket") is not None:
                piece += f" ticket {event['ticket']}"
            shown.append(piece)
        event_text = ", ".join(shown)
    if processes is None:
        process_text = "ตรวจไม่ได้"
    elif not processes:
        process_text = "ไม่ได้รัน"
    else:
        process_text = ", ".join(f"{role} {pid}" for role, pid in processes)
    execute = result.get("execute")
    if execute is True:
        send = "ได้"
    elif execute is False:
        send = "ไม่ได้ (เฝ้าอย่างเดียว)"
    else:
        send = "ไม่ทราบ"
    snapshot = result.get("snapshot") or "ไม่ทราบ"
    return "\n".join(
        [
            f"สัญญา: {snapshot}",
            f"สถานะ: {status_text}",
            f"ส่งออเดอร์: {send}",
            f"สัญญาณล่าสุด: {beat}",
            f"ไม้ที่เปิด: {position}",
            f"หยุดฉุกเฉิน: {halt}",
            f"equity วันนี้: {equity_text} ({day_name})",
            f"เหตุการณ์โบรกเกอร์: {event_text}",
            f"โปรเซส: {process_text}",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--journal",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data/trial30-demo.sqlite3",
    )
    parser.add_argument("--brief", action="store_true", help="print a short operator summary")
    args = parser.parse_args()
    conn = sqlite3.connect(args.journal.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        report = load_report(conn)
    finally:
        conn.close()
    if args.brief:
        print(format_brief(report, watcher_processes()))
        return
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
