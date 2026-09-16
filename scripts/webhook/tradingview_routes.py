"""TradingView webhook admission + execution route."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status

from scripts.webhook.lifecycle_events import handle_lifecycle_event
from scripts.webhook.runtime import WebhookRuntime
from scripts.webhook.setup_pending import handle_setup_pending

logger = logging.getLogger("webhook_bridge")


def register_tradingview_route(app: FastAPI, rt: WebhookRuntime) -> None:
    @app.post("/webhook/tradingview")
    async def handle_tradingview_webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        authorized: bool = Depends(rt.verify_auth),
    ):
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed JSON payload",
            )

        event = payload.get("event", "UNKNOWN")
        order_id = payload.get("order_id")
        logger.info(f"Received verified webhook event: {event} for order_id: {order_id}")

        if event == "SETUP_PENDING" and order_id:
            existing_setup = await asyncio.to_thread(rt.adapter.inspect_setup, payload)
            if existing_setup is not None:
                return {
                    "status": "ignored_duplicate" if existing_setup["status"] == "duplicate" else "rejected",
                    "order_id": order_id,
                    "event": event,
                    "receipt_id": existing_setup["receipt_id"],
                    **({"reason": "Conflicting payload for existing order_id"}
                       if existing_setup["status"] == "conflict" else {}),
                }

        # Idempotency Check: Fast-path in-memory check followed by SQLite
        if order_id and rt.is_processed(order_id, event):
            logger.warning(f"Ignoring duplicate webhook delivery for {order_id} ({event})")
            receipt_id = (
                await asyncio.to_thread(rt.adapter.get_setup_receipt, order_id)
                if event == "SETUP_PENDING" else None
            )
            return {
                "status": "ignored_duplicate",
                "order_id": order_id,
                "event": event,
                "message": f"Event {event} already processed for {order_id}",
                **({"receipt_id": receipt_id} if receipt_id else {}),
            }

        if event == "SETUP_PENDING":
            return await handle_setup_pending(
                rt,
                payload=payload,
                order_id=order_id,
                event=event,
                background_tasks=background_tasks,
            )

        handled = await handle_lifecycle_event(
            rt,
            payload=payload,
            order_id=order_id,
            event=event,
            background_tasks=background_tasks,
        )
        if handled is not None:
            return handled

        return {
            "status": "success",
            "event": event,
            "order_id": order_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
