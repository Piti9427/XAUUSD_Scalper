"""Clock rollover / TIME_EXIT planning and broker-evidence close execution."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import BackgroundTasks

from scripts.smc.clock_exit import (
    ClockExitPlan,
    OpenFill,
    plan_clock_rollover_exits,
    plan_clock_time_exits,
)
from scripts.smc.notification_policy import may_notify_close
from scripts.smc.quotes import disclose_missing_quote_at_exit_deadline
from scripts.smc.trade_closed_pnl import resolve_trade_closed_pnl
from scripts.smc.types import OrderIntent, OrderIntentType
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


def plan_clock_exit_orders(
    fills: Sequence[OpenFill],
    *,
    now_utc: datetime,
    rollover_hour_utc: int,
    rollover_minute_utc: int,
    max_hold_bars: Optional[int],
    bar_minutes: int,
) -> List[ClockExitPlan]:
    """ADR-007 rollover always; TIME_EXIT only when max_hold configured."""
    plans_by_id: Dict[str, ClockExitPlan] = {}
    for plan in plan_clock_rollover_exits(
        fills,
        now=now_utc,
        rollover_hour_utc=rollover_hour_utc,
        rollover_minute_utc=rollover_minute_utc,
    ):
        plans_by_id[plan.order_id] = plan
    if max_hold_bars is not None:
        for plan in plan_clock_time_exits(
            fills,
            now=now_utc,
            max_hold_bars=max_hold_bars,
            bar_minutes=bar_minutes,
        ):
            # Prefer existing ROLLOVER reason if both fire.
            plans_by_id.setdefault(plan.order_id, plan)
    return list(plans_by_id.values())


async def disclose_exit_missing_quotes(
    rt: WebhookRuntime,
    *,
    plans: Sequence[ClockExitPlan],
    bar_high: Optional[float],
    bar_low: Optional[float],
) -> List[Dict[str, Any]]:
    """Session flat / TIME_EXIT with no live quote: disclose; never invent exit px."""
    rows: List[Dict[str, Any]] = []
    if not plans or (bar_high is not None and bar_low is not None):
        return rows
    exit_quote_rows = disclose_missing_quote_at_exit_deadline(
        open_order_ids=[p.order_id for p in plans],
        have_live_quotes=False,
    )
    for row in exit_quote_rows:
        rows.append(row)
        await asyncio.to_thread(
            rt.adapter.log_lifecycle_event,
            event_type="MISSING_QUOTE",
            order_id=row["order_id"],
            reason="missing_quote:session_flat_exit",
        )
    return rows


async def execute_clock_exit_plans(
    rt: WebhookRuntime,
    *,
    plans: Sequence[ClockExitPlan],
    background_tasks: BackgroundTasks,
) -> List[Dict[str, Any]]:
    """
    CLOSE_MARKET each plan. Never invent cash; missing live PnL → reconcile_required.
    """
    exit_results: List[Dict[str, Any]] = []
    for plan in plans:
        intent = OrderIntent(
            intent_type=OrderIntentType.CLOSE_MARKET,
            order_id=plan.order_id,
            reason=plan.reason,
        )
        exec_close = await asyncio.to_thread(rt.adapter.execute_intent, intent)
        already_flat = (
            not exec_close.success
            and "not found" in (exec_close.message or "").lower()
        )
        if not exec_close.success and not already_flat:
            exit_results.append(
                {
                    "order_id": plan.order_id,
                    "status": "rejected",
                    "message": exec_close.message,
                }
            )
            continue

        if not rt.adapter.dry_run:
            exposure_after = await asyncio.to_thread(rt.adapter.get_open_exposure)
            if exposure_after == []:
                await asyncio.to_thread(rt.adapter.finish_setup, plan.order_id)

        broker_pnl = None
        fill = None
        if not rt.adapter.dry_run:
            broker_pnl = await asyncio.to_thread(
                rt.adapter.get_realized_pnl_for_order, plan.order_id
            )
            fill = await asyncio.to_thread(rt.adapter.get_fill_geometry, plan.order_id)

        entry = float((fill or {}).get("entry_price") or 0.0)
        sl = float((fill or {}).get("sl_price") or 0.0)
        lot = float((fill or {}).get("lot_size") or 0.0)
        pnl_r, pnl_dollar, pnl_status = resolve_trade_closed_pnl(
            dry_run=bool(rt.adapter.dry_run),
            broker_pnl=broker_pnl,
            entry=entry,
            sl=sl,
            lot=lot,
            exit_price=0.0,
            direction=str(plan.direction or "BUY"),
        )
        if pnl_status == "live_broker_pnl_missing":
            already_flagged = await asyncio.to_thread(
                rt.adapter.has_lifecycle_event, plan.order_id, "RECONCILE_REQUIRED"
            )
            if not already_flagged:
                await asyncio.to_thread(
                    rt.adapter.log_lifecycle_event,
                    event_type="RECONCILE_REQUIRED",
                    order_id=plan.order_id,
                    direction=plan.direction,
                    reason="broker deal cashflow missing for live clock exit",
                )
            await asyncio.to_thread(
                rt.mark_processed, plan.order_id, "TRADE_CLOSED", "reconcile_required"
            )
            exit_results.append(
                {
                    "order_id": plan.order_id,
                    "status": "reconcile_required",
                    "reason": "broker deal cashflow missing for live clock exit",
                    "pnl_dollar": None,
                    "pnl_r": None,
                    "execution": {
                        "success": exec_close.success,
                        "message": exec_close.message,
                    },
                }
            )
            continue

        await asyncio.to_thread(
            rt.adapter.log_lifecycle_event,
            event_type="TRADE_CLOSED",
            order_id=plan.order_id,
            direction=plan.direction,
            reason=plan.reason,
            pnl_dollar=pnl_dollar,
            pnl_r=pnl_r,
        )
        if rt.notifier and getattr(rt.notifier, "enabled", False):
            if (
                may_notify_close(
                    broker_close_success=bool(exec_close.success),
                    already_flat_on_broker=already_flat,
                )
                and pnl_dollar is not None
                and pnl_r is not None
            ):
                try:
                    from scripts.smc.notifier import format_trade_closed_card
                    from scripts.smc.types import Direction as Dir

                    tc_dir = (
                        Dir.BUY
                        if str(plan.direction or "BUY").upper() == "BUY"
                        else Dir.SELL
                    )
                    card = format_trade_closed_card(
                        direction=tc_dir,
                        exit_price=0.0,
                        pnl_dollars=float(pnl_dollar),
                        pnl_r=float(pnl_r),
                        reason=plan.reason,
                    )
                    background_tasks.add_task(rt.dispatch_tg_safe, card)
                except Exception as exc:
                    logger.warning("Clock TIME_EXIT notify failed: %s", exc)
            else:
                logger.warning(
                    "Clock TIME_EXIT notify suppressed — need broker evidence "
                    "and known PnL (%s success=%s pnl=%s/%s)",
                    plan.order_id,
                    exec_close.success,
                    pnl_dollar,
                    pnl_r,
                )
        exit_results.append(
            {
                "order_id": plan.order_id,
                "status": "success",
                "reason": plan.reason,
                "pnl_dollar": pnl_dollar,
                "pnl_r": pnl_r,
                "execution": {
                    "success": exec_close.success,
                    "message": exec_close.message,
                },
            }
        )
    return exit_results


async def run_clock_time_exits(
    rt: WebhookRuntime,
    *,
    now_utc: datetime,
    bar_high: Optional[float],
    bar_low: Optional[float],
    background_tasks: BackgroundTasks,
) -> Tuple[List[OpenFill], List[ClockExitPlan], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Plan + disclose missing exit quotes + execute closes.

    Returns (fills, plans, exit_results, extra_missing_quote_rows).
    """
    open_rows = await asyncio.to_thread(rt.adapter.list_open_fills)
    fills = [
        OpenFill(
            order_id=row["order_id"],
            open_time=row["open_time"],
            direction=row.get("direction"),
        )
        for row in open_rows
    ]
    plans = plan_clock_exit_orders(
        fills,
        now_utc=now_utc,
        rollover_hour_utc=rt.rollover_hour_utc,
        rollover_minute_utc=rt.rollover_minute_utc,
        max_hold_bars=rt.max_hold_bars,
        bar_minutes=rt.bar_minutes,
    )
    extra_missing = await disclose_exit_missing_quotes(
        rt, plans=plans, bar_high=bar_high, bar_low=bar_low
    )
    exit_results = await execute_clock_exit_plans(
        rt, plans=plans, background_tasks=background_tasks
    )
    return fills, plans, exit_results, extra_missing
