"""Active broker lifecycle reconciliation (foundation scenario 8/14/15/34)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from scripts.smc.reconcile import PendingExposure, reconcile_pending_exposure
from scripts.smc.trade_closed_pnl import resolve_trade_closed_pnl
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
    Broker partial fills (story 34) keep residual pending visible until cancel/expiry.
    """
    ttl_cancels: List[Dict[str, Any]] = []
    broker_fills: List[Dict[str, Any]] = []
    broker_closes: List[Dict[str, Any]] = []
    exposure_reconciles: List[Dict[str, Any]] = []

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
            "exposure_reconciles": exposure_reconciles,
        }

    for row in adapter.list_unfilled_pending_setups():
        order_id = row["order_id"]
        if adapter.has_lifecycle_event(order_id, "ORDER_FILLED"):
            continue
        position = adapter.get_matching_position(order_id)
        pending = adapter.get_matching_pending_order(order_id)
        if position is None and pending is None:
            continue

        pos_vol = float(getattr(position, "volume", 0.0) or 0.0) if position is not None else 0.0
        pend_vol = 0.0
        if pending is not None:
            pend_vol = float(
                getattr(pending, "volume_current", None)
                or getattr(pending, "volume_initial", None)
                or getattr(pending, "volume", 0.0)
                or 0.0
            )
        requested = max(pos_vol + pend_vol, pos_vol, pend_vol)
        cancel_requested = adapter.has_lifecycle_event(order_id, "ORDER_CANCELED")
        decision = reconcile_pending_exposure(
            PendingExposure(
                order_id=order_id,
                requested_volume=requested if requested > 0 else max(pos_vol, 0.01),
                filled_volume=pos_vol,
                cancel_requested=cancel_requested,
                broker_pending_volume=(
                    pend_vol if pending is not None else (0.0 if position is not None else None)
                ),
                broker_position_volume=pos_vol if position is not None else None,
            )
        )
        exposure_reconciles.append(
            {
                "order_id": order_id,
                "status": decision.status,
                "filled_volume": decision.filled_volume,
                "residual_pending_volume": decision.residual_pending_volume,
                "reason": decision.reason,
            }
        )

        if decision.status not in {
            "filled",
            "filled_during_cancel",
            "partial_fill_with_residual",
        }:
            continue
        if position is None:
            continue

        entry = float(getattr(position, "price_open", 0.0) or 0.0)
        sl = float(getattr(position, "sl", 0.0) or 0.0)
        lot = float(decision.filled_volume or getattr(position, "volume", 0.0) or 0.0)
        direction = "BUY" if getattr(position, "type", 0) == 0 else "SELL"
        ticket = getattr(position, "ticket", None)
        if decision.status == "filled_during_cancel":
            fill_reason = "broker_lifecycle_fill_during_cancel"
        elif decision.status == "partial_fill_with_residual":
            fill_reason = "broker_lifecycle_partial_fill"
        else:
            fill_reason = "broker_lifecycle_fill_detected"
        adapter.log_lifecycle_event(
            event_type="ORDER_FILLED",
            order_id=order_id,
            direction=direction,
            entry_price=entry or None,
            sl_price=sl or None,
            lot_size=lot or None,
            ticket=ticket,
            reason=fill_reason,
        )
        if decision.status == "partial_fill_with_residual":
            adapter.log_lifecycle_event(
                event_type="PARTIAL_FILL_RESIDUAL",
                order_id=order_id,
                lot_size=decision.residual_pending_volume,
                reason=decision.reason,
            )
        adapter.update_setup_status(order_id, "accepted", ticket=ticket)
        broker_fills.append(
            {
                "order_id": order_id,
                "ticket": ticket,
                "status": decision.status,
                "filled_volume": decision.filled_volume,
                "residual_pending_volume": decision.residual_pending_volume,
            }
        )

    # Residual pending after partial fill: TTL cancel still applies.
    if order_ttl_bars is not None and order_ttl_bars > 0:
        for fill in broker_fills:
            if float(fill.get("residual_pending_volume") or 0.0) <= 0:
                continue
            order_id = fill["order_id"]
            status = adapter.get_setup_status(order_id) or {}
            created_raw = status.get("created_at")
            if not created_raw:
                continue
            try:
                created_at = datetime.fromisoformat(
                    str(created_raw).replace("Z", "+00:00").replace(" ", "T")
                )
            except ValueError:
                continue
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if not pending_ttl_elapsed(created_at, now, order_ttl_bars, bar_minutes):
                continue
            if adapter.get_matching_pending_order(order_id) is None:
                continue
            reason = f"TTL_EXPIRED_RESIDUAL ({order_ttl_bars} bars)"
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
            ttl_cancels.append(
                {
                    "order_id": order_id,
                    "status": "success" if released else "rejected",
                    "reason": reason,
                    "message": exec_cancel.message,
                }
            )

    for row in adapter.list_open_fills():
        order_id = row["order_id"]
        if adapter.get_matching_position(order_id) is not None:
            continue
        if adapter.get_matching_pending_order(order_id) is not None:
            continue
        pnl_raw = adapter.get_realized_pnl_for_order(order_id)
        fill = adapter.get_fill_geometry(order_id) or {}
        pnl_r, pnl_dollar, pnl_status = resolve_trade_closed_pnl(
            dry_run=bool(getattr(adapter, "dry_run", False)),
            broker_pnl=pnl_raw,
            entry=float(fill.get("entry_price") or 0.0),
            sl=float(fill.get("sl_price") or 0.0),
            lot=float(fill.get("lot_size") or 0.0),
            direction=str(row.get("direction") or "BUY"),
        )
        if pnl_status == "live_broker_pnl_missing" or pnl_dollar is None:
            if pnl_status == "live_broker_pnl_missing" and not adapter.has_lifecycle_event(
                order_id, "RECONCILE_REQUIRED"
            ):
                adapter.log_lifecycle_event(
                    event_type="RECONCILE_REQUIRED",
                    order_id=order_id,
                    direction=row.get("direction"),
                    reason="broker deal cashflow missing for lifecycle close detect",
                )
            continue
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
        "exposure_reconciles": exposure_reconciles,
    }
