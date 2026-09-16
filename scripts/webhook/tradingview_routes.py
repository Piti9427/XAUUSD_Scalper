"""TradingView webhook admission + execution route."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status

from scripts.smc.types import Direction, OrderIntent, OrderIntentType
from scripts.smc.risk import calculate_lot_size
from scripts.smc.risk_halt import (
    observe_equity,
    record_net_losing_trade,
    save_risk_halt_state,
)
from scripts.smc.broker_identity import verify_broker_identity, BrokerIdentityReport
from scripts.smc.halt_actions import bot_owned_order_ids, plan_halt_flatten_intents
from scripts.smc.data_freshness import evaluate_new_risk_admission
from scripts.smc.broker_metadata import broker_metadata_allows_new_risk
from scripts.smc.stops_geometry import pending_stops_geometry_allows, sl_modify_freeze_allows
from scripts.smc.setup_identity import pending_h1_bias_allows
from scripts.webhook.h1_bias import resolve_h1_bias_lazy
from scripts.webhook.runtime import WebhookRuntime

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
        if event == "SETUP_PENDING":
            # 1a00. Terminal SETUP_ID must never revive (scenario 8 / B16).
            if order_id:
                allowed_id, admit_reason = rt.setup_registry.admit(order_id)
                if not allowed_id:
                    reason = f"Setup identity gate blocked new risk: {admit_reason}"
                    logger.warning(reason)
                    await asyncio.to_thread(
                        rt.mark_processed, order_id, event, "rejected_setup_terminal"
                    )
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": reason,
                    }

            # 1a0. Persistent foundation risk halt (5% DD / daily gates)
            if rt.risk_halt is not None and rt.halt_path is not None:
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
                if rt.risk_halt.halted:
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
                    flatten_results = []
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

            # 1a1. Broker/Demo identity gate before new risk
            if rt.enforce_identity:
                if rt.identity_gate is not None:
                    identity = await asyncio.to_thread(rt.identity_gate)
                else:
                    def _default_identity() -> BrokerIdentityReport:
                        try:
                            import MetaTrader5 as mt5
                        except ImportError:
                            return verify_broker_identity(
                                account_info=None, symbol_info=None
                            )
                        return verify_broker_identity(
                            account_info=mt5.account_info() if not rt.adapter.dry_run else None,
                            symbol_info=mt5.symbol_info(rt.adapter.symbol) if not rt.adapter.dry_run else None,
                        )

                    identity = await asyncio.to_thread(_default_identity)
                if not identity.ok:
                    reason = (
                        "Broker identity gate failed: "
                        + ",".join(identity.reasons)
                    )
                    logger.warning(reason)
                    if order_id:
                        await asyncio.to_thread(
                            rt.mark_processed, order_id, event, "rejected_identity"
                        )
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": reason,
                    }

            # 1a. Daily Circuit Breaker Guard (ADR-011)
            losses_today = await asyncio.to_thread(rt.adapter.get_daily_realized_losses)
            if losses_today >= rt.max_daily_losses:
                reason = f"Daily Circuit Breaker Triggered (ADR-011): {losses_today}/{rt.max_daily_losses} daily losses reached. Trading halted."
                logger.warning(reason)
                if rt.notifier and getattr(rt.notifier, "enabled", False):
                    from scripts.smc.notifier import format_circuit_breaker_card
                    background_tasks.add_task(rt.dispatch_tg_safe, format_circuit_breaker_card(losses_today=losses_today))
                if order_id:
                    await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_circuit_breaker")
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": reason,
                }

            # 1b. Rollover Flat Guard (ADR-007)
            event_time_raw = payload.get("time")
            if event_time_raw is not None:
                try:
                    if isinstance(event_time_raw, (int, float)):
                        if event_time_raw > 1e11:
                            event_dt = datetime.fromtimestamp(event_time_raw / 1000.0, tz=timezone.utc)
                        else:
                            event_dt = datetime.fromtimestamp(float(event_time_raw), tz=timezone.utc)
                    else:
                        _raw = str(event_time_raw).replace(" ", "T")
                        _parsed = datetime.fromisoformat(_raw)
                        event_dt = (
                            _parsed.replace(tzinfo=timezone.utc)
                            if _parsed.tzinfo is None
                            else _parsed.astimezone(timezone.utc)
                        )
                except Exception:
                    event_dt = datetime.now(timezone.utc)
            else:
                event_dt = datetime.now(timezone.utc)

            if (event_dt.hour > rt.rollover_hour_utc) or (
                event_dt.hour == rt.rollover_hour_utc and event_dt.minute >= rt.rollover_minute_utc
            ):
                reason = f"Rollover Flat Guard (ADR-007): Orders blocked after {rt.rollover_hour_utc}:{rt.rollover_minute_utc:02d} UTC"
                logger.warning(reason)
                if order_id:
                    await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_rollover")
                return {
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
                    reason = f"Post-SL Cooldown Active (ADR-011): {remaining_mins}m remaining before new setups allowed."
                    logger.warning(reason)
                    if order_id:
                        await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_cooldown")
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": reason,
                    }

            # 1d. High-Impact USD News Blackout / unknown schedule (ADR-010 + foundation)
            if rt.news_manager is not None:
                if hasattr(rt.news_manager, "new_risk_allowed"):
                    events = getattr(rt.news_manager, "events", None)
                    schedule_known = bool(getattr(rt.news_manager, "schedule_known", events is not None))
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
                            await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_news")
                        return {
                            "status": "rejected",
                            "order_id": order_id,
                            "event": event,
                            "reason": reason,
                        }
                else:
                    is_blackout, news_name = await asyncio.to_thread(
                        rt.news_manager.is_in_blackout, event_dt, getattr(rt.news_manager, "events", [])
                    )
                    if is_blackout:
                        reason = f"News Blackout (ADR-010): High-impact news '{news_name}' within 30m window."
                        logger.warning(reason)
                        if order_id:
                            await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_news")
                        return {
                            "status": "rejected",
                            "order_id": order_id,
                            "event": event,
                            "reason": reason,
                        }

            # 1e. Dynamic Account Equity Sizing (ADR-020)
            broker_risk = None
            if not rt.adapter.dry_run:
                broker_risk = await asyncio.to_thread(rt.adapter.get_risk_snapshot)
            if not rt.adapter.dry_run and broker_risk is None:
                reason = "Execution Gated: MT5 account or symbol risk data unavailable."
                logger.error(reason)
                return {
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
                    return {
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
                news_allowed=True,  # news already gated above
            )
            if not admission.allowed:
                reason = f"Admission gate blocked new risk: {admission.reason}"
                logger.warning(reason)
                if order_id:
                    await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_stale_data")
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": reason,
                }

            effective_balance = broker_risk["balance"] if broker_risk else rt.account_balance
            effective_equity = broker_risk["equity"] if broker_risk else rt.account_balance
            if not rt.adapter.dry_run:
                exposure = await asyncio.to_thread(rt.adapter.get_open_exposure)
                if exposure is None or exposure:
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": "Broker exposure is present or unknown; new setup blocked",
                    }

            entry = float(payload["limit"])
            sl = float(payload["sl"])
            tp1 = float(payload.get("tp1") or 0.0)
            tp2 = float(payload.get("tp2") or 0.0)
            direction = (
                Direction.BUY if payload.get("dir") == "BUY" else Direction.SELL
            )

            # Scenario 8: invalidation before submission on known opposing H1 bias.
            # Prefer TV payload fields; else live MT5 resolve (Gate C when TV omits bias).
            h1_bias, h1_bias_known = await asyncio.to_thread(
                resolve_h1_bias_lazy,
                payload,
                rt.adapter.resolve_live_h1_bias,
            )
            if h1_bias_known:
                bias_ok, bias_reason = pending_h1_bias_allows(
                    pending_direction=direction,
                    h1_bias=h1_bias,
                    bias_known=True,
                )
                if not bias_ok:
                    reason = f"H1 bias gate blocked new risk: {bias_reason}"
                    logger.warning(reason)
                    if order_id:
                        rt.setup_registry.mark_terminal(order_id, bias_reason)
                        await asyncio.to_thread(
                            rt.mark_processed, order_id, event, "rejected_h1_bias"
                        )
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": reason,
                    }

            # Sizing with zero spread double-buffer invariant
            lot_result = calculate_lot_size(
                balance=effective_balance,
                entry_price=entry,
                sl_price=sl,
                risk_pct=rt.risk_pct,
                spread_buffer=0.0,
                equity=effective_equity,
                min_lot=broker_risk["min_lot"] if broker_risk else 0.01,
                max_lot=broker_risk["max_lot"] if broker_risk else 10.0,
                lot_step=broker_risk["lot_step"] if broker_risk else 0.01,
                contract_size=broker_risk["contract_size"] if broker_risk else 100.0,
                commission_per_lot=rt.commission_per_lot,
                slippage_allowance=rt.slippage_allowance,
                require_cost_model=not rt.adapter.dry_run,
            )

            if not lot_result.is_valid:
                if order_id:
                    await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected")
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": f"ADR-020 Small-Account Risk Gate: {lot_result.reason}",
                }

            # Scenario 10: broker stops_level / point conversion must allow SL/TP geometry.
            if not rt.adapter.dry_run and broker_risk is not None:
                tp_for_geom = tp2 if tp2 > 0 else (tp1 if tp1 > 0 else None)
                geom_ok, geom_reason = pending_stops_geometry_allows(
                    entry_price=entry,
                    sl_price=sl,
                    tp_price=tp_for_geom,
                    point=float(broker_risk["point"]),
                    stops_level=float(broker_risk["stops_level"]),
                )
                if not geom_ok:
                    reason = f"Stops geometry gate blocked new risk: {geom_reason}"
                    logger.warning(reason)
                    if order_id:
                        await asyncio.to_thread(
                            rt.mark_processed, order_id, event, "rejected_stops_geometry"
                        )
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": reason,
                    }

            claim: Optional[Dict[str, str]] = None
            if order_id:
                claim = await asyncio.to_thread(rt.adapter.claim_setup, payload)
                if claim["status"] == "duplicate":
                    return {
                        "status": "ignored_duplicate",
                        "order_id": order_id,
                        "receipt_id": claim["receipt_id"],
                    }
                if claim["status"] != "claimed":
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "reason": f"Setup claim {claim['status']}; broker reconciliation required",
                    }

            intent = OrderIntent(
                intent_type=OrderIntentType.PLACE_LIMIT,
                direction=direction,
                limit_price=entry,
                sl_price=sl,
                tp_price=tp2 if tp2 > 0 else tp1,
                lot_size=lot_result.lot_size,
                order_id=order_id,
                reason=payload.get("type", "SMC_PRIME"),
            )
            # Pattern A: Offload blocking MT5 broker call to thread pool
            try:
                exec_res = await asyncio.to_thread(rt.adapter.execute_intent, intent)
            except Exception as exc:
                logger.error(f"Execution error or timeout for {order_id}: {exc}")
                if order_id:
                    await asyncio.to_thread(rt.adapter.update_setup_status, order_id, "uncertain")
                return {
                    "status": "uncertain",
                    "order_id": order_id,
                    "event": event,
                    "reason": f"Execution uncertain: {exc}. Broker reconciliation required.",
                }
            if not exec_res.success:
                from scripts.smc.notification_policy import classify_exec_outcome
                outcome = classify_exec_outcome(
                    success=exec_res.success,
                    status=getattr(exec_res, "status", None),
                )
                if outcome == "uncertain":
                    if order_id:
                        await asyncio.to_thread(rt.adapter.update_setup_status, order_id, "uncertain")
                    return {
                        "status": "uncertain",
                        "order_id": order_id,
                        "event": event,
                        "reason": exec_res.message,
                        "exec_status": getattr(exec_res, "status", "UNKNOWN"),
                    }
                if order_id:
                    await asyncio.to_thread(rt.adapter.update_setup_status, order_id, "rejected")
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": exec_res.message,
                    "exec_status": getattr(exec_res, "status", "REJECTED"),
                }
            if order_id:
                await asyncio.to_thread(rt.adapter.update_setup_status, order_id, "accepted", exec_res.order_id)
            if order_id:
                await asyncio.to_thread(rt.mark_processed, order_id, event, "success")

            # Pattern B: accepted-pending card only (never a fill/phantom trade card).
            from scripts.smc.notification_policy import may_notify_execution
            if (
                rt.notifier
                and getattr(rt.notifier, "enabled", False)
                and may_notify_execution(
                    success=exec_res.success,
                    status=getattr(exec_res, "status", "OK"),
                )
            ):
                try:
                    from scripts.smc.notifier import format_order_accepted_card
                    card = format_order_accepted_card(
                        direction=direction,
                        limit_price=entry,
                        sl_price=sl,
                        tp_price=tp2 if tp2 > 0 else tp1,
                        lot_size=lot_result.lot_size,
                        order_id=order_id,
                        ticket=exec_res.order_id,
                    )
                    background_tasks.add_task(rt.dispatch_tg_safe, card)
                except Exception as exc:
                    logger.warning(f"Failed to schedule Telegram notification: {exc}")

            return {
                "status": "success",
                "action": "LIMIT_PLACED",
                "order_id": order_id,
                **({"receipt_id": claim["receipt_id"]} if claim else {}),
                "lot_size": lot_result.lot_size,
                "ticket": exec_res.order_id,
                "message": exec_res.message,
            }

        # 2. ORDER_FILLED: Record Active Trade Correlation
        elif event == "ORDER_FILLED":
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
