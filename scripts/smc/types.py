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
    pdh: float
    pdl: float
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


@dataclass(frozen=True)
class OrderIntent:
    intent_type: OrderIntentType
    direction: Optional[Direction] = None
    limit_price: Optional[float] = None
    sl_price: Optional[float] = None
    tp_price: Optional[float] = None
    lot_size: Optional[float] = None
    reason: str = ""
    expire_bars: int = 3
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
