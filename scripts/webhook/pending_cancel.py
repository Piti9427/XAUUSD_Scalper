"""Shared unfilled-pending CANCEL_LIMIT + fill-during-cancel release."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Tuple

from scripts.smc.types import OrderIntent, OrderIntentType
from scripts.webhook.runtime import WebhookRuntime


async def cancel_unfilled_pending(
    rt: WebhookRuntime,
    *,
    order_id: str,
    intent_reason: str,
    lifecycle_reason: str,
    terminal_reason: str,
    result_reason: str,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Cancel one unfilled pending.

    Returns (still_pending, result_row).
    Fill-during-cancel ("not found") releases inbox and is not still_pending.
    """
    intent = OrderIntent(
        intent_type=OrderIntentType.CANCEL_LIMIT,
        order_id=order_id,
        reason=intent_reason,
    )
    exec_cancel = await asyncio.to_thread(rt.adapter.execute_intent, intent)
    if exec_cancel.success:
        await asyncio.to_thread(
            rt.adapter.log_lifecycle_event,
            event_type="ORDER_CANCELED",
            order_id=order_id,
            reason=lifecycle_reason,
        )
        rt.setup_registry.mark_terminal(order_id, terminal_reason)
        await asyncio.to_thread(rt.adapter.finish_setup, order_id)
        still_pending = False
    elif "not found" in (exec_cancel.message or "").lower():
        # Fill-during-cancel: release inbox so clock does not re-spam.
        rt.setup_registry.mark_terminal(order_id, "filled_during_cancel")
        await asyncio.to_thread(rt.adapter.finish_setup, order_id)
        still_pending = False
    else:
        still_pending = True

    return still_pending, {
        "order_id": order_id,
        "status": "success" if exec_cancel.success else "rejected",
        "reason": result_reason,
        "message": exec_cancel.message,
    }
