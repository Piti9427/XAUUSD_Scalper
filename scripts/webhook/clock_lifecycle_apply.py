"""Apply broker lifecycle fill / TTL / close rows on the clock tick."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import BackgroundTasks

from scripts.smc.notification_policy import may_notify_close, may_notify_execution
from scripts.smc.types import Direction, Position as PosCard
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def apply_lifecycle_fills(
    rt: WebhookRuntime,
    *,
    fill_rows: List[Dict[str, Any]],
    now_utc: datetime,
    background_tasks: BackgroundTasks,
) -> None:
    """Terminalize filled SETUP_IDs and optionally notify fill cards."""
    for fill_row in fill_rows:
        order_id = fill_row.get("order_id")
        if not order_id:
            continue
        rt.setup_registry.mark_terminal(order_id, "filled")
        await asyncio.to_thread(rt.mark_processed, order_id, "ORDER_FILLED", "success")
        if not (rt.notifier and getattr(rt.notifier, "enabled", False)):
            continue
        if not may_notify_execution(success=True, status="FILLED"):
            continue
        try:
            from scripts.smc.notifier import format_order_filled_card

            geom = await asyncio.to_thread(rt.adapter.get_fill_geometry, order_id)
            if not geom or not geom.get("entry_price") or not geom.get("sl_price"):
                continue
            entry = float(geom["entry_price"])
            sl = float(geom["sl_price"])
            lot = float(geom.get("lot_size") or 0.0) or 0.01
            dir_raw = str(geom.get("direction") or "BUY").upper()
            fill_dir = Direction.BUY if dir_raw == "BUY" else Direction.SELL
            pos_card = PosCard(
                direction=fill_dir,
                entry_price=entry,
                sl_price=sl,
                tp_price=0.0,
                lot_size=lot,
                open_time=now_utc,
                initial_sl_distance=abs(entry - sl),
            )
            background_tasks.add_task(
                rt.dispatch_tg_safe, format_order_filled_card(pos_card)
            )
        except Exception as exc:
            logger.warning("Lifecycle fill notify failed for %s: %s", order_id, exc)


async def apply_lifecycle_ttl_cancels(
    rt: WebhookRuntime,
    *,
    ttl_rows: List[Dict[str, Any]],
) -> None:
    """Scenario 8: TTL cancel must terminalize identity (no revive)."""
    for ttl_row in ttl_rows:
        order_id = ttl_row.get("order_id")
        if not order_id or ttl_row.get("status") != "success":
            continue
        reason = str(ttl_row.get("reason") or "ttl_expired")
        rt.setup_registry.mark_terminal(order_id, reason)
        await asyncio.to_thread(rt.mark_processed, order_id, "ORDER_CANCELED", "success")


async def apply_lifecycle_closes(
    rt: WebhookRuntime,
    *,
    close_rows: List[Dict[str, Any]],
    background_tasks: BackgroundTasks,
) -> None:
    """Mark TRADE_CLOSED; notify only with known broker PnL (no invent cash)."""
    for close in close_rows:
        order_id = close.get("order_id")
        pnl_dollar = close.get("pnl_dollar")
        pnl_r = close.get("pnl_r")
        if order_id:
            await asyncio.to_thread(rt.mark_processed, order_id, "TRADE_CLOSED", "success")
        if (
            rt.notifier
            and getattr(rt.notifier, "enabled", False)
            and order_id
            and pnl_dollar is not None
            and pnl_r is not None
            and may_notify_close(
                broker_close_success=False,
                already_flat_on_broker=True,
            )
        ):
            try:
                from scripts.smc.notifier import format_trade_closed_card

                fill = await asyncio.to_thread(rt.adapter.get_fill_geometry, order_id)
                dir_raw = (fill or {}).get("direction", "BUY")
                tc_dir = (
                    Direction.BUY if str(dir_raw).upper() == "BUY" else Direction.SELL
                )
                card = format_trade_closed_card(
                    direction=tc_dir,
                    exit_price=0.0,
                    pnl_dollars=float(pnl_dollar),
                    pnl_r=float(pnl_r),
                    reason="broker_lifecycle_close_detected",
                )
                background_tasks.add_task(rt.dispatch_tg_safe, card)
            except Exception as exc:
                logger.warning(
                    "Lifecycle close notify failed for %s: %s", order_id, exc
                )
