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
    ):
        self.max_daily_losses = max_daily_losses
        self.cooldown_minutes = cooldown_minutes
        self.ttl_expire_bars = ttl_expire_bars
        self.rollover_hour_utc = rollover_hour_utc
        self.rollover_minute_utc = rollover_minute_utc

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
            pos = account.open_position

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

            # Breakeven Relocation Check (ADR-008: Move SL to BE at +1.0R)
            if not pos.be_moved:
                if pos.direction == Direction.BUY:
                    if float(bar["high"]) >= (pos.entry_price + pos.initial_sl_distance):
                        pos.be_moved = True
                        pos.sl_price = pos.entry_price
                        intents.append(
                            OrderIntent(
                                intent_type=OrderIntentType.MOVE_SL_TO_BE,
                                direction=Direction.BUY,
                                limit_price=pos.entry_price,
                                sl_price=pos.entry_price,
                                reason="1.0R profit reached: SL moved to Breakeven",
                            )
                        )
                else:  # SELL
                    if float(bar["low"]) <= (pos.entry_price - pos.initial_sl_distance):
                        pos.be_moved = True
                        pos.sl_price = pos.entry_price
                        intents.append(
                            OrderIntent(
                                intent_type=OrderIntentType.MOVE_SL_TO_BE,
                                direction=Direction.SELL,
                                limit_price=pos.entry_price,
                                sl_price=pos.entry_price,
                                reason="1.0R profit reached: SL moved to Breakeven",
                            )
                        )

            # Check SL/TP hits
            if pos.direction == Direction.BUY:
                if float(bar["low"]) <= pos.sl_price:
                    # Stopped out
                    if not pos.be_moved:
                        account.daily_loss_count += 1
                        account.last_loss_time = bar_time
                    account.open_position = None
                elif float(bar["high"]) >= pos.tp_price:
                    # TP hit
                    account.open_position = None
            else:  # SELL
                if float(bar["high"]) >= pos.sl_price:
                    # Stopped out
                    if not pos.be_moved:
                        account.daily_loss_count += 1
                        account.last_loss_time = bar_time
                    account.open_position = None
                elif float(bar["low"]) <= pos.tp_price:
                    # TP hit
                    account.open_position = None

            return intents

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
                    return []

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
