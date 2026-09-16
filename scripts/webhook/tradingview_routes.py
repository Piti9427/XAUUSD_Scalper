"""TradingView webhook admission + execution route."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status

from scripts.smc.types import Direction, OrderIntent, OrderIntentType
from scripts.smc.risk_halt import (
    observe_equity,
    record_net_losing_trade,
    save_risk_halt_state,
)
from scripts.smc.stops_geometry import sl_modify_freeze_allows
from scripts.smc.setup_identity import pending_h1_bias_allows
from scripts.webhook.h1_bias import resolve_h1_bias_lazy
from scripts.webhook.runtime import WebhookRuntime
from scripts.webhook.setup_pending import handle_setup_pending

logger = logging.getLogger("webhook_bridge")


def register_tradingview_route(app: FastAPI, rt: WebhookRuntime) -> None:
    @app.post("/webhook/tradingview")
    async def handle_tradingview_webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        authorized: bool = Depends(rt.verify_auth),
    ):
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed JSON payload",
            )

        event = payload.get("event", "UNKNOWN")
        order_id = payload.get("order_id")
        logger.info(f"Received verified webhook event: {event} for order_id: {order_id}")

        if event == "SETUP_PENDING" and order_id:
            existing_setup = await asyncio.to_thread(rt.adapter.inspect_setup, payload)
            if existing_setup is not None:
                return {
                    "status": "ignored_duplicate" if existing_setup["status"] == "duplicate" else "rejected",
                    "order_id": order_id,
                    "event": event,
                    "receipt_id": existing_setup["receipt_id"],
                    **({"reason": "Conflicting payload for existing order_id"}
                       if existing_setup["status"] == "conflict" else {}),
                }

        # Idempotency Check: Fast-path in-memory check followed by SQLite
        if order_id and rt.is_processed(order_id, event):
            logger.warning(f"Ignoring duplicate webhook delivery for {order_id} ({event})")
            receipt_id = (
                await asyncio.to_thread(rt.adapter.get_setup_receipt, order_id)
                if event == "SETUP_PENDING" else None
            )
            return {
                "status": "ignored_duplicate",
                "order_id": order_id,
                "event": event,
                "message": f"Event {event} already processed for {order_id}",
                **({"receipt_id": receipt_id} if receipt_id else {}),
            }

        # 1. SETUP_PENDING: Place Pending Limit with Dynamic Risk Sizing
        # 1. SETUP_PENDING: Place Pending Limit with Dynamic Risk Sizing
        if event == "SETUP_PENDING":
            return await handle_setup_pending(
                rt,
                payload=payload,
                order_id=order_id,
                event=event,
                background_tasks=background_tasks,
            )

        if event == "ORDER_FILLED":
            if order_id and await asyncio.to_thread(
                rt.adapter.has_lifecycle_event, order_id, "ORDER_FILLED"
            ):
                await asyncio.to_thread(rt.mark_processed, order_id, event, "success")
                return {
                    "status": "ignored_duplicate",
                    "order_id": order_id,
                    "event": event,
                    "message": "ORDER_FILLED already recorded (broker lifecycle or prior webhook)",
                }

            entry = float(payload.get("entry") or 0.0)
            sl = float(payload.get("sl") or 0.0)
            tp1 = float(payload.get("tp1") or 0.0)
            tp2 = float(payload.get("tp2") or 0.0)
            direction = (
                Direction.BUY if payload.get("dir") == "BUY" else Direction.SELL
            )
            ticket = None
            reason = "TradingView Alert Fill Confirmation"
            if not rt.adapter.dry_run:
                pos = await asyncio.to_thread(rt.adapter.get_matching_position, order_id)
                if pos is None:
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": "Broker has no open position matching order_id",
                    }
                entry = float(pos.price_open)
                ticket = int(pos.ticket)
                reason = "TradingView Alert Fill Confirmation (Broker Verified)"

            await asyncio.to_thread(
                rt.adapter.log_lifecycle_event,
                event_type="ORDER_FILLED",
                direction=direction.value,
                entry_price=entry,
                sl_price=sl,
                tp_price=tp2 if tp2 > 0 else tp1,
                lot_size=(
                    float(pos.volume)
                    if not rt.adapter.dry_run and "pos" in locals() and pos is not None
                    else float(payload.get("lot_size") or 0.0) or None
                ),
                order_id=order_id,
                ticket=ticket,
                reason=reason,
            )
            if order_id and ticket and not rt.adapter.dry_run:
                await asyncio.to_thread(rt.adapter.update_setup_status, order_id, "accepted", ticket)
            if order_id:
                rt.setup_registry.mark_terminal(order_id, "filled")
                await asyncio.to_thread(rt.mark_processed, order_id, event, "success")

            if rt.notifier and getattr(rt.notifier, "enabled", False):
                try:
                    from scripts.smc.types import Position
                    from scripts.smc.notifier import format_order_filled_card
                    from scripts.smc.notification_policy import may_notify_execution
                    if not may_notify_execution(success=True, status="FILLED"):
                        raise RuntimeError("notification policy blocked fill card")
                    fill_lot = float(pos.volume) if not rt.adapter.dry_run and 'pos' in locals() and pos else float(payload.get("lot_size") or 0.01)
                    pos_card = Position(
                        direction=direction,
                        entry_price=entry,
                        sl_price=sl,
                        tp_price=tp2 if tp2 > 0 else tp1,
                        lot_size=fill_lot,
                        open_time=datetime.now(timezone.utc),
                        initial_sl_distance=abs(entry - sl),
                    )
                    background_tasks.add_task(rt.dispatch_tg_safe, format_order_filled_card(pos_card))
                except Exception as exc:
                    logger.warning(f"Failed to schedule Telegram notification: {exc}")

            return {
                "status": "success",
                "action": "ORDER_RECORDED",
                "order_id": order_id,
                "entry": entry,
                **({"ticket": ticket} if ticket else {}),
            }

        # 3. TP1_HIT_MOVE_BE: 50% Volume Scale-Out & Breakeven Relocation (ADR-018)
        elif event == "TP1_HIT_MOVE_BE":
            if not (rt.partial_tp_enabled and rt.be_enabled):
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": (
                        "TP1_HIT_MOVE_BE disabled by foundation defaults "
                        f"(partial_tp_enabled={rt.partial_tp_enabled}, be_enabled={rt.be_enabled})"
                    ),
                }

            new_sl = float(payload.get("new_sl") or 0.0)
            entry = float(payload.get("entry") or 0.0)
            close_pct = int(payload.get("close_percent") or 50)
            direction_raw = str(payload.get("dir", "BUY")).upper()
            if entry <= 0 or new_sl <= 0:
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": "TP1_HIT_MOVE_BE requires positive entry and new_sl",
                }
            # new_sl must sit on profit-side BE band (entry ± rt.be_buffer), not unconstrained.
            if direction_raw == "BUY":
                be_lo, be_hi = entry, entry + rt.be_buffer + 0.05
            else:
                be_lo, be_hi = entry - rt.be_buffer - 0.05, entry
            if not (be_lo <= new_sl <= be_hi):
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": (
                        f"new_sl {new_sl} outside BE band [{be_lo}, {be_hi}] "
                        f"for {direction_raw} entry={entry} be_buffer={rt.be_buffer}"
                    ),
                }

            # Fail closed before partial: freeze distance must allow the BE SL move.
            if not rt.adapter.dry_run:
                snap = await asyncio.to_thread(rt.adapter.get_risk_snapshot)
                if snap is None:
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": "broker risk snapshot unavailable for freeze check",
                    }
                quotes = await asyncio.to_thread(rt.adapter.get_market_quotes)
                if quotes is None:
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": "broker market quotes unavailable for freeze check",
                    }
                freeze_ok, freeze_reason = sl_modify_freeze_allows(
                    new_sl=new_sl,
                    market_bid=float(quotes["bid"]),
                    market_ask=float(quotes["ask"]),
                    point=float(snap["point"]),
                    freeze_level=float(snap["freeze_level"]),
                )
                if not freeze_ok:
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": f"rejected_freeze_level:{freeze_reason}",
                    }

            # 3a. Partial Close 50%
            intent_close = OrderIntent(
                intent_type=OrderIntentType.PARTIAL_CLOSE,
                order_id=order_id,
                reason=f"TP1_{close_pct}_PCT_SCALE_OUT",
            )
            exec_close = await asyncio.to_thread(rt.adapter.execute_intent, intent_close)
            if not exec_close.success:
                safety_close = await asyncio.to_thread(
                    rt.adapter.execute_intent,
                    OrderIntent(
                        intent_type=OrderIntentType.CLOSE_MARKET,
                        order_id=order_id,
                        reason="TP1 partial rejected: close whole position",
                    ),
                )
                return {
                    "status": "closed_for_safety" if safety_close.success else "reconcile_required",
                    "order_id": order_id,
                    "event": event,
                    "partial_message": exec_close.message,
                    "close_message": safety_close.message,
                }

            # 3b. Move SL to BE
            intent_be = OrderIntent(
                intent_type=OrderIntentType.MOVE_SL_TO_BE,
                sl_price=new_sl,
                order_id=order_id,
                reason="TP1_RELOCATE_SL_TO_BE",
            )
            exec_be = await asyncio.to_thread(rt.adapter.execute_intent, intent_be)

            if not exec_be.success:
                safety_close = await asyncio.to_thread(
                    rt.adapter.execute_intent,
                    OrderIntent(
                        intent_type=OrderIntentType.CLOSE_MARKET,
                        order_id=order_id,
                        reason="TP1 complete but BE rejected: close runner",
                    ),
                )
                return {
                    "status": "closed_for_safety" if safety_close.success else "reconcile_required",
                    "order_id": order_id,
                    "event": event,
                    "be_message": exec_be.message,
                    "close_message": safety_close.message,
                }

            if order_id:
                await asyncio.to_thread(rt.mark_processed, order_id, event, "success")

            if rt.notifier and getattr(rt.notifier, "enabled", False):
                try:
                    from scripts.smc.notifier import format_partial_tp_card
                    tp_dir = Direction.BUY if str(payload.get("dir", "BUY")).upper() == "BUY" else Direction.SELL
                    tp_lot = float(payload.get("lot_size") or 0.02)
                    closed_lot = round(tp_lot * (close_pct / 100.0), 2)
                    remaining_lot = round(tp_lot - closed_lot, 2)
                    card = format_partial_tp_card(
                        direction=tp_dir,
                        closed_lot=closed_lot,
                        remaining_lot=remaining_lot,
                        r_multiple=1.0,
                        entry_price=entry,
                    )
                    background_tasks.add_task(rt.dispatch_tg_safe, card)
                except Exception as exc:
                    logger.warning(f"Failed to schedule Telegram notification: {exc}")

            return {
                "status": "success",
                "action": "PARTIAL_CLOSE_AND_BE_MOVED",
                "order_id": order_id,
                "new_sl": new_sl,
                "close_message": exec_close.message,
                "be_message": exec_be.message,
            }

        # 4. ORDER_CANCELED: Remove Specific Pending Limit Order (ADR-024)
        elif event == "ORDER_CANCELED":
            reason = payload.get("reason", "TTL_EXPIRED")
            intent = OrderIntent(
                intent_type=OrderIntentType.CANCEL_LIMIT,
                order_id=order_id,
                reason=reason,
            )
            exec_cancel = await asyncio.to_thread(rt.adapter.execute_intent, intent)
            if not exec_cancel.success:
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": exec_cancel.message,
                }
            if not rt.adapter.dry_run:
                exposure_after_cancel = await asyncio.to_thread(rt.adapter.get_open_exposure)
                if exposure_after_cancel == []:
                    await asyncio.to_thread(rt.adapter.finish_setup, order_id)
            await asyncio.to_thread(
                rt.adapter.log_lifecycle_event,
                event_type="ORDER_CANCELED",
                order_id=order_id,
                reason=reason,
            )
            if order_id:
                rt.setup_registry.mark_terminal(order_id, str(reason or "canceled"))
                await asyncio.to_thread(rt.mark_processed, order_id, event, "success")

            return {
                "status": "success",
                "action": "ORDER_CANCELED",
                "order_id": order_id,
                "reason": reason,
                "message": exec_cancel.message,
            }

        # 5. TRADE_CLOSED: Finalize Position Lifecycle & Execute Broker Close
        elif event == "TRADE_CLOSED":
            if order_id and await asyncio.to_thread(
                rt.adapter.has_lifecycle_event, order_id, "TRADE_CLOSED"
            ):
                if order_id:
                    await asyncio.to_thread(rt.mark_processed, order_id, event, "success")
                return {
                    "status": "ignored_duplicate",
                    "order_id": order_id,
                    "event": event,
                    "message": "TRADE_CLOSED already recorded (broker lifecycle or prior webhook)",
                }

            reason = payload.get("reason", "POSITION_CLOSED")
            # Never invent R/$ from reason text — only explicit payload, broker cashflow,
            # or frozen_initial_r from fill geometry (entry/sl/lot).
            pnl_r = payload.get("pnl_r")
            pnl_dollar = payload.get("pnl_dollar")
            if pnl_r is not None:
                try:
                    pnl_r = float(pnl_r)
                except (TypeError, ValueError):
                    pnl_r = None
            if pnl_dollar is not None:
                try:
                    pnl_dollar = float(pnl_dollar)
                except (TypeError, ValueError):
                    pnl_dollar = None

            # Execute close market on broker if position is active or rollover flat
            intent_close = OrderIntent(
                intent_type=OrderIntentType.CLOSE_MARKET,
                order_id=order_id,
                reason=reason,
            )
            exec_close = await asyncio.to_thread(rt.adapter.execute_intent, intent_close)
            already_closed_by_broker = (
                not exec_close.success
                and "not found" in (exec_close.message or "").lower()
            )

            if not exec_close.success:
                if not already_closed_by_broker:
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": exec_close.message,
                    }

            if already_closed_by_broker or exec_close.success:
                # Release inbox on dry-run success and on fill-during-cancel "not found".
                if rt.adapter.dry_run or already_closed_by_broker:
                    await asyncio.to_thread(rt.adapter.finish_setup, order_id)
                if not rt.adapter.dry_run:
                    if exec_close.success:
                        exposure_after_close = await asyncio.to_thread(rt.adapter.get_open_exposure)
                        if exposure_after_close == []:
                            await asyncio.to_thread(rt.adapter.finish_setup, order_id)
                    broker_pnl = await asyncio.to_thread(
                        rt.adapter.get_realized_pnl_for_order, order_id
                    )
                    if broker_pnl is not None:
                        pnl_dollar = broker_pnl
                    else:
                        # Live: never halt/notify on TradingView invent cash.
                        pnl_dollar = None
                        pnl_r = None
                        if order_id:
                            await asyncio.to_thread(
                                rt.mark_processed, order_id, event, "reconcile_required"
                            )
                        return {
                            "status": "reconcile_required",
                            "order_id": order_id,
                            "event": event,
                            "reason": "broker deal cashflow missing for live TRADE_CLOSED",
                            "pnl_r": None,
                            "pnl_dollar": None,
                            "execution": {
                                "success": exec_close.success,
                                "message": exec_close.message,
                            },
                        }

            # Scenario 21: dollars only from payload/broker; R from frozen geometry.
            # Never invent cash from entry/exit/lot without broker/payload dollars.
            entry = float(payload.get("entry") or 0.0)
            sl = float(payload.get("sl") or 0.0)
            lot = float(payload.get("lot_size") or 0.0)
            exit_px = float(payload.get("exit_price") or 0.0)
            direction = str(payload.get("dir", "BUY")).upper()
            initial_dist = abs(entry - sl) if entry and sl else 0.0

            if pnl_r is None and pnl_dollar is not None and initial_dist > 0 and lot > 0:
                from scripts.smc.risk import frozen_initial_r

                pnl_r = frozen_initial_r(
                    pnl_dollars=float(pnl_dollar),
                    initial_sl_distance=initial_dist,
                    filled_lot=lot,
                )
            elif (
                rt.adapter.dry_run
                and pnl_r is None
                and initial_dist > 0
                and entry
                and exit_px
            ):
                # Dry-run only: geometric R from TV exit (not live invent cash).
                signed = (exit_px - entry) if direction == "BUY" else (entry - exit_px)
                pnl_r = round(signed / initial_dist, 4)

            await asyncio.to_thread(
                rt.adapter.log_lifecycle_event,
                event_type="TRADE_CLOSED",
                order_id=order_id,
                pnl_dollar=pnl_dollar,
                pnl_r=pnl_r,
                reason=reason,
                timestamp=payload.get("time"),
            )
            # Foundation risk halt: two net losing bot closes trip daily loss gate.
            if rt.risk_halt is not None and rt.halt_path is not None:
                is_net_loss = (
                    (pnl_r is not None and float(pnl_r) < 0)
                    or (pnl_dollar is not None and float(pnl_dollar) < 0)
                )
                if is_net_loss:
                    record_net_losing_trade(rt.risk_halt)
                    await asyncio.to_thread(save_risk_halt_state, rt.halt_path, rt.risk_halt)
            if order_id:
                await asyncio.to_thread(rt.mark_processed, order_id, event, "success")

            if rt.notifier and getattr(rt.notifier, "enabled", False):
                try:
                    from scripts.smc.notifier import format_trade_closed_card
                    from scripts.smc.notification_policy import may_notify_close
                    known_pnl = pnl_r is not None and pnl_dollar is not None
                    if (
                        may_notify_close(
                            broker_close_success=bool(exec_close.success),
                            already_flat_on_broker=already_closed_by_broker,
                        )
                        and known_pnl
                    ):
                        tc_dir = Direction.BUY if str(payload.get("dir", "BUY")).upper() == "BUY" else Direction.SELL
                        card = format_trade_closed_card(
                            direction=tc_dir,
                            exit_price=float(payload.get("exit_price") or 0.0),
                            pnl_dollars=float(pnl_dollar),
                            pnl_r=float(pnl_r),
                            reason=reason,
                        )
                        background_tasks.add_task(rt.dispatch_tg_safe, card)
                    else:
                        logger.warning(
                            "TRADE_CLOSED notify suppressed — need broker evidence "
                            "and known PnL (order_id=%s success=%s pnl=%s/%s)",
                            order_id,
                            exec_close.success,
                            pnl_dollar,
                            pnl_r,
                        )
                except Exception as exc:
                    logger.warning(f"Failed to schedule Telegram notification: {exc}")

            return {
                "status": "success",
                "action": "TRADE_CLOSED",
                "order_id": order_id,
                "reason": reason,
                "pnl_r": pnl_r,
                "pnl_dollar": pnl_dollar,
                "execution": {
                    "success": exec_close.success,
                    "message": exec_close.message,
                },
            }

        return {
            "status": "success",
            "event": event,
            "order_id": order_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
