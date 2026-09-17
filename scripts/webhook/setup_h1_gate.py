"""H1 bias gate for SETUP_PENDING before PLACE_LIMIT."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

from scripts.smc.setup_identity import pending_h1_bias_allows
from scripts.smc.types import Direction
from scripts.webhook.h1_bias import resolve_h1_bias_lazy
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def evaluate_setup_h1_gate(
    rt: WebhookRuntime,
    *,
    payload: Dict[str, Any],
    direction: Direction,
    order_id: Optional[str],
    event: str,
) -> Tuple[Optional[str], bool, Optional[Dict[str, Any]]]:
    """
    Scenario 8: known opposing H1 bias blocks new risk and terminalizes identity.

    Returns (h1_bias, h1_bias_known, reject_or_none).
    """
    h1_bias, h1_bias_known = await asyncio.to_thread(
        resolve_h1_bias_lazy,
        payload,
        rt.adapter.resolve_live_h1_bias,
    )
    if not h1_bias_known:
        return h1_bias, False, None

    bias_ok, bias_reason = pending_h1_bias_allows(
        pending_direction=direction,
        h1_bias=h1_bias,
        bias_known=True,
    )
    if bias_ok:
        return h1_bias, True, None

    reason = f"H1 bias gate blocked new risk: {bias_reason}"
    logger.warning(reason)
    if order_id:
        rt.setup_registry.mark_terminal(order_id, bias_reason)
        await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_h1_bias")
    return h1_bias, True, {
        "status": "rejected",
        "order_id": order_id,
        "event": event,
        "reason": reason,
    }
