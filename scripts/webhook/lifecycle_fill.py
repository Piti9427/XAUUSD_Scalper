"""ORDER_FILLED lifecycle: broker-verified fill record + notify."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks

from scripts.smc.types import Direction
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def handle_order_filled(
    rt: WebhookRuntime,
    *,
    payload: Dict[str, Any],
    order_id: Optional[str],
    event: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    if order_id and await asyncio.to_thread(
        rt.adapter.has_lifecycle_event, order_id, "ORDER_FILLED"
    ):
        await asyncio.to_thread(rt.mark_processed, order_id, event, "success")
        return {
            "status": "ignored_duplicate",
            "order_id": order_id,
            "event": event,
            "message": "ORDER_FILLED already recorded (broker lifecycle or prior webhook)",
        }

    entry = float(payload.get("entry") or 0.0)
    sl = float(payload.get("sl") or 0.0)
    tp1 = float(payload.get("tp1") or 0.0)
    tp2 = float(payload.get("tp2") or 0.0)
    direction = Direction.BUY if payload.get("dir") == "BUY" else Direction.SELL
    ticket = None
    pos = None
    reason = "TradingView Alert Fill Confirmation"
    if not rt.adapter.dry_run:
        pos = await asyncio.to_thread(rt.adapter.get_matching_position, order_id)
        if pos is None:
            return {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": "Broker has no open position matching order_id",
            }
        entry = float(pos.price_open)
        ticket = int(pos.ticket)
        reason = "TradingView Alert Fill Confirmation (Broker Verified)"

    await asyncio.to_thread(
        rt.adapter.log_lifecycle_event,
        event_type="ORDER_FILLED",
        direction=direction.value,
        entry_price=entry,
        sl_price=sl,
        tp_price=tp2 if tp2 > 0 else tp1,
        lot_size=(
            float(pos.volume) if pos is not None else float(payload.get("lot_size") or 0.0) or None
        ),
        order_id=order_id,
        ticket=ticket,
        reason=reason,
    )
    if order_id and ticket and not rt.adapter.dry_run:
        await asyncio.to_thread(rt.adapter.update_setup_status, order_id, "accepted", ticket)
    if order_id:
        rt.setup_registry.mark_terminal(order_id, "filled")
        await asyncio.to_thread(rt.mark_processed, order_id, event, "success")

    if rt.notifier and getattr(rt.notifier, "enabled", False):
        try:
            from scripts.smc.types import Position
            from scripts.smc.notifier import format_order_filled_card
            from scripts.smc.notification_policy import may_notify_execution

            if not may_notify_execution(success=True, status="FILLED"):
                raise RuntimeError("notification policy blocked fill card")
            fill_lot = (
                float(pos.volume) if pos is not None else float(payload.get("lot_size") or 0.01)
            )
            pos_card = Position(
                direction=direction,
                entry_price=entry,
                sl_price=sl,
                tp_price=tp2 if tp2 > 0 else tp1,
                lot_size=fill_lot,
                open_time=datetime.now(timezone.utc),
                initial_sl_distance=abs(entry - sl),
            )
            background_tasks.add_task(rt.dispatch_tg_safe, format_order_filled_card(pos_card))
        except Exception as exc:
            logger.warning(f"Failed to schedule Telegram notification: {exc}")

    return {
        "status": "success",
        "action": "ORDER_RECORDED",
        "order_id": order_id,
        "entry": entry,
        **({"ticket": ticket} if ticket else {}),
    }
