import pandas as pd
try:
    import pandas_ta as ta
except ImportError:
    ta = None

class XAUUSDSniperStrategy:
    def __init__(self, config):
        self.config = config['strategy']
        self.tp_pips = self.config['tp_pips']
        self.sl_pips = self.config['sl_pips']
        self.max_spread = self.config['max_spread']
        self.atr_multiplier_tp = self.config.get('atr_multiplier_tp', 2.0)
        self.atr_multiplier_sl = self.config.get('atr_multiplier_sl', 1.5)

    def calculate_indicators(self, df):
        """Calculates indicators needed for the strategy."""
        if ta is None:
            raise RuntimeError("pandas_ta is not installed. Run pip install -r requirements.txt.")

        df['ema_short'] = ta.ema(df['close'], length=self.config['ema_short'])
        df['ema_long'] = ta.ema(df['close'], length=self.config['ema_long'])
        df['rsi'] = ta.rsi(df['close'], length=self.config['rsi_period'])
        df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['tick_volume'], length=14)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
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
        df_m15['time'] = pd.to_datetime(df_m15['time'])
        last_bar = df_m15.iloc[-2] # Last closed bar
        prev_bar = df_m15.iloc[-3]
        
        # 3. Liquidity Sweep (Gold Hunter) & Wick Rejection Logic
        # Calculate wick sizes
        upper_wick = last_bar['high'] - max(last_bar['open'], last_bar['close'])
        lower_wick = min(last_bar['open'], last_bar['close']) - last_bar['low']
        body_size = abs(last_bar['open'] - last_bar['close'])
        
        # Rejection Criteria: Wick is at least 2x the body
        is_bearish_rejection = upper_wick > (body_size * 2) and upper_wick > 2.0 # 2.0 points for Gold
        is_bullish_rejection = lower_wick > (body_size * 2) and lower_wick > 2.0

        # 4. Market Structure Shift (MSS) Detection
        # Short: Sweep of a high + break of previous low
        mss_short = is_bearish_rejection and last_bar['close'] < prev_bar['low']
        # Long: Sweep of a low + break of previous high
        mss_long = is_bullish_rejection and last_bar['close'] > prev_bar['high']

        # 5. Time Filter (New York Session: 11:00 - 16:00 UTC)
        current_hour = last_bar['time'].hour
        is_ny_session = (11 <= current_hour <= 16)

        if not is_ny_session:
            return "OUTSIDE_SESSION"

        if mss_long:
            return "BUY"
        if mss_short:
            return "SELL"
            
        return "NO_MSS"

    def get_tp_sl(self, entry_price, signal_type, atr_value=None):
        """Calculates dynamic TP and SL prices using ATR."""
        pip_size = 0.1 # Standard for Gold
        
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
