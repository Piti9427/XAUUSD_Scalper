from datetime import datetime, timezone
from typing import Optional, List, Tuple
import pandas as pd
import numpy as np
from scripts.smc.types import Direction, SetupSignal, SetupDecision, LiquidityLevels
from scripts.smc.liquidity import select_nearest_opposing_pool_tp
from scripts.smc.setup_identity import make_setup_id
from scripts.smc.fibonacci import compute_fibonacci_features
from scripts.smc.structure import (
    find_fractals_5bar,
    measure_displacement,
    detect_fvg,
    check_sweep,
    is_expansion_breakout,
    StructureEventKind,
    replay_structure_until,
    classify_candidate_break,
    available_confirmed_pivots,
    pivot_confirmation_time,
    bar_time_as_utc,
    RULE_VERSION_DISPLACEMENT,
)


def is_in_session(dt: datetime, extended: bool = True) -> bool:
    """
    Checks if datetime dt is within London or NY Killzones.
    Standard: London (07:00-10:00 UTC), NY (12:30-15:30 UTC).
    Extended (Gold): London (07:00-10:30 UTC), NY (12:30-16:30 UTC).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    minutes_of_day = dt.hour * 60 + dt.minute

    if extended:
        is_london = 420 <= minutes_of_day < 630  # 07:00 - 10:30
        is_ny = 750 <= minutes_of_day < 990  # 12:30 - 16:30
    else:
        is_london = 420 <= minutes_of_day < 600  # 07:00 - 10:00
        is_ny = 750 <= minutes_of_day < 930  # 12:30 - 15:30

    return is_london or is_ny


def calculate_ema(series: pd.Series, length: int) -> pd.Series:
    """Calculates exponential moving average."""
    return series.ewm(span=length, adjust=False).mean()


def resolve_h1_ema_bias(h1_candles: pd.DataFrame) -> Tuple[Optional[Direction], str]:
    """
    H1 EMA200 bias from closed H1 data (ADR-006).

    Returns (Direction, "ok") when directional, (None, reason) when flat/unknown.
    Does not invent bias from insufficient history.
    """
    if h1_candles is None or len(h1_candles) < 200:
        return None, "h1_warmup_insufficient"
    latest_h1_close = float(h1_candles["close"].iloc[-1])
    if "ema200" in h1_candles.columns:
        latest_h1_ema = float(h1_candles["ema200"].iloc[-1])
    else:
        latest_h1_ema = float(calculate_ema(h1_candles["close"], 200).iloc[-1])
    if latest_h1_close > latest_h1_ema:
        return Direction.BUY, "ok"
    if latest_h1_close < latest_h1_ema:
        return Direction.SELL, "ok"
    return None, "h1_bias_flat"


def evaluate_smc_setup(
    h1_candles: pd.DataFrame,
    m5_candles: pd.DataFrame,
    liquidity: Optional[LiquidityLevels],
    current_time: datetime,
    spread_buffer: float = 0.30,
    max_sl_cap: float = 25.00,
    max_sweep_to_mss_bars: int = 8,
    max_mss_to_fvg_bars: int = 4,
    current_spread: Optional[float] = None,
    max_spread: float = 0.35,
    precomputed_swings: Optional[Tuple[List[bool], List[bool]]] = None,
    min_body_ratio: float = 0.45,
    atr_sl_multiplier: Optional[float] = None,
    min_fvg_gap: float = 0.30,
    tp_r: float = 2.0,
    max_sweep_pierce: float = 8.0,
    sweep_lookback: int = 25,
    extended_killzones: bool = True,
    max_breakout_pierce: float = 8.0,
    require_choch: bool = True,
    min_target_r: float = 1.5,
) -> SetupDecision:
    """
    Pure Functional Seam: Evaluates market conditions and returns SetupDecision (signal or reject_reason).
    Stateless, reproducible, and decoupled from brokers or execution platforms.

    Key parameters tuned for XAUUSD (Gold) BaselinePlay / Issue #1:
      max_sl_cap: Hard dollar cap on SL distance (default $25)
      atr_sl_multiplier: Dynamic SL cap = ATR(14) × multiplier when set
      min_body_ratio: Minimum displacement body ratio (default 45%)
      min_fvg_gap: Minimum FVG size in dollars (default $0.30)
      max_sweep_pierce: Max wick distance beyond liquidity level (default $8)
      sweep_lookback: Bars to search backwards for sweep (default 25)
      max_sweep_to_mss_bars / max_mss_to_fvg_bars: 8 / 4
      require_choch: Foundation requires protected-swing CHoCH (default True)
      extended_killzones: True for London 07:00-10:30, NY 12:30-16:30
    """
    # 0. Live Spread Guard
    if current_spread is not None and current_spread > max_spread:
        return SetupDecision(None, "spread_guard")

    if liquidity is None:
        return SetupDecision(None, "liquidity_unavailable")

    if not is_in_session(current_time, extended=extended_killzones):
        return SetupDecision(None, "out_of_session")

    if h1_candles is None or len(h1_candles) < 200:
        return SetupDecision(None, "h1_warmup_insufficient")

    if m5_candles is None or len(m5_candles) < 15:
        return SetupDecision(None, "m5_warmup_insufficient")

    # Compute optional ATR(14) on recent bars for dynamic SL cap
    if atr_sl_multiplier is not None:
        recent_bars = m5_candles.tail(min(50, len(m5_candles)))
        tr_values = (recent_bars["high"] - recent_bars["low"]).values
        atr_14 = (
            float(np.mean(tr_values[-14:])) if len(tr_values) >= 14 else float(np.mean(tr_values))
        )
        effective_sl_cap = min(max_sl_cap, atr_14 * atr_sl_multiplier)
    else:
        effective_sl_cap = max_sl_cap

    # 1. H1 Direction Bias (ADR-006: EMA 200 filter) - O(1) if precomputed
    bias, bias_reason = resolve_h1_ema_bias(h1_candles)
    if bias is None:
        return SetupDecision(None, bias_reason)

    # 2. Slice M5 data up to current_time (avoid redundant full copy if already aligned)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    else:
        current_time = current_time.astimezone(timezone.utc)

    m5_time = m5_candles["time"]
    if not pd.api.types.is_datetime64_any_dtype(m5_time):
        m5_candles = m5_candles.copy()
        m5_candles["time"] = pd.to_datetime(m5_time, utc=True)
    elif m5_time.dt.tz is None:
        m5_candles = m5_candles.copy()
        m5_candles["time"] = m5_time.dt.tz_localize("UTC")

    if m5_candles["time"].iloc[-1] <= current_time:
        df_m5 = m5_candles
    else:
        df_m5 = m5_candles[m5_candles["time"] <= current_time]

    n_m5 = len(df_m5)
    if n_m5 < 15:
        return SetupDecision(None, "m5_slice_insufficient")

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
    if bias == Direction.BUY:
        levels_to_check = [lvl for lvl in [liquidity.asian_low, liquidity.pdl] if lvl is not None]
        if current_time.hour >= 12 and liquidity.london_low is not None:
            levels_to_check.append(liquidity.london_low)
    else:
        levels_to_check = [lvl for lvl in [liquidity.asian_high, liquidity.pdh] if lvl is not None]
        if current_time.hour >= 12 and liquidity.london_high is not None:
            levels_to_check.append(liquidity.london_high)
    if not levels_to_check:
        return SetupDecision(None, "no_liquidity_levels")
    is_high_level = bias == Direction.SELL

    # Search backwards for a valid sweep bar within the last sweep_lookback bars
    sweep_idx = None
    sweep_wick = None
    swept_level = None

    for i in range(n_m5 - 1, max(0, n_m5 - sweep_lookback), -1):
        bar = df_m5.iloc[i].to_dict()

        # A breakout invalidates older sweeps of that level only.
        levels_to_check = [
            lvl
            for lvl in levels_to_check
            if not is_expansion_breakout(
                bar,
                lvl,
                is_high_level=is_high_level,
                max_breakout_pierce=max_breakout_pierce,
            )
        ]
        if not levels_to_check:
            break

        for lvl in levels_to_check:
            is_sw, wick = check_sweep(
                bar, level=lvl, is_high_level=is_high_level, max_pierce=max_sweep_pierce
            )
            if is_sw:
                sweep_idx = i
                sweep_wick = wick
                swept_level = lvl
                break
        if sweep_idx is not None:
            break

    if sweep_idx is None:
        return SetupDecision(None, "no_sweep")

    # 3. MSS and Displacement (ADR-003, ADR-004, ADR-014 / story 19)
    # MSS must occur within max_sweep_to_mss_bars after sweep
    mss_idx = None
    mss_swing_price = None
    true_sweep_wick = float(sweep_wick)
    displacement_body_ratio: Optional[float] = None

    if bias == Direction.BUY:
        # Find the latest confirmed swing high prior to candidate MSS bar
        for i in range(sweep_idx + 1, min(n_m5, sweep_idx + max_sweep_to_mss_bars + 1)):
            swing_idx = next((k for k in range(i - 1, -1, -1) if swing_highs[k]), None)
            if swing_idx is None:
                continue
            recent_swing_high = df_m5.iloc[swing_idx]["high"]

            bar_i = df_m5.iloc[i]
            # Body close must exceed swing high AND be a green candle
            if bar_i["close"] > recent_swing_high and bar_i["close"] > bar_i["open"]:
                ok_disp, ratio, _reason = measure_displacement(
                    bar_i["open"], bar_i["high"], bar_i["low"], bar_i["close"], min_body_ratio
                )
                if ok_disp:
                    mss_idx = i
                    mss_swing_price = recent_swing_high
                    displacement_body_ratio = float(ratio)
                    # True Swing Extremum: lowest low among all candles from sweep up to MSS
                    true_sweep_wick = min(
                        float(df_m5.iloc[k]["low"]) for k in range(sweep_idx, mss_idx + 1)
                    )
                    break
    else:  # SELL
        for i in range(sweep_idx + 1, min(n_m5, sweep_idx + max_sweep_to_mss_bars + 1)):
            swing_idx = next((k for k in range(i - 1, -1, -1) if swing_lows[k]), None)
            if swing_idx is None:
                continue
            recent_swing_low = df_m5.iloc[swing_idx]["low"]

            bar_i = df_m5.iloc[i]
            # Body close must drop below swing low AND be a red candle
            if bar_i["close"] < recent_swing_low and bar_i["close"] < bar_i["open"]:
                ok_disp, ratio, _reason = measure_displacement(
                    bar_i["open"], bar_i["high"], bar_i["low"], bar_i["close"], min_body_ratio
                )
                if ok_disp:
                    mss_idx = i
                    mss_swing_price = recent_swing_low
                    displacement_body_ratio = float(ratio)
                    # True Swing Extremum: highest high among all candles from sweep up to MSS
                    true_sweep_wick = max(
                        float(df_m5.iloc[k]["high"]) for k in range(sweep_idx, mss_idx + 1)
                    )
                    break

    if mss_idx is None:
        return SetupDecision(None, "no_mss_displacement")

    broken_swing_index: Optional[int] = None
    protected_swing_index: Optional[int] = None
    broken_swing_confirmed_at: Optional[str] = None
    protected_swing_confirmed_at: Optional[str] = None

    if require_choch:
        highs = [float(x) for x in df_m5["high"].tolist()]
        lows = [float(x) for x in df_m5["low"].tolist()]
        closes = [float(x) for x in df_m5["close"].tolist()]
        state_before = replay_structure_until(
            highs,
            lows,
            closes,
            swing_highs,
            swing_lows,
            mss_idx,
        )
        break_side = "above" if bias == Direction.BUY else "below"
        if bias == Direction.BUY:
            opposite = [
                (idx, price)
                for idx, price in available_confirmed_pivots(swing_lows, lows, mss_idx)
                if price is not None
            ]
            # Opposite pivots must sit between the broken swing and the break bar.
            broken_idx = next(
                (
                    k
                    for k in range(mss_idx - 1, -1, -1)
                    if swing_highs[k] and float(df_m5.iloc[k]["high"]) == float(mss_swing_price)
                ),
                None,
            )
            if broken_idx is None:
                return SetupDecision(None, "choch_broken_swing_unresolved")
            opposite = [(idx, price) for idx, price in opposite if broken_idx < idx < mss_idx]
        else:
            broken_idx = next(
                (
                    k
                    for k in range(mss_idx - 1, -1, -1)
                    if swing_lows[k] and float(df_m5.iloc[k]["low"]) == float(mss_swing_price)
                ),
                None,
            )
            if broken_idx is None:
                return SetupDecision(None, "choch_broken_swing_unresolved")
            opposite = [
                (idx, price)
                for idx, price in available_confirmed_pivots(swing_highs, highs, mss_idx)
                if broken_idx < idx < mss_idx
            ]
        event = classify_candidate_break(
            state_before,
            break_side=break_side,
            broken_swing_price=float(mss_swing_price),
            break_index=mss_idx,
            opposite_pivots_between=opposite,
        )
        if event.kind != StructureEventKind.CHOCH:
            return SetupDecision(None, "choch_required_not_met")

        # Story 17: record confirmation times (second right-hand bar close).
        broken_swing_index = int(broken_idx)
        bar_times = df_m5["time"].tolist() if "time" in df_m5.columns else None
        if bar_times is not None:
            bt = pivot_confirmation_time(broken_swing_index, bar_times)
            if bt is not None:
                broken_swing_confirmed_at = bt.isoformat()
        if event.protected_price is not None:
            for idx, price in opposite:
                if float(price) == float(event.protected_price):
                    protected_swing_index = int(idx)
                    if bar_times is not None:
                        pt = pivot_confirmation_time(protected_swing_index, bar_times)
                        if pt is not None:
                            protected_swing_confirmed_at = pt.isoformat()
                    break

    # 4. FVG Detection (ADR-004)
    # FVG formed on MSS bar or up to max_mss_to_fvg_bars after
    # Story 21: right-hand (third) candle must exist in closed M5 frame before order.
    fvg_found = False
    fvg_high_val = 0.0
    fvg_low_val = 0.0
    entry_limit_price = 0.0
    fvg_right_hand_index: Optional[int] = None
    fvg_available_at: Optional[str] = None

    for disp_i in range(mss_idx, min(n_m5 - 1, mss_idx + max_mss_to_fvg_bars + 1)):
        if disp_i < 1 or disp_i + 1 >= n_m5:
            continue
        c_prev = df_m5.iloc[disp_i - 1].to_dict()
        c_disp = df_m5.iloc[disp_i].to_dict()
        c_next = df_m5.iloc[disp_i + 1].to_dict()

        is_fvg, g_high, g_low, ce_50 = detect_fvg(
            c_prev, c_disp, c_next, direction=bias, min_gap=min_fvg_gap
        )
        if is_fvg:
            fvg_found = True
            fvg_high_val = g_high
            fvg_low_val = g_low
            entry_limit_price = ce_50
            fvg_right_hand_index = int(disp_i + 1)
            if "time" in df_m5.columns:
                rh_t = bar_time_as_utc(df_m5.iloc[fvg_right_hand_index]["time"])
                if rh_t is not None:
                    fvg_available_at = rh_t.isoformat()
            break

    if not fvg_found:
        return SetupDecision(None, "no_fvg")

    # 5. Risk, SL, TP (ADR-018, ADR-019 / foundation pool TP when require_choch)
    if bias == Direction.BUY:
        sl_price = round(true_sweep_wick - spread_buffer, 2)
        raw_sl_dist = abs(entry_limit_price - true_sweep_wick)
        total_sl_dist = round(raw_sl_dist + spread_buffer, 2)
    else:  # SELL
        sl_price = round(true_sweep_wick + spread_buffer, 2)
        raw_sl_dist = abs(entry_limit_price - true_sweep_wick)
        total_sl_dist = round(raw_sl_dist + spread_buffer, 2)

    # SL Cap Check (max_sl_cap or ATR dynamic)
    if total_sl_dist > effective_sl_cap:
        return SetupDecision(None, "sl_cap_exceeded")

    pool_tp_name = None
    if require_choch:
        tp_price, pool_tp_name = select_nearest_opposing_pool_tp(
            bias,
            entry_price=float(entry_limit_price),
            sl_distance=float(total_sl_dist),
            liquidity=liquidity,
            min_r=min_target_r,
        )
        if tp_price is None:
            return SetupDecision(None, "no_eligible_pool_tp")
        risk_r = abs(float(tp_price) - float(entry_limit_price)) / float(total_sl_dist)
    else:
        if bias == Direction.BUY:
            tp_price = round(entry_limit_price + (total_sl_dist * tp_r), 2)
        else:
            tp_price = round(entry_limit_price - (total_sl_dist * tp_r), 2)
        risk_r = tp_r

    structure_label = "CHOCH" if require_choch else "MSS"
    target_note = f" pool={pool_tp_name}" if pool_tp_name else ""
    ts = current_time
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    setup_id = make_setup_id(
        direction=bias.value,
        entry_price=float(entry_limit_price),
        sl_price=float(sl_price),
        tp_price=float(tp_price),
        sweep_wick=float(true_sweep_wick),
        available_at=ts.isoformat(),
    )
    # ADR-0028: Fib/OTE research log on Sweep→break range — never filters admission.
    if bias == Direction.BUY:
        fib_high = float(mss_swing_price)
        fib_low = float(true_sweep_wick)
    else:
        fib_high = float(true_sweep_wick)
        fib_low = float(mss_swing_price)
    fib = compute_fibonacci_features(
        direction=bias.value,
        swing_high=fib_high,
        swing_low=fib_low,
        entry=float(entry_limit_price),
    )
    ote_note = (
        f" fib={fib.retracement:.4f} ote={fib.in_ote}"
        if fib.available and fib.retracement is not None
        else f" fib={fib.reason}"
    )
    return SetupDecision(
        SetupSignal(
            direction=bias,
            sweep_price=float(swept_level),
            sweep_wick=float(true_sweep_wick),
            mss_price=float(mss_swing_price),
            entry_price=float(entry_limit_price),
            sl_price=float(sl_price),
            tp_price=float(tp_price),
            sl_distance=float(total_sl_dist),
            risk_r=float(risk_r),
            fvg_high=float(fvg_high_val),
            fvg_low=float(fvg_low_val),
            reason=(
                f"{bias.value} SMC Setup: Swept {swept_level} -> {structure_label} "
                f"{mss_swing_price} -> FVG [{fvg_low_val}, {fvg_high_val}]{target_note}{ote_note}"
            ),
            timestamp=current_time,
            setup_id=setup_id,
            fib_retracement=fib.retracement,
            fib_in_ote=bool(fib.in_ote),
            fib_reason=fib.reason,
            broken_swing_index=broken_swing_index,
            protected_swing_index=protected_swing_index,
            broken_swing_confirmed_at=broken_swing_confirmed_at,
            protected_swing_confirmed_at=protected_swing_confirmed_at,
            fvg_right_hand_index=fvg_right_hand_index,
            fvg_available_at=fvg_available_at,
            displacement_body_ratio=displacement_body_ratio,
            displacement_rule_version=(
                RULE_VERSION_DISPLACEMENT if displacement_body_ratio is not None else None
            ),
        ),
        None,
    )


def detect_smc_setup(
    h1_candles: pd.DataFrame,
    m5_candles: pd.DataFrame,
    liquidity: Optional[LiquidityLevels],
    current_time: datetime,
    spread_buffer: float = 0.30,
    max_sl_cap: float = 25.00,
    max_sweep_to_mss_bars: int = 8,
    max_mss_to_fvg_bars: int = 4,
    current_spread: Optional[float] = None,
    max_spread: float = 0.35,
    precomputed_swings: Optional[Tuple[List[bool], List[bool]]] = None,
    min_body_ratio: float = 0.45,
    atr_sl_multiplier: Optional[float] = None,
    min_fvg_gap: float = 0.30,
    tp_r: float = 2.0,
    max_sweep_pierce: float = 8.0,
    sweep_lookback: int = 25,
    extended_killzones: bool = True,
    max_breakout_pierce: float = 8.0,
    require_choch: bool = True,
    min_target_r: float = 1.5,
) -> Optional[SetupSignal]:
    """Backward-compatible wrapper — prefer evaluate_smc_setup for reject reasons."""
    return evaluate_smc_setup(
        h1_candles,
        m5_candles,
        liquidity,
        current_time,
        spread_buffer=spread_buffer,
        max_sl_cap=max_sl_cap,
        max_sweep_to_mss_bars=max_sweep_to_mss_bars,
        max_mss_to_fvg_bars=max_mss_to_fvg_bars,
        current_spread=current_spread,
        max_spread=max_spread,
        precomputed_swings=precomputed_swings,
        min_body_ratio=min_body_ratio,
        atr_sl_multiplier=atr_sl_multiplier,
        min_fvg_gap=min_fvg_gap,
        tp_r=tp_r,
        max_sweep_pierce=max_sweep_pierce,
        sweep_lookback=sweep_lookback,
        extended_killzones=extended_killzones,
        max_breakout_pierce=max_breakout_pierce,
        require_choch=require_choch,
        min_target_r=min_target_r,
    ).signal
