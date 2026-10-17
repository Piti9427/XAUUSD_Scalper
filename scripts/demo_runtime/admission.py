"""New-entry detection, admission and intent-before-send ordering."""

from datetime import datetime, timedelta
import time

import pandas as pd

from scripts.demo_runtime.broker import _finite, _cash
from scripts.demo_runtime.costs import validate_policy
from scripts.smc.mt5_filling import resolve_type_filling
from scripts.smc.risk import check_fixed_lot_risk


class Admission:
    """Internal collaborator sharing runner context; no independent persisted state."""

    def __init__(self, context):
        self.context = context

    def admit(self, account, positions, orders, deals, info, tick, bars, now):
        ctx = self.context
        frame = ctx.strategy.frame(bars, ctx.mt5, ctx.symbol, now)
        row = frame.iloc[-1]
        closed = frame.index[-1].to_pydatetime() + timedelta(minutes=15)
        bar = closed.isoformat()
        if ctx.journal.get("safety_halt"):
            raise ValueError("safety_halt")
        baseline = ctx.broker._baseline(account, positions, deals, now)
        if positions or orders:
            raise ValueError("foreign_exposure")
        if ctx.journal.get("last_bar") == bar:
            return {"status": "WAIT", "reason": "duplicate_bar"}
        if int(row.direction) not in ctx.strategy.allowed_sides:
            ctx.journal.put("last_bar", bar)
            return {"status": "WAIT", "reason": ctx.strategy.no_signal_reason, "bar": bar}
        direction = int(row.direction)
        order_type = ctx.mt5.ORDER_TYPE_BUY if direction == 1 else ctx.mt5.ORDER_TYPE_SELL
        if (
            ctx.strategy.max_daily_losses
            and ctx._daily_losses(deals, now) >= ctx.strategy.max_daily_losses
        ):
            ctx.journal.put("last_bar", bar)
            raise ValueError("max_daily_losses")
        if now < closed or now - closed > timedelta(seconds=90):
            ctx.journal.put("last_bar", bar)
            raise ValueError("entry_window_expired")
        first = ctx._first_quote(closed, now)
        if int(first.time_msc) > int((closed + timedelta(seconds=90)).timestamp() * 1000):
            raise ValueError("first_quote_late")
        cost, status = validate_policy(ctx.policy, fingerprint=ctx.fingerprint, now=now)
        if not cost:
            raise ValueError("cost_policy_" + status)
        if baseline - float(account.equity) >= baseline * ctx.strategy.daily_loss_limit:
            ctx.journal.put("last_bar", bar)
            raise ValueError("daily_loss_limit")
        entry = float(tick.ask if direction == 1 else tick.bid)
        risk_entry, sl, tp = ctx.strategy.levels(row, tick, info, cost, account)
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
            max_risk_cap_pct=ctx.strategy.risk_cap,
        )
        if not risk.is_valid:
            ctx.journal.put("last_bar", bar)
            raise ValueError("risk_cap_or_volume")
        profit = ctx.mt5.order_calc_profit(order_type, ctx.symbol, 0.01, risk_entry, sl)
        commission = 0.01 * float(cost["commission_per_lot"])
        risk_amount = (
            -float(profit) + allowance * 0.01 * info.trade_contract_size + commission
            if profit is not None
            else None
        )
        if (
            risk_amount is None
            or not _finite(risk_amount, positive=True)
            or risk_amount > account.equity * ctx.strategy.risk_cap
        ):
            raise ValueError("broker_risk_invalid")
        distance = max(info.trade_stops_level, info.trade_freeze_level) * info.point
        executable = float(tick.bid if direction == 1 else tick.ask)
        if direction * (executable - sl) <= distance or direction * (tp - executable) <= distance:
            raise ValueError("stop_geometry")
        margin = ctx.mt5.order_calc_margin(order_type, ctx.symbol, 0.01, entry)
        if margin is None or not _finite(margin) or margin < 0 or margin > account.margin_free:
            raise ValueError("insufficient_margin")
        filling = resolve_type_filling(int(info.filling_mode), for_pending=False, mt5_mod=ctx.mt5)
        if int(info.filling_mode) & 1:
            filling = ctx.mt5.ORDER_FILLING_FOK
        comment = ctx.strategy.prefix + format(int(closed.timestamp()), "x")
        request = dict(
            action=ctx.mt5.TRADE_ACTION_DEAL,
            symbol=ctx.symbol,
            volume=0.01,
            type=order_type,
            price=entry,
            sl=sl,
            tp=tp,
            deviation=max(0, int(allowance / info.point)),
            magic=ctx.strategy.magic,
            comment=comment,
            type_time=ctx.mt5.ORDER_TIME_GTC,
            type_filling=filling,
        )
        check = ctx.mt5.order_check(request)
        if check is None or int(check.retcode) != 0:
            ctx.journal.put("last_bar", bar)
            raise ValueError("order_check_rejected")
        if not ctx.execute:
            return {
                "status": "SHADOW_ADMIT",
                "bar": bar,
                "request": request,
                "risk": risk_amount,
                "day_start": baseline,
            }
        fresh_account = ctx.broker.identity()
        send_now = now + timedelta(seconds=time.monotonic() - ctx._started)
        fresh_tick = ctx.broker._quote(send_now)
        if send_now - closed > timedelta(seconds=90):
            raise ValueError("entry_window_expired")
        if abs(float(fresh_tick.ask if direction == 1 else fresh_tick.bid) - entry) > allowance:
            raise ValueError("quote_changed_before_send")
        if (
            risk_amount > float(fresh_account.equity) * ctx.strategy.risk_cap
            or baseline - float(fresh_account.equity) >= baseline * ctx.strategy.daily_loss_limit
        ):
            raise ValueError("capital_changed_before_send")
        current_positions, current_orders = ctx.broker._exposure()
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
        thesis = getattr(ctx.strategy, "entry_thesis", None)
        if callable(thesis):
            note = thesis()
            if note:
                active["thesis"] = note
        ctx.journal.put("active", active)  # Commit BEFORE irreversible API.
        ctx.journal.put("last_bar", bar)
        try:
            sent = ctx.mt5.order_send(request)
        except Exception:
            sent = None
        if sent is not None and int(sent.retcode) not in (10009, 10010, 10008, 10012, 10031):
            ctx.journal.put("active", None)
            return {"status": "REJECTED", "retcode": int(sent.retcode)}
        active["status"] = "UNKNOWN"
        ctx.journal.put("active", active)
        positions, _ = ctx.broker._exposure()
        return ctx._reconcile(
            positions, ctx.broker._history(now + timedelta(minutes=1)), tick, info, closed, now
        )

    def _daily_losses(self, deals, now):
        """Route exits through owned opening position IDs, never closing magic."""
        ctx = self.context
        ids = {
            int(d.position_id)
            for d in deals
            if int(d.entry) == 0
            and int(d.type) in (0, 1)
            and int(d.magic) == ctx.strategy.magic
            and str(d.comment).startswith(ctx.strategy.prefix)
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
        ctx = self.context
        rows = ctx.mt5.copy_ticks_range(ctx.symbol, closed, now, ctx.mt5.COPY_TICKS_ALL)
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
