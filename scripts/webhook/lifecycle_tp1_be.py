"""TP1_HIT_MOVE_BE lifecycle: partial scale-out + BE relocate (legacy path)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks

from scripts.smc.stops_geometry import sl_modify_freeze_allows
from scripts.smc.types import Direction, OrderIntent, OrderIntentType
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def handle_tp1_hit_move_be(
    rt: WebhookRuntime,
    *,
    payload: Dict[str, Any],
    order_id: Optional[str],
    event: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    if not (rt.partial_tp_enabled and rt.be_enabled):
        return {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": (
                "TP1_HIT_MOVE_BE disabled by foundation defaults "
                f"(partial_tp_enabled={rt.partial_tp_enabled}, be_enabled={rt.be_enabled})"
            ),
        }

    new_sl = float(payload.get("new_sl") or 0.0)
    entry = float(payload.get("entry") or 0.0)
    close_pct = int(payload.get("close_percent") or 50)
    direction_raw = str(payload.get("dir", "BUY")).upper()
    if entry <= 0 or new_sl <= 0:
        return {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": "TP1_HIT_MOVE_BE requires positive entry and new_sl",
        }
    # new_sl must sit on profit-side BE band (entry ± rt.be_buffer), not unconstrained.
    if direction_raw == "BUY":
        be_lo, be_hi = entry, entry + rt.be_buffer + 0.05
    else:
        be_lo, be_hi = entry - rt.be_buffer - 0.05, entry
    if not (be_lo <= new_sl <= be_hi):
        return {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": (
                f"new_sl {new_sl} outside BE band [{be_lo}, {be_hi}] "
                f"for {direction_raw} entry={entry} be_buffer={rt.be_buffer}"
            ),
        }

    # Fail closed before partial: freeze distance must allow the BE SL move.
    if not rt.adapter.dry_run:
        snap = await asyncio.to_thread(rt.adapter.get_risk_snapshot)
        if snap is None:
            return {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": "broker risk snapshot unavailable for freeze check",
            }
        quotes = await asyncio.to_thread(rt.adapter.get_market_quotes)
        if quotes is None:
            return {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": "broker market quotes unavailable for freeze check",
            }
        freeze_ok, freeze_reason = sl_modify_freeze_allows(
            new_sl=new_sl,
            market_bid=float(quotes["bid"]),
            market_ask=float(quotes["ask"]),
            point=float(snap["point"]),
            freeze_level=float(snap["freeze_level"]),
        )
        if not freeze_ok:
            return {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": f"rejected_freeze_level:{freeze_reason}",
            }

    intent_close = OrderIntent(
        intent_type=OrderIntentType.PARTIAL_CLOSE,
        order_id=order_id,
        reason=f"TP1_{close_pct}_PCT_SCALE_OUT",
    )
    exec_close = await asyncio.to_thread(rt.adapter.execute_intent, intent_close)
    if not exec_close.success:
        safety_close = await asyncio.to_thread(
            rt.adapter.execute_intent,
            OrderIntent(
                intent_type=OrderIntentType.CLOSE_MARKET,
                order_id=order_id,
                reason="TP1 partial rejected: close whole position",
            ),
        )
        return {
            "status": "closed_for_safety" if safety_close.success else "reconcile_required",
            "order_id": order_id,
            "event": event,
            "partial_message": exec_close.message,
            "close_message": safety_close.message,
        }

    intent_be = OrderIntent(
        intent_type=OrderIntentType.MOVE_SL_TO_BE,
        sl_price=new_sl,
        order_id=order_id,
        reason="TP1_RELOCATE_SL_TO_BE",
    )
    exec_be = await asyncio.to_thread(rt.adapter.execute_intent, intent_be)

    if not exec_be.success:
        safety_close = await asyncio.to_thread(
            rt.adapter.execute_intent,
            OrderIntent(
                intent_type=OrderIntentType.CLOSE_MARKET,
                order_id=order_id,
                reason="TP1 complete but BE rejected: close runner",
            ),
        )
        return {
            "status": "closed_for_safety" if safety_close.success else "reconcile_required",
            "order_id": order_id,
            "event": event,
            "be_message": exec_be.message,
            "close_message": safety_close.message,
        }

    if order_id:
        await asyncio.to_thread(rt.mark_processed, order_id, event, "success")

    if rt.notifier and getattr(rt.notifier, "enabled", False):
        try:
            from scripts.smc.notifier import format_partial_tp_card

            tp_dir = (
                Direction.BUY
                if str(payload.get("dir", "BUY")).upper() == "BUY"
                else Direction.SELL
            )
            tp_lot = float(payload.get("lot_size") or 0.02)
            closed_lot = round(tp_lot * (close_pct / 100.0), 2)
            remaining_lot = round(tp_lot - closed_lot, 2)
            card = format_partial_tp_card(
                direction=tp_dir,
                closed_lot=closed_lot,
                remaining_lot=remaining_lot,
                r_multiple=1.0,
                entry_price=entry,
            )
            background_tasks.add_task(rt.dispatch_tg_safe, card)
        except Exception as exc:
            logger.warning(f"Failed to schedule Telegram notification: {exc}")

    return {
        "status": "success",
        "action": "PARTIAL_CLOSE_AND_BE_MOVED",
        "order_id": order_id,
        "new_sl": new_sl,
        "close_message": exec_close.message,
        "be_message": exec_be.message,
    }
