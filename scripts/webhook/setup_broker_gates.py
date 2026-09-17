"""Broker risk snapshot, metadata, stale-data, and exposure gates for SETUP."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from scripts.smc.broker_metadata import broker_metadata_allows_new_risk
from scripts.smc.data_freshness import evaluate_new_risk_admission
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def evaluate_setup_broker_gates(
    rt: WebhookRuntime,
    *,
    event_dt: datetime,
    order_id: Optional[str],
    event: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Fetch broker risk and enforce metadata / stale / flat-exposure admission.

    Returns (broker_risk_or_none, reject_or_none).
    On success reject is None; broker_risk may still be None in dry_run.
    """
    # 1e. Dynamic Account Equity Sizing (ADR-020) — snapshot first
    broker_risk = None
    if not rt.adapter.dry_run:
        broker_risk = await asyncio.to_thread(rt.adapter.get_risk_snapshot)
    if not rt.adapter.dry_run and broker_risk is None:
        reason = "Execution Gated: MT5 account or symbol risk data unavailable."
        logger.error(reason)
        return None, {
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
            return broker_risk, {
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
        news_allowed=True,  # news already gated upstream
    )
    if not admission.allowed:
        reason = f"Admission gate blocked new risk: {admission.reason}"
        logger.warning(reason)
        if order_id:
            await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_stale_data")
        return broker_risk, {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": reason,
        }

    if not rt.adapter.dry_run:
        exposure = await asyncio.to_thread(rt.adapter.get_open_exposure)
        if exposure is None or exposure:
            return broker_risk, {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": "Broker exposure is present or unknown; new setup blocked",
            }

    return broker_risk, None
