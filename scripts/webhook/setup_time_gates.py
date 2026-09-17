"""Time-window SETUP admission: circuit, session, rollover, cooldown, news."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from fastapi import BackgroundTasks

from scripts.smc.detection import is_in_session
from scripts.webhook.runtime import WebhookRuntime
from scripts.webhook.setup_time import parse_setup_event_time

logger = logging.getLogger("webhook_bridge")


async def evaluate_setup_time_gates(
    rt: WebhookRuntime,
    *,
    payload: Dict[str, Any],
    order_id: Optional[str],
    event: str,
    background_tasks: BackgroundTasks,
) -> Tuple[datetime, Optional[Dict[str, Any]]]:
    """
    Run ADR-011/007/010 + session admission checks.

    Returns (event_dt_utc, reject_or_none).
    """
    # 1a. Daily Circuit Breaker Guard (ADR-011)
    losses_today = await asyncio.to_thread(rt.adapter.get_daily_realized_losses)
    if losses_today >= rt.max_daily_losses:
        reason = (
            f"Daily Circuit Breaker Triggered (ADR-011): "
            f"{losses_today}/{rt.max_daily_losses} daily losses reached. Trading halted."
        )
        logger.warning(reason)
        if rt.notifier and getattr(rt.notifier, "enabled", False):
            from scripts.smc.notifier import format_circuit_breaker_card

            background_tasks.add_task(
                rt.dispatch_tg_safe, format_circuit_breaker_card(losses_today=losses_today)
            )
        if order_id:
            await asyncio.to_thread(
                rt.mark_processed, order_id, event, "rejected_circuit_breaker"
            )
        return parse_setup_event_time(payload.get("time")), {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": reason,
        }

    event_dt = parse_setup_event_time(payload.get("time"))

    # S1–S4 / foundation: new entry only inside fixed UTC admission windows.
    if not is_in_session(event_dt, extended=True):
        reason = (
            "Admission window blocked new risk: out_of_session "
            "(London 07:00–10:30 / NY 12:30–16:30 UTC)"
        )
        logger.warning(reason)
        if order_id:
            await asyncio.to_thread(
                rt.mark_processed, order_id, event, "rejected_out_of_session"
            )
        return event_dt, {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": reason,
        }

    if (event_dt.hour > rt.rollover_hour_utc) or (
        event_dt.hour == rt.rollover_hour_utc
        and event_dt.minute >= rt.rollover_minute_utc
    ):
        reason = (
            f"Rollover Flat Guard (ADR-007): Orders blocked after "
            f"{rt.rollover_hour_utc}:{rt.rollover_minute_utc:02d} UTC"
        )
        logger.warning(reason)
        if order_id:
            await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_rollover")
        return event_dt, {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": reason,
        }

    # 1c. 30-Minute Post-SL Cooldown Check (ADR-011)
    last_loss_dt = await asyncio.to_thread(rt.adapter.get_last_loss_timestamp)
    if last_loss_dt:
        elapsed_seconds = (event_dt - last_loss_dt).total_seconds()
        if 0 <= elapsed_seconds < 1800:
            remaining_mins = int((1800 - elapsed_seconds) // 60) + 1
            reason = (
                f"Post-SL Cooldown Active (ADR-011): {remaining_mins}m remaining "
                "before new setups allowed."
            )
            logger.warning(reason)
            if order_id:
                await asyncio.to_thread(
                    rt.mark_processed, order_id, event, "rejected_cooldown"
                )
            return event_dt, {
                "status": "rejected",
                "order_id": order_id,
                "event": event,
                "reason": reason,
            }

    # 1d. High-Impact USD News Blackout / unknown schedule (ADR-010 + foundation)
    if rt.news_manager is not None:
        if hasattr(rt.news_manager, "new_risk_allowed"):
            events = getattr(rt.news_manager, "events", None)
            schedule_known = bool(
                getattr(rt.news_manager, "schedule_known", events is not None)
            )
            allowed_news, news_reason = await asyncio.to_thread(
                rt.news_manager.new_risk_allowed,
                event_dt,
                events,
                schedule_known=schedule_known,
            )
            if not allowed_news:
                reason = f"News gate blocked new risk: {news_reason}"
                logger.warning(reason)
                if order_id:
                    await asyncio.to_thread(
                        rt.mark_processed, order_id, event, "rejected_news"
                    )
                return event_dt, {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": reason,
                }
        else:
            is_blackout, news_name = await asyncio.to_thread(
                rt.news_manager.is_in_blackout,
                event_dt,
                getattr(rt.news_manager, "events", []),
            )
            if is_blackout:
                reason = (
                    f"News Blackout (ADR-010): High-impact news '{news_name}' "
                    "within 30m window."
                )
                logger.warning(reason)
                if order_id:
                    await asyncio.to_thread(
                        rt.mark_processed, order_id, event, "rejected_news"
                    )
                return event_dt, {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": reason,
                }

    return event_dt, None
