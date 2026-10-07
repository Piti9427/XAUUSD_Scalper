import os
import pandas as pd
import numpy as np
from pathlib import Path
from scripts.research.data import acquire, load_year, bars

def rsi(series, period):
    delta = series.diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    roll_up = up.ewm(span=period, adjust=False).mean()
    roll_down = down.abs().ewm(span=period, adjust=False).mean()
    RS = roll_up / roll_down
    return 100.0 - (100.0 / (1.0 + RS))

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def atr(high, low, close, period):
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def run():
    print("Downloading/loading data...")
    cache_dir = Path("data/research_cache")
    acquire(cache_dir, [2024, 2025, 2026], download=True)
    
    p24, _ = load_year(cache_dir, 2024)
    p25, _ = load_year(cache_dir, 2025)
    p26, _ = load_year(cache_dir, 2026)
    paired = pd.concat([p24, p25, p26])
    print(f"Loaded {len(paired)} M1 rows.")
    
    m15 = bars(paired, minutes=15)
    print(f"Generated {len(m15)} M15 bars.")
    
    m15['donchian_high'] = m15['high'].rolling(30).max().shift(1)
    m15['donchian_low'] = m15['low'].rolling(30).min().shift(1)
    m15['rsi'] = rsi(m15['close'], 14)
    m15['ema50'] = ema(m15['close'], 50)
    m15['atr'] = atr(m15['high'], m15['low'], m15['close'], 14)
    
    m15 = m15.dropna()
    m15['signal'] = 0
    buy_cond = (m15['close'] > m15['donchian_high']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] > m15['ema50'])
    sell_cond = (m15['close'] < m15['donchian_low']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] < m15['ema50'])
    
    m15.loc[buy_cond, 'signal'] = 1
    m15.loc[sell_cond, 'signal'] = -1
    
    print(f"Found {m15['signal'].abs().sum()} raw signals.")
    
    balance = 200.0
    max_risk_cap = 0.10
    
    trades = 0
    wins = 0
    peak = balance
    in_trade = False
    
    for i in range(len(m15)):
        if balance <= 0: break
        row = m15.iloc[i]
        
        if not in_trade and row['signal'] != 0:
            sl_dist = 2.5 * row['atr']
            tp_dist = 6.25 * row['atr']
            min_lot_risk = sl_dist * 1.0 # 0.01 lot
            
            if min_lot_risk > balance * max_risk_cap:
                continue
                
            in_trade = True
            entry_price = row['close']
            trade_dir = row['signal']
            trade_sl = entry_price - (trade_dir * sl_dist)
            trade_tp = entry_price + (trade_dir * tp_dist)
            
        elif in_trade:
            high, low = row['high'], row['low']
            hit_sl = False
            hit_tp = False
            
            if trade_dir == 1:
                if low <= trade_sl: hit_sl = True
                elif high >= trade_tp: hit_tp = True
            else:
                if high >= trade_sl: hit_sl = True
                elif low <= trade_tp: hit_tp = True
                
            if hit_sl or hit_tp:
                in_trade = False
                trades += 1
                if hit_tp:
                    wins += 1
                    balance += (min_lot_risk * (6.25 / 2.5)) 
                else:
                    balance -= min_lot_risk
                    
                if balance > peak: peak = balance

    print("--- RESULTS ---")
    print(f"Initial Balance: $200.0")
    print(f"Final Balance: ${balance:.2f}")
    print(f"Trades: {trades}")
    if trades > 0:
        print(f"Win Rate: {(wins/trades)*100:.2f}%")
        print(f"Max Peak: ${peak:.2f}")

run()
