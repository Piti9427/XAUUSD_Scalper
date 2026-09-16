"""Active broker lifecycle reconciliation (foundation scenario 8/14/15)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from scripts.smc.types import OrderIntent, OrderIntentType

if TYPE_CHECKING:
    from scripts.smc.mt5_adapter import SMCExecutionAdapter


def pending_ttl_elapsed(
    created_at: datetime,
    now: datetime,
    ttl_bars: int,
    bar_minutes: int,
) -> bool:
    if ttl_bars <= 0 or bar_minutes <= 0:
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    else:
        created_at = created_at.astimezone(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    max_seconds = ttl_bars * bar_minutes * 60
    return (now - created_at).total_seconds() >= max_seconds


def reconcile_broker_lifecycle(
    adapter: "SMCExecutionAdapter",
    *,
    now: datetime,
    order_ttl_bars: Optional[int],
    bar_minutes: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Poll broker + local ledger: TTL cancel, fill detection, close detection.

    BaselinePlay: no partial TP / BE — unlock setup_inbox when broker goes flat.
    """
    ttl_cancels: List[Dict[str, Any]] = []
    broker_fills: List[Dict[str, Any]] = []
    broker_closes: List[Dict[str, Any]] = []

    if order_ttl_bars is not None and order_ttl_bars > 0:
        for row in adapter.list_unfilled_pending_setups():
            order_id = row["order_id"]
            created_at = row["created_at"]
            if not pending_ttl_elapsed(created_at, now, order_ttl_bars, bar_minutes):
                continue
            reason = f"TTL_EXPIRED ({order_ttl_bars} bars)"
            intent = OrderIntent(
                intent_type=OrderIntentType.CANCEL_LIMIT,
                order_id=order_id,
                reason=reason,
            )
            exec_cancel = adapter.execute_intent(intent)
            released = exec_cancel.success or "not found" in (exec_cancel.message or "").lower()
            if released:
                adapter.log_lifecycle_event(
                    event_type="ORDER_CANCELED",
                    order_id=order_id,
                    reason=reason,
                )
                adapter.finish_setup(order_id)
            ttl_cancels.append(
                {
                    "order_id": order_id,
                    "status": "success" if released else "rejected",
                    "reason": reason,
                    "message": exec_cancel.message,
                }
            )

    if adapter.dry_run or not adapter.connected:
        return {
            "ttl_cancels": ttl_cancels,
            "broker_fills": broker_fills,
            "broker_closes": broker_closes,
        }

    for row in adapter.list_unfilled_pending_setups():
        order_id = row["order_id"]
        if adapter.has_lifecycle_event(order_id, "ORDER_FILLED"):
            continue
        position = adapter.get_matching_position(order_id)
        if position is None:
            continue
        entry = float(getattr(position, "price_open", 0.0) or 0.0)
        sl = float(getattr(position, "sl", 0.0) or 0.0)
        lot = float(getattr(position, "volume", 0.0) or 0.0)
        direction = "BUY" if getattr(position, "type", 0) == 0 else "SELL"
        ticket = getattr(position, "ticket", None)
        adapter.log_lifecycle_event(
            event_type="ORDER_FILLED",
            order_id=order_id,
            direction=direction,
            entry_price=entry or None,
            sl_price=sl or None,
            lot_size=lot or None,
            ticket=ticket,
            reason="broker_lifecycle_fill_detected",
        )
        adapter.update_setup_status(order_id, "accepted", ticket=ticket)
        broker_fills.append({"order_id": order_id, "ticket": ticket})

    for row in adapter.list_open_fills():
        order_id = row["order_id"]
        if adapter.get_matching_position(order_id) is not None:
            continue
        pnl_dollar = adapter.get_realized_pnl_for_order(order_id)
        if pnl_dollar is None:
            continue
        pnl_r = None
        fill = adapter.get_fill_geometry(order_id)
        if fill and fill.get("entry_price") and fill.get("sl_price") and fill.get("lot_size"):
            from scripts.smc.risk import frozen_initial_r

            pnl_r = frozen_initial_r(
                pnl_dollars=float(pnl_dollar),
                initial_sl_distance=abs(
                    float(fill["entry_price"]) - float(fill["sl_price"])
                ),
                filled_lot=float(fill["lot_size"]),
            )
        adapter.log_lifecycle_event(
            event_type="TRADE_CLOSED",
            order_id=order_id,
            direction=row.get("direction"),
            pnl_dollar=pnl_dollar,
            pnl_r=pnl_r,
            reason="broker_lifecycle_close_detected",
        )
        adapter.finish_setup(order_id)
        broker_closes.append(
            {
                "order_id": order_id,
                "pnl_dollar": pnl_dollar,
                "pnl_r": pnl_r,
            }
        )

    return {
        "ttl_cancels": ttl_cancels,
        "broker_fills": broker_fills,
        "broker_closes": broker_closes,
    }
