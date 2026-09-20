"""TRADE_CLOSED lifecycle: broker close + no-invent PnL resolve."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks

from scripts.smc.risk_halt import (
    record_net_losing_trade,
    save_risk_halt_state,
)
from scripts.smc.trade_closed_pnl import resolve_trade_closed_pnl
from scripts.smc.types import Direction, OrderIntent, OrderIntentType
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def handle_trade_closed(
    rt: WebhookRuntime,
    *,
    payload: Dict[str, Any],
    order_id: Optional[str],
    event: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    if order_id and await asyncio.to_thread(
        rt.adapter.has_lifecycle_event, order_id, "TRADE_CLOSED"
    ):
        if order_id:
            await asyncio.to_thread(rt.mark_processed, order_id, event, "success")
        return {
            "status": "ignored_duplicate",
            "order_id": order_id,
            "event": event,
            "message": "TRADE_CLOSED already recorded (broker lifecycle or prior webhook)",
        }

    reason = payload.get("reason", "POSITION_CLOSED")
    intent_close = OrderIntent(
        intent_type=OrderIntentType.CLOSE_MARKET,
        order_id=order_id,
        reason=reason,
    )
    exec_close = await asyncio.to_thread(rt.adapter.execute_intent, intent_close)
    already_closed_by_broker = (
        not exec_close.success and "not found" in (exec_close.message or "").lower()
    )

    if not exec_close.success:
        if not already_closed_by_broker:
            return {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": exec_close.message,
            }

    if already_closed_by_broker or exec_close.success:
        # Release inbox on dry-run success and on fill-during-cancel "not found".
        if rt.adapter.dry_run or already_closed_by_broker:
            await asyncio.to_thread(rt.adapter.finish_setup, order_id)
        if not rt.adapter.dry_run:
            if exec_close.success:
                exposure_after_close = await asyncio.to_thread(rt.adapter.get_open_exposure)
                if exposure_after_close == []:
                    await asyncio.to_thread(rt.adapter.finish_setup, order_id)

    broker_pnl = None
    if not rt.adapter.dry_run and (already_closed_by_broker or exec_close.success):
        broker_pnl = await asyncio.to_thread(rt.adapter.get_realized_pnl_for_order, order_id)

    entry = float(payload.get("entry") or 0.0)
    sl = float(payload.get("sl") or 0.0)
    lot = float(payload.get("lot_size") or 0.0)
    exit_px = float(payload.get("exit_price") or 0.0)
    direction = str(payload.get("dir", "BUY")).upper()
    pnl_r, pnl_dollar, pnl_status = resolve_trade_closed_pnl(
        dry_run=bool(rt.adapter.dry_run),
        payload_pnl_r=payload.get("pnl_r"),
        payload_pnl_dollar=payload.get("pnl_dollar"),
        broker_pnl=broker_pnl,
        entry=entry,
        sl=sl,
        lot=lot,
        exit_price=exit_px,
        direction=direction,
    )
    if pnl_status == "live_broker_pnl_missing":
        if order_id:
            await asyncio.to_thread(rt.mark_processed, order_id, event, "reconcile_required")
        return {
            "status": "reconcile_required",
            "order_id": order_id,
            "event": event,
            "reason": "broker deal cashflow missing for live TRADE_CLOSED",
            "pnl_r": None,
            "pnl_dollar": None,
            "execution": {
                "success": exec_close.success,
                "message": exec_close.message,
            },
        }

    await asyncio.to_thread(
        rt.adapter.log_lifecycle_event,
        event_type="TRADE_CLOSED",
        order_id=order_id,
        pnl_dollar=pnl_dollar,
        pnl_r=pnl_r,
        reason=reason,
        timestamp=payload.get("time"),
    )
    # Foundation risk halt: two net losing bot closes trip daily loss gate.
    if rt.risk_halt is not None and rt.halt_path is not None:
        is_net_loss = (pnl_r is not None and float(pnl_r) < 0) or (
            pnl_dollar is not None and float(pnl_dollar) < 0
        )
        if is_net_loss:
            record_net_losing_trade(rt.risk_halt)
            await asyncio.to_thread(save_risk_halt_state, rt.halt_path, rt.risk_halt)
    if order_id:
        await asyncio.to_thread(rt.mark_processed, order_id, event, "success")

    if rt.notifier and getattr(rt.notifier, "enabled", False):
        try:
            from scripts.smc.notifier import format_trade_closed_card
            from scripts.smc.notification_policy import may_notify_close

            known_pnl = pnl_r is not None and pnl_dollar is not None
            if (
                may_notify_close(
                    broker_close_success=bool(exec_close.success),
                    already_flat_on_broker=already_closed_by_broker,
                )
                and known_pnl
            ):
                tc_dir = (
                    Direction.BUY
                    if str(payload.get("dir", "BUY")).upper() == "BUY"
                    else Direction.SELL
                )
                card = format_trade_closed_card(
                    direction=tc_dir,
                    exit_price=float(payload.get("exit_price") or 0.0),
                    pnl_dollars=float(pnl_dollar),
                    pnl_r=float(pnl_r),
                    reason=reason,
                )
                background_tasks.add_task(rt.dispatch_tg_safe, card)
            else:
                logger.warning(
                    "TRADE_CLOSED notify suppressed — need broker evidence "
                    "and known PnL (order_id=%s success=%s pnl=%s/%s)",
                    order_id,
                    exec_close.success,
                    pnl_dollar,
                    pnl_r,
                )
        except Exception as exc:
            logger.warning(f"Failed to schedule Telegram notification: {exc}")

    return {
        "status": "success",
        "action": "TRADE_CLOSED",
        "order_id": order_id,
        "reason": reason,
        "pnl_r": pnl_r,
        "pnl_dollar": pnl_dollar,
        "execution": {
            "success": exec_close.success,
            "message": exec_close.message,
        },
    }
