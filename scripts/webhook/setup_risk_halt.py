"""Foundation risk-halt gate for SETUP_PENDING (story 10)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from scripts.smc.halt_actions import bot_owned_order_ids, plan_halt_flatten_intents
from scripts.smc.risk_halt import observe_equity, save_risk_halt_state
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def evaluate_risk_halt_gate(
    rt: WebhookRuntime,
    *,
    order_id: Optional[str],
    event: str,
) -> Optional[Dict[str, Any]]:
    """
    Observe equity / persist halt state. If halted, flatten bot exposure and reject.

    Returns a reject response dict when halted; None when new risk may continue.
    """
    if rt.risk_halt is None or rt.halt_path is None:
        return None

    equity_raw = await asyncio.to_thread(rt.adapter.get_account_equity)
    # Dry-run uses configured balance; live must see broker equity or stay blocked.
    history_ready = rt.adapter.dry_run or equity_raw is not None
    equity_now = (
        float(equity_raw) if equity_raw is not None else float(rt.account_balance)
    )
    observe_equity(
        rt.risk_halt,
        equity_now,
        now=datetime.now(timezone.utc),
        history_ready=history_ready,
    )
    await asyncio.to_thread(save_risk_halt_state, rt.halt_path, rt.risk_halt)
    if not rt.risk_halt.halted:
        return None

    # Story 10: request cancel/close of bot-owned exposure, then block new risk.
    exposure = None
    if not rt.adapter.dry_run:
        exposure = await asyncio.to_thread(rt.adapter.get_open_exposure)
    bot_ids = bot_owned_order_ids(exposure)
    flatten = plan_halt_flatten_intents(
        pending_order_ids=bot_ids,
        open_position_ids=bot_ids,
        reason="foundation_risk_halt",
    )
    flatten_results: List[Dict[str, Any]] = []
    for intent in flatten:
        result = await asyncio.to_thread(rt.adapter.execute_intent, intent)
        flatten_results.append(
            {
                "intent": intent.intent_type.value,
                "order_id": intent.order_id,
                "success": result.success,
                "message": result.message,
            }
        )
    reason = (
        "Foundation risk halt active: "
        f"dd={rt.risk_halt.drawdown_halt} daily={rt.risk_halt.daily_equity_halt} "
        f"losses_today={rt.risk_halt.net_losing_trades_today} "
        f"history_ready={rt.risk_halt.history_ready}"
    )
    logger.warning(reason)
    if order_id:
        await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_risk_halt")
    return {
        "status": "rejected",
        "order_id": order_id,
        "event": event,
        "reason": reason,
        "flatten_actions": flatten_results,
    }
