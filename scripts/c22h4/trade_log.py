"""Readable C22H4 trade notes. Facts from the frozen contract, no parameter changes."""

from __future__ import annotations

import json
from pathlib import Path


def explain_block(reason: str) -> str:
    """Why a cycle refused a new order. The reason code stays the source of truth."""
    notes = {
        "day_start_floating_unknown": (
            "ยังเข้าออเดอร์ไม่ได้เพราะมีสถานะเปิดค้างตอน 00:00 UTC "
            "และไม่ได้จับ equity ในวินาทีแรก จึงไม่มี baseline ขาดทุนรายวัน. "
            "ปิดไม้เองหลังเที่ยงคืนแล้วยังติดเงื่อนไขนี้จนถึง 00:00 UTC ถัดไป."
        ),
        "cost_policy_invalid_or_stale": (
            "ยังเข้าออเดอร์ไม่ได้เพราะใบรับรองต้นทุนเก่าเกิน 24 ชั่วโมง. "
            "บอทใช้ค่าคอมมิชชันต่อล็อตและเผื่อสลิปเพจจากใบนี้ก่อนคิดเพดานเสี่ยง 10%. "
            "ต้องตรวจ tariff ของบัญชีแล้วบันทึกเวลาใหม่ การแก้เฉพาะ timestamp ไม่ผ่าน."
        ),
        "foreign_exposure": (
            "ยังเข้าออเดอร์ไม่ได้เพราะบัญชีมี position หรือ order อยู่แล้ว. "
            "สัญญานี้เข้าได้ไม้เดียว และไม่แยกไม้ที่เปิดเองออกจากไม้ของบอท."
        ),
        "daily_loss_limit": "ยังเข้าออเดอร์ไม่ได้เพราะขาดทุนจาก baseline ของวันนี้ถึง 10% ของ equity.",
        "max_daily_losses": "ยังเข้าออเดอร์ไม่ได้เพราะวันนี้มีไม้ของ C22 ที่ปิดแล้วขาดทุนครบ 1 ไม้.",
        "safety_halt": "ยังเข้าออเดอร์ไม่ได้เพราะ safety halt ยังอยู่ ต้องเคลียร์จากหลักฐานโบรกเกอร์ก่อน.",
        "entry_window_expired": "ยังเข้าออเดอร์ไม่ได้เพราะเลยหน้าต่าง 90 วินาทีหลังแท่ง M15 ปิด.",
        "risk_cap_or_volume": "ยังเข้าออเดอร์ไม่ได้เพราะความเสี่ยงของล็อต 0.01 เกินเพดาน 10%.",
        "order_check_rejected": "ยังเข้าออเดอร์ไม่ได้เพราะ broker order_check ปฏิเสธคำสั่ง.",
    }
    return notes.get(reason, f"ยังเข้าออเดอร์ไม่ได้เพราะ runner ปฏิเสธด้วยเหตุผล {reason}.")


def review_exit(
    *,
    side: str,
    fill: float,
    stop: float,
    target: float,
    exit_price: float | None,
    net: float,
    profit: float,
    commission: float,
    swap: float,
    fee: float,
    safety_reason: str | None = None,
) -> dict:
    """Explain a closed trade without proposing a contract change."""
    cash = (
        f"ราคา {profit:.2f}, commission {commission:.2f}, swap {swap:.2f}, fee {fee:.2f}, "
        f"สุทธิ {net:.2f}"
    )
    if safety_reason:
        return dict(
            outcome="ปิดเพราะผิดสัญญาของไม้ที่เติม",
            because=f"runner สั่ง safety close เพราะ {safety_reason}. {cash}",
            mistake=safety_reason,
            next=(
                "ไม่เข้าไม้ใหม่ขณะ safety halt ยังอยู่. "
                "ไม่ใช้ไม้ใบนี้เป็นเหตุให้เปลี่ยน SL, TP หรือตัวตรวจจับของสัญญาที่ล็อกไว้."
            ),
        )
    hit_stop = _hit_stop(stop, target, exit_price)
    if profit > 0 and net < 0:
        return dict(
            outcome="ขาดทุนสุทธิทั้งที่ราคาไปทางกำไร",
            because=f"ส่วนต่างราคาเป็นบวก แต่ต้นทุนทำให้สุทธิติดลบ. {cash}",
            mistake="ไม่มีสัญญาณหลุดกฎ ต้นทุนที่หักจริงมากกว่าส่วนต่างราคา",
            next="รอบหน้ายังใช้สัญญาเดิม. ตรวจว่า commission และ swap ในดีลยังตรงกับใบรับรองต้นทุน.",
        )
    if net > 0 and not hit_stop:
        where = f"TP {target:.3f}" if exit_price is not None else "ฝั่งกำไร"
        return dict(
            outcome="กำไร",
            because=(f"กำไรเพราะราคาออกที่ {where} จากจุดเข้า {fill:.3f} ฝั่ง {side} ตามแผน. {cash}"),
            mistake="ไม่มี ออกตามแผนที่วางไว้ตอนเข้า",
            next="ไม่ปรับพารามิเตอร์ของสัญญาที่ล็อกไว้จากไม้ที่กำไร.",
        )
    if net < 0 and hit_stop:
        return dict(
            outcome="ขาดทุน",
            because=(f"ขาดทุนเพราะราคาถึง SL {stop:.3f} จากจุดเข้า {fill:.3f} ฝั่ง {side}. {cash}"),
            mistake="ไม่มี เป็นการขาดทุนตาม SL ที่รับไว้ตอนเข้า ไม่ใช่การเข้าผิดกฎ",
            next="รอบหน้าใช้สัญญาเดิม. ไม่ขยับ SL, TP หรือตัวตรวจจับจากไม้เดียวนี้.",
        )
    return dict(
        outcome="กำไร" if net > 0 else "ขาดทุน" if net < 0 else "เสมอ",
        because=f"โบรกเกอร์ปิดไม้ที่ราคา {exit_price}. {cash}",
        mistake="ไม่มีหลักว่าหลุดแผนเข้า ใช้ตัวเลขดีลที่ปิดเป็นหลัก",
        next="ไม่ปรับสัญญาจากไม้ที่เหตุผลการปิดไม่ตรง SL หรือ TP ชัดเจน จนกว่าจะมีดีลครบ.",
    )


def _hit_stop(stop, target, exit_price) -> bool:
    if exit_price is None:
        return False
    return abs(exit_price - stop) <= abs(exit_price - target)


def render_block(captured_utc: str, reason: str) -> tuple[str, str, dict]:
    record = dict(
        kind="BLOCKED", captured_utc=captured_utc, reason=reason, note=explain_block(reason)
    )
    body = f"สถานะ: ยังไม่เข้าออเดอร์\nเหตุผลโค้ด: {reason}\nบันทึก: {record['note']}"
    return f"{captured_utc} BLOCKED", body, record


def render_entry(captured_utc: str, thesis: dict, fill: float, stop: float, target: float) -> tuple:
    record = dict(
        kind="ENTRY",
        captured_utc=captured_utc,
        side=thesis.get("side"),
        fill=fill,
        stop=stop,
        target=target,
        why=thesis.get("why"),
        close=thesis.get("close"),
        macro_ema=thesis.get("macro_ema"),
        atr=thesis.get("atr"),
    )
    body = (
        f"ฝั่ง: {record['side']}\n"
        f"ราคาเข้า: {fill:.3f}\n"
        f"SL: {stop:.3f}\n"
        f"TP: {target:.3f}\n"
        f"เพราะ: {record['why']}"
    )
    return f"{captured_utc} ENTRY {record['side']}", body, record


def render_exit(captured_utc: str, thesis: dict, review: dict, **facts) -> tuple:
    record = dict(
        kind="EXIT", captured_utc=captured_utc, why_entry=thesis.get("why"), **review, **facts
    )
    body = (
        f"ฝั่ง: {facts.get('side')}\n"
        f"ราคาเข้า: {facts.get('fill')}\n"
        f"ราคาออก: {facts.get('exit_price')}\n"
        f"ผล: {review['outcome']}\n"
        f"เพราะ: {review['because']}\n"
        f"ผิดพลาด: {review['mistake']}\n"
        f"รอบหน้า: {review['next']}\n"
        f"เหตุผลตอนเข้า: {thesis.get('why')}"
    )
    return f"{captured_utc} EXIT {review['outcome']}", body, record


def append_note(path: Path, title: str, body: str, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"## {title}\n\n{body}\n\n")
    with path.with_suffix(".jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
