"""Internal clock reconciler route (scenarios 8/18/19 + lifecycle)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import BackgroundTasks, Depends, FastAPI, Request

from scripts.smc.types import Direction, OrderIntent, OrderIntentType
from scripts.smc.risk_halt import (
    apply_broker_lifecycle_losses,
    observe_equity,
    save_risk_halt_state,
)
from scripts.smc.setup_identity import pending_h1_bias_allows
from scripts.smc.quotes import (
    disclose_missing_quote_at_exit_deadline,
    disclose_missing_quote_for_pending_sl,
    pending_sl_touched_before_fill,
)
from scripts.smc.trade_closed_pnl import resolve_trade_closed_pnl
from scripts.webhook.h1_bias import resolve_h1_bias_lazy
from scripts.webhook.pending_cancel import cancel_unfilled_pending
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


def register_clock_route(app: FastAPI, rt: WebhookRuntime) -> None:
    @app.post("/internal/clock")
    async def handle_clock_tick(
        request: Request,
        background_tasks: BackgroundTasks,
        authorized: bool = Depends(rt.verify_auth),
    ):
        """
        Periodic reconciler: news-cancel unfilled pendings + wall-clock TIME_EXIT.

        Scenario 18/19 — never force-close filled positions on news; never notify
        TRADE CLOSED without broker evidence.
        Optional JSON body may carry h1_bias / h1_bias_known (scenario 8).
        """
        from scripts.smc.broker_lifecycle import reconcile_broker_lifecycle
        from scripts.smc.clock_exit import (
            OpenFill,
            plan_clock_time_exits,
            plan_clock_rollover_exits,
        )
        from scripts.smc.notification_policy import may_notify_close, may_notify_execution
        from scripts.smc.types import Position as PosCard

        clock_payload: Dict[str, Any] = {}
        try:
            parsed = await request.json()
            if isinstance(parsed, dict):
                clock_payload = parsed
        except Exception:
            clock_payload = {}

        now_utc = datetime.now(timezone.utc)
        cancel_results = []
        h1_bias_cancels = []
        sl_before_fill_cancels = []
        missing_quote_disclosures = []
        exit_results = []
        uncertain_results = []
        lifecycle = await asyncio.to_thread(
            reconcile_broker_lifecycle,
            rt.adapter,
            now=now_utc,
            order_ttl_bars=rt.order_ttl_bars,
            bar_minutes=rt.bar_minutes,
        )

        # Story 35: reconcile uncertain intents before admitting new risk / more submits.
        uncertain_ids = await asyncio.to_thread(rt.adapter.list_uncertain_order_ids)
        for oid in uncertain_ids:
            outcome = await asyncio.to_thread(rt.adapter.reconcile_uncertain, oid)
            uncertain_results.append({"order_id": oid, "outcome": outcome})
            logger.info("Clock reconcile_uncertain %s -> %s", oid, outcome)

        # Stories 5–7: disclose bot vs manual vs cash_flow deal cash separately.
        account_pnl_rows = await asyncio.to_thread(rt.adapter.sync_classified_account_pnl)

        if rt.risk_halt is not None and rt.halt_path is not None:
            equity_raw = await asyncio.to_thread(rt.adapter.get_account_equity)
            history_ready = rt.adapter.dry_run or equity_raw is not None
            equity_now = (
                float(equity_raw)
                if equity_raw is not None
                else float(rt.account_balance)
            )
            observe_equity(
                rt.risk_halt,
                equity_now,
                now=now_utc,
                history_ready=history_ready,
            )
            apply_broker_lifecycle_losses(
                rt.risk_halt, lifecycle.get("broker_closes", [])
            )
            await asyncio.to_thread(save_risk_halt_state, rt.halt_path, rt.risk_halt)

        for fill_row in lifecycle.get("broker_fills", []):
            order_id = fill_row.get("order_id")
            if not order_id:
                continue
            rt.setup_registry.mark_terminal(order_id, "filled")
            await asyncio.to_thread(rt.mark_processed, order_id, "ORDER_FILLED", "success")
            if not (rt.notifier and getattr(rt.notifier, "enabled", False)):
                continue
            if not may_notify_execution(success=True, status="FILLED"):
                continue
            try:
                from scripts.smc.notifier import format_order_filled_card

                geom = await asyncio.to_thread(rt.adapter.get_fill_geometry, order_id)
                if not geom or not geom.get("entry_price") or not geom.get("sl_price"):
                    continue
                entry = float(geom["entry_price"])
                sl = float(geom["sl_price"])
                lot = float(geom.get("lot_size") or 0.0) or 0.01
                dir_raw = str(geom.get("direction") or "BUY").upper()
                fill_dir = Direction.BUY if dir_raw == "BUY" else Direction.SELL
                pos_card = PosCard(
                    direction=fill_dir,
                    entry_price=entry,
                    sl_price=sl,
                    tp_price=0.0,
                    lot_size=lot,
                    open_time=now_utc,
                    initial_sl_distance=abs(entry - sl),
                )
                background_tasks.add_task(
                    rt.dispatch_tg_safe, format_order_filled_card(pos_card)
                )
            except Exception as exc:
                logger.warning(
                    "Lifecycle fill notify failed for %s: %s", order_id, exc
                )

        for close in lifecycle.get("broker_closes", []):
            order_id = close.get("order_id")
            pnl_dollar = close.get("pnl_dollar")
            pnl_r = close.get("pnl_r")
            if order_id:
                await asyncio.to_thread(rt.mark_processed, order_id, "TRADE_CLOSED", "success")
            if (
                rt.notifier
                and getattr(rt.notifier, "enabled", False)
                and order_id
                and pnl_dollar is not None
                and pnl_r is not None
                and may_notify_close(
                    broker_close_success=False,
                    already_flat_on_broker=True,
                )
            ):
                try:
                    from scripts.smc.notifier import format_trade_closed_card

                    fill = await asyncio.to_thread(rt.adapter.get_fill_geometry, order_id)
                    dir_raw = (fill or {}).get("direction", "BUY")
                    tc_dir = (
                        Direction.BUY
                        if str(dir_raw).upper() == "BUY"
                        else Direction.SELL
                    )
                    card = format_trade_closed_card(
                        direction=tc_dir,
                        exit_price=0.0,
                        pnl_dollars=float(pnl_dollar),
                        pnl_r=float(pnl_r),
                        reason="broker_lifecycle_close_detected",
                    )
                    background_tasks.add_task(rt.dispatch_tg_safe, card)
                except Exception as exc:
                    logger.warning(
                        "Lifecycle close notify failed for %s: %s", order_id, exc
                    )

        # Scenario 18: cancel unfilled pendings when news gate blocks new risk.
        # Fetch pendings once; mutate local list after cancels (perf).
        pending_ids = await asyncio.to_thread(rt.adapter.list_unfilled_pendings)
        if rt.news_manager is not None and hasattr(rt.news_manager, "should_cancel_pending"):
            events = getattr(rt.news_manager, "events", None)
            schedule_known = bool(
                getattr(rt.news_manager, "schedule_known", events is not None)
            )
            cancel_pending, cancel_reason = await asyncio.to_thread(
                rt.news_manager.should_cancel_pending,
                now_utc,
                events,
                schedule_known=schedule_known,
                window_mins=30,
            )
            if cancel_pending:
                still_pending = []
                for oid in pending_ids:
                    kept, row = await cancel_unfilled_pending(
                        rt,
                        order_id=oid,
                        intent_reason=f"news_pending_cancel:{cancel_reason}",
                        lifecycle_reason=f"news_pending_cancel:{cancel_reason}",
                        terminal_reason=f"news_pending_cancel:{cancel_reason}",
                        result_reason=cancel_reason,
                    )
                    if kept:
                        still_pending.append(oid)
                    cancel_results.append(row)
                pending_ids = still_pending

        # Scenario 8: known H1 bias flip cancels opposing unfilled pendings (webhook path).
        # Prefer explicit clock JSON; else live MT5 resolve (Gate C cron empty body).
        h1_bias, h1_bias_known = await asyncio.to_thread(
            resolve_h1_bias_lazy,
            clock_payload,
            rt.adapter.resolve_live_h1_bias,
        )
        if h1_bias_known:
            still_pending = []
            for oid in pending_ids:
                pending_dir = await asyncio.to_thread(rt.adapter.get_pending_direction, oid)
                if not pending_dir:
                    still_pending.append(oid)
                    continue
                bias_ok, bias_reason = pending_h1_bias_allows(
                    pending_direction=pending_dir,
                    h1_bias=h1_bias,
                    bias_known=True,
                )
                if bias_ok:
                    still_pending.append(oid)
                    continue
                intent_reason = f"H1 bias invalidation: {bias_reason}"
                kept, row = await cancel_unfilled_pending(
                    rt,
                    order_id=oid,
                    intent_reason=intent_reason,
                    lifecycle_reason=f"h1_bias_invalidated:{bias_reason}",
                    terminal_reason=bias_reason,
                    result_reason=bias_reason,
                )
                if kept:
                    still_pending.append(oid)
                h1_bias_cancels.append(row)
            pending_ids = still_pending

        # B15 / S1–S4: SL before fill using clock OHLC or live bid/ask snapshot.
        # Missing both → disclose; never invent a synthetic high/low.
        bar_high = None
        bar_low = None
        have_ohlc = isinstance(clock_payload.get("high"), (int, float)) and isinstance(
            clock_payload.get("low"), (int, float)
        )
        if have_ohlc:
            bar_high = float(clock_payload["high"])
            bar_low = float(clock_payload["low"])
        else:
            quotes = await asyncio.to_thread(rt.adapter.get_market_quotes)
            if quotes and quotes.get("ask") is not None and quotes.get("bid") is not None:
                bar_high = float(quotes["ask"])
                bar_low = float(quotes["bid"])
        if bar_high is None or bar_low is None:
            missing_quote_disclosures = disclose_missing_quote_for_pending_sl(
                pending_order_ids=pending_ids,
                have_ohlc=False,
                have_live_quotes=False,
            )
            for row in missing_quote_disclosures:
                await asyncio.to_thread(
                    rt.adapter.log_lifecycle_event,
                    event_type="MISSING_QUOTE",
                    order_id=row["order_id"],
                    reason="missing_quote:sl_before_fill_check",
                )
                logger.info(
                    "Clock missing quote disclosure for pending %s (no invent OHLC)",
                    row["order_id"],
                )
        else:
            still_pending = []
            for oid in pending_ids:
                geom = await asyncio.to_thread(rt.adapter.get_pending_geometry, oid)
                if not geom or geom.get("sl_price") is None or not geom.get("direction"):
                    still_pending.append(oid)
                    continue
                limit_price = geom.get("limit_price")
                if limit_price is None:
                    limit_price = geom["sl_price"]
                if not pending_sl_touched_before_fill(
                    direction=str(geom["direction"]),
                    limit_price=float(limit_price),
                    sl_price=float(geom["sl_price"]),
                    bar_high=bar_high,
                    bar_low=bar_low,
                ):
                    still_pending.append(oid)
                    continue
                kept, row = await cancel_unfilled_pending(
                    rt,
                    order_id=oid,
                    intent_reason="SL before fill: planned stop reached while pending",
                    lifecycle_reason="sl_before_fill",
                    terminal_reason="sl_before_fill",
                    result_reason="sl_before_fill",
                )
                if kept:
                    still_pending.append(oid)
                sl_before_fill_cancels.append(row)
            pending_ids = still_pending

        open_rows = await asyncio.to_thread(rt.adapter.list_open_fills)
        fills = [
            OpenFill(
                order_id=row["order_id"],
                open_time=row["open_time"],
                direction=row.get("direction"),
            )
            for row in open_rows
        ]
        # ADR-007 rollover always; TIME_EXIT only when max_hold configured.
        plans_by_id = {}
        for plan in plan_clock_rollover_exits(
            fills,
            now=now_utc,
            rollover_hour_utc=rt.rollover_hour_utc,
            rollover_minute_utc=rt.rollover_minute_utc,
        ):
            plans_by_id[plan.order_id] = plan
        if rt.max_hold_bars is not None:
            for plan in plan_clock_time_exits(
                fills,
                now=now_utc,
                max_hold_bars=rt.max_hold_bars,
                bar_minutes=rt.bar_minutes,
            ):
                # Prefer existing ROLLOVER reason if both fire.
                plans_by_id.setdefault(plan.order_id, plan)
        plans = list(plans_by_id.values())

        # Session flat / TIME_EXIT with no live quote: disclose; never invent exit px.
        if plans and (bar_high is None or bar_low is None):
            exit_quote_rows = disclose_missing_quote_at_exit_deadline(
                open_order_ids=[p.order_id for p in plans],
                have_live_quotes=False,
            )
            for row in exit_quote_rows:
                missing_quote_disclosures.append(row)
                await asyncio.to_thread(
                    rt.adapter.log_lifecycle_event,
                    event_type="MISSING_QUOTE",
                    order_id=row["order_id"],
                    reason="missing_quote:session_flat_exit",
                )

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
                # Close already requested; keep fill open until broker cash appears.
                # Stamp RECONCILE once — no invent dollars, no TRADE_CLOSED yet.
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
                # No phantom WIN card: require broker evidence AND known PnL.
                if may_notify_close(
                    broker_close_success=bool(exec_close.success),
                    already_flat_on_broker=already_flat,
                ) and pnl_dollar is not None and pnl_r is not None:
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

        has_work = bool(
            cancel_results
            or h1_bias_cancels
            or sl_before_fill_cancels
            or missing_quote_disclosures
            or exit_results
            or uncertain_results
            or account_pnl_rows
            or lifecycle.get("ttl_cancels")
            or lifecycle.get("broker_fills")
            or lifecycle.get("broker_closes")
        )
        status_out = "ok"
        reason_out = None
        if rt.max_hold_bars is None and not plans and not has_work:
            # Idle tick: rollover planner still armed; max_hold optional.
            status_out = "ok"
            reason_out = "idle_clock_tick"
        return {
            "status": status_out,
            "action": "CLOCK_TICK",
            "checked": len(fills),
            "cancels": cancel_results,
            "h1_bias_cancels": h1_bias_cancels,
            "sl_before_fill_cancels": sl_before_fill_cancels,
            "missing_quote_disclosures": missing_quote_disclosures,
            "exits": exit_results,
            "uncertain": uncertain_results,
            "account_pnl": account_pnl_rows,
            "lifecycle": lifecycle,
            "reason": reason_out,
            "max_hold_bars": rt.max_hold_bars,
            "timestamp": now_utc.isoformat(),
        }
