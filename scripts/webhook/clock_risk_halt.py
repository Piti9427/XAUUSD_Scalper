"""Clock risk-halt observe + flatten when halt trips (story 10 / master-pro)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Sequence, Tuple

from scripts.smc.halt_actions import bot_owned_order_ids, plan_halt_flatten_intents
from scripts.smc.risk_halt import (
    apply_broker_lifecycle_losses,
    observe_equity,
    save_risk_halt_state,
)
from scripts.smc.types import OrderIntentType
from scripts.webhook.pending_cancel import cancel_unfilled_pending
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def observe_and_persist_risk_halt(
    rt: WebhookRuntime,
    *,
    now_utc: datetime,
    broker_closes: Sequence[Dict[str, Any]],
) -> None:
    """Update equity gates + broker loss counts; persist when halt path configured."""
    if rt.risk_halt is None or rt.halt_path is None:
        return
    equity_raw = await asyncio.to_thread(rt.adapter.get_account_equity)
    history_ready = rt.adapter.dry_run or equity_raw is not None
    equity_now = float(equity_raw) if equity_raw is not None else float(rt.account_balance)
    observe_equity(
        rt.risk_halt,
        equity_now,
        now=now_utc,
        history_ready=history_ready,
    )
    apply_broker_lifecycle_losses(rt.risk_halt, broker_closes)
    await asyncio.to_thread(save_risk_halt_state, rt.halt_path, rt.risk_halt)


async def flatten_on_risk_halt(
    rt: WebhookRuntime,
    *,
    pending_ids: Sequence[str],
) -> Tuple[List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Spec: cancel bot pendings + close bot positions when risk halt is active.

    Dry-run uses journal pending/open-fill IDs. Live merges broker SMC_ comments.
    Returns (still_pending, halt_cancels, halt_closes).
    """
    halt_cancels: List[Dict[str, Any]] = []
    halt_closes: List[Dict[str, Any]] = []
    ids = list(pending_ids)
    if rt.risk_halt is None or not rt.risk_halt.halted:
        return ids, halt_cancels, halt_closes

    open_rows = await asyncio.to_thread(rt.adapter.list_open_fills)
    open_ids = [str(row["order_id"]) for row in open_rows if row.get("order_id")]

    if not rt.adapter.dry_run:
        exposure = await asyncio.to_thread(rt.adapter.get_open_exposure)
        journal_pending = set(await asyncio.to_thread(rt.adapter.list_unfilled_pendings))
        for oid in bot_owned_order_ids(exposure):
            if oid in journal_pending and oid not in ids:
                ids.append(oid)
            elif oid not in open_ids and oid not in ids:
                open_ids.append(oid)

    still_pending: List[str] = []
    for oid in ids:
        kept, row = await cancel_unfilled_pending(
            rt,
            order_id=oid,
            intent_reason="foundation_risk_halt: cancel bot pending",
            lifecycle_reason="foundation_risk_halt",
            terminal_reason="foundation_risk_halt",
            result_reason="foundation_risk_halt",
        )
        if kept:
            still_pending.append(oid)
        halt_cancels.append(row)

    for intent in plan_halt_flatten_intents(
        pending_order_ids=(),
        open_position_ids=open_ids,
        reason="foundation_risk_halt",
    ):
        if intent.intent_type != OrderIntentType.CLOSE_MARKET:
            continue
        result = await asyncio.to_thread(rt.adapter.execute_intent, intent)
        halt_closes.append(
            {
                "order_id": intent.order_id,
                "status": "success" if result.success else "rejected",
                "reason": "foundation_risk_halt",
                "message": result.message,
            }
        )
        if result.success and intent.order_id:
            await asyncio.to_thread(
                rt.adapter.log_lifecycle_event,
                event_type="TRADE_CLOSED",
                order_id=intent.order_id,
                reason="foundation_risk_halt: close bot position",
            )
            rt.setup_registry.mark_terminal(intent.order_id, "foundation_risk_halt")
            await asyncio.to_thread(rt.adapter.finish_setup, intent.order_id)

    if halt_cancels or halt_closes:
        logger.warning(
            "Clock risk halt flatten: cancels=%s closes=%s",
            len(halt_cancels),
            len(halt_closes),
        )
    return still_pending, halt_cancels, halt_closes
