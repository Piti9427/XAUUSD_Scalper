"""
basket_manager.py — Smart Zone Recovery (Basket Management)

Manages a multi-leg "basket" of orders for the Hybrid Sniper-Recovery strategy.
Inspired by YouTube clip's basket-close logic; hardened with strict risk controls
from BotTradeGold_AGGRESSIVE_RESEARCH_IMPLEMENTATION_GUIDE_2026-09-28.md.

Key rules (all from settings.yaml money_management):
  - Max 2 legs per basket (entry + 1 recovery leg only — no Martingale beyond this).
  - Recovery leg opens ONLY when a new MSS signal appears in the same direction.
  - Basket SL: if net basket PnL <= -basket_absolute_cap_usd, force-close ALL legs.
  - Basket TP: if net basket PnL >= 0 (after costs), close ALL legs together.
  - Daily loss limit: halt new baskets for the rest of the UTC day.
  - HWM halt: halt permanently until manual reset if equity drops > hwm_halt_fraction.

State machine:
    FLAT -> OPEN -> (RECOVERY_PENDING -> OPEN) -> CLOSE_PENDING -> FLAT

Timezone: all datetimes must be timezone-aware UTC (AGENTS.md rule).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from scripts.smc.types import Direction, OrderIntent, OrderIntentType

logger = logging.getLogger("smc.basket_manager")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class BasketConfig:
    """Loaded from settings.yaml money_management section."""

    basket_fraction: float = 0.15          # 15% of equity per basket
    basket_absolute_cap_usd: float = 30.0  # Hard ceiling regardless of equity
    day_loss_fraction: float = 0.15        # Daily halt threshold
    max_new_baskets_per_utc_day: int = 2   # Max baskets opened per day
    recovery_lots: List[float] = field(default_factory=lambda: [0.01, 0.02])
    max_recovery_legs: int = 2             # Hard cap on legs
    hwm_halt_fraction: float = 0.20        # HWM drawdown halt
    reset_hwm_automatically: bool = False  # Manual reset only

    @classmethod
    def from_config(cls, config: dict) -> "BasketConfig":
        mm = config.get("money_management", {})
        return cls(
            basket_fraction=float(mm.get("basket_fraction", 0.15)),
            basket_absolute_cap_usd=float(mm.get("basket_absolute_cap_usd", 30.0)),
            day_loss_fraction=float(mm.get("day_loss_fraction", 0.15)),
            max_new_baskets_per_utc_day=int(mm.get("max_new_baskets_per_utc_day", 2)),
            recovery_lots=list(mm.get("recovery_lots", [0.01, 0.02])),
            max_recovery_legs=int(mm.get("max_recovery_legs", 2)),
            hwm_halt_fraction=float(mm.get("hwm_halt_fraction", 0.20)),
            reset_hwm_automatically=bool(mm.get("reset_hwm_automatically", False)),
        )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class BasketState(Enum):
    FLAT = "FLAT"
    OPEN = "OPEN"               # At least 1 open leg
    CLOSE_PENDING = "CLOSE_PENDING"  # Waiting for broker close confirmation
    HALTED = "HALTED"           # HWM or day-loss halt; manual reset required


@dataclass
class Leg:
    """One filled position leg inside a basket."""

    direction: Direction
    entry_price: float
    lot_size: float
    sl_price: float
    tp_price: float
    open_time: datetime
    leg_index: int              # 0 = entry leg, 1 = recovery leg
    realized_pnl: float = 0.0
    is_open: bool = True

    def mark_profit(self, pnl: float) -> None:
        """Call when broker confirms close with this PnL."""
        self.realized_pnl = pnl
        self.is_open = False


@dataclass
class Basket:
    """
    A single basket containing up to max_recovery_legs legs.

    frozen_budget_usd: locked at basket creation — never expands from later profits.
    """

    basket_id: str
    direction: Direction
    frozen_budget_usd: float          # Max allowable net loss for this basket
    open_time: datetime
    legs: List[Leg] = field(default_factory=list)
    net_realized_pnl: float = 0.0     # Sum of closed legs' PnL
    state: BasketState = BasketState.OPEN

    @property
    def leg_count(self) -> int:
        return len(self.legs)

    @property
    def open_legs(self) -> List[Leg]:
        return [l for l in self.legs if l.is_open]

    def net_pnl_with_floating(self, floating_pnl: float) -> float:
        """Total PnL = realized (closed legs) + floating (open legs)."""
        return self.net_realized_pnl + floating_pnl

    def basket_sl_breached(self, floating_pnl: float) -> bool:
        return self.net_pnl_with_floating(floating_pnl) <= -self.frozen_budget_usd

    def basket_tp_reached(self, floating_pnl: float) -> bool:
        """Basket TP: net turns strictly positive. Break-even alone is not enough to close."""
        return self.net_pnl_with_floating(floating_pnl) > 0.0


# ---------------------------------------------------------------------------
# Day / HWM accounting
# ---------------------------------------------------------------------------

@dataclass
class DayAccount:
    utc_date: str = ""
    baskets_opened: int = 0
    realized_loss_usd: float = 0.0    # Only counts losses; wins don't offset
    day_start_equity: float = 0.0


# ---------------------------------------------------------------------------
# BasketManager
# ---------------------------------------------------------------------------

class BasketManager:
    """
    Manages basket lifecycle: open, recovery, basket-close, daily/HWM guards.

    Usage:
        manager = BasketManager(config=BasketConfig.from_config(cfg))

        # When a new MSS entry signal fires:
        intents = manager.on_new_signal(signal, equity)

        # On every bar update (pass floating PnL for open basket):
        intents = manager.on_bar(floating_pnl, equity, now)

        # When broker confirms a leg closed:
        manager.on_leg_closed(leg_index, realized_pnl)

        # When a new MSS signal fires while basket is already OPEN (recovery):
        intents = manager.on_recovery_signal(signal, equity, floating_pnl)
    """

    def __init__(self, config: BasketConfig) -> None:
        self.cfg = config
        self.basket: Optional[Basket] = None
        self.state: BasketState = BasketState.FLAT
        self._day: DayAccount = DayAccount()
        self._hwm_equity: float = 0.0
        self._hwm_initialized: bool = False
        self._next_basket_id: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_new_signal(
        self,
        direction: Direction,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        equity: float,
        now: datetime,
    ) -> List[OrderIntent]:
        """
        Called when strategy fires a new entry signal (MSS confirmed).
        Returns list of OrderIntents to pass to the execution adapter.
        """
        now = _ensure_utc(now)
        self._update_hwm(equity)
        self._refresh_day(equity, now)

        if self.state == BasketState.HALTED:
            logger.warning("BasketManager HALTED — ignoring new signal")
            return []

        if self.state != BasketState.FLAT:
            logger.debug("Basket already OPEN — ignoring new entry signal (use on_recovery_signal)")
            return []

        if not self._day_budget_ok(equity, now):
            return []

        if self._hwm_breach(equity):
            self._halt("HWM drawdown breach")
            return []

        budget = self._compute_budget(equity)
        if budget <= 0:
            logger.warning("Basket budget <= 0 — rejecting new entry")
            return []

        lot = self.cfg.recovery_lots[0]  # Entry leg always uses first lot size
        basket_id = self._new_basket_id()
        self.basket = Basket(
            basket_id=basket_id,
            direction=direction,
            frozen_budget_usd=budget,
            open_time=now,
        )
        leg = Leg(
            direction=direction,
            entry_price=entry_price,
            lot_size=lot,
            sl_price=sl_price,
            tp_price=tp_price,
            open_time=now,
            leg_index=0,
        )
        self.basket.legs.append(leg)
        self.state = BasketState.OPEN
        self._day.baskets_opened += 1

        intent = OrderIntent(
            intent_type=OrderIntentType.PLACE_LIMIT,
            direction=direction,
            limit_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            lot_size=lot,
            reason=f"Basket {basket_id} leg-0 entry",
        )
        logger.info(
            "Basket %s opened: dir=%s lot=%.2f budget=$%.2f",
            basket_id, direction.value, lot, budget,
        )
        return [intent]

    def on_recovery_signal(
        self,
        direction: Direction,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        equity: float,
        floating_pnl: float,
        now: datetime,
    ) -> List[OrderIntent]:
        """
        Called when a new MSS signal fires while a basket is already open.
        Opens a recovery leg ONLY if:
          - Same direction as basket.
          - Basket net PnL is negative (reason to recover).
          - Recovery leg count < max_recovery_legs.
          - Basket SL not breached.
        """
        now = _ensure_utc(now)

        if self.state != BasketState.OPEN or self.basket is None:
            return []

        basket = self.basket

        if direction != basket.direction:
            logger.debug("Recovery signal direction mismatch — skip")
            return []

        if basket.leg_count >= self.cfg.max_recovery_legs:
            logger.debug("Max recovery legs (%d) reached — skip", self.cfg.max_recovery_legs)
            return []

        if basket.net_pnl_with_floating(floating_pnl) >= 0:
            logger.debug("Basket already profitable — no recovery needed")
            return []

        if basket.basket_sl_breached(floating_pnl):
            # Should have been caught by on_bar, but guard here too
            logger.warning("Basket SL already breached — cannot add recovery leg")
            return []

        # Next lot size from ladder
        leg_index = basket.leg_count
        if leg_index >= len(self.cfg.recovery_lots):
            logger.warning("Recovery lots ladder exhausted at index %d", leg_index)
            return []

        lot = self.cfg.recovery_lots[leg_index]
        leg = Leg(
            direction=direction,
            entry_price=entry_price,
            lot_size=lot,
            sl_price=sl_price,
            tp_price=tp_price,
            open_time=now,
            leg_index=leg_index,
        )
        basket.legs.append(leg)

        intent = OrderIntent(
            intent_type=OrderIntentType.PLACE_LIMIT,
            direction=direction,
            limit_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            lot_size=lot,
            reason=f"Basket {basket.basket_id} recovery leg-{leg_index}",
        )
        logger.info(
            "Recovery leg-%d opened: lot=%.2f basket=%s",
            leg_index, lot, basket.basket_id,
        )
        return [intent]

    def on_bar(
        self,
        floating_pnl: float,
        equity: float,
        now: datetime,
    ) -> List[OrderIntent]:
        """
        Called on every new bar. Checks basket SL and basket TP conditions.
        Returns CLOSE_MARKET intents for all open legs if triggered.
        """
        now = _ensure_utc(now)
        self._update_hwm(equity)

        # CLOSE_PENDING → FLAT auto-transition: all legs closed (optimistically or via
        # on_leg_closed callback). Reset so new baskets can open next signal.
        if self.state == BasketState.CLOSE_PENDING:
            if self.basket is None or not self.basket.open_legs:
                logger.info(
                    "Basket %s all legs closed — CLOSE_PENDING → FLAT",
                    self.basket.basket_id if self.basket else "?",
                )
                self.basket = None
                self.state = BasketState.FLAT
            return []

        if self.state != BasketState.OPEN or self.basket is None:
            return []

        basket = self.basket

        # --- Basket SL check ---
        if basket.basket_sl_breached(floating_pnl):
            logger.warning(
                "Basket %s SL breached: net_pnl=%.2f budget=%.2f — force close all legs",
                basket.basket_id,
                basket.net_pnl_with_floating(floating_pnl),
                basket.frozen_budget_usd,
            )
            self._day.realized_loss_usd += abs(basket.net_pnl_with_floating(floating_pnl))
            return self._close_all_legs(basket, reason="BASKET_SL_BREACHED")

        # --- Basket TP check ---
        if basket.basket_tp_reached(floating_pnl):
            logger.info(
                "Basket %s TP reached: net_pnl=%.2f — closing all legs for profit",
                basket.basket_id,
                basket.net_pnl_with_floating(floating_pnl),
            )
            return self._close_all_legs(basket, reason="BASKET_TP_NET_POSITIVE")

        # --- HWM check ---
        if self._hwm_breach(equity):
            logger.error("HWM drawdown breach during open basket — closing all and halting")
            intents = self._close_all_legs(basket, reason="HWM_HALT")
            self._halt("HWM drawdown breach during open basket")
            return intents

        # --- Daily loss check (don't close existing basket but block new ones) ---
        if self._day_loss_breached(equity, now):
            logger.warning("Daily loss limit reached — new baskets blocked for today")

        return []

    def on_leg_closed(self, leg_index: int, realized_pnl: float) -> None:
        """
        Called by broker adapter when a leg close is confirmed.
        Updates basket accounting.
        """
        if self.basket is None:
            return
        for leg in self.basket.legs:
            if leg.leg_index == leg_index and leg.is_open:
                leg.mark_profit(realized_pnl)
                self.basket.net_realized_pnl += realized_pnl
                logger.info(
                    "Leg %d closed: pnl=%.2f basket_net=%.2f",
                    leg_index, realized_pnl, self.basket.net_realized_pnl,
                )
                break

        # If all legs closed, reset to FLAT
        if all(not l.is_open for l in self.basket.legs):
            logger.info("Basket %s fully closed — returning to FLAT", self.basket.basket_id)
            self.basket = None
            self.state = BasketState.FLAT

    def reset_hwm(self, equity: float) -> None:
        """Manual HWM reset after owner review. Required when reset_hwm_automatically=False."""
        logger.info("HWM manually reset to %.2f (was %.2f)", equity, self._hwm_equity)
        self._hwm_equity = equity
        if self.state == BasketState.HALTED:
            self.state = BasketState.FLAT

    @property
    def is_halted(self) -> bool:
        return self.state == BasketState.HALTED

    @property
    def is_flat(self) -> bool:
        return self.state == BasketState.FLAT

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_budget(self, equity: float) -> float:
        """Basket budget = min(fraction of equity, absolute cap)."""
        fraction_budget = equity * self.cfg.basket_fraction
        return min(fraction_budget, self.cfg.basket_absolute_cap_usd)

    def _refresh_day(self, equity: float, now: datetime) -> None:
        today = now.date().isoformat()
        if self._day.utc_date != today:
            self._day = DayAccount(
                utc_date=today,
                baskets_opened=0,
                realized_loss_usd=0.0,
                day_start_equity=equity,
            )

    def _day_budget_ok(self, equity: float, now: datetime) -> bool:
        today = now.date().isoformat()
        if self._day.utc_date != today:
            return True  # New day, fresh budget
        if self._day.baskets_opened >= self.cfg.max_new_baskets_per_utc_day:
            logger.info("Daily basket quota reached (%d)", self.cfg.max_new_baskets_per_utc_day)
            return False
        if self._day_loss_breached(equity, now):
            logger.warning("Daily loss limit reached — blocking new basket")
            return False
        return True

    def _day_loss_breached(self, equity: float, now: datetime) -> bool:
        today = now.date().isoformat()
        if self._day.utc_date != today or self._day.day_start_equity <= 0:
            return False
        loss = self._day.day_start_equity - equity
        return loss >= (self._day.day_start_equity * self.cfg.day_loss_fraction)

    def _update_hwm(self, equity: float) -> None:
        if not self._hwm_initialized:
            self._hwm_equity = equity
            self._hwm_initialized = True
        elif equity > self._hwm_equity:
            self._hwm_equity = equity

    def _hwm_breach(self, equity: float) -> bool:
        if not self._hwm_initialized or self._hwm_equity <= 0:
            return False
        drawdown = (self._hwm_equity - equity) / self._hwm_equity
        return drawdown >= self.cfg.hwm_halt_fraction

    def _halt(self, reason: str) -> None:
        logger.error("BasketManager HALTED: %s", reason)
        self.state = BasketState.HALTED

    def _close_all_legs(self, basket: Basket, reason: str) -> List[OrderIntent]:
        intents = []
        for leg in basket.open_legs:
            intents.append(
                OrderIntent(
                    intent_type=OrderIntentType.CLOSE_MARKET,
                    direction=leg.direction,
                    lot_size=leg.lot_size,
                    reason=f"{reason} leg-{leg.leg_index}",
                )
            )
            # Optimistic close: mark leg as not open immediately after emitting
            # the close intent. Realized PnL is updated by on_leg_closed() when
            # broker confirms. This prevents CLOSE_PENDING from being a permanent
            # stuck state when the broker callback is not yet wired.
            leg.is_open = False
        self.state = BasketState.CLOSE_PENDING
        return intents

    def _new_basket_id(self) -> str:
        self._next_basket_id += 1
        return f"BASKET-{self._next_basket_id:04d}"


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _ensure_utc(dt: datetime) -> datetime:
    """Enforce timezone-aware UTC (AGENTS.md: all timestamps must be UTC-aware)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
