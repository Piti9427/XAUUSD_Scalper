"""Broker/Demo identity gate for SETUP_PENDING."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from scripts.smc.broker_identity import verify_broker_identity, BrokerIdentityReport
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def evaluate_identity_gate(
    rt: WebhookRuntime,
    *,
    order_id: Optional[str],
    event: str,
) -> Optional[Dict[str, Any]]:
    """Return reject dict when identity enforcement fails; None when ok / disabled."""
    if not rt.enforce_identity:
        return None

    if rt.identity_gate is not None:
        identity = await asyncio.to_thread(rt.identity_gate)
    else:

        def _default_identity() -> BrokerIdentityReport:
            try:
                import MetaTrader5 as mt5
            except ImportError:
                return verify_broker_identity(account_info=None, symbol_info=None)
            return verify_broker_identity(
                account_info=mt5.account_info() if not rt.adapter.dry_run else None,
                symbol_info=(
                    mt5.symbol_info(rt.adapter.symbol) if not rt.adapter.dry_run else None
                ),
            )

        identity = await asyncio.to_thread(_default_identity)

    if identity.ok:
        return None

    reason = "Broker identity gate failed: " + ",".join(identity.reasons)
    logger.warning(reason)
    if order_id:
        await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_identity")
    return {
        "status": "rejected",
        "order_id": order_id,
        "event": event,
        "reason": reason,
    }
