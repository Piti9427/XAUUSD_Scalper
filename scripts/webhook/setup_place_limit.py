"""ADR-020 sizing, stops geometry, claim, PLACE_LIMIT execute + accepted notify."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks

from scripts.smc.risk import calculate_lot_size
from scripts.smc.stops_geometry import pending_stops_geometry_allows
from scripts.smc.types import Direction, OrderIntent, OrderIntentType
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def place_setup_limit(
    rt: WebhookRuntime,
    *,
    payload: Dict[str, Any],
    broker_risk: Optional[Dict[str, Any]],
    effective_balance: float,
    effective_equity: float,
    entry: float,
    sl: float,
    tp1: float,
    tp2: float,
    direction: Direction,
    order_id: Optional[str],
    event: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """Size, geometry-gate, claim, execute PLACE_LIMIT. Never invent fill cards."""
    lot_result = calculate_lot_size(
        balance=effective_balance,
        entry_price=entry,
        sl_price=sl,
        risk_pct=rt.risk_pct,
        spread_buffer=0.0,
        equity=effective_equity,
        min_lot=broker_risk["min_lot"] if broker_risk else 0.01,
        max_lot=broker_risk["max_lot"] if broker_risk else 10.0,
        lot_step=broker_risk["lot_step"] if broker_risk else 0.01,
        contract_size=broker_risk["contract_size"] if broker_risk else 100.0,
        commission_per_lot=rt.commission_per_lot,
        slippage_allowance=rt.slippage_allowance,
        require_cost_model=not rt.adapter.dry_run,
    )

    if not lot_result.is_valid:
        if order_id:
            await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected")
        return {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": f"ADR-020 Small-Account Risk Gate: {lot_result.reason}",
        }

    # Scenario 10: broker stops_level / point conversion must allow SL/TP geometry.
    if not rt.adapter.dry_run and broker_risk is not None:
        tp_for_geom = tp2 if tp2 > 0 else (tp1 if tp1 > 0 else None)
        geom_ok, geom_reason = pending_stops_geometry_allows(
            entry_price=entry,
            sl_price=sl,
            tp_price=tp_for_geom,
            point=float(broker_risk["point"]),
            stops_level=float(broker_risk["stops_level"]),
        )
        if not geom_ok:
            reason = f"Stops geometry gate blocked new risk: {geom_reason}"
            logger.warning(reason)
            if order_id:
                await asyncio.to_thread(
                    rt.mark_processed, order_id, event, "rejected_stops_geometry"
                )
            return {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": reason,
            }

    claim: Optional[Dict[str, str]] = None
    if order_id:
        claim = await asyncio.to_thread(rt.adapter.claim_setup, payload)
        if claim["status"] == "duplicate":
            return {
                "status": "ignored_duplicate",
                "order_id": order_id,
                "receipt_id": claim["receipt_id"],
            }
        if claim["status"] != "claimed":
            return {
                "status": "rejected",
                "order_id": order_id,
                "reason": f"Setup claim {claim['status']}; broker reconciliation required",
            }

    intent = OrderIntent(
        intent_type=OrderIntentType.PLACE_LIMIT,
        direction=direction,
        limit_price=entry,
        sl_price=sl,
        tp_price=tp2 if tp2 > 0 else tp1,
        lot_size=lot_result.lot_size,
        order_id=order_id,
        reason=payload.get("type", "SMC_PRIME"),
    )
    try:
        exec_res = await asyncio.to_thread(rt.adapter.execute_intent, intent)
    except Exception as exc:
        logger.error(f"Execution error or timeout for {order_id}: {exc}")
        if order_id:
            await asyncio.to_thread(rt.adapter.update_setup_status, order_id, "uncertain")
        return {
            "status": "uncertain",
            "order_id": order_id,
            "event": event,
            "reason": f"Execution uncertain: {exc}. Broker reconciliation required.",
        }
    if not exec_res.success:
        from scripts.smc.notification_policy import classify_exec_outcome

        outcome = classify_exec_outcome(
            success=exec_res.success,
            status=getattr(exec_res, "status", None),
        )
        if outcome == "uncertain":
            if order_id:
                await asyncio.to_thread(rt.adapter.update_setup_status, order_id, "uncertain")
            return {
                "status": "uncertain",
                "order_id": order_id,
                "event": event,
                "reason": exec_res.message,
                "exec_status": getattr(exec_res, "status", "UNKNOWN"),
            }
        if order_id:
            await asyncio.to_thread(rt.adapter.update_setup_status, order_id, "rejected")
        return {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": exec_res.message,
            "exec_status": getattr(exec_res, "status", "REJECTED"),
        }
    if order_id:
        await asyncio.to_thread(
            rt.adapter.update_setup_status, order_id, "accepted", exec_res.order_id
        )
    if order_id:
        await asyncio.to_thread(rt.mark_processed, order_id, event, "success")

    # Accepted-pending card only (never fill/phantom trade card).
    from scripts.smc.notification_policy import may_notify_execution

    if (
        rt.notifier
        and getattr(rt.notifier, "enabled", False)
        and may_notify_execution(
            success=exec_res.success,
            status=getattr(exec_res, "status", "OK"),
        )
    ):
        try:
            from scripts.smc.notifier import format_order_accepted_card

            card = format_order_accepted_card(
                direction=direction,
                limit_price=entry,
                sl_price=sl,
                tp_price=tp2 if tp2 > 0 else tp1,
                lot_size=lot_result.lot_size,
                order_id=order_id,
                ticket=exec_res.order_id,
            )
            background_tasks.add_task(rt.dispatch_tg_safe, card)
        except Exception as exc:
            logger.warning(f"Failed to schedule Telegram notification: {exc}")

    return {
        "status": "success",
        "action": "LIMIT_PLACED",
        "order_id": order_id,
        **({"receipt_id": claim["receipt_id"]} if claim else {}),
        "lot_size": lot_result.lot_size,
        "ticket": exec_res.order_id,
        "message": exec_res.message,
    }
