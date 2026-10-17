"""Broker fill reconciliation, BE, complete close and safety containment."""

from scripts.demo_runtime.broker import _finite, _cash
from scripts.pure_b1.decision import round_level
from scripts.smc.mt5_filling import resolve_type_filling


class Lifecycle:
    """Internal collaborator sharing runner context; no independent persisted state."""

    def __init__(self, context):
        self.context = context

    def _reconcile(self, positions, deals, tick, info, closed, now):
        ctx = self.context
        active = ctx.journal.get("active")
        matches = [
            p
            for p in positions
            if p.symbol == ctx.symbol
            and int(p.magic) == ctx.strategy.magic
            and p.comment == active["comment"]
        ]
        if not matches:
            ident = active.get("position_id")
            if ident is None:
                opened = [
                    d
                    for d in deals
                    if int(d.magic) == ctx.strategy.magic
                    and d.comment == active["comment"]
                    and int(d.entry) == 0
                ]
                ids = {int(d.position_id) for d in opened}
                if len(ids) == 1:
                    ident = ids.pop()
            if ident is not None:
                ledger = [d for d in deals if int(d.position_id) == ident and int(d.type) in (0, 1)]
                net_volume = sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in ledger)
                if (
                    ledger
                    and abs(net_volume) < 1e-8
                    and any(int(d.entry) in (1, 3) for d in ledger)
                ):
                    safety = active.get("safety_close_reason")
                    if not safety and active.get("safety_close_pending"):
                        safety = ctx.journal.get("safety_halt") or "safety_close"
                    return ctx._record_closed(active, ledger, ident, safety_reason=safety)
            return {"status": "UNKNOWN", "reason": "awaiting_broker_reconciliation"}
        if len(matches) != 1:
            raise ValueError("multiple_owned_positions")
        position = matches[0]
        if (
            float(position.volume) != 0.01
            or int(position.type) != (0 if active.get("direction", -1) == 1 else 1)
            or position.sl <= 0
            or position.tp <= 0
        ):
            return ctx._safety_close(
                position, active, info, now, "filled_position_contract_violation"
            )
        if active.get("safety_close_pending"):
            return ctx._safety_close(
                position,
                active,
                info,
                now,
                active.get("safety_close_reason")
                or ctx.journal.get("safety_halt")
                or "safety_close",
            )
        if active["status"] != "FILLED":
            opening = [
                d
                for d in deals
                if int(d.position_id) == int(position.identifier)
                and int(d.entry) == 0
                and int(d.type) in (0, 1)
            ]
            if not opening:
                return {"status": "UNKNOWN", "reason": "awaiting_fill_deal_costs"}
            observed_cost = sum(
                max(0.0, -float(d.commission) - float(d.fee) - float(d.swap)) for d in opening
            )
            if observed_cost > active["commission"] + 0.00000001:
                return ctx._safety_close(position, active, info, now, "fill_cost_policy_violation")
            active["observed_entry_cost"] = observed_cost
            if (
                not all(
                    _finite(v, positive=True)
                    for v in (position.price_open, position.sl, position.tp)
                )
                or abs(float(position.sl) - active["request"]["sl"])
                > float(info.trade_tick_size) / 2
                or abs(float(position.tp) - active["request"]["tp"])
                > float(info.trade_tick_size) / 2
            ):
                return ctx._safety_close(
                    position, active, info, now, "filled_stop_target_violation"
                )
            broker_loss = ctx.mt5.order_calc_profit(
                ctx.mt5.ORDER_TYPE_BUY
                if active.get("direction", -1) == 1
                else ctx.mt5.ORDER_TYPE_SELL,
                ctx.symbol,
                0.01,
                float(position.price_open),
                float(position.sl),
            )
            actual_risk = (
                (
                    -float(broker_loss)
                    + active["commission"]
                    + active["slippage"] * 0.01 * info.trade_contract_size
                )
                if broker_loss is not None
                else None
            )
            if (
                actual_risk is None
                or not _finite(actual_risk, positive=True)
                or actual_risk > active["entry_equity"] * ctx.strategy.risk_cap
            ):
                return ctx._safety_close(position, active, info, now, "filled_risk_violation")
            active["risk"] = actual_risk
            active.update(
                status="FILLED",
                ticket=int(position.ticket),
                position_id=int(position.identifier),
                fill=float(position.price_open),
                entry_ms=int(position.time_msc),
            )
            ctx.journal.transition(
                "active",
                active,
                dict(
                    kind="FILLED",
                    ticket=int(position.ticket),
                    symbol=ctx.symbol,
                    volume=0.01,
                    entry=float(position.price_open),
                    sl=float(position.sl),
                    tp=float(position.tp),
                    snapshot=ctx.strategy.snapshot,
                ),
            )
            return {"status": "FILLED", "ticket": int(position.ticket)}
        direction = active.get("direction", -1)
        if not ctx.strategy.protects(direction):
            return {"status": "MANAGING", "ticket": int(position.ticket)}
        bar = closed.isoformat()
        if active.get("be_pending") is not None:
            candidate = float(active["be_pending"])
            if direction * (float(position.sl) - candidate) >= -float(info.trade_tick_size) / 2:
                active.pop("be_pending")
                active["be_done"] = True
                ctx.journal.transition(
                    "active",
                    active,
                    dict(
                        kind="BE_MOVED",
                        ticket=int(position.ticket),
                        sl=float(position.sl),
                        tp=float(position.tp),
                        snapshot=ctx.strategy.snapshot,
                    ),
                )
                return {"status": "BE_MOVED", "ticket": int(position.ticket)}
            return {"status": "UNKNOWN", "reason": "awaiting_be_confirmation"}
        if active.get("be_done"):
            return {"status": "MANAGING", "ticket": int(position.ticket)}
        if bar != active["last_be_bar"] and int(closed.timestamp() * 1000) > active["entry_ms"]:
            first = ctx._first_quote(closed, now)
            active["be_activation_quote"] = dict(
                time_msc=int(first.time_msc), bid=float(first.bid), ask=float(first.ask)
            )
            profit = ctx.mt5.order_calc_profit(
                ctx.mt5.ORDER_TYPE_BUY
                if active.get("direction", -1) == 1
                else ctx.mt5.ORDER_TYPE_SELL,
                ctx.symbol,
                0.01,
                float(position.price_open),
                float(first.bid if direction == 1 else first.ask),
            )
            if profit is None or not _finite(profit):
                raise ValueError("broker_profit_unknown")
            net = (
                float(profit)
                - active["commission"]
                - active["slippage"] * 0.01 * info.trade_contract_size
            )
            active["last_be_bar"] = bar
            if net >= active["risk"]:
                active["protection_active"] = True
            ctx.journal.put("active", active)
        if not active.get("protection_active"):
            return {"status": "MANAGING", "ticket": int(position.ticket)}
        candidate = round_level(
            float(position.price_open)
            + direction
            * (active["commission"] / (0.01 * info.trade_contract_size) + active["slippage"]),
            float(info.trade_tick_size),
            -direction,
        )
        distance = max(info.trade_stops_level, info.trade_freeze_level) * info.point
        executable = float(tick.bid if direction == 1 else tick.ask)
        if (
            direction * (candidate - float(position.sl)) <= 0
            or direction * (executable - candidate) <= distance
        ):
            return {"status": "MANAGING", "reason": "be_geometry", "ticket": int(position.ticket)}
        if not ctx.execute:
            return {"status": "SHADOW_BE", "sl": candidate, "ticket": int(position.ticket)}
        request = dict(
            action=ctx.mt5.TRADE_ACTION_SLTP,
            symbol=ctx.symbol,
            position=int(position.ticket),
            sl=candidate,
            tp=float(position.tp),
            magic=ctx.strategy.magic,
        )
        check = ctx.mt5.order_check(request)
        if check is None or int(check.retcode) != 0:
            return {"status": "MANAGING", "reason": "be_check_rejected"}
        ctx.broker.identity()
        positions, _ = ctx.broker._exposure()
        matches = [
            p
            for p in positions
            if int(p.ticket) == int(position.ticket)
            and p.symbol == ctx.symbol
            and int(p.magic) == ctx.strategy.magic
            and p.comment == active["comment"]
        ]
        if len(matches) != 1:
            return {"status": "UNKNOWN", "reason": "be_position_changed"}
        current = matches[0]
        fresh_tick = ctx.broker._quote(ctx._send_clock(now))
        executable = float(fresh_tick.bid if direction == 1 else fresh_tick.ask)
        if (
            direction * (candidate - float(current.sl)) <= 0
            or direction * (executable - candidate) <= distance
        ):
            return {"status": "MANAGING", "reason": "be_geometry_changed"}
        request["tp"] = float(current.tp)
        active["be_pending"] = candidate
        ctx.journal.put("active", active)
        try:
            sent = ctx.mt5.order_send(request)
        except Exception:
            sent = None
        if sent is not None and int(sent.retcode) not in (10009, 10012, 10031):
            active.pop("be_pending")
            ctx.journal.put("active", active)
            return {"status": "MANAGING", "reason": "be_rejected", "retcode": int(sent.retcode)}
        positions, _ = ctx.broker._exposure()
        return ctx._reconcile(positions, deals, tick, info, closed, now)

    def _record_closed(self, active, ledger, ident, *, safety_reason=None):
        """One complete position ledger supplies both result and confirmed event."""
        ctx = self.context
        exits = [deal for deal in ledger if int(deal.entry) in (1, 3)]
        last_exit = max(exits, key=lambda deal: int(deal.time_msc))
        components = {
            key: sum(float(getattr(deal, key)) for deal in ledger)
            for key in ("profit", "commission", "swap", "fee")
        }
        kind = "SAFETY_CLOSED" if safety_reason else "CLOSED"
        event = dict(
            kind=kind,
            position_id=ident,
            net=sum(_cash(deal) for deal in ledger),
            snapshot=ctx.strategy.snapshot,
            fill=active.get("fill"),
            exit_price=float(getattr(last_exit, "price", 0) or 0) or None,
            **components,
        )
        if safety_reason:
            event.update(reason=safety_reason, ticket=active.get("safety_close_ticket"))
        ctx.journal.transition("active", None, event)
        baseline = ctx.journal.get("day")
        result = dict(
            status=kind,
            net=event["net"],
            exit_price=event["exit_price"],
            day_start=baseline["equity"] if baseline else None,
            **components,
        )
        if safety_reason:
            result["reason"] = safety_reason
        return result

    def _safety_close(self, position, active, info, now, reason):
        """Contain unexpected fills; never touch another strategy's position."""
        ctx = self.context
        ctx.journal.put("safety_halt", reason)
        if not ctx.execute:
            return {"status": "BLOCKED", "reason": reason}
        if active.get("safety_close_pending"):
            attempt = active.get("safety_close_attempt") or {}
            if attempt.get("retcode") != 10010:
                return {"status": "UNKNOWN", "reason": "awaiting_safety_close_confirmation"}
        ctx.broker.identity()
        fresh, orders = ctx.broker._exposure()
        owned = [
            p
            for p in fresh
            if int(p.ticket) == int(position.ticket)
            and p.symbol == ctx.symbol
            and int(p.magic) == ctx.strategy.magic
            and p.comment == active["comment"]
        ]
        if len(owned) != 1:
            return {"status": "UNKNOWN", "reason": "safety_close_position_changed"}
        position = owned[0]
        ledger = [
            deal
            for deal in ctx.broker._history(ctx._send_clock(now))
            if int(deal.position_id) == int(position.identifier) and int(deal.type) in (0, 1)
        ]
        exit_volume = sum(float(deal.volume) for deal in ledger if int(deal.entry) in (1, 3))
        if active.get("safety_close_pending"):
            attempt = active.get("safety_close_attempt") or {}
            if orders:
                return {"status": "UNKNOWN", "reason": "awaiting_safety_close_confirmation"}
            requested = float(attempt.get("volume", 0))
            progress = exit_volume - float(attempt.get("exit_volume_before", exit_volume))
            residual = float(position.volume)
            net_volume = sum(
                float(deal.volume) * (1 if int(deal.type) == 0 else -1) for deal in ledger
            )
            if (
                not all(_finite(value, positive=True) for value in (requested, progress, residual))
                or abs(progress + residual - requested) > 1e-8
                or abs(net_volume - residual * (1 if int(position.type) == 0 else -1)) > 1e-8
                or int(attempt.get("position_id", 0)) != int(position.identifier)
            ):
                return {"status": "UNKNOWN", "reason": "awaiting_safety_close_confirmation"}
            # Confirmed partial completion, complete ledger and no pending orders:
            # close only freshly observed residual, never repeat an ambiguous request.
        tick = ctx.broker._quote(ctx._send_clock(now))
        if int(position.type) not in (0, 1):
            return {"status": "BLOCKED", "reason": "safety_position_type_unknown"}
        request = dict(
            action=ctx.mt5.TRADE_ACTION_DEAL,
            symbol=ctx.symbol,
            position=int(position.ticket),
            volume=float(position.volume),
            type=ctx.mt5.ORDER_TYPE_BUY if int(position.type) == 1 else ctx.mt5.ORDER_TYPE_SELL,
            price=float(tick.ask if int(position.type) == 1 else tick.bid),
            magic=ctx.strategy.magic,
            comment=ctx.strategy.prefix + "SAFETY",
            deviation=max(0, int(active["slippage"] / info.point)),
            type_filling=resolve_type_filling(
                int(info.filling_mode), for_pending=False, mt5_mod=ctx.mt5
            ),
        )
        active["safety_close_pending"] = True
        active["position_id"] = int(position.identifier)
        active["safety_close_reason"] = reason
        active["safety_close_ticket"] = int(position.ticket)
        active["safety_close_attempt"] = dict(
            position_id=int(position.identifier),
            volume=float(position.volume),
            exit_volume_before=exit_volume,
            order_ticket=None,
            retcode=None,
        )
        if _finite(position.price_open, positive=True):
            active["fill"] = float(position.price_open)
        ctx.journal.put("active", active)
        try:
            sent = ctx.mt5.order_send(request)
        except Exception:
            sent = None
        if sent is not None:
            active["safety_close_attempt"].update(
                retcode=int(sent.retcode),
                order_ticket=int(getattr(sent, "order", 0) or 0),
            )
            ctx.journal.put("active", active)
        fresh, _ = ctx.broker._exposure()
        ledger = [
            d
            for d in ctx.broker._history(ctx._send_clock(now))
            if int(d.position_id) == int(position.identifier) and int(d.type) in (0, 1)
        ]
        volume = sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in ledger)
        if (
            not any(int(p.ticket) == int(position.ticket) for p in fresh)
            and ledger
            and abs(volume) < 1e-8
            and any(int(deal.entry) in (1, 3) for deal in ledger)
        ):
            return ctx._record_closed(
                active, ledger, int(position.identifier), safety_reason=reason
            )
        if sent is not None and int(sent.retcode) not in (10009, 10010, 10008, 10012, 10031):
            active.pop("safety_close_pending")
            ctx.journal.put("active", active)
        return {"status": "UNKNOWN", "reason": "awaiting_safety_close_confirmation"}
