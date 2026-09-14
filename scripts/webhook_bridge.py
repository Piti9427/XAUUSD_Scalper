from datetime import datetime, timezone
import time
from typing import Optional, Dict, Any
import logging
from fastapi import FastAPI, Depends, HTTPException, Header, Request, status
from fastapi.responses import JSONResponse

from scripts.smc.types import Direction, OrderIntentType, OrderIntent
from scripts.smc.mt5_adapter import SMCExecutionAdapter
from scripts.smc.risk import calculate_lot_size

logger = logging.getLogger("webhook_bridge")


def create_app(
    auth_token: str = "XAUUSD_DEFAULT_SECRET",
    dry_run: bool = True,
    db_path: str = "data/smc_trades.db",
    account_balance: float = 10000.0,
    risk_pct: float = 0.01,
    max_daily_losses: int = 2,
    rollover_hour_utc: int = 20,
    rollover_minute_utc: int = 55,
) -> FastAPI:
    """
    Factory creating the FastAPI Webhook Bridge application.
    """
    app = FastAPI(
        title="XAUUSD Master Pro Webhook Bridge",
        version="1.0.0",
        description="Translates TradingView alerts into broker MT5 executions with strict risk shields.",
    )

    start_time = time.time()
    adapter = SMCExecutionAdapter(symbol="XAUUSD", dry_run=dry_run, db_path=db_path)

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
        return {
            "status": "ok",
            "mode": "dry-run" if adapter.dry_run else "live",
            "uptime_seconds": round(time.time() - start_time, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.post("/webhook/tradingview")
    async def handle_tradingview_webhook(
        request: Request,
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

        # Idempotency Check: Reject duplicates
        if order_id and adapter.is_webhook_processed(order_id, event):
            logger.warning(f"Ignoring duplicate webhook delivery for {order_id} ({event})")
            return {
                "status": "ignored_duplicate",
                "order_id": order_id,
                "event": event,
                "message": f"Event {event} already processed for {order_id}",
            }

        # 1. SETUP_PENDING: Place Pending Limit with Dynamic Risk Sizing
        if event == "SETUP_PENDING":
            # 1a. Daily Circuit Breaker Guard (ADR-011)
            losses_today = adapter.get_daily_realized_losses()
            if losses_today >= max_daily_losses:
                reason = f"Daily Circuit Breaker Triggered (ADR-011): {losses_today}/{max_daily_losses} daily losses reached. Trading halted."
                logger.warning(reason)
                if order_id:
                    adapter.mark_webhook_processed(order_id, event, status="rejected_circuit_breaker")
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": reason,
                }

            # 1b. Rollover Flat Guard (ADR-007)
            event_time_str = payload.get("time")
            if event_time_str:
                try:
                    event_dt = datetime.fromisoformat(event_time_str.replace(" ", "T"))
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
                    adapter.mark_webhook_processed(order_id, event, status="rejected_rollover")
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": reason,
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
                balance=account_balance,
                entry_price=entry,
                sl_price=sl,
                risk_pct=risk_pct,
                spread_buffer=0.0,
            )

            if not lot_result.is_valid:
                if order_id:
                    adapter.mark_webhook_processed(order_id, event, status="rejected")
                return {
                    "status": "rejected",
                    "order_id": order_id,
                    "event": event,
                    "reason": f"ADR-020 Small-Account Risk Gate: {lot_result.reason}",
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
            exec_res = adapter.execute_intent(intent)
            if order_id:
                adapter.mark_webhook_processed(order_id, event, status="success")

            return {
                "status": "success",
                "action": "LIMIT_PLACED",
                "order_id": order_id,
                "lot_size": lot_result.lot_size,
                "ticket": exec_res.order_id,
                "message": exec_res.message,
            }

        # 2. ORDER_FILLED: Record Active Trade Correlation
        elif event == "ORDER_FILLED":
            entry = float(payload.get("entry") or 0.0)
            sl = float(payload.get("sl") or 0.0)
            tp1 = float(payload.get("tp1") or 0.0)
            tp2 = float(payload.get("tp2") or 0.0)
            direction = (
                Direction.BUY if payload.get("dir") == "BUY" else Direction.SELL
            )
            adapter.log_lifecycle_event(
                event_type="ORDER_FILLED",
                direction=direction.value,
                entry_price=entry,
                sl_price=sl,
                tp_price=tp2 if tp2 > 0 else tp1,
                order_id=order_id,
                reason="TradingView Alert Fill Confirmation",
            )
            if order_id:
                adapter.mark_webhook_processed(order_id, event, status="success")

            return {
                "status": "success",
                "action": "ORDER_RECORDED",
                "order_id": order_id,
                "entry": entry,
            }

        # 3. TP1_HIT_MOVE_BE: 50% Volume Scale-Out & Breakeven Relocation (ADR-018)
        elif event == "TP1_HIT_MOVE_BE":
            new_sl = float(payload.get("new_sl") or 0.0)
            entry = float(payload.get("entry") or 0.0)
            close_pct = int(payload.get("close_percent") or 50)

            # 3a. Partial Close 50%
            intent_close = OrderIntent(
                intent_type=OrderIntentType.PARTIAL_CLOSE,
                order_id=order_id,
                reason=f"TP1_{close_pct}_PCT_SCALE_OUT",
            )
            exec_close = adapter.execute_intent(intent_close)

            # 3b. Move SL to BE
            intent_be = OrderIntent(
                intent_type=OrderIntentType.MOVE_SL_TO_BE,
                sl_price=new_sl,
                order_id=order_id,
                reason="TP1_RELOCATE_SL_TO_BE",
            )
            exec_be = adapter.execute_intent(intent_be)

            if order_id:
                adapter.mark_webhook_processed(order_id, event, status="success")

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
            exec_cancel = adapter.execute_intent(intent)
            adapter.log_lifecycle_event(
                event_type="ORDER_CANCELED",
                order_id=order_id,
                reason=reason,
            )
            if order_id:
                adapter.mark_webhook_processed(order_id, event, status="success")

            return {
                "status": "success",
                "action": "ORDER_CANCELED",
                "order_id": order_id,
                "reason": reason,
                "message": exec_cancel.message,
            }

        # 5. TRADE_CLOSED: Finalize Position Lifecycle
        elif event == "TRADE_CLOSED":
            reason = payload.get("reason", "POSITION_CLOSED")
            adapter.log_lifecycle_event(
                event_type="TRADE_CLOSED",
                order_id=order_id,
                reason=reason,
            )
            if order_id:
                adapter.mark_webhook_processed(order_id, event, status="success")

            return {
                "status": "success",
                "action": "TRADE_CLOSED",
                "order_id": order_id,
                "reason": reason,
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

    secret = os.environ.get("WEBHOOK_SECRET", "DEV_SECRET_123")
    app = create_app(auth_token=secret, dry_run=True)
    uvicorn.run(app, host="0.0.0.0", port=8000)
