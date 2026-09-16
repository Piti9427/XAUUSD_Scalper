from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from scripts.smc.types import (
    Direction,
    OrderIntentType,
    OrderIntent,
    Position,
    AccountState,
    SetupSignal,
)
from scripts.smc.risk import calculate_lot_size
from scripts.smc.risk_halt import RiskHaltState
from scripts.smc.quotes import ohlc_dual_touch_flag, first_exit_from_ticks
from scripts.smc.setup_identity import SetupRegistry, make_setup_id


class StrategyOrchestrator:
    """
    Stateful Strategy Orchestrator: Manages position and order lifecycles,
    Order TTL expiration, Breakeven at 1.0R, Rollover flat, News rules, and Circuit Breaker.
    """

    def __init__(
        self,
        max_daily_losses: int = 2,
        cooldown_minutes: int = 30,
        ttl_expire_bars: int = 4,
        rollover_hour_utc: int = 20,
        rollover_minute_utc: int = 55,
        max_sl_cap: float = 25.00,
        partial_tp_enabled: bool = False,
        partial_tp_r: float = 1.2,
        partial_tp_ratio: float = 0.5,
        be_trigger_r: float = 1.0,
        spread_buffer: float = 0.30,
        be_buffer: float = 0.10,
        max_hold_bars: Optional[int] = None,
        bar_minutes: int = 5,
        setup_registry: Optional[SetupRegistry] = None,
        risk_pct: float = 0.005,
    ):
        self.max_daily_losses = max_daily_losses
        self.cooldown_minutes = cooldown_minutes
        self.ttl_expire_bars = ttl_expire_bars
        self.rollover_hour_utc = rollover_hour_utc
        self.rollover_minute_utc = rollover_minute_utc
        self.max_sl_cap = max_sl_cap
        self.partial_tp_enabled = partial_tp_enabled
        self.partial_tp_r = partial_tp_r
        self.partial_tp_ratio = partial_tp_ratio
        self.be_trigger_r = be_trigger_r
        self.spread_buffer = spread_buffer
        self.be_buffer = be_buffer
        self.max_hold_bars = max_hold_bars
        self.bar_minutes = bar_minutes
        self.setup_registry = setup_registry if setup_registry is not None else SetupRegistry()
        self.risk_pct = risk_pct

    def _evaluate_open_position(
        self,
        account: AccountState,
        bar: Dict[str, Any],
        bar_time: datetime,
    ) -> List[OrderIntent]:
        intents: List[OrderIntent] = []
        pos = account.open_position
        if pos is None:
            return intents

        pos.bars_held += 1

        # Rollover Flat Check (ADR-007: Flat before 21:00 UTC)
        if (bar_time.hour > self.rollover_hour_utc) or (
            bar_time.hour == self.rollover_hour_utc
            and bar_time.minute >= self.rollover_minute_utc
        ):
            intents.append(
                OrderIntent(
                    intent_type=OrderIntentType.CLOSE_MARKET,
                    direction=pos.direction,
                    reason="Rollover Flat Rule: Closing all positions before 21:00 UTC",
                )
            )
            account.open_position = None
            return intents

        # SL / TP touch detection. Dual OHLC touch without tick order is AMBIGUOUS
        # (U9 / B17) — never invent a favorable SL-or-TP path.
        if pos.direction == Direction.BUY:
            sl_hit = float(bar["low"]) <= pos.sl_price
            tp_hit = float(bar["high"]) >= pos.tp_price
        else:  # SELL
            sl_hit = float(bar["high"]) >= pos.sl_price
            tp_hit = (float(bar["low"]) + self.spread_buffer) <= pos.tp_price

        has_tick_order = bool(bar.get("has_tick_order", False))
        tick_first_exit = bar.get("tick_first_exit")
        if tick_first_exit is None and has_tick_order and bar.get("ticks"):
            tick_first_exit = first_exit_from_ticks(
                direction=pos.direction.value,
                sl_price=pos.sl_price,
                tp_price=pos.tp_price,
                ticks=bar["ticks"],
            )
        exit_flag = ohlc_dual_touch_flag(
            sl_touched=sl_hit,
            tp_touched=tp_hit,
            has_tick_order=has_tick_order,
            tick_first_exit=tick_first_exit,
        )
        if exit_flag == "AMBIGUOUS":
            intents.append(
                OrderIntent(
                    intent_type=OrderIntentType.CLOSE_MARKET,
                    direction=pos.direction,
                    reason=(
                        "AMBIGUOUS OHLC dual touch: SL and TP both touched "
                        "without tick-order evidence"
                    ),
                )
            )
            account.open_position = None
            return intents

        if exit_flag == "SL":
            if not pos.be_moved:
                account.daily_loss_count += 1
                account.last_loss_time = bar_time
            account.open_position = None
            return intents

        # Dual-touch resolved to TP by ticks: close immediately (no BE invention).
        if exit_flag == "TP" and sl_hit:
            account.open_position = None
            return intents

        # Foundation TIME_EXIT after protective levels checked (scenario 16/19)
        if self.max_hold_bars is not None and pos.bars_held >= self.max_hold_bars:
            intents.append(
                OrderIntent(
                    intent_type=OrderIntentType.CLOSE_MARKET,
                    direction=pos.direction,
                    reason=f"TIME_EXIT after {pos.bars_held} bars (max_hold_bars={self.max_hold_bars})",
                )
            )
            account.open_position = None
            return intents

        # Partial Take Profit Check (Gold Profit Maximizer)
        if self.partial_tp_enabled and not pos.partial_closed:
            partial_hit = False
            if pos.direction == Direction.BUY:
                if float(bar["high"]) >= (pos.entry_price + pos.initial_sl_distance * self.partial_tp_r):
                    partial_hit = True
            else:  # SELL
                if (float(bar["low"]) + self.spread_buffer) <= (pos.entry_price - pos.initial_sl_distance * self.partial_tp_r):
                    partial_hit = True

            if partial_hit:
                pos.partial_closed = True
                partial_lot = round(pos.lot_size * self.partial_tp_ratio, 2)
                pos.lot_size = max(0.01, round(pos.lot_size - partial_lot, 2))
                pos.remaining_ratio = 1.0 - self.partial_tp_ratio
                intents.append(
                    OrderIntent(
                        intent_type=OrderIntentType.PARTIAL_CLOSE,
                        direction=pos.direction,
                        lot_size=partial_lot,
                        reason=f"Partial TP hit (+{self.partial_tp_r}R): Closed {partial_lot} lots",
                    )
                )
                # Automatically lock in breakeven with be_buffer (ADR-018/ADR-024)
                if not pos.be_moved:
                    pos.be_moved = True
                    be_price = round(pos.entry_price + (self.be_buffer if pos.direction == Direction.BUY else -self.be_buffer), 2)
                    pos.sl_price = be_price
                    intents.append(
                        OrderIntent(
                            intent_type=OrderIntentType.MOVE_SL_TO_BE,
                            direction=pos.direction,
                            limit_price=be_price,
                            sl_price=be_price,
                            reason=f"Partial TP reached: SL moved to Breakeven ({be_price})",
                        )
                    )

        # Breakeven Relocation Check (Move SL to BE at be_trigger_r if partial TP disabled or didn't move it)
        if not pos.be_moved:
            if pos.direction == Direction.BUY:
                if float(bar["high"]) >= (pos.entry_price + pos.initial_sl_distance * self.be_trigger_r):
                    pos.be_moved = True
                    be_price = round(pos.entry_price + self.be_buffer, 2)
                    pos.sl_price = be_price
                    intents.append(
                        OrderIntent(
                            intent_type=OrderIntentType.MOVE_SL_TO_BE,
                            direction=Direction.BUY,
                            limit_price=be_price,
                            sl_price=be_price,
                            reason=f"{self.be_trigger_r}R profit reached: SL moved to Breakeven ({be_price})",
                        )
                    )
            else:  # SELL
                if (float(bar["low"]) + self.spread_buffer) <= (pos.entry_price - pos.initial_sl_distance * self.be_trigger_r):
                    pos.be_moved = True
                    be_price = round(pos.entry_price - self.be_buffer, 2)
                    pos.sl_price = be_price
                    intents.append(
                        OrderIntent(
                            intent_type=OrderIntentType.MOVE_SL_TO_BE,
                            direction=Direction.SELL,
                            limit_price=be_price,
                            sl_price=be_price,
                            reason=f"{self.be_trigger_r}R profit reached: SL moved to Breakeven ({be_price})",
                        )
                    )

        # Full TP (OHLC TP-only path; dual-touch TP already returned above)
        if exit_flag == "TP":
            account.open_position = None

        return intents

    def on_clock(
        self,
        account: AccountState,
        now: datetime,
    ) -> List[OrderIntent]:
        """
        Wall-clock TIME_EXIT when M5 feed stalls (foundation scenario 19).

        Does not invent a broker close confirmation — emits CLOSE_MARKET intent only.
        Callers must wait for adapter evidence before notifying "closed".
        """
        pos = account.open_position
        if pos is None or self.max_hold_bars is None:
            return []
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)
        open_time = pos.open_time
        if open_time.tzinfo is None:
            open_time = open_time.replace(tzinfo=timezone.utc)
        else:
            open_time = open_time.astimezone(timezone.utc)
        max_hold = timedelta(minutes=self.max_hold_bars * self.bar_minutes)
        if now - open_time < max_hold:
            return []
        intent = OrderIntent(
            intent_type=OrderIntentType.CLOSE_MARKET,
            direction=pos.direction,
            reason=(
                f"TIME_EXIT wall-clock after {self.max_hold_bars}*{self.bar_minutes}m "
                f"without requiring a new bar"
            ),
        )
        # Keep local position until broker confirms; do not clear here.
        return [intent]

    def on_bar(
        self,
        bar: Dict[str, Any],
        account: AccountState,
        setup_signal: Optional[SetupSignal] = None,
        current_spread: Optional[float] = None,
        max_spread: float = 0.35,
        risk_halt: Optional[RiskHaltState] = None,
        news_cancel_pending: bool = False,
        news_cancel_reason: str = "",
    ) -> List[OrderIntent]:
        intents: List[OrderIntent] = []

        bar_time = bar["time"]
        if bar_time.tzinfo is None:
            bar_time = bar_time.replace(tzinfo=timezone.utc)
        else:
            bar_time = bar_time.astimezone(timezone.utc)

        # 1. Check Date Rollover for Circuit Breaker
        bar_date_str = bar_time.date().isoformat()
        if account.current_utc_date != bar_date_str:
            account.current_utc_date = bar_date_str
            account.daily_loss_count = 0

        # 2. Check Open Position Lifecycle
        if account.open_position is not None:
            return self._evaluate_open_position(account, bar, bar_time)

        # 3. Check Pending Order Lifecycle
        if account.pending_order is not None:
            order = account.pending_order
            is_filled = False

            if order.direction == Direction.BUY:
                if float(bar["low"]) <= order.limit_price:
                    is_filled = True
            else:  # SELL
                if float(bar["high"]) >= order.limit_price:
                    is_filled = True

            if is_filled:
                # Scenario 15: once pending is accepted, a later spread blowout must not
                # invent a no-fill when price already touched the limit. Spread gates
                # only new risk admission (below), not authoritative broker fills.
                sl_dist = abs(order.limit_price - order.sl_price)
                account.open_position = Position(
                    direction=order.direction,
                    entry_price=order.limit_price,
                    sl_price=order.sl_price,
                    tp_price=order.tp_price,
                    lot_size=order.lot_size or 0.01,
                    open_time=bar_time,
                    initial_sl_distance=sl_dist,
                    be_moved=False,
                )
                account.pending_order = None
                account.pending_bars_held = 0
                # Immediate SL/TP evaluation on fill bar
                return self._evaluate_open_position(account, bar, bar_time)

            if news_cancel_pending:
                cancel_intent = OrderIntent(
                    intent_type=OrderIntentType.CANCEL_LIMIT,
                    direction=order.direction,
                    reason=f"News pending cancel: {news_cancel_reason or 'news_gate'}",
                    order_id=order.order_id,
                )
                self.setup_registry.mark_terminal(
                    order.order_id, news_cancel_reason or "news_cancel"
                )
                account.pending_order = None
                account.pending_bars_held = 0
                intents.append(cancel_intent)
                return intents

            # Not filled: Increment TTL held bars
            account.pending_bars_held += 1
            if account.pending_bars_held >= order.expire_bars:
                cancel_intent = OrderIntent(
                    intent_type=OrderIntentType.CANCEL_LIMIT,
                    direction=order.direction,
                    reason=f"Order TTL expired ({order.expire_bars} bars without fill)",
                    order_id=order.order_id,
                )
                self.setup_registry.mark_terminal(order.order_id, "ttl_expired")
                account.pending_order = None
                account.pending_bars_held = 0
                intents.append(cancel_intent)
                return intents

            return []

        # 4. Circuit Breaker & Cooldown Checks (ADR-011 / foundation risk halt)
        if risk_halt is not None and risk_halt.halted:
            return []

        if account.daily_loss_count >= self.max_daily_losses:
            return []

        if account.last_loss_time is not None:
            time_since_loss = (bar_time - account.last_loss_time).total_seconds()
            if time_since_loss < (self.cooldown_minutes * 60):
                return []

        # 5. Evaluate New Setup Signal if Provided
        if setup_signal is not None:
            if current_spread is not None and current_spread > max_spread:
                return []
            setup_id = setup_signal.setup_id
            if not setup_id:
                ts = setup_signal.timestamp
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                else:
                    ts = ts.astimezone(timezone.utc)
                setup_id = make_setup_id(
                    direction=setup_signal.direction.value,
                    entry_price=setup_signal.entry_price,
                    sl_price=setup_signal.sl_price,
                    tp_price=setup_signal.tp_price,
                    sweep_wick=setup_signal.sweep_wick,
                    available_at=ts.isoformat(),
                )
            allowed, _admit_reason = self.setup_registry.admit(setup_id)
            if not allowed:
                return []
            lot_res = calculate_lot_size(
                balance=account.balance,
                entry_price=setup_signal.entry_price,
                sl_price=setup_signal.sweep_wick,
                max_sl_cap=self.max_sl_cap,
                risk_pct=self.risk_pct,
            )
            if lot_res.is_valid and lot_res.lot_size > 0:
                new_order = OrderIntent(
                    intent_type=OrderIntentType.PLACE_LIMIT,
                    direction=setup_signal.direction,
                    limit_price=setup_signal.entry_price,
                    sl_price=setup_signal.sl_price,
                    tp_price=setup_signal.tp_price,
                    lot_size=lot_res.lot_size,
                    reason=setup_signal.reason,
                    expire_bars=self.ttl_expire_bars,
                    order_id=setup_id,
                )
                account.pending_order = new_order
                account.pending_bars_held = 0
                intents.append(new_order)

        return intents
