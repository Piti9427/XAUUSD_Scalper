"""Pinned trial30 research-Demo runner; every mutation verifies Demo identity."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from scripts.pure_b1.broker_data import completed_m15_from_m1
from scripts.trial30.costs import validate_policy
from scripts.pure_b1.decision import round_level
from scripts.smc.mt5_filling import resolve_type_filling
from scripts.smc.risk import check_fixed_lot_risk
from scripts.trial30.strategy import Trial30Strategy
from scripts.trial30.journal import Journal
from scripts.trial30.broker import BrokerView, _finite, _cash

SNAPSHOT = "RESEARCH-D48-SELL-BE1R-20261001-T030"
MAGIC = 30261001


class Trial30DemoRunner:
    def __init__(
        self,
        *,
        mt5: Any,
        expected_login: int,
        expected_server: str,
        journal_path: Path,
        cost_policy: dict,
        execute: bool = False,
        notify: Callable[[dict], None] | None = None,
        symbol: str = "XAUUSDm",
        strategy=None,
        account_guard_dir: Path | None = None,
    ):
        if expected_login <= 0 or not expected_server or symbol != "XAUUSDm":
            raise ValueError("explicit target Demo identity and XAUUSDm required")
        self.strategy = strategy or Trial30Strategy()
        self.mt5 = mt5
        self.login = expected_login
        self.server = expected_server
        self.symbol = symbol
        self.execute = execute
        self.policy = cost_policy
        self.notify = notify
        self.journal = Journal(journal_path)
        self.fingerprint = hashlib.sha256(
            f"{expected_server}:{expected_login}".encode()
        ).hexdigest()[:16]

        # Same-account runners share a local single-writer guard, even with
        # separate strategy journals. Journal implementation stays unchanged.
        try:
            recorded = self.journal.get("strategy_snapshot")
            active = self.journal.get("active")
            if recorded not in (None, self.strategy.snapshot) or (
                active and int(active["request"]["magic"]) != self.strategy.magic
            ):
                raise ValueError("journal_strategy_mismatch")
            self.account_guard = Journal(
                (account_guard_dir or journal_path.parent)
                / f"demo-account-{self.fingerprint}.sqlite3"
            )
            self.journal.put("strategy_snapshot", self.strategy.snapshot)
        except Exception:
            guard = getattr(self, "account_guard", None)
            if guard is not None:
                guard.close()
            self.journal.close()
            raise

        self.broker = BrokerView(
            mt5, expected_login, expected_server, symbol, self.fingerprint, self.journal
        )

    def close(self):
        self.journal.close()
        self.account_guard.close()

    def cycle(self, *, now: datetime) -> dict:
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("cycle clock must be aware UTC")
        self._started = time.monotonic()
        try:
            result = self._cycle(now)
        except ValueError as exc:
            result = {"status": "BLOCKED", "reason": str(exc)}
        except Exception as exc:
            result = {"status": "BLOCKED", "reason": type(exc).__name__}
        result.update(
            snapshot=self.strategy.snapshot, execute=self.execute, captured_utc=now.isoformat()
        )
        result.update(self.strategy.diagnostics())
        self.journal.put("last_result", result)
        try:
            self.journal.flush(self.notify)
        except Exception:
            result["notification"] = "pending_retry"
        return result

    def _cycle(self, now):
        account = self.broker.identity()
        positions, orders = self.broker._exposure()
        deals = self.broker._history(now)
        info = self.broker._spec()
        tick = self.broker._quote(now)
        if self.journal.get("active"):
            # Source/cache warmup gates apply only to admission. Reconcile on restart
            # even if detector/history bootstrap fails; retain last BE bar then.
            active = self.journal.get("active")
            closed = datetime.fromisoformat(active["last_be_bar"])
            try:
                bars = completed_m15_from_m1(
                    self.mt5.copy_rates_from_pos(self.symbol, self.mt5.TIMEFRAME_M1, 0, 5000),
                    now=now,
                )
                closed = bars.index[-1].to_pydatetime() + timedelta(minutes=15)
            except ValueError:
                pass
            try:
                self.broker._baseline(account, positions, deals, now)
            except ValueError:
                pass
            return self._reconcile(positions, deals, tick, info, closed, now)
        bars = completed_m15_from_m1(
            self.mt5.copy_rates_from_pos(self.symbol, self.mt5.TIMEFRAME_M1, 0, 5000), now=now
        )
        frame = self.strategy.frame(bars, self.mt5, self.symbol, now)
        row = frame.iloc[-1]
        closed = frame.index[-1].to_pydatetime() + timedelta(minutes=15)
        bar = closed.isoformat()
        if self.journal.get("safety_halt"):
            raise ValueError("safety_halt")
        baseline = self.broker._baseline(account, positions, deals, now)
        if positions or orders:
            raise ValueError("foreign_exposure")
        if self.journal.get("last_bar") == bar:
            return {"status": "WAIT", "reason": "duplicate_bar"}
        if int(row.direction) not in self.strategy.allowed_sides:
            self.journal.put("last_bar", bar)
            return {"status": "WAIT", "reason": self.strategy.no_signal_reason, "bar": bar}
        direction = int(row.direction)
        order_type = self.mt5.ORDER_TYPE_BUY if direction == 1 else self.mt5.ORDER_TYPE_SELL
        if (
            self.strategy.max_daily_losses
            and self._daily_losses(deals, now) >= self.strategy.max_daily_losses
        ):
            self.journal.put("last_bar", bar)
            raise ValueError("max_daily_losses")
        if now < closed or now - closed > timedelta(seconds=90):
            self.journal.put("last_bar", bar)
            raise ValueError("entry_window_expired")
        first = self._first_quote(closed, now)
        if int(first.time_msc) > int((closed + timedelta(seconds=90)).timestamp() * 1000):
            raise ValueError("first_quote_late")
        cost, status = validate_policy(self.policy, fingerprint=self.fingerprint, now=now)
        if not cost:
            raise ValueError("cost_policy_" + status)
        if baseline - float(account.equity) >= baseline * self.strategy.daily_loss_limit:
            self.journal.put("last_bar", bar)
            raise ValueError("daily_loss_limit")
        entry = float(tick.ask if direction == 1 else tick.bid)
        risk_entry, sl, tp = self.strategy.levels(row, tick, info, cost, account)
        allowance = float(cost["slippage_allowance_price"])
        risk = check_fixed_lot_risk(
            equity=float(account.equity),
            entry_price=risk_entry,
            sl_price=sl,
            contract_size=float(info.trade_contract_size),
            commission_per_lot=float(cost["commission_per_lot"]),
            slippage_allowance=allowance,
            min_lot=float(info.volume_min),
            max_lot=float(info.volume_max),
            lot_step=float(info.volume_step),
            require_cost_model=True,
            max_risk_cap_pct=self.strategy.risk_cap,
        )
        if not risk.is_valid:
            self.journal.put("last_bar", bar)
            raise ValueError("risk_cap_or_volume")
        profit = self.mt5.order_calc_profit(order_type, self.symbol, 0.01, risk_entry, sl)
        commission = 0.01 * float(cost["commission_per_lot"])
        risk_amount = (
            -float(profit) + allowance * 0.01 * info.trade_contract_size + commission
            if profit is not None
            else None
        )
        if (
            risk_amount is None
            or not _finite(risk_amount, positive=True)
            or risk_amount > account.equity * self.strategy.risk_cap
        ):
            raise ValueError("broker_risk_invalid")
        distance = max(info.trade_stops_level, info.trade_freeze_level) * info.point
        executable = float(tick.bid if direction == 1 else tick.ask)
        if direction * (executable - sl) <= distance or direction * (tp - executable) <= distance:
            raise ValueError("stop_geometry")
        margin = self.mt5.order_calc_margin(order_type, self.symbol, 0.01, entry)
        if margin is None or not _finite(margin) or margin < 0 or margin > account.margin_free:
            raise ValueError("insufficient_margin")
        filling = resolve_type_filling(int(info.filling_mode), for_pending=False, mt5_mod=self.mt5)
        if int(info.filling_mode) & 1:
            filling = self.mt5.ORDER_FILLING_FOK
        comment = self.strategy.prefix + format(int(closed.timestamp()), "x")
        request = dict(
            action=self.mt5.TRADE_ACTION_DEAL,
            symbol=self.symbol,
            volume=0.01,
            type=order_type,
            price=entry,
            sl=sl,
            tp=tp,
            deviation=max(0, int(allowance / info.point)),
            magic=self.strategy.magic,
            comment=comment,
            type_time=self.mt5.ORDER_TIME_GTC,
            type_filling=filling,
        )
        check = self.mt5.order_check(request)
        if check is None or int(check.retcode) != 0:
            self.journal.put("last_bar", bar)
            raise ValueError("order_check_rejected")
        if not self.execute:
            return {
                "status": "SHADOW_ADMIT",
                "bar": bar,
                "request": request,
                "risk": risk_amount,
                "day_start": baseline,
            }
        fresh_account = self.broker.identity()
        send_now = now + timedelta(seconds=time.monotonic() - self._started)
        fresh_tick = self.broker._quote(send_now)
        if send_now - closed > timedelta(seconds=90):
            raise ValueError("entry_window_expired")
        if abs(float(fresh_tick.ask if direction == 1 else fresh_tick.bid) - entry) > allowance:
            raise ValueError("quote_changed_before_send")
        if (
            risk_amount > float(fresh_account.equity) * self.strategy.risk_cap
            or baseline - float(fresh_account.equity) >= baseline * self.strategy.daily_loss_limit
        ):
            raise ValueError("capital_changed_before_send")
        current_positions, current_orders = self.broker._exposure()
        if current_positions or current_orders:
            raise ValueError("exposure_changed")
        active = dict(
            direction=direction,
            comment=comment,
            bar=bar,
            status="SENDING",
            request=request,
            risk=risk_amount,
            commission=commission,
            slippage=allowance,
            entry_equity=float(fresh_account.equity),
            first_quote=dict(
                time_msc=int(first.time_msc), bid=float(first.bid), ask=float(first.ask)
            ),
            entry_ms=int(tick.time_msc),
            last_be_bar=bar,
        )
        thesis = getattr(self.strategy, "entry_thesis", None)
        if callable(thesis):
            note = thesis()
            if note:
                active["thesis"] = note
        self.journal.put("active", active)  # Commit BEFORE irreversible API.
        self.journal.put("last_bar", bar)
        try:
            sent = self.mt5.order_send(request)
        except Exception:
            sent = None
        if sent is not None and int(sent.retcode) not in (10009, 10010, 10008, 10012, 10031):
            self.journal.put("active", None)
            return {"status": "REJECTED", "retcode": int(sent.retcode)}
        active["status"] = "UNKNOWN"
        self.journal.put("active", active)
        positions, _ = self.broker._exposure()
        return self._reconcile(
            positions, self.broker._history(now + timedelta(minutes=1)), tick, info, closed, now
        )

    def _daily_losses(self, deals, now):
        """Route exits through owned opening position IDs, never closing magic."""
        ids = {
            int(d.position_id)
            for d in deals
            if int(d.entry) == 0
            and int(d.type) in (0, 1)
            and int(d.magic) == self.strategy.magic
            and str(d.comment).startswith(self.strategy.prefix)
        }
        losses = 0
        for ident in ids:
            ledger = [d for d in deals if int(d.position_id) == ident and int(d.type) in (0, 1)]
            exits = [d for d in ledger if int(d.entry) in (1, 3)]
            volume = sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in ledger)
            if exits and abs(volume) < 1e-8 and sum(_cash(d) for d in ledger) < 0:
                last = max(int(d.time_msc) for d in exits)
                if datetime.fromtimestamp(last / 1000, now.tzinfo).date() == now.date():
                    losses += 1
        return losses

    def _first_quote(self, closed, now):
        rows = self.mt5.copy_ticks_range(self.symbol, closed, now, self.mt5.COPY_TICKS_ALL)
        frame = pd.DataFrame(rows)
        if frame.empty or not {"time_msc", "bid", "ask"}.issubset(frame.columns):
            raise ValueError("first_quote_unknown")
        frame = frame[
            (frame.time_msc >= int(closed.timestamp() * 1000))
            & (frame.time_msc <= int(now.timestamp() * 1000))
        ]
        if frame.empty:
            raise ValueError("first_quote_unknown")
        first = frame.sort_values("time_msc", kind="stable").iloc[0]
        if (
            not all(_finite(first[k], positive=True) for k in ("bid", "ask"))
            or first.ask < first.bid
        ):
            raise ValueError("first_quote_invalid")
        return first

    def _send_clock(self, now):
        return now + timedelta(seconds=time.monotonic() - self._started)

    def _reconcile(self, positions, deals, tick, info, closed, now):
        active = self.journal.get("active")
        matches = [
            p
            for p in positions
            if p.symbol == self.symbol
            and int(p.magic) == self.strategy.magic
            and p.comment == active["comment"]
        ]
        if not matches:
            ident = active.get("position_id")
            if ident is None:
                opened = [
                    d
                    for d in deals
                    if int(d.magic) == self.strategy.magic
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
                        safety = self.journal.get("safety_halt") or "safety_close"
                    return self._record_closed(active, ledger, ident, safety_reason=safety)
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
            return self._safety_close(
                position, active, info, now, "filled_position_contract_violation"
            )
        if active.get("safety_close_pending"):
            return self._safety_close(
                position,
                active,
                info,
                now,
                active.get("safety_close_reason")
                or self.journal.get("safety_halt")
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
                return self._safety_close(position, active, info, now, "fill_cost_policy_violation")
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
                return self._safety_close(
                    position, active, info, now, "filled_stop_target_violation"
                )
            broker_loss = self.mt5.order_calc_profit(
                self.mt5.ORDER_TYPE_BUY
                if active.get("direction", -1) == 1
                else self.mt5.ORDER_TYPE_SELL,
                self.symbol,
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
                or actual_risk > active["entry_equity"] * self.strategy.risk_cap
            ):
                return self._safety_close(position, active, info, now, "filled_risk_violation")
            active["risk"] = actual_risk
            active.update(
                status="FILLED",
                ticket=int(position.ticket),
                position_id=int(position.identifier),
                fill=float(position.price_open),
                entry_ms=int(position.time_msc),
            )
            self.journal.transition(
                "active",
                active,
                dict(
                    kind="FILLED",
                    ticket=int(position.ticket),
                    symbol=self.symbol,
                    volume=0.01,
                    entry=float(position.price_open),
                    sl=float(position.sl),
                    tp=float(position.tp),
                    snapshot=self.strategy.snapshot,
                ),
            )
            return {"status": "FILLED", "ticket": int(position.ticket)}
        direction = active.get("direction", -1)
        if not self.strategy.protects(direction):
            return {"status": "MANAGING", "ticket": int(position.ticket)}
        bar = closed.isoformat()
        if active.get("be_pending") is not None:
            candidate = float(active["be_pending"])
            if direction * (float(position.sl) - candidate) >= -float(info.trade_tick_size) / 2:
                active.pop("be_pending")
                active["be_done"] = True
                self.journal.transition(
                    "active",
                    active,
                    dict(
                        kind="BE_MOVED",
                        ticket=int(position.ticket),
                        sl=float(position.sl),
                        tp=float(position.tp),
                        snapshot=self.strategy.snapshot,
                    ),
                )
                return {"status": "BE_MOVED", "ticket": int(position.ticket)}
            return {"status": "UNKNOWN", "reason": "awaiting_be_confirmation"}
        if active.get("be_done"):
            return {"status": "MANAGING", "ticket": int(position.ticket)}
        if bar != active["last_be_bar"] and int(closed.timestamp() * 1000) > active["entry_ms"]:
            first = self._first_quote(closed, now)
            active["be_activation_quote"] = dict(
                time_msc=int(first.time_msc), bid=float(first.bid), ask=float(first.ask)
            )
            profit = self.mt5.order_calc_profit(
                self.mt5.ORDER_TYPE_BUY
                if active.get("direction", -1) == 1
                else self.mt5.ORDER_TYPE_SELL,
                self.symbol,
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
            self.journal.put("active", active)
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
        if not self.execute:
            return {"status": "SHADOW_BE", "sl": candidate, "ticket": int(position.ticket)}
        request = dict(
            action=self.mt5.TRADE_ACTION_SLTP,
            symbol=self.symbol,
            position=int(position.ticket),
            sl=candidate,
            tp=float(position.tp),
            magic=self.strategy.magic,
        )
        check = self.mt5.order_check(request)
        if check is None or int(check.retcode) != 0:
            return {"status": "MANAGING", "reason": "be_check_rejected"}
        self.broker.identity()
        positions, _ = self.broker._exposure()
        matches = [
            p
            for p in positions
            if int(p.ticket) == int(position.ticket)
            and p.symbol == self.symbol
            and int(p.magic) == self.strategy.magic
            and p.comment == active["comment"]
        ]
        if len(matches) != 1:
            return {"status": "UNKNOWN", "reason": "be_position_changed"}
        current = matches[0]
        fresh_tick = self.broker._quote(self._send_clock(now))
        executable = float(fresh_tick.bid if direction == 1 else fresh_tick.ask)
        if (
            direction * (candidate - float(current.sl)) <= 0
            or direction * (executable - candidate) <= distance
        ):
            return {"status": "MANAGING", "reason": "be_geometry_changed"}
        request["tp"] = float(current.tp)
        active["be_pending"] = candidate
        self.journal.put("active", active)
        try:
            sent = self.mt5.order_send(request)
        except Exception:
            sent = None
        if sent is not None and int(sent.retcode) not in (10009, 10012, 10031):
            active.pop("be_pending")
            self.journal.put("active", active)
            return {"status": "MANAGING", "reason": "be_rejected", "retcode": int(sent.retcode)}
        positions, _ = self.broker._exposure()
        return self._reconcile(positions, deals, tick, info, closed, now)

    def _record_closed(self, active, ledger, ident, *, safety_reason=None):
        """One complete position ledger supplies both result and confirmed event."""
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
            snapshot=self.strategy.snapshot,
            fill=active.get("fill"),
            exit_price=float(getattr(last_exit, "price", 0) or 0) or None,
            **components,
        )
        if safety_reason:
            event.update(reason=safety_reason, ticket=active.get("safety_close_ticket"))
        self.journal.transition("active", None, event)
        baseline = self.journal.get("day")
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
        self.journal.put("safety_halt", reason)
        if not self.execute:
            return {"status": "BLOCKED", "reason": reason}
        if active.get("safety_close_pending"):
            attempt = active.get("safety_close_attempt") or {}
            if attempt.get("retcode") != 10010:
                return {"status": "UNKNOWN", "reason": "awaiting_safety_close_confirmation"}
        self.broker.identity()
        fresh, orders = self.broker._exposure()
        owned = [
            p
            for p in fresh
            if int(p.ticket) == int(position.ticket)
            and p.symbol == self.symbol
            and int(p.magic) == self.strategy.magic
            and p.comment == active["comment"]
        ]
        if len(owned) != 1:
            return {"status": "UNKNOWN", "reason": "safety_close_position_changed"}
        position = owned[0]
        ledger = [
            deal
            for deal in self.broker._history(self._send_clock(now))
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
        tick = self.broker._quote(self._send_clock(now))
        if int(position.type) not in (0, 1):
            return {"status": "BLOCKED", "reason": "safety_position_type_unknown"}
        request = dict(
            action=self.mt5.TRADE_ACTION_DEAL,
            symbol=self.symbol,
            position=int(position.ticket),
            volume=float(position.volume),
            type=self.mt5.ORDER_TYPE_BUY if int(position.type) == 1 else self.mt5.ORDER_TYPE_SELL,
            price=float(tick.ask if int(position.type) == 1 else tick.bid),
            magic=self.strategy.magic,
            comment=self.strategy.prefix + "SAFETY",
            deviation=max(0, int(active["slippage"] / info.point)),
            type_filling=resolve_type_filling(
                int(info.filling_mode), for_pending=False, mt5_mod=self.mt5
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
        self.journal.put("active", active)
        try:
            sent = self.mt5.order_send(request)
        except Exception:
            sent = None
        if sent is not None:
            active["safety_close_attempt"].update(
                retcode=int(sent.retcode),
                order_ticket=int(getattr(sent, "order", 0) or 0),
            )
            self.journal.put("active", active)
        fresh, _ = self.broker._exposure()
        ledger = [
            d
            for d in self.broker._history(self._send_clock(now))
            if int(d.position_id) == int(position.identifier) and int(d.type) in (0, 1)
        ]
        volume = sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in ledger)
        if (
            not any(int(p.ticket) == int(position.ticket) for p in fresh)
            and ledger
            and abs(volume) < 1e-8
            and any(int(deal.entry) in (1, 3) for deal in ledger)
        ):
            return self._record_closed(
                active, ledger, int(position.identifier), safety_reason=reason
            )
        if sent is not None and int(sent.retcode) not in (10009, 10010, 10008, 10012, 10031):
            active.pop("safety_close_pending")
            self.journal.put("active", active)
        return {"status": "UNKNOWN", "reason": "awaiting_safety_close_confirmation"}
