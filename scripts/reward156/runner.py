"""Pinned Reward156 research-Demo runner; every mutation verifies Demo identity.

- Snapshot: RESEARCH-HYBRID-RSI7BUY-D48SELL-T156
- BUY: RSI7 cross > 35, positive delta, close > EMA50, rising EMA50
- SELL: D48 breakout (prior 48-bar low)
- Levels: SL 2.5 ATR, TP 1.35x rounded stop distance
- Risk & Circuits: fixed 0.01 lot, 10% risk cap, 20% daily loss limit, 5% BUY-pause drawdown
"""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import time
from pathlib import Path
from typing import Any, Callable

from scripts.pure_b1.broker_data import completed_m15_from_m1
from scripts.trial30.costs import validate_policy
from scripts.pure_b1.decision import round_level
from scripts.smc.mt5_filling import resolve_type_filling
from scripts.smc.risk import check_fixed_lot_risk
from scripts.strategy import reward156_bars, reward156_levels
from scripts.trial30.journal import Journal
from scripts.trial30.broker import BrokerView, _finite

SNAPSHOT = "RESEARCH-HYBRID-RSI7BUY-D48SELL-T156"
MAGIC = 15626104


class Reward156DemoRunner:
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
        frame = reward156_bars(bars)
        if len(frame) < 55:
            raise ValueError("warmup_insufficient")
        row = frame.iloc[-1]
        closed = frame.index[-1].to_pydatetime() + timedelta(minutes=15)
        bar = closed.isoformat()

        # Update high-water mark / peak equity for BUY pause tracking
        peak_equity = float(self.journal.get("peak_equity") or account.equity)
        if float(account.equity) > peak_equity:
            peak_equity = float(account.equity)
            self.journal.put("peak_equity", peak_equity)

        if self.journal.get("active"):
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

        direction = int(row.direction)
        if direction not in (-1, 1):
            self.journal.put("last_bar", bar)
            return {"status": "WAIT", "reason": "no_signal", "bar": bar}

        # BUY pause drawdown circuit: equity DD >= 5% suppresses BUY
        if direction == 1:
            drawdown_from_peak = (peak_equity - float(account.equity)) / peak_equity
            if drawdown_from_peak >= 0.05:
                self.journal.put("last_bar", bar)
                raise ValueError("buy_pause_drawdown")

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

        # Entry price: BUY uses Ask, SELL uses Bid
        order_type = self.mt5.ORDER_TYPE_BUY if direction == 1 else self.mt5.ORDER_TYPE_SELL
        entry = float(tick.ask) if direction == 1 else float(tick.bid)

        # SL and TP levels from reward156_levels
        raw_sl, raw_tp = reward156_levels(entry, direction, float(row.atr))
        sl = round_level(raw_sl, float(info.trade_tick_size), -direction)
        tp = round_level(raw_tp, float(info.trade_tick_size), direction)

        allowance = float(cost["slippage_allowance_price"])
        eff_entry = entry + allowance if direction == 1 else entry - allowance

        risk = check_fixed_lot_risk(
            equity=float(account.equity),
            entry_price=eff_entry,
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

        profit = self.mt5.order_calc_profit(order_type, self.symbol, 0.01, eff_entry, sl)
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
        if direction == 1:
            if tick.bid - sl <= distance or tp - tick.bid <= distance:
                raise ValueError("stop_geometry")
        else:
            if sl - tick.ask <= distance or tick.ask - tp <= distance:
                raise ValueError("stop_geometry")

        margin = self.mt5.order_calc_margin(order_type, self.symbol, 0.01, entry)
        if margin is None or not _finite(margin) or margin < 0 or margin > account.margin_free:
            raise ValueError("insufficient_margin")

        filling = resolve_type_filling(int(info.filling_mode), for_pending=False, mt5_mod=self.mt5)
        if int(info.filling_mode) & 1:
            filling = self.mt5.ORDER_FILLING_FOK

        side_prefix = "BUY_" if direction == 1 else "SELL_"
        comment = "R156_" + side_prefix + format(int(closed.timestamp()), "x")
        request = dict(
            action=self.mt5.TRADE_ACTION_DEAL,
            symbol=self.symbol,
            volume=0.01,
            type=order_type,
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
                "direction": direction,
                "request": request,
                "risk": risk_amount,
                "day_start": baseline,
            }

        fresh_account = self.broker.identity()
        send_now = now + timedelta(seconds=time.monotonic() - self._started)
        fresh_tick = self.broker._quote(send_now)
        if send_now - closed > timedelta(seconds=90):
            raise ValueError("entry_window_expired")
        ref_quote = float(fresh_tick.ask) if direction == 1 else float(fresh_tick.bid)
        if abs(ref_quote - entry) > allowance:
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
            direction=direction,
            request=request,
            risk=risk_amount,
            commission=commission,
            slippage=allowance,
            entry_equity=float(account.equity),
            first_quote=dict(
                time_msc=int(first.time_msc), bid=float(first.bid), ask=float(first.ask)
            ),
            entry_ms=int(tick.time_msc),
            submitted_utc=send_now.isoformat(),
        )
        self.journal.claim_active(active)
        sent = self.mt5.order_send(request)
        if sent is None or int(sent.retcode) not in (
            self.mt5.TRADE_RETCODE_DONE,
            self.mt5.TRADE_RETCODE_PLACED,
        ):
            code = getattr(sent, "retcode", None)
            raise ValueError(f"order_send_failed_{code}")

        self.journal.record_event(
            "ORDER_SUBMITTED",
            dict(
                ticket=int(sent.order),
                deal=getattr(sent, "deal", None),
                retcode=int(sent.retcode),
                price=float(sent.price) if getattr(sent, "price", None) else entry,
            ),
        )
        active.update(status="SUBMITTED", ticket=int(sent.order))
        self.journal.put("active", active)
        return {"status": "SUBMITTED", "bar": bar, "ticket": int(sent.order), "direction": direction}

    def _first_quote(self, closed: datetime, now: datetime):
        return self.broker._quote(now)

    def _reconcile(self, positions, deals, tick, info, closed, now):
        active = self.journal.get("active")
        ticket = active.get("ticket")
        matching = [p for p in positions if int(p.ticket) == ticket or p.comment == active["comment"]]
        if matching:
            return {"status": "OPEN", "ticket": ticket, "bar": active.get("bar")}
        # Position closed
        self.journal.put("active", None)
        return {"status": "CLOSED", "ticket": ticket, "bar": active.get("bar")}
