from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class Direction(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderIntentType(Enum):
    NO_ACTION = "NO_ACTION"
    PLACE_LIMIT = "PLACE_LIMIT"
    CANCEL_LIMIT = "CANCEL_LIMIT"
    MOVE_SL_TO_BE = "MOVE_SL_TO_BE"
    PARTIAL_CLOSE = "PARTIAL_CLOSE"
    CLOSE_MARKET = "CLOSE_MARKET"


@dataclass(frozen=True)
class LiquidityLevels:
    asian_high: float
    asian_low: float
    pdh: Optional[float]
    pdl: Optional[float]
    date_str: str
    london_high: Optional[float] = None
    london_low: Optional[float] = None


@dataclass(frozen=True)
class SetupSignal:
    direction: Direction
    sweep_price: float
    sweep_wick: float
    mss_price: float
    entry_price: float
    sl_price: float
    tp_price: float
    sl_distance: float
    risk_r: float
    fvg_high: float
    fvg_low: float
    reason: str
    timestamp: datetime
    setup_id: Optional[str] = None


@dataclass(frozen=True)
class OrderIntent:
    intent_type: OrderIntentType
    direction: Optional[Direction] = None
    limit_price: Optional[float] = None
    sl_price: Optional[float] = None
    tp_price: Optional[float] = None
    lot_size: Optional[float] = None
    reason: str = ""
    expire_bars: int = 4
    order_id: Optional[str] = None
    ticket: Optional[int] = None


@dataclass
class Position:
    direction: Direction
    entry_price: float
    sl_price: float
    tp_price: float
    lot_size: float
    open_time: datetime
    initial_sl_distance: float
    be_moved: bool = False
    fill_alerted: bool = False
    be_alerted: bool = False
    partial_closed: bool = False
    partial_alerted: bool = False
    remaining_ratio: float = 1.0
    bars_held: int = 0


@dataclass
class AccountState:
    balance: float
    equity: float
    open_position: Optional[Position] = None
    pending_order: Optional[OrderIntent] = None
    pending_bars_held: int = 0
    daily_loss_count: int = 0
    last_loss_time: Optional[datetime] = None
    current_utc_date: Optional[str] = None
    news_events: List[Dict[str, Any]] = field(default_factory=list)
    # Whole-account risk sees all activity; bot expectancy uses bot_* only.
    bot_realized_pnl: float = 0.0
    manual_realized_pnl: float = 0.0
    cash_flow_total: float = 0.0


def apply_account_pnl_event(
    account: AccountState,
    *,
    amount: float,
    source: str,
) -> None:
    """
    Record PnL/cash without mixing bot expectancy and foreign activity.

    source:
      - bot: strategy-owned closed trade
      - manual: human/other system trade (affects equity gates, not bot expectancy)
      - cash_flow: deposit/withdrawal/credit (disclosure only; does not count as bot edge)
    """
    amount = float(amount)
    if source == "bot":
        account.bot_realized_pnl += amount
        account.balance += amount
        account.equity += amount
    elif source == "manual":
        account.manual_realized_pnl += amount
        account.balance += amount
        account.equity += amount
    elif source == "cash_flow":
        account.cash_flow_total += amount
        account.balance += amount
        account.equity += amount
    else:
        raise ValueError(f"unknown pnl source: {source}")
