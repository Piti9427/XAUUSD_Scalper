from dataclasses import dataclass
from enum import Enum
from typing import Tuple, List, Dict, Any, Optional
import pandas as pd
import numpy as np
from scripts.smc.types import Direction

RULE_VERSION_STRUCTURE = "s1-s4-mechanical-v1"


class StructureBias(Enum):
    UNKNOWN = "UNKNOWN"
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class StructureEventKind(Enum):
    NONE = "NONE"
    BOS = "BOS"
    CHOCH = "CHOCH"
    INTERNAL = "INTERNAL"


@dataclass(frozen=True)
class StructureEvent:
    kind: StructureEventKind
    broken_price: Optional[float] = None
    protected_price: Optional[float] = None


@dataclass(frozen=True)
class StructureState:
    bias: StructureBias
    protected_price: Optional[float] = None
    protected_index: Optional[int] = None
    last_broken_price: Optional[float] = None

    @classmethod
    def initial(cls) -> "StructureState":
        return cls(bias=StructureBias.UNKNOWN)


def _latest_opposite_pivot(
    opposite_pivots_between: List[Tuple[int, float]],
) -> Optional[Tuple[int, float]]:
    if not opposite_pivots_between:
        return None
    return max(opposite_pivots_between, key=lambda item: item[0])


def apply_close_break(
    state: StructureState,
    *,
    break_side: str,
    broken_swing_price: float,
    break_index: int,
    opposite_pivots_between: List[Tuple[int, float]],
) -> Tuple[StructureState, StructureEvent]:
    """
    Apply one closed-bar swing break under ADR-0027 / mechanical §3.5.

    opposite_pivots_between: confirmed opposite pivots with index in
    (broken_swing_index, break_index). Caller supplies the filtered list.
    """
    if state.last_broken_price is not None and broken_swing_price == state.last_broken_price:
        return state, StructureEvent(kind=StructureEventKind.NONE)

    opposite = _latest_opposite_pivot(opposite_pivots_between)

    if state.bias == StructureBias.UNKNOWN:
        if opposite is None:
            return state, StructureEvent(kind=StructureEventKind.NONE, broken_price=broken_swing_price)
        opp_index, opp_price = opposite
        new_bias = StructureBias.BULLISH if break_side == "above" else StructureBias.BEARISH
        nxt = StructureState(
            bias=new_bias,
            protected_price=opp_price,
            protected_index=opp_index,
            last_broken_price=broken_swing_price,
        )
        return nxt, StructureEvent(
            kind=StructureEventKind.BOS,
            broken_price=broken_swing_price,
            protected_price=opp_price,
        )

    is_continuation = (
        (state.bias == StructureBias.BULLISH and break_side == "above")
        or (state.bias == StructureBias.BEARISH and break_side == "below")
    )
    is_protected_break = (
        state.protected_price is not None
        and broken_swing_price == state.protected_price
        and (
            (state.bias == StructureBias.BULLISH and break_side == "below")
            or (state.bias == StructureBias.BEARISH and break_side == "above")
        )
    )

    if is_protected_break:
        if opposite is None:
            nxt = StructureState(
                bias=StructureBias.UNKNOWN,
                last_broken_price=broken_swing_price,
            )
            return nxt, StructureEvent(
                kind=StructureEventKind.CHOCH,
                broken_price=broken_swing_price,
            )
        opp_index, opp_price = opposite
        new_bias = StructureBias.BEARISH if state.bias == StructureBias.BULLISH else StructureBias.BULLISH
        nxt = StructureState(
            bias=new_bias,
            protected_price=opp_price,
            protected_index=opp_index,
            last_broken_price=broken_swing_price,
        )
        return nxt, StructureEvent(
            kind=StructureEventKind.CHOCH,
            broken_price=broken_swing_price,
            protected_price=opp_price,
        )

    if is_continuation:
        if opposite is None:
            return state, StructureEvent(kind=StructureEventKind.NONE, broken_price=broken_swing_price)
        opp_index, opp_price = opposite
        nxt = StructureState(
            bias=state.bias,
            protected_price=opp_price,
            protected_index=opp_index,
            last_broken_price=broken_swing_price,
        )
        return nxt, StructureEvent(
            kind=StructureEventKind.BOS,
            broken_price=broken_swing_price,
            protected_price=opp_price,
        )

    return state, StructureEvent(
        kind=StructureEventKind.INTERNAL,
        broken_price=broken_swing_price,
        protected_price=state.protected_price,
    )


def find_fractals_5bar(df: pd.DataFrame) -> Tuple[List[bool], List[bool]]:
    """
    Identifies 5-bar Fractal swing points (2 bars left, 1 center, 2 bars right).
    Returns (swing_highs, swing_lows) boolean lists matching DataFrame length.
    """
    n = len(df)
    swing_highs = [False] * n
    swing_lows = [False] * n

    if n < 5:
        return swing_highs, swing_lows

    highs = df["high"].values
    lows = df["low"].values

    for i in range(2, n - 2):
        # 5-bar high: higher than 2 previous and 2 next bars
        if (
            highs[i] > highs[i - 1]
            and highs[i] > highs[i - 2]
            and highs[i] > highs[i + 1]
            and highs[i] > highs[i + 2]
        ):
            swing_highs[i] = True

        # 5-bar low: lower than 2 previous and 2 next bars
        if (
            lows[i] < lows[i - 1]
            and lows[i] < lows[i - 2]
            and lows[i] < lows[i + 1]
            and lows[i] < lows[i + 2]
        ):
            swing_lows[i] = True

    return swing_highs, swing_lows


def check_displacement(
    open_val: float,
    high_val: float,
    low_val: float,
    close_val: float,
    min_body_ratio: float = 0.60
) -> bool:
    """
    Verifies that the candle body comprises at least min_body_ratio (default 60%)
    of the total candle range.
    """
    total_range = high_val - low_val
    if total_range <= 0:
        return False
    body_size = abs(close_val - open_val)
    return (body_size / total_range) >= min_body_ratio


def detect_fvg(
    candle_prev: Dict[str, Any],
    candle_disp: Dict[str, Any],
    candle_next: Dict[str, Any],
    direction: Direction,
    min_gap: float = 0.50
) -> Tuple[bool, float, float, float]:
    """
    Detects 3-candle Fair Value Gap (FVG).
    Bullish: candle_next.low > candle_prev.high by at least min_gap ($0.50).
    Bearish: candle_prev.low > candle_next.high by at least min_gap ($0.50).
    
    Returns: (is_fvg, gap_high, gap_low, ce_50)
    """
    if direction == Direction.BUY:
        gap_low = float(candle_prev["high"])
        gap_high = float(candle_next["low"])
        gap_size = gap_high - gap_low
        if gap_size >= min_gap:
            ce_50 = round((gap_high + gap_low) / 2.0, 4)
            return True, gap_high, gap_low, ce_50
    else:  # SELL
        gap_high = float(candle_prev["low"])
        gap_low = float(candle_next["high"])
        gap_size = gap_high - gap_low
        if gap_size >= min_gap:
            ce_50 = round((gap_high + gap_low) / 2.0, 4)
            return True, gap_high, gap_low, ce_50

    return False, 0.0, 0.0, 0.0


def check_sweep(
    candle: Dict[str, Any],
    level: float,
    is_high_level: bool = True,
    max_pierce: float = 5.0
) -> Tuple[bool, float]:
    """
    Verifies a strict Wick-Only Liquidity Sweep (ADR-002).
    
    For High Level (Asian High or PDH):
        - high > level
        - close <= level (wick only, no body close above)
        - high - level <= max_pierce ($5.00)
    
    For Low Level (Asian Low or PDL):
        - low < level
        - close >= level (wick only, no body close below)
        - level - low <= max_pierce ($5.00)
        
    Returns: (is_sweep, sweep_wick_price)
    """
    c_open = float(candle["open"])
    c_high = float(candle["high"])
    c_low = float(candle["low"])
    c_close = float(candle["close"])

    if is_high_level:
        if c_high > level and c_close <= level:
            pierce = c_high - level
            if pierce <= max_pierce:
                return True, c_high
    else:
        if c_low < level and c_close >= level:
            pierce = level - c_low
            if pierce <= max_pierce:
                return True, c_low

    return False, 0.0


def is_expansion_breakout(
    candle: Dict[str, Any],
    level: float,
    is_high_level: bool = True,
    max_breakout_pierce: float = 8.0
) -> bool:
    """
    ADR-002 Expansion Breakout: a candle's body closes through the level,
    or its wick pierces beyond the fixed $8.00 breakout cap, invalidates
    sweep search immediately -- a sweep before this bar must not be reused.
    """
    c_high = float(candle["high"])
    c_low = float(candle["low"])
    c_close = float(candle["close"])

    if is_high_level:
        if c_high > level:
            pierce = c_high - level
            if c_close > level or pierce > max_breakout_pierce:
                return True
    else:
        if c_low < level:
            pierce = level - c_low
            if c_close < level or pierce > max_breakout_pierce:
                return True

    return False
