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
from scripts.strategy import trial30_bars
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
    ):
        if expected_login <= 0 or not expected_server or symbol != "XAUUSDm":
            raise ValueError("explicit target Demo identity and XAUUSDm required")
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

        self.broker = BrokerView(
            mt5, expected_login, expected_server, symbol, self.fingerprint, self.journal
        )

    def close(self):
        self.journal.close()

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
        result.update(snapshot=SNAPSHOT, execute=self.execute, captured_utc=now.isoformat())
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
        bars = completed_m15_from_m1(
            self.mt5.copy_rates_from_pos(self.symbol, self.mt5.TIMEFRAME_M1, 0, 5000), now=now
        )
        frame = trial30_bars(bars)
        if len(frame) < 49:
            raise ValueError("warmup_insufficient")
        row = frame.iloc[-1]
        closed = frame.index[-1].to_pydatetime() + timedelta(minutes=15)
        bar = closed.isoformat()
        if self.journal.get("active"):
            # Admission baselines never suppress protection of an existing trade.
            try:
                self.broker._baseline(account, positions, deals, now)
            except ValueError:
                pass
            return self._reconcile(positions, deals, tick, info, closed, now)
        if self.journal.get("safety_halt"):
            raise ValueError("safety_halt")
        baseline = self.broker._baseline(account, positions, deals, now)
        if positions or orders:
            raise ValueError("foreign_exposure")
        if self.journal.get("last_bar") == bar:
            return {"status": "WAIT", "reason": "duplicate_bar"}
        if int(row.direction) != -1:
            self.journal.put("last_bar", bar)
            return {"status": "WAIT", "reason": "no_sell_signal", "bar": bar}
        if now < closed or now - closed > timedelta(seconds=90):
            self.journal.put("last_bar", bar)
            raise ValueError("entry_window_expired")
        first = self._first_quote(closed, now)
        if int(first.time_msc) > int((closed + timedelta(seconds=90)).timestamp() * 1000):
            raise ValueError("first_quote_late")
        cost, status = validate_policy(self.policy, fingerprint=self.fingerprint, now=now)
        if not cost:
            raise ValueError("cost_policy_" + status)
        if baseline - float(account.equity) >= baseline * 0.20:
            self.journal.put("last_bar", bar)
            raise ValueError("daily_loss_limit")
        entry = float(tick.bid)
        sl = round_level(entry + float(row.atr) * 2.5, float(info.trade_tick_size), -1)
        tp = round_level(entry - float(row.atr) * 3.0, float(info.trade_tick_size), -1)
        allowance = float(cost["slippage_allowance_price"])
        risk = check_fixed_lot_risk(
            equity=float(account.equity),
            entry_price=entry - allowance,
            sl_price=sl,
            contract_size=float(info.trade_contract_size),
            commission_per_lot=float(cost["commission_per_lot"]),
            slippage_allowance=allowance,
            min_lot=float(info.volume_min),
            max_lot=float(info.volume_max),
            lot_step=float(info.volume_step),
            require_cost_model=True,
        )
        if not risk.is_valid:
            self.journal.put("last_bar", bar)
            raise ValueError("risk_cap_or_volume")
        profit = self.mt5.order_calc_profit(
            self.mt5.ORDER_TYPE_SELL, self.symbol, 0.01, entry - allowance, sl
        )
        commission = 0.01 * float(cost["commission_per_lot"])
        risk_amount = (
            -float(profit) + allowance * 0.01 * info.trade_contract_size + commission
            if profit is not None
            else None
        )
        if (
            risk_amount is None
            or not _finite(risk_amount, positive=True)
            or risk_amount > account.equity * 0.10
        ):
            raise ValueError("broker_risk_invalid")
        distance = max(info.trade_stops_level, info.trade_freeze_level) * info.point
        if sl - tick.ask <= distance or tick.ask - tp <= distance:
            raise ValueError("stop_geometry")
        margin = self.mt5.order_calc_margin(self.mt5.ORDER_TYPE_SELL, self.symbol, 0.01, entry)
        if margin is None or not _finite(margin) or margin < 0 or margin > account.margin_free:
            raise ValueError("insufficient_margin")
        filling = resolve_type_filling(int(info.filling_mode), for_pending=False, mt5_mod=self.mt5)
        if int(info.filling_mode) & 1:
            filling = self.mt5.ORDER_FILLING_FOK
        comment = "T30_" + format(int(closed.timestamp()), "x")
        request = dict(
            action=self.mt5.TRADE_ACTION_DEAL,
            symbol=self.symbol,
            volume=0.01,
            type=self.mt5.ORDER_TYPE_SELL,
            price=entry,
            sl=sl,
            tp=tp,
            deviation=max(0, int(allowance / info.point)),
            magic=MAGIC,
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
        if abs(float(fresh_tick.bid) - entry) > allowance:
            raise ValueError("quote_changed_before_send")
        if (
            risk_amount > float(fresh_account.equity) * 0.10
            or baseline - float(fresh_account.equity) >= baseline * 0.20
        ):
            raise ValueError("capital_changed_before_send")
        current_positions, current_orders = self.broker._exposure()
        if current_positions or current_orders:
            raise ValueError("exposure_changed")
        active = dict(
            comment=comment,
            bar=bar,
            status="SENDING",
            request=request,
            risk=risk_amount,
            commission=commission,
            slippage=allowance,
            entry_equity=float(account.equity),
            first_quote=dict(
                time_msc=int(first.time_msc), bid=float(first.bid), ask=float(first.ask)
            ),
            entry_ms=int(tick.time_msc),
            last_be_bar=bar,
        )
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
            if p.symbol == self.symbol and int(p.magic) == MAGIC and p.comment == active["comment"]
        ]
        if not matches:
            ident = active.get("position_id")
            if ident is None:
                opened = [
                    d
                    for d in deals
                    if int(d.magic) == MAGIC
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
                    net = sum(_cash(d) for d in ledger)
                    event = dict(kind="CLOSED", position_id=ident, net=net, snapshot=SNAPSHOT)
                    self.journal.transition("active", None, event)
                    baseline = self.journal.get("day")
                    return {
                        "status": "CLOSED",
                        "net": net,
                        "day_start": baseline["equity"] if baseline else None,
                    }
            return {"status": "UNKNOWN", "reason": "awaiting_broker_reconciliation"}
        if len(matches) != 1:
            raise ValueError("multiple_owned_positions")
        position = matches[0]
        if (
            float(position.volume) != 0.01
            or int(position.type) != 1
            or position.sl <= 0
            or position.tp <= 0
        ):
            return self._safety_close(
                position, active, info, now, "filled_position_contract_violation"
            )
        if active.get("safety_close_pending"):
            return {"status": "UNKNOWN", "reason": "awaiting_safety_close_confirmation"}
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
                self.mt5.ORDER_TYPE_SELL,
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
                or actual_risk > active["entry_equity"] * 0.10
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
                    snapshot=SNAPSHOT,
                ),
            )
            return {"status": "FILLED", "ticket": int(position.ticket)}
        bar = closed.isoformat()
        if active.get("be_pending") is not None:
            candidate = float(active["be_pending"])
            if float(position.sl) <= candidate + float(info.trade_tick_size) / 2:
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
                        snapshot=SNAPSHOT,
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
                self.mt5.ORDER_TYPE_SELL,
                self.symbol,
                0.01,
                float(position.price_open),
                float(first.ask),
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
            - (active["commission"] / (0.01 * info.trade_contract_size) + active["slippage"]),
            float(info.trade_tick_size),
            1,
        )
        distance = max(info.trade_stops_level, info.trade_freeze_level) * info.point
        if candidate >= float(position.sl) or candidate - float(tick.ask) <= distance:
            return {"status": "MANAGING", "reason": "be_geometry", "ticket": int(position.ticket)}
        if not self.execute:
            return {"status": "SHADOW_BE", "sl": candidate, "ticket": int(position.ticket)}
        request = dict(
            action=self.mt5.TRADE_ACTION_SLTP,
            symbol=self.symbol,
            position=int(position.ticket),
            sl=candidate,
            tp=float(position.tp),
            magic=MAGIC,
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
            and int(p.magic) == MAGIC
            and p.comment == active["comment"]
        ]
        if len(matches) != 1:
            return {"status": "UNKNOWN", "reason": "be_position_changed"}
        current = matches[0]
        fresh_tick = self.broker._quote(self._send_clock(now))
        if candidate >= float(current.sl) or candidate - float(fresh_tick.ask) <= distance:
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

    def _safety_close(self, position, active, info, now, reason):
        """Contain unexpected fills; never touch another strategy's position."""
        self.journal.put("safety_halt", reason)
        if not self.execute:
            return {"status": "BLOCKED", "reason": reason}
        if active.get("safety_close_pending"):
            return {"status": "UNKNOWN", "reason": "awaiting_safety_close_confirmation"}
        self.broker.identity()
        fresh, _ = self.broker._exposure()
        owned = [
            p
            for p in fresh
            if int(p.ticket) == int(position.ticket)
            and p.symbol == self.symbol
            and int(p.magic) == MAGIC
            and p.comment == active["comment"]
        ]
        if len(owned) != 1:
            return {"status": "UNKNOWN", "reason": "safety_close_position_changed"}
        position = owned[0]
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
            magic=MAGIC,
            comment="T30_SAFETY",
            deviation=max(0, int(active["slippage"] / info.point)),
            type_filling=resolve_type_filling(
                int(info.filling_mode), for_pending=False, mt5_mod=self.mt5
            ),
        )
        active["safety_close_pending"] = True
        active["position_id"] = int(position.identifier)
        self.journal.put("active", active)
        try:
            sent = self.mt5.order_send(request)
        except Exception:
            sent = None
        fresh, _ = self.broker._exposure()
        ledger = [
            d
            for d in self.broker._history(now)
            if int(d.position_id) == int(position.identifier) and int(d.type) in (0, 1)
        ]
        volume = sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in ledger)
        if (
            not any(int(p.ticket) == int(position.ticket) for p in fresh)
            and ledger
            and abs(volume) < 1e-8
        ):
            event = dict(
                kind="SAFETY_CLOSED",
                ticket=int(position.ticket),
                reason=reason,
                net=sum(_cash(d) for d in ledger),
                snapshot=SNAPSHOT,
            )
            self.journal.transition("active", None, event)
            return {"status": "SAFETY_CLOSED", "reason": reason}
        if sent is not None and int(sent.retcode) not in (10009, 10010, 10008, 10012, 10031):
            active.pop("safety_close_pending")
            self.journal.put("active", active)
        return {"status": "UNKNOWN", "reason": "awaiting_safety_close_confirmation"}
