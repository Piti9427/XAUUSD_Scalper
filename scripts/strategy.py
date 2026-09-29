import pandas as pd
import numpy as np
import math

try:
    import pandas_ta as ta
except ImportError:
    ta = None


def pure_b1_direction(close, prior_high, prior_low, rsi, ema50):
    """Return BUY=1, SELL=-1, or flat=0 for the target completed M15 bar."""
    values = (close, prior_high, prior_low, rsi, ema50)
    if not all(math.isfinite(value) for value in values) or not 30 < rsi < 70:
        return 0
    if close > prior_high and close > ema50:
        return 1
    if close < prior_low and close < ema50:
        return -1
    return 0


def pure_b1_bars(completed):
    """Calculate target Pure B1 signals from completed, UTC-aligned Bid M15 bars.

    RSI uses EWM span=14; EMA uses EWM span=50; ATR uses rolling mean 14.
    These match the target OHLC research script, not frozen B1-FINAL-v1.
    """
    index = completed.index
    if not isinstance(index, pd.DatetimeIndex) or index.tz is None:
        raise ValueError("Pure B1 requires timezone-aware UTC M15 bars")
    if any(stamp.utcoffset() != pd.Timedelta(0) for stamp in index):
        raise ValueError("Pure B1 requires UTC bars")
    if (
        index.has_duplicates
        or not index.is_monotonic_increasing
        or (index.as_unit("ns").asi8 % (900 * 10**9)).any()
    ):
        raise ValueError("Pure B1 requires ordered, aligned M15 bars")
    frame = completed[["open", "high", "low", "close"]].astype(float).copy()
    if not np.isfinite(frame.to_numpy()).all() or (frame.to_numpy() <= 0).any():
        raise ValueError("Pure B1 requires finite, positive OHLC")
    if (
        (frame.high < frame[["open", "close"]].max(axis=1))
        | (frame.low > frame[["open", "close"]].min(axis=1))
        | (frame.high < frame.low)
    ).any():
        raise ValueError("Pure B1 invalid OHLC geometry")

    frame["hh30"] = frame.high.rolling(30).max().shift(1)
    frame["ll30"] = frame.low.rolling(30).min().shift(1)
    delta = frame.close.diff()
    gain = delta.clip(lower=0).ewm(span=14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(span=14, adjust=False).mean()
    relative_strength = gain / loss.replace(0, np.nan)
    frame["rsi"] = 100 - 100 / (1 + relative_strength)
    frame["ema50"] = frame.close.ewm(span=50, adjust=False).mean()
    prior_close = frame.close.shift()
    true_range = pd.concat(
        [
            frame.high - frame.low,
            (frame.high - prior_close).abs(),
            (frame.low - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr"] = true_range.rolling(14).mean()
    frame["ready"] = frame[["hh30", "ll30", "rsi", "ema50", "atr"]].notna().all(axis=1)
    frame["direction"] = [
        pure_b1_direction(close, high, low, rsi, trend) if ready else 0
        for close, high, low, rsi, trend, ready in zip(
            frame.close, frame.hh30, frame.ll30, frame.rsi, frame.ema50, frame.ready
        )
    ]
    return frame


def pure_b1_levels(entry_price, direction, atr):
    """Return stop and target before broker tick-size normalization."""
    if direction not in (-1, 1) or not all(
        math.isfinite(value) and value > 0 for value in (entry_price, atr)
    ):
        raise ValueError("Invalid Pure B1 entry, direction, or ATR")
    return entry_price - direction * atr * 2.5, entry_price + direction * atr * 6.25


class XAUUSDSniperStrategy:
    def __init__(self, config):
        self.config = config["strategy"]
        self.tp_pips = self.config["tp_pips"]
        self.sl_pips = self.config["sl_pips"]
        self.max_spread = self.config["max_spread"]
        self.atr_multiplier_tp = self.config.get("atr_multiplier_tp", 2.0)
        self.atr_multiplier_sl = self.config.get("atr_multiplier_sl", 1.5)

    def calculate_indicators(self, df):
        """Calculates indicators needed for the strategy."""
        if ta is None:
            raise RuntimeError("pandas_ta is not installed. Run pip install -r requirements.txt.")

        df["ema_short"] = ta.ema(df["close"], length=self.config["ema_short"])
        df["ema_long"] = ta.ema(df["close"], length=self.config["ema_long"])
        df["rsi"] = ta.rsi(df["close"], length=self.config["rsi_period"])
        df["mfi"] = ta.mfi(df["high"], df["low"], df["close"], df["tick_volume"], length=14)
        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        return df

    def check_signals(self, df_m15, df_h1, df_h4, current_spread):
        """Checks for Buy/Sell signals based on Omni-Sniper logic."""
        if len(df_m15) < 5 or df_h1 is None or df_h4 is None:
            return "NOT_ENOUGH_DATA"

        # 1. Spread Check
        if current_spread is None:
            return "SPREAD_UNAVAILABLE"
        if current_spread > self.max_spread:
            return "SKIP_SPREAD_TOO_HIGH"

        # 2. Identify Asian Session High/Low (Simplified for Backtest)
        # In a real run, this would be calculated from current day's 00:00-08:00
        df_m15["time"] = pd.to_datetime(df_m15["time"])
        last_bar = df_m15.iloc[-2]  # Last closed bar
        prev_bar = df_m15.iloc[-3]

        # 3. Liquidity Sweep (Gold Hunter) & Wick Rejection Logic
        # Calculate wick sizes
        upper_wick = last_bar["high"] - max(last_bar["open"], last_bar["close"])
        lower_wick = min(last_bar["open"], last_bar["close"]) - last_bar["low"]
        body_size = abs(last_bar["open"] - last_bar["close"])

        # Rejection Criteria: Wick is at least 2x the body
        is_bearish_rejection = (
            upper_wick > (body_size * 2) and upper_wick > 2.0
        )  # 2.0 points for Gold
        is_bullish_rejection = lower_wick > (body_size * 2) and lower_wick > 2.0

        # 4. Market Structure Shift (MSS) Detection
        # Short: Sweep of a high + break of previous low
        mss_short = is_bearish_rejection and last_bar["close"] < prev_bar["low"]
        # Long: Sweep of a low + break of previous high
        mss_long = is_bullish_rejection and last_bar["close"] > prev_bar["high"]

        # 5. Time Filter (New York Session: 11:00 - 16:00 UTC)
        current_hour = last_bar["time"].hour
        is_ny_session = 11 <= current_hour <= 16

        if not is_ny_session:
            return "OUTSIDE_SESSION"

        # 6. EMA Trend Filter (optional, default enabled)
        if self.config.get("ema_trend_filter", True):
            ema_long_val = last_bar.get("ema_long")
            if ema_long_val is None or pd.isna(ema_long_val):
                # Fail-closed: no EMA data → block signal rather than let it pass
                return "EMA_DATA_MISSING"
            if mss_long and last_bar["close"] <= ema_long_val:
                return "EMA_FILTER_BLOCKED"
            if mss_short and last_bar["close"] >= ema_long_val:
                return "EMA_FILTER_BLOCKED"

        if mss_long:
            return "BUY"
        if mss_short:
            return "SELL"

        return "NO_MSS"

    def get_tp_sl(self, entry_price, signal_type, atr_value=None):
        """Calculates dynamic TP and SL prices using ATR."""
        pip_size = 0.1  # Standard for Gold

        # If ATR is provided, use dynamic scaling, otherwise fallback to fixed pips
        if atr_value and not pd.isna(atr_value):
            if signal_type == "BUY":
                tp = entry_price + (atr_value * self.atr_multiplier_tp)
                sl = entry_price - (atr_value * self.atr_multiplier_sl)
            else:
                tp = entry_price - (atr_value * self.atr_multiplier_tp)
                sl = entry_price + (atr_value * self.atr_multiplier_sl)
        else:
            if signal_type == "BUY":
                tp = entry_price + (self.tp_pips * pip_size)
                sl = entry_price - (self.sl_pips * pip_size)
            else:
                tp = entry_price - (self.tp_pips * pip_size)
                sl = entry_price + (self.sl_pips * pip_size)

        return round(tp, 2), round(sl, 2)
