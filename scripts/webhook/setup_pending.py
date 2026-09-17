"""SETUP_PENDING admission + PLACE_LIMIT path."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks

from scripts.smc.types import Direction, OrderIntent, OrderIntentType
from scripts.smc.risk import calculate_lot_size
from scripts.smc.data_freshness import evaluate_new_risk_admission
from scripts.smc.broker_metadata import broker_metadata_allows_new_risk
from scripts.smc.stops_geometry import pending_stops_geometry_allows
from scripts.smc.setup_identity import pending_h1_bias_allows
from scripts.webhook.h1_bias import resolve_h1_bias_lazy
from scripts.webhook.runtime import WebhookRuntime
from scripts.webhook.setup_identity_gate import evaluate_identity_gate
from scripts.webhook.setup_risk_halt import evaluate_risk_halt_gate
from scripts.webhook.setup_time_gates import evaluate_setup_time_gates

logger = logging.getLogger("webhook_bridge")


async def handle_setup_pending(
    rt: WebhookRuntime,
    *,
    payload: Dict[str, Any],
    order_id: Optional[str],
    event: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    # 1a00. Terminal SETUP_ID must never revive (scenario 8 / B16).
    if order_id:
        allowed_id, admit_reason = rt.setup_registry.admit(order_id)
        if not allowed_id:
            reason = f"Setup identity gate blocked new risk: {admit_reason}"
            logger.warning(reason)
            await asyncio.to_thread(
                rt.mark_processed, order_id, event, "rejected_setup_terminal"
            )
            return {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": reason,
            }

    # 1a0. Persistent foundation risk halt (5% DD / daily gates)
    halt_reject = await evaluate_risk_halt_gate(rt, order_id=order_id, event=event)
    if halt_reject is not None:
        return halt_reject

    # 1a1. Broker/Demo identity gate before new risk
    identity_reject = await evaluate_identity_gate(rt, order_id=order_id, event=event)
    if identity_reject is not None:
        return identity_reject

    # 1a. Daily circuit / session / rollover / cooldown / news (ADR-011/007/010)
    event_dt, time_reject = await evaluate_setup_time_gates(
        rt,
        payload=payload,
        order_id=order_id,
        event=event,
        background_tasks=background_tasks,
    )
    if time_reject is not None:
        return time_reject

    # 1e. Dynamic Account Equity Sizing (ADR-020)
    broker_risk = None
    if not rt.adapter.dry_run:
        broker_risk = await asyncio.to_thread(rt.adapter.get_risk_snapshot)
    if not rt.adapter.dry_run and broker_risk is None:
        reason = "Execution Gated: MT5 account or symbol risk data unavailable."
        logger.error(reason)
        return {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": reason,
        }

    if not rt.adapter.dry_run:
        meta_ok, meta_reason = broker_metadata_allows_new_risk(broker_risk)
        if not meta_ok:
            reason = f"Broker metadata gate blocked new risk: {meta_reason}"
            logger.warning(reason)
            if order_id:
                await asyncio.to_thread(
                    rt.mark_processed, order_id, event, "rejected_broker_metadata"
                )
            return {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": reason,
            }

    # 1e2. Story 32: unknown/stale market or incomplete account blocks new risk.
    wall_now = datetime.now(timezone.utc)
    history_ready = True
    if rt.risk_halt is not None:
        history_ready = bool(getattr(rt.risk_halt, "history_ready", True))
    admission = evaluate_new_risk_admission(
        last_bar_time=event_dt,
        now=wall_now,
        history_ready=history_ready if not rt.adapter.dry_run else True,
        equity_known=rt.adapter.dry_run or broker_risk is not None,
        news_allowed=True,  # news already gated above
    )
    if not admission.allowed:
        reason = f"Admission gate blocked new risk: {admission.reason}"
        logger.warning(reason)
        if order_id:
            await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_stale_data")
        return {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": reason,
        }

    effective_balance = broker_risk["balance"] if broker_risk else rt.account_balance
    effective_equity = broker_risk["equity"] if broker_risk else rt.account_balance
    if not rt.adapter.dry_run:
        exposure = await asyncio.to_thread(rt.adapter.get_open_exposure)
        if exposure is None or exposure:
            return {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": "Broker exposure is present or unknown; new setup blocked",
            }

    entry = float(payload["limit"])
    sl = float(payload["sl"])
    tp1 = float(payload.get("tp1") or 0.0)
    tp2 = float(payload.get("tp2") or 0.0)
    direction = (
        Direction.BUY if payload.get("dir") == "BUY" else Direction.SELL
    )

    # Scenario 8: invalidation before submission on known opposing H1 bias.
    # Prefer TV payload fields; else live MT5 resolve (Gate C when TV omits bias).
    h1_bias, h1_bias_known = await asyncio.to_thread(
        resolve_h1_bias_lazy,
        payload,
        rt.adapter.resolve_live_h1_bias,
    )
    if h1_bias_known:
        bias_ok, bias_reason = pending_h1_bias_allows(
            pending_direction=direction,
            h1_bias=h1_bias,
            bias_known=True,
        )
        if not bias_ok:
            reason = f"H1 bias gate blocked new risk: {bias_reason}"
            logger.warning(reason)
            if order_id:
                rt.setup_registry.mark_terminal(order_id, bias_reason)
                await asyncio.to_thread(
                    rt.mark_processed, order_id, event, "rejected_h1_bias"
                )
            return {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": reason,
            }

    # Sizing with zero spread double-buffer invariant
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
    # Pattern A: Offload blocking MT5 broker call to thread pool
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
        await asyncio.to_thread(rt.adapter.update_setup_status, order_id, "accepted", exec_res.order_id)
    if order_id:
        await asyncio.to_thread(rt.mark_processed, order_id, event, "success")

    # Pattern B: accepted-pending card only (never a fill/phantom trade card).
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

