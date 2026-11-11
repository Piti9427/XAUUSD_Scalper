"""Broker fill reconciliation, BE, complete close and safety containment."""

from datetime import datetime, timezone

from scripts.demo_runtime.broker import _finite, _cash
from scripts.pure_b1.decision import round_level
from scripts.smc.mt5_filling import resolve_type_filling


class Lifecycle:
    """Internal collaborator sharing runner context; no independent persisted state."""

    def __init__(self, context):
        self.context = context

    def reconcile_closed(self, positions, deals):
        """Record a proven owned exit without requiring mutation prerequisites."""
        ctx = self.context
        active = ctx.journal.get("active")
        if active is None:
            return None
        ident = active.get("position_id")
        if ident is None:
            opening = [
                d
                for d in deals
                if int(d.entry) == 0
                and int(d.type) in (0, 1)
                and int(d.magic) == ctx.strategy.magic
                and d.comment == active["comment"]
                and int(d.time_msc) >= active["entry_ms"]
                and (
                    not active.get("broker_order")
                    or int(getattr(d, "order", active["broker_order"])) == active["broker_order"]
                )
            ]
            ids = {int(d.position_id) for d in opening}
            if len(ids) > 1:
                ctx.journal.put("safety_halt", "ambiguous_position_identity")
                return {"status": "UNKNOWN", "reason": "ambiguous_position_identity"}
            if ids:
                ident = ids.pop()
                active["position_id"] = ident
                ctx.journal.put("active", active)
        if ident is None or any(int(p.identifier) == ident for p in positions):
            return None
        ledger = [d for d in deals if int(d.position_id) == ident and int(d.type) in (0, 1)]
        net_volume = sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in ledger)
        if (
            ledger
            and any(
                int(d.entry) == 0
                and int(d.magic) == ctx.strategy.magic
                and d.comment == active["comment"]
                for d in ledger
            )
            and abs(net_volume) < 1e-8
            and any(int(d.entry) in (1, 3) for d in ledger)
        ):
            safety = active.get("safety_close_reason")
            if not safety and active.get("safety_close_pending"):
                safety = ctx.journal.get("safety_halt") or "safety_close"
            return ctx._record_closed(active, ledger, ident, safety_reason=safety)
        return None

    def _reconcile(self, positions, deals, tick, info, closed, now):
        ctx = self.context
        result = self.reconcile_closed(positions, deals)
        if result is not None:
            return result
        active = ctx.journal.get("active")
        ident = active.get("position_id")
        matches = [
            p
            for p in positions
            if ident is not None
            and int(p.identifier) == ident
            and p.symbol == ctx.symbol
            and int(p.magic) == ctx.strategy.magic
        ]
        if ident is None and any(
            p.symbol == ctx.symbol
            and int(p.magic) == ctx.strategy.magic
            and p.comment == active["comment"]
            for p in positions
        ):
            return {"status": "UNKNOWN", "reason": "awaiting_fill_deal_costs"}
        if not matches:
            ctx.journal.put("safety_halt", "position_identity_unresolved")
            return {"status": "UNKNOWN", "reason": "awaiting_broker_reconciliation"}
        if len(matches) != 1:
            raise ValueError("multiple_owned_positions")
        position = matches[0]
        ledger = [d for d in deals if int(d.position_id) == ident and int(d.type) in (0, 1)]
        owned_opening = [
            d
            for d in ledger
            if int(d.entry) == 0
            and int(d.magic) == ctx.strategy.magic
            and d.comment == active["comment"]
        ]
        net_volume = sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in ledger)
        if not owned_opening or (
            not active.get("safety_close_pending")
            and (
                not _finite(position.volume, positive=True)
                or abs(net_volume - float(position.volume) * (1 if int(position.type) == 0 else -1))
                > 1e-8
            )
        ):
            ctx.journal.put("safety_halt", "position_ledger_unresolved")
            return {"status": "UNKNOWN", "reason": "position_ledger_unresolved"}
        active["ticket"] = int(position.ticket)
        ctx.journal.put("active", active)
        if not active.get("safety_close_pending"):
            violation = self._contract_violation(position, active, info)
            if violation:
                ctx.journal.audit(
                    "CONTRACT_VIOLATION", expected=active, observed=position, reason=violation
                )
                return ctx._safety_close(position, active, info, now, violation)
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
        observed_cost = sum(
            max(0.0, -float(d.commission)) + max(0.0, -float(d.fee)) for d in owned_opening
        )
        if observed_cost > active["commission"] + 0.00000001:
            return ctx._safety_close(position, active, info, now, "fill_cost_policy_violation")
        active["observed_entry_cost"] = observed_cost
        if active["status"] != "FILLED":
            active.update(
                status="FILLED",
                ticket=int(position.ticket),
                position_id=int(position.identifier),
                fill=float(position.price_open),
                confirmed_sl=float(position.sl),
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
                    signal_to_fill_ms=int(position.time_msc)
                    - int(datetime.fromisoformat(active["bar"]).timestamp() * 1000),
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
        intrabar = getattr(ctx.strategy, "intrabar_protect", None)
        mode = intrabar(direction) if callable(intrabar) else None
        if mode == "observe" and not active.get("protection_active"):
            self._observe_intrabar_be(active, position, tick, info, now, direction)
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
            if int(p.identifier) == int(active["position_id"])
            and p.symbol == ctx.symbol
            and int(p.magic) == ctx.strategy.magic
        ]
        if len(matches) != 1:
            return {"status": "UNKNOWN", "reason": "be_position_changed"}
        current = matches[0]
        violation = self._contract_violation(current, active, info)
        if violation:
            return ctx._safety_close(current, active, info, now, violation)
        request["position"] = int(current.ticket)
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
        sent = ctx.send(request, now)
        if sent is not None and int(sent.retcode) not in (10008, 10009, 10012, 10031):
            active.pop("be_pending")
            ctx.journal.put("active", active)
            return {"status": "MANAGING", "reason": "be_rejected", "retcode": int(sent.retcode)}
        positions, _ = ctx.broker._exposure()
        return ctx._reconcile(positions, deals, tick, info, closed, now)

    def _observe_intrabar_be(self, active, position, tick, info, now, direction):
        """Record (once) the first fresh intrabar quote at which the BE trigger is met.

        Observe-only: never changes protection_active, SL or TP, and never raises, so the
        existing bar-close protection path below runs exactly as before.
        """
        ctx = self.context
        if active.get("intrabar_observed"):
            return
        try:
            quote_ms = int(tick.time_msc)
            age_ms = int(ctx._send_clock(now).timestamp() * 1000) - quote_ms
            last = getattr(self, "_intrabar_last_quote", None)
            if (
                quote_ms <= int(active["entry_ms"])
                or not 0 <= age_ms <= self._intrabar_max_age_ms()
                or (last is not None and last[0] == active.get("position_id") and quote_ms <= last[1])
            ):
                return
            self._intrabar_last_quote = (active.get("position_id"), quote_ms)
            executable = float(tick.bid if direction == 1 else tick.ask)
            profit = ctx.mt5.order_calc_profit(
                ctx.mt5.ORDER_TYPE_BUY if direction == 1 else ctx.mt5.ORDER_TYPE_SELL,
                ctx.symbol, 0.01, float(position.price_open), executable)
            if profit is None or not _finite(profit):
                return
            net = (float(profit) - active["commission"]
                   - active["slippage"] * 0.01 * info.trade_contract_size)
        except (AttributeError, KeyError, TypeError, ValueError):
            return
        if net < active["risk"]:
            return
        active["intrabar_observed"] = dict(
            source="intrabar", time_msc=quote_ms, executable=executable, net=net,
            risk=active["risk"], age_ms=age_ms)
        ctx.journal.transition("active", active, dict(
            kind="BE_TRIGGER_INTRABAR_OBSERVED", ticket=int(position.ticket),
            quote_time_msc=quote_ms, executable=executable, net=net, risk=active["risk"],
            age_ms=age_ms, snapshot=ctx.strategy.snapshot))

    def _intrabar_max_age_ms(self):
        return int(getattr(self.context.strategy, "intrabar_quote_max_age_ms", 5000))

    def _contract_violation(self, position, active, info):
        """Revalidate every observation; confirmed protection can only tighten."""
        ctx = self.context
        direction = active.get("direction", -1)
        if (
            not _finite(position.volume, positive=True)
            or float(position.volume) != 0.01
            or int(position.type) != (0 if direction == 1 else 1)
            or not all(
                _finite(getattr(position, k, None), positive=True)
                for k in ("price_open", "sl", "tp")
            )
        ):
            return "filled_position_contract_violation"
        tolerance = float(info.trade_tick_size) / 2
        floor = active.get("confirmed_sl", active["request"]["sl"])
        if (
            direction * (float(position.sl) - floor) < -1e-8
            or abs(float(position.tp) - active["request"]["tp"]) > tolerance
            or direction * (float(position.tp) - float(position.sl)) <= 0
        ):
            return "filled_stop_target_violation"
        profit = ctx.mt5.order_calc_profit(
            ctx.mt5.ORDER_TYPE_BUY if direction == 1 else ctx.mt5.ORDER_TYPE_SELL,
            ctx.symbol,
            0.01,
            float(position.price_open),
            float(position.sl),
        )
        if profit is None or not _finite(profit):
            return "filled_risk_violation"
        risk = (
            max(0.0, -float(profit))
            + active["commission"]
            + active["slippage"] * 0.01 * info.trade_contract_size
        )
        if not _finite(risk) or risk > active["entry_equity"] * ctx.strategy.risk_cap:
            return "filled_risk_violation"
        # Keep original entry risk for the frozen BE1R trigger.
        if active["status"] != "FILLED":
            active["risk"] = risk
        active["confirmed_sl"] = (
            max(floor, float(position.sl)) if direction == 1 else min(floor, float(position.sl))
        )
        ctx.journal.put("active", active)
        return None

    def _record_closed(self, active, ledger, ident, *, safety_reason=None):
        """One complete position ledger supplies both result and confirmed event."""
        ctx = self.context
        exits = [deal for deal in ledger if int(deal.entry) in (1, 3)]
        last_exit = max(exits, key=lambda deal: int(deal.time_msc))
        baseline = ctx.journal.get("day")
        exit_day = datetime.fromtimestamp(int(last_exit.time_msc) / 1000, timezone.utc).date().isoformat()
        baseline_metadata = dict(
            day_start=baseline["equity"] if baseline else None,
            day_start_day=baseline.get("day") if baseline else None,
            day_start_source=baseline.get("source") if baseline else None,
            day_start_valid=bool(
                baseline
                and baseline.get("day") == exit_day
                and baseline.get("source") in (
                    "captured_at_utc_boundary",
                    "reconstructed_flat_midnight_from_reconciled_history",
                )
                and baseline.get("account_fingerprint") == ctx.fingerprint
                and _finite(baseline.get("equity"), positive=True)
            ),
        )
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
            **baseline_metadata,
            **components,
        )
        if safety_reason:
            event.update(reason=safety_reason, ticket=active.get("safety_close_ticket"))
        ctx.journal.transition("active", None, event)
        result = dict(
            status=kind,
            net=event["net"],
            exit_price=event["exit_price"],
            **baseline_metadata,
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
            if int(p.identifier) == int(active["position_id"])
            and p.symbol == ctx.symbol
            and int(p.magic) == ctx.strategy.magic
        ]
        if len(owned) != 1:
            return {"status": "UNKNOWN", "reason": "safety_close_position_changed"}
        position = owned[0]
        ledger = [
            deal
            for deal in ctx.broker._history(ctx._send_clock(now))
            if int(deal.position_id) == int(position.identifier) and int(deal.type) in (0, 1)
        ]
        if not any(
            int(d.entry) == 0
            and int(d.magic) == ctx.strategy.magic
            and d.comment == active["comment"]
            for d in ledger
        ):
            return {"status": "UNKNOWN", "reason": "safety_ownership_unproven"}
        if not _finite(position.volume, positive=True):
            return {"status": "UNKNOWN", "reason": "safety_volume_unknown"}
        signed_volume = sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in ledger)
        if (
            orders
            or not _finite(signed_volume)
            or abs(signed_volume - float(position.volume) * (1 if int(position.type) == 0 else -1))
            > 1e-8
        ):
            return {"status": "UNKNOWN", "reason": "safety_ledger_unresolved"}
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
        sent = ctx.send(request, now)
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
            not any(int(p.identifier) == int(position.identifier) for p in fresh)
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
