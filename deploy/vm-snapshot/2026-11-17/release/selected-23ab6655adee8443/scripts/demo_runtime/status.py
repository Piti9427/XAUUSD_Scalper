"""Read-only local trial30 status; no Wine/broker APIs or secrets."""

import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone

from scripts.demo_runtime.costs import validate_policy
from scripts.demo_runtime.diagnostics import RESUME


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
    "day_start_floating_unknown": "baseline equity ต้นวัน UTC ไม่ครบตาม account-bound UTC policy",
}


def entry_availability(*, result, values, now, review=None, cooldown_minutes=None):
    """Explain known blockers only; never query a broker or grant admission.

    This is observational. Short-circuited signal/risk/ledger checks are not
    claimed to pass. Previous observations supply timestamps, never permission.
    """
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("availability_clock_must_be_aware_utc")
    waits = {"no_signal", "no_sell_signal", "duplicate_bar", "macro_gate"}
    resume = RESUME
    previous = values.get("last_result", {})
    previous = previous.get("entry_availability", {}) if isinstance(previous, dict) else {}
    previous = previous if isinstance(previous, dict) else {}
    prior_items = previous.get("known_blockers", [])
    since = {}
    for item in prior_items if isinstance(prior_items, list) else []:
        try:
            code = item["code"]
            stamp = datetime.fromisoformat(item["since_utc"])
            if (isinstance(code, str) and stamp.tzinfo is not None
                    and stamp.utcoffset() == timedelta(0) and stamp <= now):
                since[code] = stamp.isoformat()
        except (KeyError, TypeError, ValueError, OverflowError):
            pass
    blockers = {}

    def add(code, *, operator=None, condition=None):
        action, text = resume.get(code, (True, "restore_valid_source_bound_owner_review"))
        blockers[code] = dict(code=code, since_utc=since.get(code) or now.isoformat(),
            requires_operator=action if operator is None else operator,
            resume_condition=text if condition is None else condition, resume_not_before_utc=None,
            next_check="NEXT_SENDER_CYCLE")

    reason = result.get("reason")
    if result.get("status") in {"BLOCKED", "REJECTED", "UNKNOWN"}:
        identity = result.get("identity_blockers")
        if reason == "algo_permissions_required" and isinstance(identity, list) and identity:
            for code in identity:
                add(code if code in resume else "algo_permissions_required")
        elif reason not in waits:
            add(reason if reason in resume else "runtime_blocked")
    if values.get("safety_halt"):
        add("safety_halt")
    active = values.get("active") is not None
    if active:
        add("active_reconciliation")
    if result.get("execute") is not True:
        add("shadow_mode")
    if review and review.get("status") == "BLOCKED":
        code = review.get("code")
        # Only validator-owned finite codes; never reflect arbitrary file text.
        allowed = {"review_missing", "review_unreadable", "review_oversized", "review_malformed",
            "review_binding_mismatch", "review_input_binding_invalid", "cost_policy_changed",
            "cost_policy_invalid", "cost_policy_expired", "cost_policy_future", "review_initial_stale",
            "review_acceptance_unavailable", "review_inspection_unavailable", "review_time_invalid"}
        add(code if code in allowed else "selected_execution_review_invalid")
    if "armed_trial_not_started" in blockers and review:
        try:
            stamp = datetime.fromisoformat(review["arm_not_before_utc"])
            if stamp.tzinfo is not None and stamp.utcoffset() == timedelta(0):
                blockers["armed_trial_not_started"]["resume_not_before_utc"] = stamp.isoformat()
        except (KeyError, TypeError, ValueError, OverflowError):
            pass
    if "armed_trial_new_closed_m15_required" in blockers and review:
        try:
            approved = datetime.fromisoformat(review["approved_utc"])
            arm = datetime.fromisoformat(review["arm_not_before_utc"])
            if all(stamp.tzinfo is not None and stamp.utcoffset() == timedelta(0)
                   for stamp in (approved, arm)):
                next_close = approved.replace(minute=approved.minute // 15 * 15,
                    second=0, microsecond=0) + timedelta(minutes=15)
                arm_close = arm.replace(minute=arm.minute // 15 * 15, second=0, microsecond=0)
                if arm_close < arm:
                    arm_close += timedelta(minutes=15)
                blockers["armed_trial_new_closed_m15_required"]["resume_not_before_utc"] = max(
                    next_close, arm_close).isoformat()
        except (KeyError, TypeError, ValueError, OverflowError):
            pass
    if "max_daily_losses" in blockers:
        blockers["max_daily_losses"]["resume_not_before_utc"] = (
            now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()
    loss_ms = values.get("selected_last_loss_ms")
    if ("cooldown" in blockers and type(loss_ms) is int and loss_ms > 0
            and type(cooldown_minutes) in (int, float) and 0 <= cooldown_minutes <= 1440):
        try:
            blockers["cooldown"]["resume_not_before_utc"] = (
                datetime.fromtimestamp(loss_ms / 1000, now.tzinfo)
                + timedelta(minutes=cooldown_minutes)).isoformat()
        except (ValueError, OSError, OverflowError):
            pass
    admitted = result.get("status") in {"SHADOW_ADMIT", "FILLED"}
    state = ("MANAGING" if active else "SHADOW_ONLY" if result.get("status") == "SHADOW_ADMIT"
             else "BLOCKED" if blockers else "ORDER_CONFIRMED" if result.get("status") == "FILLED"
             else "WAITING_SIGNAL" if result.get("status") == "WAIT" else "UNVERIFIED")
    return dict(status=state, coverage="KNOWN_BLOCKERS_ONLY", known_blockers=list(blockers.values()),
        requires_operator=any(item["requires_operator"] for item in blockers.values()),
        downstream_admission="PASSED_THIS_CYCLE" if admitted else "NOT_PROVEN")


def cost_report(values, path: Path, now: datetime, *, source: str) -> dict:
    """Read local attestation without changing it or querying the broker."""
    report = dict(path=str(path), source=source, status="BLOCKED", reason="cost_policy_unreadable")
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        return report
    fingerprint = values.get("identity")
    if not isinstance(fingerprint, str) or not fingerprint:
        costs, status = {}, "identity_unknown"
    else:
        costs, status = validate_policy(
            raw,
            fingerprint=fingerprint,
            now=now,
            strategy="c22h4"
            if values.get("strategy_snapshot", "").startswith("RESEARCH-C22")
            else "trial30",
        )
    report.update(
        status="VALID" if costs else "BLOCKED",
        reason=status if costs else "cost_policy_" + status,
    )
    try:
        reviewed = datetime.fromisoformat(raw["reviewed_utc"])
        if reviewed.tzinfo is not None and reviewed.utcoffset() == timedelta(0):
            report.update(
                reviewed_utc=reviewed.isoformat(),
                expires_utc=(
                    reviewed + timedelta(hours=168 if raw.get("version") == 2 else 24)
                ).isoformat(),
                age_hours=(now - reviewed).total_seconds() / 3600,
            )
    except (KeyError, TypeError, ValueError, OverflowError):
        pass
    return report


def load_report(conn: sqlite3.Connection, *, cost_policy_path=None, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    values = {key: json.loads(value) for key, value in conn.execute("SELECT key,value FROM kv")}
    active = values.get("active")
    result = values.get("last_result", {})
    stamp = result.get("captured_utc")
    age = (now - datetime.fromisoformat(stamp)).total_seconds() if stamp else None
    policy = cost_report(
        values,
        cost_policy_path
        or Path(__file__).resolve().parents[2] / "data/trial30-demo-cost-policy.json",
        now,
        source="explicit" if cost_policy_path is not None else "default",
    )
    readiness = dict(status="UNVERIFIED", reason="awaiting_signal_and_broker_checks")
    if values.get("safety_halt"):
        readiness.update(status="BLOCKED", reason="safety_halt")
    elif active:
        readiness.update(status="BLOCKED", reason="active_reconciliation")
    elif age is None or not 0 <= age < 15:
        readiness["reason"] = "heartbeat_stale_or_unknown"
    elif policy["status"] != "VALID":
        readiness.update(status="BLOCKED", reason=policy["reason"])
    elif result.get("status") == "BLOCKED":
        readiness.update(status="BLOCKED", reason=result.get("reason") or "runtime_blocked")
    elif result.get("execute") is False:
        readiness.update(status="BLOCKED", reason="shadow_mode")
    has_exposure = bool(
        active or result.get("observed_positions") or result.get("position_protection") == "unknown"
    )
    return dict(
        last_result=result,
        cost_policy=policy,
        entry_readiness=readiness,
        last_blocked_note=values.get("trade_block_note"),
        heartbeat_age_seconds=age,
        position_protection=(
            "unknown"
            if has_exposure and (age is None or age >= 15)
            else result.get("position_protection", "unverified")
        ),
        critical=bool(has_exposure and (age is None or age >= 180 or result.get("critical"))),
        day=values.get("day"),
        active={
            k: active.get(k) for k in ("status", "ticket", "position_id", "fill", "risk", "be_done")
        }
        if active
        else None,
        safety_halt=values.get("safety_halt"),
        broker_events=[
            json.loads(row[0])
            for row in conn.execute("SELECT payload FROM events ORDER BY id DESC LIMIT 10")
        ],
    )


def watcher_processes(name="trial30") -> list[tuple[str, str]] | None:
    try:
        found = subprocess.run(
            ["pgrep", "-fl", f"run_{name}_wine|mt5_wine_{name}"],
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
        role = "wine" if f"mt5_wine_{name}" in command else "watcher"
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
        send = "execution (เปิดส่ง)"
    elif execute is False:
        send = "shadow (ไม่ส่ง)"
    else:
        send = "ไม่ทราบ"
    snapshot = result.get("snapshot") or "ไม่ทราบ"
    readiness = report.get("entry_readiness") or {}
    ready_text = "ไม่พร้อม" if readiness.get("status") == "BLOCKED" else "ยังไม่ยืนยัน"
    if readiness.get("reason"):
        ready_text += " — " + str(readiness["reason"])
    policy = report.get("cost_policy") or {}
    cost_text = (
        "ผ่าน local attestation"
        if policy.get("status") == "VALID"
        else str(policy.get("reason") or "ไม่ทราบ")
    )
    if policy.get("expires_utc"):
        cost_text += "; หมดอายุ " + policy["expires_utc"]
    if policy.get("source"):
        cost_text += " (ไฟล์ " + policy["source"] + ")"
    blocked = str(report.get("last_blocked_note") or "")
    if "|" in blocked:
        blocked_day, blocked_reason = blocked.split("|", 1)
        blocked = blocked_day + " — " + blocked_reason
        if blocked_reason in REASON_TEXT:
            blocked += " (" + REASON_TEXT[blocked_reason] + ")"
    else:
        blocked = "ไม่มีบันทึก"
    return "\n".join(
        [
            f"สัญญา: {snapshot}",
            f"สถานะ: {status_text}",
            f"โหมดส่งออเดอร์: {send}",
            f"ความพร้อมรับไม้: {ready_text}",
            f"ต้นทุน: {cost_text}",
            f"blocker ล่าสุดที่บันทึก: {blocked}",
            f"heartbeat ล่าสุด: {beat}",
            f"ไม้ที่เปิด: {position}",
            f"position protection: {report.get('position_protection', 'unverified')}; critical={report.get('critical', False)}",
            f"หยุดฉุกเฉิน: {halt}",
            f"equity วันนี้: {equity_text} ({day_name})",
            f"เหตุการณ์โบรกเกอร์: {event_text}",
            f"โปรเซส: {process_text}",
        ]
    )


def main(argv=None, *, name="trial30"):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--journal",
        type=Path,
        default=Path(__file__).resolve().parents[2] / f"data/{name}-demo.sqlite3",
    )
    parser.add_argument("--brief", action="store_true", help="print a short operator summary")
    parser.add_argument(
        "--cost-policy",
        type=Path,
        help="match the watcher's cost-policy override; default is the CLI default file",
    )
    args = parser.parse_args(argv)
    if not args.journal.exists():
        report = dict(last_result=dict(status="UNKNOWN", reason="journal_missing"), active=None)
        print(format_brief(report, watcher_processes(name)) if args.brief else json.dumps(report))
        return
    conn = sqlite3.connect(args.journal.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        report = load_report(conn, cost_policy_path=args.cost_policy)
    finally:
        conn.close()
    if args.brief:
        print(format_brief(report, watcher_processes(name)))
        return
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
