from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np
from scripts.smc.types import Direction, SetupSignal, LiquidityLevels
from scripts.smc.structure import (
    find_fractals_5bar,
    check_displacement,
    detect_fvg,
    check_sweep,
)


def is_in_session(dt: datetime) -> bool:
    """
    Checks if datetime dt is within London (07:00-10:00 UTC) or NY (12:30-15:30 UTC) Killzones.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    minutes_of_day = dt.hour * 60 + dt.minute

    # London: 07:00 - 10:00 UTC (420 to 600 min)
    is_london = 420 <= minutes_of_day < 600
    # NY: 12:30 - 15:30 UTC (750 to 930 min)
    is_ny = 750 <= minutes_of_day < 930

    return is_london or is_ny


def calculate_ema(series: pd.Series, length: int) -> pd.Series:
    """Calculates exponential moving average."""
    return series.ewm(span=length, adjust=False).mean()


def detect_smc_setup(
    h1_candles: pd.DataFrame,
    m5_candles: pd.DataFrame,
    liquidity: Optional[LiquidityLevels],
    current_time: datetime,
    spread_buffer: float = 0.30,
    max_sl_cap: float = 6.00,
    max_sweep_to_mss_bars: int = 6,
    max_mss_to_fvg_bars: int = 2,
    current_spread: Optional[float] = None,
    max_spread: float = 0.35,
    precomputed_swings: Optional[Tuple[List[bool], List[bool]]] = None,
) -> Optional[SetupSignal]:
    """
    Pure Functional Seam: Evaluates market conditions for a deterministic SMC setup.
    Stateless, reproducible, and decoupled from brokers or execution platforms.
    Optimized for O(1) step evaluation in backtesting and live loops.
    """
    # 0. Live Spread Guard
    if current_spread is not None and current_spread > max_spread:
        return None

    if liquidity is None:
        return None

    if not is_in_session(current_time):
        return None

    if h1_candles is None or len(h1_candles) < 200:
        return None

    if m5_candles is None or len(m5_candles) < 15:
        return None

    # 1. H1 Direction Bias (ADR-006: EMA 200 filter) - O(1) if precomputed
    latest_h1_close = h1_candles["close"].iloc[-1]
    if "ema200" in h1_candles.columns:
        latest_h1_ema = h1_candles["ema200"].iloc[-1]
    else:
        h1_ema200 = calculate_ema(h1_candles["close"], 200)
        latest_h1_ema = h1_ema200.iloc[-1]

    if latest_h1_close > latest_h1_ema:
        bias = Direction.BUY
    elif latest_h1_close < latest_h1_ema:
        bias = Direction.SELL
    else:
        return None

    # 2. Slice M5 data up to current_time (avoid redundant full copy if already aligned)
    if m5_candles["time"].iloc[-1] <= current_time:
        df_m5 = m5_candles
    else:
        df_m5 = m5_candles[m5_candles["time"] <= current_time]

    n_m5 = len(df_m5)
    if n_m5 < 15:
        return None

    # Compute 5-bar fractals (O(1) with precomputed or recent lookback slice)
    if precomputed_swings is not None:
        swing_highs, swing_lows = precomputed_swings
    else:
        # Compute on recent 60-bar lookback slice for O(1) performance
        lookback_slice = df_m5.tail(60).reset_index(drop=True)
        sh_slice, sl_slice = find_fractals_5bar(lookback_slice)
        offset = n_m5 - len(lookback_slice)
        swing_highs = [False] * offset + sh_slice
        swing_lows = [False] * offset + sl_slice

    # 2. Identify Sweep
    # For BUY: sweep of Asian Low or PDL
    # For SELL: sweep of Asian High or PDH
    levels_to_check = (
        [liquidity.asian_low, liquidity.pdl] if bias == Direction.BUY
        else [liquidity.asian_high, liquidity.pdh]
    )
    is_high_level = (bias == Direction.SELL)

    # Search backwards for a valid sweep bar within the last 20 bars
    sweep_idx = None
    sweep_wick = None
    swept_level = None

    for i in range(n_m5 - 1, max(0, n_m5 - 20), -1):
        bar = df_m5.iloc[i].to_dict()
        for lvl in levels_to_check:
            is_sw, wick = check_sweep(bar, level=lvl, is_high_level=is_high_level, max_pierce=5.0)
            if is_sw:
                sweep_idx = i
                sweep_wick = wick
                swept_level = lvl
                break
        if sweep_idx is not None:
            break

    if sweep_idx is None:
        return None

    # 3. MSS and Displacement (ADR-003, ADR-004, ADR-014)
    # MSS must occur within max_sweep_to_mss_bars (6 bars) after sweep
    mss_idx = None
    mss_swing_price = None

    if bias == Direction.BUY:
        # Find the latest confirmed swing high prior to candidate MSS bar
        for i in range(sweep_idx + 1, min(n_m5, sweep_idx + max_sweep_to_mss_bars + 1)):
            # Look for most recent swing high before i
            prev_swing_highs = [
                df_m5.iloc[k]["high"] for k in range(0, i) if swing_highs[k]
            ]
            if not prev_swing_highs:
                continue
            recent_swing_high = prev_swing_highs[-1]
            
            bar_i = df_m5.iloc[i]
            # Body close must exceed swing high
            if bar_i["close"] > recent_swing_high:
                # Must be displacement candle (body >= 60%)
                if check_displacement(bar_i["open"], bar_i["high"], bar_i["low"], bar_i["close"], 0.60):
                    mss_idx = i
                    mss_swing_price = recent_swing_high
                    break
    else:  # SELL
        for i in range(sweep_idx + 1, min(n_m5, sweep_idx + max_sweep_to_mss_bars + 1)):
            prev_swing_lows = [
                df_m5.iloc[k]["low"] for k in range(0, i) if swing_lows[k]
            ]
            if not prev_swing_lows:
                continue
            recent_swing_low = prev_swing_lows[-1]

            bar_i = df_m5.iloc[i]
            # Body close must drop below swing low
            if bar_i["close"] < recent_swing_low:
                if check_displacement(bar_i["open"], bar_i["high"], bar_i["low"], bar_i["close"], 0.60):
                    mss_idx = i
                    mss_swing_price = recent_swing_low
                    break

    if mss_idx is None:
        return None

    # 4. FVG Detection (ADR-004)
    # FVG formed on MSS bar or up to max_mss_to_fvg_bars (2 bars) after
    fvg_found = False
    fvg_high_val = 0.0
    fvg_low_val = 0.0
    entry_limit_price = 0.0

    for disp_i in range(mss_idx, min(n_m5 - 1, mss_idx + max_mss_to_fvg_bars + 1)):
        if disp_i < 1 or disp_i + 1 >= n_m5:
            continue
        c_prev = df_m5.iloc[disp_i - 1].to_dict()
        c_disp = df_m5.iloc[disp_i].to_dict()
        c_next = df_m5.iloc[disp_i + 1].to_dict()

        is_fvg, g_high, g_low, ce_50 = detect_fvg(c_prev, c_disp, c_next, direction=bias, min_gap=0.50)
        if is_fvg:
            fvg_found = True
            fvg_high_val = g_high
            fvg_low_val = g_low
            entry_limit_price = ce_50
            break

    if not fvg_found:
        return None

    # 5. Risk, SL, TP (ADR-008, ADR-009)
    if bias == Direction.BUY:
        sl_price = round(sweep_wick - spread_buffer, 2)
        raw_sl_dist = abs(entry_limit_price - sweep_wick)
        total_sl_dist = round(raw_sl_dist + spread_buffer, 2)
        tp_price = round(entry_limit_price + (total_sl_dist * 2.0), 2)
    else:  # SELL
        sl_price = round(sweep_wick + spread_buffer, 2)
        raw_sl_dist = abs(entry_limit_price - sweep_wick)
        total_sl_dist = round(raw_sl_dist + spread_buffer, 2)
        tp_price = round(entry_limit_price - (total_sl_dist * 2.0), 2)

    # Max SL Cap ($6.00 / 600 points)
    if total_sl_dist > max_sl_cap:
        return None

    return SetupSignal(
        direction=bias,
        sweep_price=float(swept_level),
        sweep_wick=float(sweep_wick),
        mss_price=float(mss_swing_price),
        entry_price=float(entry_limit_price),
        sl_price=float(sl_price),
        tp_price=float(tp_price),
        sl_distance=float(total_sl_dist),
        risk_r=2.0,
        fvg_high=float(fvg_high_val),
        fvg_low=float(fvg_low_val),
        reason=f"{bias.value} SMC Setup: Swept {swept_level} -> MSS {mss_swing_price} -> FVG [{fvg_low_val}, {fvg_high_val}]",
        timestamp=current_time
    )
