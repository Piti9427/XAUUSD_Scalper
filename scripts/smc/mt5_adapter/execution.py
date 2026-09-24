"""OrderIntent → MT5 order_send / dry-run simulation."""

from __future__ import annotations

import logging

from scripts.smc.types import Direction, OrderIntentType, OrderIntent

from .models import BOT_COMMENT_PREFIX, ExecutionResult, is_bot_owned_comment
from . import runtime

logger = logging.getLogger(__name__)


class ExecutionMixin:
    def execute_intent(self, intent: OrderIntent) -> ExecutionResult:
        """Translates domain OrderIntent into MT5 broker calls or dry-run simulation."""
        # Enforce target scoping (ADR-024) on live broker execution
        is_rollover_all = "ROLLOVER" in intent.reason.upper() and (
            intent.ticket is None and not intent.order_id
        )
        if not self.dry_run:
            if intent.intent_type in (
                OrderIntentType.CANCEL_LIMIT,
                OrderIntentType.MOVE_SL_TO_BE,
                OrderIntentType.PARTIAL_CLOSE,
            ):
                if intent.ticket is None and not intent.order_id:
                    return ExecutionResult(
                        success=False,
                        order_id=None,
                        message=f"{intent.intent_type.value} rejected: Both ticket and order_id are missing. Targeted execution required.",
                    )
            elif intent.intent_type == OrderIntentType.CLOSE_MARKET:
                if intent.ticket is None and not intent.order_id and not is_rollover_all:
                    return ExecutionResult(
                        success=False,
                        order_id=None,
                        message="CLOSE_MARKET rejected: Both ticket and order_id are missing. Targeted execution required.",
                    )

        if self.dry_run:
            msg = f"DRY_RUN: Successfully simulated {intent.intent_type.value} for {self.symbol} - {intent.reason}"
            logger.info(msg)
            self.log_lifecycle_event(
                event_type=intent.intent_type.value,
                direction=intent.direction.value if intent.direction else None,
                entry_price=intent.limit_price,
                sl_price=intent.sl_price,
                tp_price=intent.tp_price,
                lot_size=intent.lot_size,
                reason=intent.reason,
                order_id=intent.order_id,
                ticket=intent.ticket,
            )
            return ExecutionResult(success=True, order_id=intent.ticket or 123456, message=msg)

        if intent.intent_type == OrderIntentType.PLACE_LIMIT:
            order_type = (
                runtime.mt5.ORDER_TYPE_BUY_LIMIT
                if intent.direction == Direction.BUY
                else runtime.mt5.ORDER_TYPE_SELL_LIMIT
            )
            comment_str = (
                f"SMC_{intent.order_id}" if intent.order_id else f"SMC_v1_{intent.reason[:20]}"
            )
            # Defense in depth: stops_level geometry even if caller skipped webhook gate.
            from scripts.smc.stops_geometry import pending_stops_geometry_allows

            snap = self.get_risk_snapshot()
            if snap is None:
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    message="PLACE_LIMIT rejected: broker risk snapshot unavailable",
                    status="REJECTED",
                )
            geom_ok, geom_reason = pending_stops_geometry_allows(
                entry_price=float(intent.limit_price),
                sl_price=float(intent.sl_price),
                tp_price=float(intent.tp_price) if intent.tp_price else None,
                point=float(snap["point"]),
                stops_level=float(snap["stops_level"]),
            )
            if not geom_ok:
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    message=f"PLACE_LIMIT rejected: {geom_reason}",
                    status="REJECTED",
                )
            self.log_lifecycle_event(
                event_type="INTENT_SUBMITTED",
                direction=intent.direction.value if intent.direction else None,
                entry_price=intent.limit_price,
                sl_price=intent.sl_price,
                tp_price=intent.tp_price,
                lot_size=intent.lot_size,
                reason=intent.reason,
                order_id=intent.order_id,
                ticket=intent.ticket,
            )
            type_filling = self._type_filling_for_symbol(for_pending=True)
            if type_filling is None:
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    message="Cannot resolve type_filling for symbol — broker symbol_info unavailable",
                    status="REJECTED",
                )
            request = {
                "action": runtime.mt5.TRADE_ACTION_PENDING,
                "symbol": self.symbol,
                "volume": intent.lot_size,
                "type": order_type,
                "price": intent.limit_price,
                "sl": intent.sl_price,
                "tp": intent.tp_price,
                "type_time": runtime.mt5.ORDER_TIME_GTC,
                "type_filling": type_filling,
                "comment": comment_str,
            }
            result = runtime.mt5.order_send(request)
            if result is None:
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    message="Order submit returned None — status UNKNOWN; reconcile before retry",
                    status="UNKNOWN",
                )
            if result.retcode != runtime.mt5.TRADE_RETCODE_DONE:
                err_msg = f"retcode {result.retcode}: {result.comment}"
                return ExecutionResult(
                    success=False,
                    order_id=None,
                    message=f"Order failed with {err_msg}",
                    status="REJECTED",
                )
            self.log_lifecycle_event(
                event_type="PLACE_LIMIT",
                direction=intent.direction.value if intent.direction else None,
                entry_price=intent.limit_price,
                sl_price=intent.sl_price,
                tp_price=intent.tp_price,
                lot_size=intent.lot_size,
                reason=intent.reason,
                order_id=intent.order_id,
                ticket=result.order,
            )
            return ExecutionResult(
                success=True,
                order_id=result.order,
                message=f"Limit order #{result.order} placed successfully",
            )

        elif intent.intent_type == OrderIntentType.CANCEL_LIMIT:
            orders = runtime.mt5.orders_get(symbol=self.symbol)
            canceled_count = 0
            if orders:
                for o in orders:
                    owned = is_bot_owned_comment(getattr(o, "comment", ""), intent.order_id)
                    match_ticket = (
                        intent.ticket is not None
                        and o.ticket == intent.ticket
                        and is_bot_owned_comment(getattr(o, "comment", ""))
                    )
                    match_order_id = intent.order_id is not None and owned
                    if match_ticket or match_order_id:
                        req = {"action": runtime.mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                        result = runtime.mt5.order_send(req)
                        if result is None or result.retcode != runtime.mt5.TRADE_RETCODE_DONE:
                            return ExecutionResult(
                                False, o.ticket, "Broker rejected limit cancellation"
                            )
                        canceled_count += 1
            if canceled_count == 0:
                return ExecutionResult(False, intent.ticket, "Target limit order not found")
            self.log_lifecycle_event(
                event_type="CANCEL_LIMIT",
                order_id=intent.order_id,
                ticket=intent.ticket,
                reason=intent.reason,
            )
            return ExecutionResult(
                success=True,
                order_id=intent.ticket,
                message=f"Cancelled {canceled_count} limit order(s) for {self.symbol}",
            )

        elif intent.intent_type == OrderIntentType.MOVE_SL_TO_BE:
            # Defense in depth: reject SL mods inside broker freeze distance.
            from scripts.smc.stops_geometry import sl_modify_freeze_allows

            snap = self.get_risk_snapshot()
            if snap is None:
                return ExecutionResult(
                    False,
                    intent.ticket,
                    "MOVE_SL_TO_BE rejected: broker risk snapshot unavailable",
                )
            tick = runtime.mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return ExecutionResult(
                    False,
                    intent.ticket,
                    "MOVE_SL_TO_BE rejected: broker symbol tick unavailable",
                )
            freeze_ok, freeze_reason = sl_modify_freeze_allows(
                new_sl=float(intent.sl_price),
                market_bid=float(getattr(tick, "bid", float("nan"))),
                market_ask=float(getattr(tick, "ask", float("nan"))),
                point=float(snap["point"]),
                freeze_level=float(snap["freeze_level"]),
            )
            if not freeze_ok:
                return ExecutionResult(
                    False,
                    intent.ticket,
                    f"MOVE_SL_TO_BE rejected: {freeze_reason}",
                )
            positions = runtime.mt5.positions_get(symbol=self.symbol)
            moved_count = 0
            if positions:
                for pos in positions:
                    owned = is_bot_owned_comment(getattr(pos, "comment", ""), intent.order_id)
                    match_ticket = (
                        intent.ticket is not None
                        and pos.ticket == intent.ticket
                        and is_bot_owned_comment(getattr(pos, "comment", ""))
                    )
                    match_order_id = intent.order_id is not None and owned
                    if match_ticket or match_order_id:
                        req = {
                            "action": runtime.mt5.TRADE_ACTION_SLTP,
                            "position": pos.ticket,
                            "sl": intent.sl_price,
                            "tp": pos.tp,
                        }
                        result = runtime.mt5.order_send(req)
                        if result is None or result.retcode != runtime.mt5.TRADE_RETCODE_DONE:
                            return ExecutionResult(
                                False, pos.ticket, "Broker rejected SL modification"
                            )
                        moved_count += 1
            if moved_count == 0:
                return ExecutionResult(False, intent.ticket, "Target position not found")
            self.log_lifecycle_event(
                event_type="MOVE_SL_TO_BE",
                order_id=intent.order_id,
                ticket=intent.ticket,
                sl_price=intent.sl_price,
                reason=intent.reason,
            )
            return ExecutionResult(
                success=True,
                order_id=intent.ticket,
                message=f"Moved SL to BE for {moved_count} position(s) on {self.symbol}",
            )

        elif intent.intent_type == OrderIntentType.PARTIAL_CLOSE:
            positions = runtime.mt5.positions_get(symbol=self.symbol)
            closed_count = 0
            if positions:
                for pos in positions:
                    owned = is_bot_owned_comment(getattr(pos, "comment", ""), intent.order_id)
                    match_ticket = (
                        intent.ticket is not None
                        and pos.ticket == intent.ticket
                        and is_bot_owned_comment(getattr(pos, "comment", ""))
                    )
                    match_order_id = intent.order_id is not None and owned
                    if match_ticket or match_order_id:
                        close_type = (
                            runtime.mt5.ORDER_TYPE_SELL
                            if pos.type == runtime.mt5.ORDER_TYPE_BUY
                            else runtime.mt5.ORDER_TYPE_BUY
                        )
                        tick = runtime.mt5.symbol_info_tick(self.symbol)
                        if tick is None:
                            return ExecutionResult(
                                False, intent.ticket, "Broker symbol tick unavailable"
                            )
                        price = tick.bid if close_type == runtime.mt5.ORDER_TYPE_SELL else tick.ask
                        vol = min(pos.volume, intent.lot_size or (pos.volume * 0.5))
                        deal_filling = self._type_filling_for_symbol(for_pending=False)
                        if deal_filling is None:
                            return ExecutionResult(
                                False,
                                intent.ticket,
                                "Cannot resolve type_filling for market deal",
                            )
                        req = {
                            "action": runtime.mt5.TRADE_ACTION_DEAL,
                            "position": pos.ticket,
                            "symbol": self.symbol,
                            "volume": vol,
                            "type": close_type,
                            "price": price,
                            "deviation": 20,
                            "type_time": runtime.mt5.ORDER_TIME_GTC,
                            "type_filling": deal_filling,
                            "comment": f"SMC_Partial_{intent.order_id or ''}",
                        }
                        result = runtime.mt5.order_send(req)
                        if result is None or result.retcode != runtime.mt5.TRADE_RETCODE_DONE:
                            return ExecutionResult(
                                False, pos.ticket, "Broker rejected partial close"
                            )
                        closed_count += 1
            if closed_count == 0:
                return ExecutionResult(False, intent.ticket, "Target position not found")
            self.log_lifecycle_event(
                event_type="PARTIAL_CLOSE",
                order_id=intent.order_id,
                ticket=intent.ticket,
                lot_size=intent.lot_size,
                reason=intent.reason,
            )
            return ExecutionResult(
                success=True,
                order_id=intent.ticket,
                message=f"Partially closed {closed_count} position(s) on {self.symbol}",
            )

        elif intent.intent_type == OrderIntentType.CLOSE_MARKET:
            positions = runtime.mt5.positions_get(symbol=self.symbol)
            closed_count = 0
            if positions:
                for pos in positions:
                    owned_any = is_bot_owned_comment(getattr(pos, "comment", ""))
                    owned = is_bot_owned_comment(getattr(pos, "comment", ""), intent.order_id)
                    match_ticket = (
                        intent.ticket is not None and pos.ticket == intent.ticket and owned_any
                    )
                    match_order_id = intent.order_id is not None and owned
                    # Rollover closes only bot-owned exposure — never foreign manual trades.
                    if match_ticket or match_order_id or (is_rollover_all and owned_any):
                        close_type = (
                            runtime.mt5.ORDER_TYPE_SELL
                            if pos.type == runtime.mt5.ORDER_TYPE_BUY
                            else runtime.mt5.ORDER_TYPE_BUY
                        )
                        tick = runtime.mt5.symbol_info_tick(self.symbol)
                        if tick is None:
                            return ExecutionResult(
                                False, intent.ticket, "Broker symbol tick unavailable"
                            )
                        price = tick.bid if close_type == runtime.mt5.ORDER_TYPE_SELL else tick.ask
                        deal_filling = self._type_filling_for_symbol(for_pending=False)
                        if deal_filling is None:
                            return ExecutionResult(
                                False,
                                intent.ticket,
                                "Cannot resolve type_filling for market close",
                            )
                        close_comment = (
                            f"SMC_{intent.order_id}"
                            if intent.order_id
                            else (getattr(pos, "comment", "") or BOT_COMMENT_PREFIX)
                        )
                        req = {
                            "action": runtime.mt5.TRADE_ACTION_DEAL,
                            "position": pos.ticket,
                            "symbol": self.symbol,
                            "volume": pos.volume,
                            "type": close_type,
                            "price": price,
                            "deviation": 20,
                            "type_filling": deal_filling,
                            "comment": close_comment[:31],
                        }
                        result = runtime.mt5.order_send(req)
                        if result is None or result.retcode != runtime.mt5.TRADE_RETCODE_DONE:
                            return ExecutionResult(
                                False, pos.ticket, "Broker rejected market close"
                            )
                        closed_count += 1
            if closed_count == 0:
                return ExecutionResult(False, intent.ticket, "Target position not found")
            self.log_lifecycle_event(
                event_type="CLOSE_MARKET",
                order_id=intent.order_id,
                ticket=intent.ticket,
                reason=intent.reason,
            )
            return ExecutionResult(
                success=True,
                order_id=intent.ticket,
                message=f"Closed {closed_count} market position(s) for {self.symbol}",
            )

        return ExecutionResult(success=True, order_id=None, message="No action needed")
