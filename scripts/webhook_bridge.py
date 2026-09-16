import asyncio
from datetime import datetime, timezone
import math
import time
from typing import Optional, Dict, Any, Set, Tuple, Callable
import logging
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Header, Request, BackgroundTasks, status
from fastapi.responses import JSONResponse

from scripts.smc.types import Direction, OrderIntentType, OrderIntent
from scripts.smc.mt5_adapter import SMCExecutionAdapter
from scripts.smc.risk import calculate_lot_size
from scripts.smc.risk_halt import (
    load_risk_halt_state,
    new_risk_halt_state,
    observe_equity,
    record_net_losing_trade,
    apply_broker_lifecycle_losses,
    save_risk_halt_state,
)
from scripts.smc.broker_identity import verify_broker_identity, BrokerIdentityReport
from scripts.smc.halt_actions import bot_owned_order_ids, plan_halt_flatten_intents

logger = logging.getLogger("webhook_bridge")


def create_app(
    auth_token: str = "XAUUSD_DEFAULT_SECRET",
    dry_run: bool = True,
    db_path: str = "data/smc_trades.db",
    account_balance: float = 10000.0,
    risk_pct: float = 0.005,
    max_daily_losses: int = 2,
    rollover_hour_utc: int = 20,
    rollover_minute_utc: int = 55,
    notifier: Optional[Any] = None,
    news_manager: Optional[Any] = None,
    commission_per_lot: Optional[float] = None,
    slippage_allowance: Optional[float] = None,
    tp_r: float = 2.5,
    partial_tp_r: float = 1.0,
    risk_halt_path: Optional[str] = None,
    require_broker_identity: Optional[bool] = None,
    identity_gate: Optional[Callable[[], BrokerIdentityReport]] = None,
    max_hold_bars: Optional[int] = None,
    bar_minutes: int = 5,
    order_ttl_bars: Optional[int] = 4,
    partial_tp_enabled: bool = False,
    be_enabled: bool = False,
    be_buffer: float = 0.10,
) -> FastAPI:
    """
    Factory creating the FastAPI Webhook Bridge application with non-blocking async architecture.
    """
    app = FastAPI(
        title="XAUUSD Master Pro Webhook Bridge",
        version="1.1.0",
        description="Translates TradingView alerts into broker MT5 executions with strict async risk shields.",
    )

    start_time = time.time()
    adapter = SMCExecutionAdapter(symbol="XAUUSD", dry_run=dry_run, db_path=db_path)
    app.state.adapter = adapter

    enforce_identity = (
        require_broker_identity
        if require_broker_identity is not None
        else (not dry_run or identity_gate is not None)
    )
    halt_path = Path(risk_halt_path) if risk_halt_path else None
    risk_halt = None
    if halt_path is not None:
        risk_halt = load_risk_halt_state(halt_path) or new_risk_halt_state(account_balance)
        app.state.risk_halt = risk_halt

    # Pattern C: Two-Tier In-Memory Idempotency Cache (ADR-024)
    memory_idempotency_cache: Set[Tuple[str, str]] = set()

    def is_processed(oid: str, ev: str) -> bool:
        if (oid, ev) in memory_idempotency_cache:
            return True
        if adapter.is_webhook_processed(oid, ev):
            memory_idempotency_cache.add((oid, ev))
            return True
        return False

    def mark_processed(oid: str, ev: str, status_str: str = "success"):
        memory_idempotency_cache.add((oid, ev))
        adapter.mark_webhook_processed(oid, ev, status=status_str)

    # Pattern B: Safe Non-Blocking Dispatcher for Side-Effects (Telegram Notifier)
    def _dispatch_tg_safe(card: str):
        if notifier and getattr(notifier, "enabled", False):
            try:
                notifier.send_message(card)
            except Exception as exc:
                logger.warning(f"Background Telegram dispatch error: {exc}")

    async def verify_auth(
        authorization: Optional[str] = Header(None),
        x_webhook_secret: Optional[str] = Header(None),
    ):
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[len("Bearer ") :].strip()
        elif x_webhook_secret:
            token = x_webhook_secret.strip()

        if not token or token != auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing authorization token",
            )
        return True

    @app.get("/health")
    async def health_check():
        daily_losses = await asyncio.to_thread(adapter.get_daily_realized_losses)
        equity = (await asyncio.to_thread(adapter.get_account_equity)) or account_balance
        circuit_tripped = daily_losses >= max_daily_losses
        return {
            "status": "ok",
            "mode": "dry-run" if adapter.dry_run else "live",
            "mt5_connected": not adapter.dry_run and adapter.connected,
            "account_equity": equity,
            "daily_realized_losses": daily_losses,
            "circuit_breaker_tripped": circuit_tripped,
            "uptime_seconds": round(time.time() - start_time, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "max_hold_bars": max_hold_bars,
        }

    @app.post("/internal/clock")
    async def handle_clock_tick(
        background_tasks: BackgroundTasks,
        authorized: bool = Depends(verify_auth),
    ):
        """
        Periodic reconciler: news-cancel unfilled pendings + wall-clock TIME_EXIT.

        Scenario 18/19 — never force-close filled positions on news; never notify
        TRADE CLOSED without broker evidence.
        """
        from scripts.smc.broker_lifecycle import reconcile_broker_lifecycle
        from scripts.smc.clock_exit import OpenFill, plan_clock_time_exits
        from scripts.smc.notification_policy import may_notify_close, may_notify_execution
        from scripts.smc.types import Position as PosCard

        now_utc = datetime.now(timezone.utc)
        cancel_results = []
        exit_results = []
        lifecycle = await asyncio.to_thread(
            reconcile_broker_lifecycle,
            adapter,
            now=now_utc,
            order_ttl_bars=order_ttl_bars,
            bar_minutes=bar_minutes,
        )

        if risk_halt is not None and halt_path is not None:
            equity_raw = await asyncio.to_thread(adapter.get_account_equity)
            history_ready = adapter.dry_run or equity_raw is not None
            equity_now = (
                float(equity_raw)
                if equity_raw is not None
                else float(account_balance)
            )
            observe_equity(
                risk_halt,
                equity_now,
                now=now_utc,
                history_ready=history_ready,
            )
            apply_broker_lifecycle_losses(
                risk_halt, lifecycle.get("broker_closes", [])
            )
            await asyncio.to_thread(save_risk_halt_state, halt_path, risk_halt)

        for fill_row in lifecycle.get("broker_fills", []):
            order_id = fill_row.get("order_id")
            if not order_id:
                continue
            await asyncio.to_thread(mark_processed, order_id, "ORDER_FILLED", "success")
            if not (notifier and getattr(notifier, "enabled", False)):
                continue
            if not may_notify_execution(success=True, status="FILLED"):
                continue
            try:
                from scripts.smc.notifier import format_order_filled_card

                geom = await asyncio.to_thread(adapter.get_fill_geometry, order_id)
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
                    _dispatch_tg_safe, format_order_filled_card(pos_card)
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
                await asyncio.to_thread(mark_processed, order_id, "TRADE_CLOSED", "success")
            if (
                notifier
                and getattr(notifier, "enabled", False)
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

                    fill = await asyncio.to_thread(adapter.get_fill_geometry, order_id)
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
                    background_tasks.add_task(_dispatch_tg_safe, card)
                except Exception as exc:
                    logger.warning(
                        "Lifecycle close notify failed for %s: %s", order_id, exc
                    )

        # Scenario 18: cancel unfilled pendings when news gate blocks new risk.
        if news_manager is not None and hasattr(news_manager, "should_cancel_pending"):
            events = getattr(news_manager, "events", None)
            schedule_known = bool(
                getattr(news_manager, "schedule_known", events is not None)
            )
            cancel_pending, cancel_reason = await asyncio.to_thread(
                news_manager.should_cancel_pending,
                now_utc,
                events,
                schedule_known=schedule_known,
                window_mins=30,
            )
            if cancel_pending:
                pending_ids = await asyncio.to_thread(adapter.list_unfilled_pendings)
                for oid in pending_ids:
                    intent = OrderIntent(
                        intent_type=OrderIntentType.CANCEL_LIMIT,
                        order_id=oid,
                        reason=f"news_pending_cancel:{cancel_reason}",
                    )
                    exec_cancel = await asyncio.to_thread(adapter.execute_intent, intent)
                    if exec_cancel.success:
                        await asyncio.to_thread(
                            adapter.log_lifecycle_event,
                            event_type="ORDER_CANCELED",
                            order_id=oid,
                            reason=f"news_pending_cancel:{cancel_reason}",
                        )
                        await asyncio.to_thread(adapter.finish_setup, oid)
                    elif "not found" in (exec_cancel.message or "").lower():
                        # Fill-during-cancel: release inbox so clock does not re-spam.
                        await asyncio.to_thread(adapter.finish_setup, oid)
                    cancel_results.append(
                        {
                            "order_id": oid,
                            "status": "success" if exec_cancel.success else "rejected",
                            "reason": cancel_reason,
                            "message": exec_cancel.message,
                        }
                    )

        if max_hold_bars is None:
            has_work = bool(cancel_results or lifecycle.get("ttl_cancels"))
            return {
                "status": "ok" if has_work else "disabled",
                "action": "CLOCK_TICK",
                "cancels": cancel_results,
                "exits": [],
                "lifecycle": lifecycle,
                "reason": None if has_work else "max_hold_bars_not_configured",
                "timestamp": now_utc.isoformat(),
            }

        open_rows = await asyncio.to_thread(adapter.list_open_fills)
        fills = [
            OpenFill(
                order_id=row["order_id"],
                open_time=row["open_time"],
                direction=row.get("direction"),
            )
            for row in open_rows
        ]
        plans = plan_clock_time_exits(
            fills,
            now=now_utc,
            max_hold_bars=max_hold_bars,
            bar_minutes=bar_minutes,
        )
        for plan in plans:
            intent = OrderIntent(
                intent_type=OrderIntentType.CLOSE_MARKET,
                order_id=plan.order_id,
                reason=plan.reason,
            )
            exec_close = await asyncio.to_thread(adapter.execute_intent, intent)
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

            if not adapter.dry_run:
                exposure_after = await asyncio.to_thread(adapter.get_open_exposure)
                if exposure_after == []:
                    await asyncio.to_thread(adapter.finish_setup, plan.order_id)

            pnl_dollar = None
            pnl_r = None
            if not adapter.dry_run:
                broker_pnl = await asyncio.to_thread(
                    adapter.get_realized_pnl_for_order, plan.order_id
                )
                if broker_pnl is not None:
                    pnl_dollar = broker_pnl
                    fill = await asyncio.to_thread(adapter.get_fill_geometry, plan.order_id)
                    if fill and fill.get("entry_price") and fill.get("sl_price") and fill.get("lot_size"):
                        from scripts.smc.risk import frozen_initial_r

                        pnl_r = frozen_initial_r(
                            pnl_dollars=float(pnl_dollar),
                            initial_sl_distance=abs(
                                float(fill["entry_price"]) - float(fill["sl_price"])
                            ),
                            filled_lot=float(fill["lot_size"]),
                        )

            await asyncio.to_thread(
                adapter.log_lifecycle_event,
                event_type="TRADE_CLOSED",
                order_id=plan.order_id,
                direction=plan.direction,
                reason=plan.reason,
                pnl_dollar=pnl_dollar,
                pnl_r=pnl_r,
            )
            if notifier and getattr(notifier, "enabled", False):
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
                        background_tasks.add_task(_dispatch_tg_safe, card)
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

        return {
            "status": "ok",
            "action": "CLOCK_TICK",
            "checked": len(fills),
            "cancels": cancel_results,
            "exits": exit_results,
            "lifecycle": lifecycle,
            "timestamp": now_utc.isoformat(),
        }

    @app.post("/webhook/tradingview")
    async def handle_tradingview_webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        authorized: bool = Depends(verify_auth),
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

        if event == "SETUP_PENDING" and order_id and not adapter.dry_run:
            existing_setup = await asyncio.to_thread(adapter.inspect_setup, payload)
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
        if order_id and is_processed(order_id, event):
            logger.warning(f"Ignoring duplicate webhook delivery for {order_id} ({event})")
            receipt_id = (
                await asyncio.to_thread(adapter.get_setup_receipt, order_id)
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
            # 1a0. Persistent foundation risk halt (5% DD / daily gates)
            if risk_halt is not None and halt_path is not None:
                equity_raw = await asyncio.to_thread(adapter.get_account_equity)
                # Dry-run uses configured balance; live must see broker equity or stay blocked.
                history_ready = adapter.dry_run or equity_raw is not None
                equity_now = (
                    float(equity_raw) if equity_raw is not None else float(account_balance)
                )
                observe_equity(
                    risk_halt,
                    equity_now,
                    now=datetime.now(timezone.utc),
                    history_ready=history_ready,
                )
                await asyncio.to_thread(save_risk_halt_state, halt_path, risk_halt)
                if risk_halt.halted:
                    # Story 10: request cancel/close of bot-owned exposure, then block new risk.
                    exposure = None
                    if not adapter.dry_run:
                        exposure = await asyncio.to_thread(adapter.get_open_exposure)
                    bot_ids = bot_owned_order_ids(exposure)
                    flatten = plan_halt_flatten_intents(
                        pending_order_ids=bot_ids,
                        open_position_ids=bot_ids,
                        reason="foundation_risk_halt",
                    )
                    flatten_results = []
                    for intent in flatten:
                        result = await asyncio.to_thread(adapter.execute_intent, intent)
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
                        f"dd={risk_halt.drawdown_halt} daily={risk_halt.daily_equity_halt} "
                        f"losses_today={risk_halt.net_losing_trades_today} "
                        f"history_ready={risk_halt.history_ready}"
                    )
                    logger.warning(reason)
                    if order_id:
                        await asyncio.to_thread(mark_processed, order_id, event, "rejected_risk_halt")
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": reason,
                        "flatten_actions": flatten_results,
                    }

            # 1a1. Broker/Demo identity gate before new risk
            if enforce_identity:
                if identity_gate is not None:
                    identity = await asyncio.to_thread(identity_gate)
                else:
                    def _default_identity() -> BrokerIdentityReport:
                        try:
                            import MetaTrader5 as mt5
                        except ImportError:
                            return verify_broker_identity(
                                account_info=None, symbol_info=None
                            )
                        return verify_broker_identity(
                            account_info=mt5.account_info() if not adapter.dry_run else None,
                            symbol_info=mt5.symbol_info(adapter.symbol) if not adapter.dry_run else None,
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
                            mark_processed, order_id, event, "rejected_identity"
                        )
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": reason,
                    }

            # 1a. Daily Circuit Breaker Guard (ADR-011)
            losses_today = await asyncio.to_thread(adapter.get_daily_realized_losses)
            if losses_today >= max_daily_losses:
                reason = f"Daily Circuit Breaker Triggered (ADR-011): {losses_today}/{max_daily_losses} daily losses reached. Trading halted."
                logger.warning(reason)
                if notifier and getattr(notifier, "enabled", False):
                    from scripts.smc.notifier import format_circuit_breaker_card
                    background_tasks.add_task(_dispatch_tg_safe, format_circuit_breaker_card(losses_today=losses_today))
                if order_id:
                    await asyncio.to_thread(mark_processed, order_id, event, "rejected_circuit_breaker")
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

            if (event_dt.hour > rollover_hour_utc) or (
                event_dt.hour == rollover_hour_utc and event_dt.minute >= rollover_minute_utc
            ):
                reason = f"Rollover Flat Guard (ADR-007): Orders blocked after {rollover_hour_utc}:{rollover_minute_utc:02d} UTC"
                logger.warning(reason)
                if order_id:
                    await asyncio.to_thread(mark_processed, order_id, event, "rejected_rollover")
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": reason,
                }

            # 1c. 30-Minute Post-SL Cooldown Check (ADR-011)
            last_loss_dt = await asyncio.to_thread(adapter.get_last_loss_timestamp)
            if last_loss_dt:
                elapsed_seconds = (event_dt - last_loss_dt).total_seconds()
                if 0 <= elapsed_seconds < 1800:
                    remaining_mins = int((1800 - elapsed_seconds) // 60) + 1
                    reason = f"Post-SL Cooldown Active (ADR-011): {remaining_mins}m remaining before new setups allowed."
                    logger.warning(reason)
                    if order_id:
                        await asyncio.to_thread(mark_processed, order_id, event, "rejected_cooldown")
                    return {
                        "status": "rejected",
                        "order_id": order_id,
                        "event": event,
                        "reason": reason,
                    }

            # 1d. High-Impact USD News Blackout / unknown schedule (ADR-010 + foundation)
            if news_manager is not None:
                if hasattr(news_manager, "new_risk_allowed"):
                    events = getattr(news_manager, "events", None)
                    schedule_known = bool(getattr(news_manager, "schedule_known", events is not None))
                    allowed_news, news_reason = await asyncio.to_thread(
                        news_manager.new_risk_allowed,
                        event_dt,
                        events,
                        schedule_known=schedule_known,
                    )
                    if not allowed_news:
                        reason = f"News gate blocked new risk: {news_reason}"
                        logger.warning(reason)
                        if order_id:
                            await asyncio.to_thread(mark_processed, order_id, event, "rejected_news")
                        return {
                            "status": "rejected",
                            "order_id": order_id,
                            "event": event,
                            "reason": reason,
                        }
                else:
                    is_blackout, news_name = await asyncio.to_thread(
                        news_manager.is_in_blackout, event_dt, getattr(news_manager, "events", [])
                    )
                    if is_blackout:
                        reason = f"News Blackout (ADR-010): High-impact news '{news_name}' within 30m window."
                        logger.warning(reason)
                        if order_id:
                            await asyncio.to_thread(mark_processed, order_id, event, "rejected_news")
                        return {
                            "status": "rejected",
                            "order_id": order_id,
                            "event": event,
                            "reason": reason,
                        }

            # 1e. Dynamic Account Equity Sizing (ADR-020)
            broker_risk = None
            if not adapter.dry_run:
                broker_risk = await asyncio.to_thread(adapter.get_risk_snapshot)
            if not adapter.dry_run and broker_risk is None:
                reason = "Execution Gated: MT5 account or symbol risk data unavailable."
                logger.error(reason)
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": reason,
                }
            effective_balance = broker_risk["balance"] if broker_risk else account_balance
            effective_equity = broker_risk["equity"] if broker_risk else account_balance
            if not adapter.dry_run:
                exposure = await asyncio.to_thread(adapter.get_open_exposure)
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

            # Sizing with zero spread double-buffer invariant
            lot_result = calculate_lot_size(
                balance=effective_balance,
                entry_price=entry,
                sl_price=sl,
                risk_pct=risk_pct,
                spread_buffer=0.0,
                equity=effective_equity,
                min_lot=broker_risk["min_lot"] if broker_risk else 0.01,
                max_lot=broker_risk["max_lot"] if broker_risk else 10.0,
                lot_step=broker_risk["lot_step"] if broker_risk else 0.01,
                contract_size=broker_risk["contract_size"] if broker_risk else 100.0,
                commission_per_lot=commission_per_lot,
                slippage_allowance=slippage_allowance,
                require_cost_model=not adapter.dry_run,
            )

            if not lot_result.is_valid:
                if order_id:
                    await asyncio.to_thread(mark_processed, order_id, event, "rejected")
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": f"ADR-020 Small-Account Risk Gate: {lot_result.reason}",
                }

            if not adapter.dry_run:
                claim = await asyncio.to_thread(adapter.claim_setup, payload)
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
                exec_res = await asyncio.to_thread(adapter.execute_intent, intent)
            except Exception as exc:
                logger.error(f"Execution error or timeout for {order_id}: {exc}")
                if not adapter.dry_run and order_id:
                    await asyncio.to_thread(adapter.update_setup_status, order_id, "uncertain")
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
                    if not adapter.dry_run and order_id:
                        await asyncio.to_thread(adapter.update_setup_status, order_id, "uncertain")
                    return {
                        "status": "uncertain",
                        "order_id": order_id,
                        "event": event,
                        "reason": exec_res.message,
                        "exec_status": getattr(exec_res, "status", "UNKNOWN"),
                    }
                if not adapter.dry_run and order_id:
                    await asyncio.to_thread(adapter.update_setup_status, order_id, "rejected")
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": exec_res.message,
                    "exec_status": getattr(exec_res, "status", "REJECTED"),
                }
            if not adapter.dry_run and order_id:
                await asyncio.to_thread(adapter.update_setup_status, order_id, "accepted", exec_res.order_id)
            if order_id:
                await asyncio.to_thread(mark_processed, order_id, event, "success")

            # Pattern B: accepted-pending card only (never a fill/phantom trade card).
            from scripts.smc.notification_policy import may_notify_execution
            if (
                notifier
                and getattr(notifier, "enabled", False)
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
                    background_tasks.add_task(_dispatch_tg_safe, card)
                except Exception as exc:
                    logger.warning(f"Failed to schedule Telegram notification: {exc}")

            return {
                "status": "success",
                "action": "LIMIT_PLACED",
                "order_id": order_id,
                **({"receipt_id": claim["receipt_id"]} if not adapter.dry_run else {}),
                "lot_size": lot_result.lot_size,
                "ticket": exec_res.order_id,
                "message": exec_res.message,
            }

        # 2. ORDER_FILLED: Record Active Trade Correlation
        elif event == "ORDER_FILLED":
            if order_id and await asyncio.to_thread(
                adapter.has_lifecycle_event, order_id, "ORDER_FILLED"
            ):
                await asyncio.to_thread(mark_processed, order_id, event, "success")
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
            if not adapter.dry_run:
                pos = await asyncio.to_thread(adapter.get_matching_position, order_id)
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
                adapter.log_lifecycle_event,
                event_type="ORDER_FILLED",
                direction=direction.value,
                entry_price=entry,
                sl_price=sl,
                tp_price=tp2 if tp2 > 0 else tp1,
                lot_size=(
                    float(pos.volume)
                    if not adapter.dry_run and "pos" in locals() and pos is not None
                    else float(payload.get("lot_size") or 0.0) or None
                ),
                order_id=order_id,
                ticket=ticket,
                reason=reason,
            )
            if order_id and ticket and not adapter.dry_run:
                await asyncio.to_thread(adapter.update_setup_status, order_id, "accepted", ticket)
            if order_id:
                await asyncio.to_thread(mark_processed, order_id, event, "success")

            if notifier and getattr(notifier, "enabled", False):
                try:
                    from scripts.smc.types import Position
                    from scripts.smc.notifier import format_order_filled_card
                    from scripts.smc.notification_policy import may_notify_execution
                    if not may_notify_execution(success=True, status="FILLED"):
                        raise RuntimeError("notification policy blocked fill card")
                    fill_lot = float(pos.volume) if not adapter.dry_run and 'pos' in locals() and pos else float(payload.get("lot_size") or 0.01)
                    pos_card = Position(
                        direction=direction,
                        entry_price=entry,
                        sl_price=sl,
                        tp_price=tp2 if tp2 > 0 else tp1,
                        lot_size=fill_lot,
                        open_time=datetime.now(timezone.utc),
                        initial_sl_distance=abs(entry - sl),
                    )
                    background_tasks.add_task(_dispatch_tg_safe, format_order_filled_card(pos_card))
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
            if not (partial_tp_enabled and be_enabled):
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": (
                        "TP1_HIT_MOVE_BE disabled by foundation defaults "
                        f"(partial_tp_enabled={partial_tp_enabled}, be_enabled={be_enabled})"
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
            # new_sl must sit on profit-side BE band (entry ± be_buffer), not unconstrained.
            if direction_raw == "BUY":
                be_lo, be_hi = entry, entry + be_buffer + 0.05
            else:
                be_lo, be_hi = entry - be_buffer - 0.05, entry
            if not (be_lo <= new_sl <= be_hi):
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": (
                        f"new_sl {new_sl} outside BE band [{be_lo}, {be_hi}] "
                        f"for {direction_raw} entry={entry} be_buffer={be_buffer}"
                    ),
                }

            # 3a. Partial Close 50%
            intent_close = OrderIntent(
                intent_type=OrderIntentType.PARTIAL_CLOSE,
                order_id=order_id,
                reason=f"TP1_{close_pct}_PCT_SCALE_OUT",
            )
            exec_close = await asyncio.to_thread(adapter.execute_intent, intent_close)
            if not exec_close.success:
                safety_close = await asyncio.to_thread(
                    adapter.execute_intent,
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
            exec_be = await asyncio.to_thread(adapter.execute_intent, intent_be)

            if not exec_be.success:
                safety_close = await asyncio.to_thread(
                    adapter.execute_intent,
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
                await asyncio.to_thread(mark_processed, order_id, event, "success")

            if notifier and getattr(notifier, "enabled", False):
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
                    background_tasks.add_task(_dispatch_tg_safe, card)
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
            exec_cancel = await asyncio.to_thread(adapter.execute_intent, intent)
            if not exec_cancel.success:
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": exec_cancel.message,
                }
            if not adapter.dry_run:
                exposure_after_cancel = await asyncio.to_thread(adapter.get_open_exposure)
                if exposure_after_cancel == []:
                    await asyncio.to_thread(adapter.finish_setup, order_id)
            await asyncio.to_thread(
                adapter.log_lifecycle_event,
                event_type="ORDER_CANCELED",
                order_id=order_id,
                reason=reason,
            )
            if order_id:
                await asyncio.to_thread(mark_processed, order_id, event, "success")

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
                adapter.has_lifecycle_event, order_id, "TRADE_CLOSED"
            ):
                if order_id:
                    await asyncio.to_thread(mark_processed, order_id, event, "success")
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
            exec_close = await asyncio.to_thread(adapter.execute_intent, intent_close)
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
                if adapter.dry_run or already_closed_by_broker:
                    await asyncio.to_thread(adapter.finish_setup, order_id)
                if not adapter.dry_run:
                    if exec_close.success:
                        exposure_after_close = await asyncio.to_thread(adapter.get_open_exposure)
                        if exposure_after_close == []:
                            await asyncio.to_thread(adapter.finish_setup, order_id)
                    broker_pnl = await asyncio.to_thread(
                        adapter.get_realized_pnl_for_order, order_id
                    )
                    if broker_pnl is not None:
                        pnl_dollar = broker_pnl
                    else:
                        # Live: never halt/notify on TradingView invent cash.
                        pnl_dollar = None
                        pnl_r = None
                        if order_id:
                            await asyncio.to_thread(
                                mark_processed, order_id, event, "reconcile_required"
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
                adapter.dry_run
                and pnl_r is None
                and initial_dist > 0
                and entry
                and exit_px
            ):
                # Dry-run only: geometric R from TV exit (not live invent cash).
                signed = (exit_px - entry) if direction == "BUY" else (entry - exit_px)
                pnl_r = round(signed / initial_dist, 4)

            await asyncio.to_thread(
                adapter.log_lifecycle_event,
                event_type="TRADE_CLOSED",
                order_id=order_id,
                pnl_dollar=pnl_dollar,
                pnl_r=pnl_r,
                reason=reason,
                timestamp=payload.get("time"),
            )
            # Foundation risk halt: two net losing bot closes trip daily loss gate.
            if risk_halt is not None and halt_path is not None:
                is_net_loss = (
                    (pnl_r is not None and float(pnl_r) < 0)
                    or (pnl_dollar is not None and float(pnl_dollar) < 0)
                )
                if is_net_loss:
                    record_net_losing_trade(risk_halt)
                    await asyncio.to_thread(save_risk_halt_state, halt_path, risk_halt)
            if order_id:
                await asyncio.to_thread(mark_processed, order_id, event, "success")

            if notifier and getattr(notifier, "enabled", False):
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
                        background_tasks.add_task(_dispatch_tg_safe, card)
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

    return app


if __name__ == "__main__":
    import uvicorn
    import os

    from scripts.smc.news import NewsManager

    secret = os.environ.get("WEBHOOK_SECRET", "DEV_SECRET_123")
    hold_raw = os.environ.get("SMC_MAX_HOLD_BARS")
    max_hold_bars = int(hold_raw) if hold_raw not in (None, "") else None
    bar_minutes = int(os.environ.get("SMC_BAR_MINUTES", "5"))
    news_mgr = NewsManager()
    news_mgr.events = None
    news_mgr.schedule_known = False
    app = create_app(
        auth_token=secret,
        dry_run=True,
        news_manager=news_mgr,
        max_hold_bars=max_hold_bars,
        bar_minutes=bar_minutes,
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)
