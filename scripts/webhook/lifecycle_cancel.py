"""ORDER_CANCELED lifecycle: targeted pending cancel (ADR-024)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from scripts.smc.types import OrderIntent, OrderIntentType
from scripts.webhook.runtime import WebhookRuntime


async def handle_order_canceled(
    rt: WebhookRuntime,
    *,
    payload: Dict[str, Any],
    order_id: Optional[str],
    event: str,
) -> Dict[str, Any]:
    reason = payload.get("reason", "TTL_EXPIRED")
    intent = OrderIntent(
        intent_type=OrderIntentType.CANCEL_LIMIT,
        order_id=order_id,
        reason=reason,
    )
    exec_cancel = await asyncio.to_thread(rt.adapter.execute_intent, intent)
    if not exec_cancel.success:
        return {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": exec_cancel.message,
        }
    if not rt.adapter.dry_run:
        exposure_after_cancel = await asyncio.to_thread(rt.adapter.get_open_exposure)
        if exposure_after_cancel == []:
            await asyncio.to_thread(rt.adapter.finish_setup, order_id)
    await asyncio.to_thread(
        rt.adapter.log_lifecycle_event,
        event_type="ORDER_CANCELED",
        order_id=order_id,
        reason=reason,
    )
    if order_id:
        rt.setup_registry.mark_terminal(order_id, str(reason or "canceled"))
        await asyncio.to_thread(rt.mark_processed, order_id, event, "success")

    return {
        "status": "success",
        "action": "ORDER_CANCELED",
        "order_id": order_id,
        "reason": reason,
        "message": exec_cancel.message,
    }
