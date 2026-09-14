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


class StrategyOrchestrator:
    """
    Stateful Strategy Orchestrator: Manages position and order lifecycles,
    Order TTL expiration, Breakeven at 1.0R, Rollover flat, News rules, and Circuit Breaker.
    """

    def __init__(
        self,
        max_daily_losses: int = 2,
        cooldown_minutes: int = 30,
        ttl_expire_bars: int = 3,
        rollover_hour_utc: int = 20,
        rollover_minute_utc: int = 55,
        max_sl_cap: float = 25.00,
        partial_tp_enabled: bool = False,
        partial_tp_r: float = 1.2,
        partial_tp_ratio: float = 0.5,
        be_trigger_r: float = 1.0,
        spread_buffer: float = 0.30,
        be_buffer: float = 0.10,
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

        # Check Stop Loss first (Conservative Financial Safety: SL takes priority over TP/BE if both hit)
        sl_hit = False
        if pos.direction == Direction.BUY:
            if float(bar["low"]) <= pos.sl_price:
                sl_hit = True
        else:  # SELL
            if float(bar["high"]) >= pos.sl_price:
                sl_hit = True

        if sl_hit:
            if not pos.be_moved:
                account.daily_loss_count += 1
                account.last_loss_time = bar_time
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

        # Check Full TP hits (Ask-calibrated on SELL)
        if pos.direction == Direction.BUY:
            if float(bar["high"]) >= pos.tp_price:
                account.open_position = None
        else:  # SELL
            if (float(bar["low"]) + self.spread_buffer) <= pos.tp_price:
                account.open_position = None

        return intents

    def on_bar(
        self,
        bar: Dict[str, Any],
        account: AccountState,
        setup_signal: Optional[SetupSignal] = None,
        current_spread: Optional[float] = None,
        max_spread: float = 0.35,
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
                if current_spread is not None and current_spread > max_spread:
                    # Spread blown out, skip fill on this bar
                    is_filled = False
                else:
                    # Open position
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

            # Not filled: Increment TTL held bars
            account.pending_bars_held += 1
            if account.pending_bars_held >= order.expire_bars:
                cancel_intent = OrderIntent(
                    intent_type=OrderIntentType.CANCEL_LIMIT,
                    direction=order.direction,
                    reason=f"Order TTL expired ({order.expire_bars} bars without fill)",
                )
                account.pending_order = None
                account.pending_bars_held = 0
                intents.append(cancel_intent)
                return intents

            return []

        # 4. Circuit Breaker & Cooldown Checks (ADR-011)
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
            lot_res = calculate_lot_size(
                balance=account.balance,
                entry_price=setup_signal.entry_price,
                sl_price=setup_signal.sweep_wick,
                max_sl_cap=self.max_sl_cap,
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
                )
                account.pending_order = new_order
                account.pending_bars_held = 0
                intents.append(new_order)

        return intents
