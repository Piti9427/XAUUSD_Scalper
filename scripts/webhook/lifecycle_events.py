"""Post-admission TradingView lifecycle events (fill / BE / cancel / close)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import BackgroundTasks

from scripts.webhook.lifecycle_cancel import handle_order_canceled
from scripts.webhook.lifecycle_close import handle_trade_closed
from scripts.webhook.lifecycle_fill import handle_order_filled
from scripts.webhook.lifecycle_tp1_be import handle_tp1_hit_move_be
from scripts.webhook.runtime import WebhookRuntime


async def handle_lifecycle_event(
    rt: WebhookRuntime,
    *,
    payload: Dict[str, Any],
    order_id: Optional[str],
    event: str,
    background_tasks: BackgroundTasks,
) -> Optional[Dict[str, Any]]:
    """Return response dict if event handled; None if unknown event."""
    if event == "ORDER_FILLED":
        return await handle_order_filled(
            rt,
            payload=payload,
            order_id=order_id,
            event=event,
            background_tasks=background_tasks,
        )
    if event == "TP1_HIT_MOVE_BE":
        return await handle_tp1_hit_move_be(
            rt,
            payload=payload,
            order_id=order_id,
            event=event,
            background_tasks=background_tasks,
        )
    if event == "ORDER_CANCELED":
        return await handle_order_canceled(
            rt,
            payload=payload,
            order_id=order_id,
            event=event,
        )
    if event == "TRADE_CLOSED":
        return await handle_trade_closed(
            rt,
            payload=payload,
            order_id=order_id,
            event=event,
            background_tasks=background_tasks,
        )
    return None
