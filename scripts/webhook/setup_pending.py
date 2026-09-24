"""SETUP_PENDING admission + PLACE_LIMIT path."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks

from scripts.smc.types import Direction
from scripts.webhook.runtime import WebhookRuntime
from scripts.webhook.setup_broker_gates import evaluate_setup_broker_gates
from scripts.webhook.setup_h1_gate import evaluate_setup_h1_gate
from scripts.webhook.setup_identity_gate import evaluate_identity_gate
from scripts.webhook.setup_place_limit import place_setup_limit
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
            await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_setup_terminal")
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

    # 1e–1e2. Broker snapshot / metadata / stale / flat exposure
    broker_risk, broker_reject = await evaluate_setup_broker_gates(
        rt,
        event_dt=event_dt,
        order_id=order_id,
        event=event,
    )
    if broker_reject is not None:
        return broker_reject

    effective_balance = broker_risk["balance"] if broker_risk else rt.account_balance
    effective_equity = broker_risk["equity"] if broker_risk else rt.account_balance

    entry = float(payload["limit"])
    sl = float(payload["sl"])
    tp1 = float(payload.get("tp1") or 0.0)
    tp2 = float(payload.get("tp2") or 0.0)
    direction = Direction.BUY if payload.get("dir") == "BUY" else Direction.SELL

    # Scenario 8: invalidation before submission on known opposing H1 bias.
    _, _, h1_reject = await evaluate_setup_h1_gate(
        rt,
        payload=payload,
        direction=direction,
        order_id=order_id,
        event=event,
    )
    if h1_reject is not None:
        return h1_reject

    return await place_setup_limit(
        rt,
        payload=payload,
        broker_risk=broker_risk,
        effective_balance=effective_balance,
        effective_equity=effective_equity,
        entry=entry,
        sl=sl,
        tp1=tp1,
        tp2=tp2,
        direction=direction,
        order_id=order_id,
        event=event,
        background_tasks=background_tasks,
    )
