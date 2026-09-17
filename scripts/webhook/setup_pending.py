"""SETUP_PENDING admission + PLACE_LIMIT path."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks

from scripts.smc.types import Direction, OrderIntent, OrderIntentType
from scripts.smc.risk import calculate_lot_size
from scripts.smc.risk_halt import observe_equity, save_risk_halt_state
from scripts.smc.broker_identity import verify_broker_identity, BrokerIdentityReport
from scripts.smc.halt_actions import bot_owned_order_ids, plan_halt_flatten_intents
from scripts.smc.data_freshness import evaluate_new_risk_admission
from scripts.smc.broker_metadata import broker_metadata_allows_new_risk
from scripts.smc.stops_geometry import pending_stops_geometry_allows
from scripts.smc.setup_identity import pending_h1_bias_allows
from scripts.smc.detection import is_in_session
from scripts.webhook.h1_bias import resolve_h1_bias_lazy
from scripts.webhook.runtime import WebhookRuntime

logger = logging.getLogger("webhook_bridge")


async def handle_setup_pending(
    rt: WebhookRuntime,
    *,
    payload: Dict[str, Any],
    order_id: Optional[str],
    event: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
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

    # S1–S4 / foundation: new entry only inside fixed UTC admission windows.
    if not is_in_session(event_dt, extended=True):
        reason = (
            "Admission window blocked new risk: out_of_session "
            "(London 07:00–10:30 / NY 12:30–16:30 UTC)"
        )
        logger.warning(reason)
        if order_id:
            await asyncio.to_thread(rt.mark_processed, order_id, event, "rejected_out_of_session")
        return {
            "status": "rejected",
            "order_id": order_id,
            "event": event,
            "reason": reason,
        }

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

