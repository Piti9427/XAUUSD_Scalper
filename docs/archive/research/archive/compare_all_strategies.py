import pandas as pd
import numpy as np
from pathlib import Path
from scripts.research.data import load_year, bars

def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    roll_up = up.ewm(span=period, adjust=False).mean()
    roll_down = down.ewm(span=period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

print("Loading 2024-2026 data...")
cache_dir = Path("data/research_cache")
p24, _ = load_year(cache_dir, 2024)
p25, _ = load_year(cache_dir, 2025)
p26, _ = load_year(cache_dir, 2026)
paired = pd.concat([p24, p25, p26])
m15 = bars(paired, minutes=15)
print(f"Total M15 bars: {len(m15)}")

# Indicators
m15['rsi'] = rsi(m15['close'], 14)
m15['ema20'] = ema(m15['close'], 20)
m15['ema50'] = ema(m15['close'], 50)
m15['ema200'] = ema(m15['close'], 200)
m15['atr'] = atr(m15['high'], m15['low'], m15['close'], 14)

for n in [20, 30, 40]:
    m15[f'donchian_high_{n}'] = m15['high'].rolling(n).max().shift(1)
    m15[f'donchian_low_{n}'] = m15['low'].rolling(n).min().shift(1)

m15 = m15.dropna().copy()

def backtest_signals(signal_series, sl_mult, tp_mult, name):
    balance = 200.0
    peak = balance
    max_dd_pct = 0.0
    trades = []
    in_trade = False
    trade_dir = 0
    trade_sl = 0.0
    trade_tp = 0.0
    min_lot_risk = 0.0
    
    for idx, row in m15.iterrows():
        if balance <= 0:
            break
        sig = signal_series.loc[idx]
        
        if not in_trade:
            if sig != 0:
                sl_dist = sl_mult * row['atr']
                tp_dist = tp_mult * row['atr']
                min_lot_risk = sl_dist * 1.0
                if min_lot_risk > balance * 0.10:
                    continue
                in_trade = True
                trade_dir = sig
                entry_price = row['close']
                trade_sl = entry_price - (trade_dir * sl_dist)
                trade_tp = entry_price + (trade_dir * tp_dist)
        else:
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
                if hit_tp:
                    pnl = (min_lot_risk * (tp_mult / sl_mult)) - 0.30
                    win = True
                else:
                    pnl = -min_lot_risk - 0.30
                    win = False
                balance += pnl
                if balance > peak: peak = balance
                dd = (peak - balance) / peak * 100.0
                if dd > max_dd_pct: max_dd_pct = dd
                trades.append(win)
                
    total = len(trades)
    wins = sum(trades)
    wr = (wins / total * 100) if total > 0 else 0
    ret = ((balance - 200.0) / 200.0) * 100
    return {
        'name': name,
        'final': balance,
        'ret_pct': ret,
        'trades': total,
        'wr': wr,
        'max_dd': max_dd_pct,
        'sl': sl_mult,
        'tp': tp_mult
    }

candidates = []

# Strategy 1: Core Strategy (Pure B1: Donchian 30 + RSI Guard + EMA 50)
sig_core = pd.Series(0, index=m15.index)
sig_core.loc[(m15['close'] > m15['donchian_high_30']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] > m15['ema50'])] = 1
sig_core.loc[(m15['close'] < m15['donchian_low_30']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] < m15['ema50'])] = -1
for sl, tp in [(2.5, 6.25), (2.5, 5.0), (2.5, 3.0), (2.0, 5.0), (2.0, 4.0)]:
    candidates.append(backtest_signals(sig_core, sl, tp, f"Pure_B1_Donchian30_RSI_EMA50 (SL{sl}/TP{tp})"))

# Strategy 2: Donchian 20 + RSI + EMA 50
sig_d20 = pd.Series(0, index=m15.index)
sig_d20.loc[(m15['close'] > m15['donchian_high_20']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] > m15['ema50'])] = 1
sig_d20.loc[(m15['close'] < m15['donchian_low_20']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] < m15['ema50'])] = -1
for sl, tp in [(2.5, 6.25), (2.0, 4.0), (2.5, 3.0)]:
    candidates.append(backtest_signals(sig_d20, sl, tp, f"Donchian20_RSI_EMA50 (SL{sl}/TP{tp})"))

# Strategy 3: Donchian 40 + RSI + EMA 50
sig_d40 = pd.Series(0, index=m15.index)
sig_d40.loc[(m15['close'] > m15['donchian_high_40']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] > m15['ema50'])] = 1
sig_d40.loc[(m15['close'] < m15['donchian_low_40']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] < m15['ema50'])] = -1
for sl, tp in [(2.5, 6.25), (2.5, 5.0)]:
    candidates.append(backtest_signals(sig_d40, sl, tp, f"Donchian40_RSI_EMA50 (SL{sl}/TP{tp})"))

# Strategy 4: Pure Donchian 30 (NO RSI, NO EMA)
sig_d30_raw = pd.Series(0, index=m15.index)
sig_d30_raw.loc[m15['close'] > m15['donchian_high_30']] = 1
sig_d30_raw.loc[m15['close'] < m15['donchian_low_30']] = -1
candidates.append(backtest_signals(sig_d30_raw, 2.5, 6.25, "Donchian30_NoFilters (SL2.5/TP6.25)"))

# Strategy 5: EMA 20 x 50 Crossover (Trend Following)
sig_ema = pd.Series(0, index=m15.index)
sig_ema.loc[(m15['ema20'] > m15['ema50']) & (m15['ema20'].shift(1) <= m15['ema50'].shift(1))] = 1
sig_ema.loc[(m15['ema20'] < m15['ema50']) & (m15['ema20'].shift(1) >= m15['ema50'].shift(1))] = -1
for sl, tp in [(2.0, 4.0), (2.5, 6.25)]:
    candidates.append(backtest_signals(sig_ema, sl, tp, f"EMA20x50_Cross (SL{sl}/TP{tp})"))

# Strategy 6: RSI Reversal (Mean Reversion: Buy <30, Sell >70)
sig_rsi = pd.Series(0, index=m15.index)
sig_rsi.loc[(m15['rsi'] > 30) & (m15['rsi'].shift(1) <= 30)] = 1
sig_rsi.loc[(m15['rsi'] < 70) & (m15['rsi'].shift(1) >= 70)] = -1
for sl, tp in [(1.5, 2.0), (2.0, 3.0)]:
    candidates.append(backtest_signals(sig_rsi, sl, tp, f"RSI_Reversal (SL{sl}/TP{tp})"))

df_res = pd.DataFrame(candidates)
df_res['calmar'] = df_res['ret_pct'] / df_res['max_dd'].replace(0, np.nan)
df_res = df_res.sort_values('ret_pct', ascending=False)

print("\n" + "="*100)
print("TOURNAMENT RESULTS: UNBIASED REAL-DATA BACKTEST (2024 - 2026)")
print("="*100)
for idx, r in df_res.iterrows():
    print(f"{r['name']:<45} | Ret: {r['ret_pct']:+7.1f}% | Balance: ${r['final']:7.2f} | Max DD: {r['max_dd']:4.1f}% | WR: {r['wr']:4.1f}% | Trades: {r['trades']:3d} | Calmar: {r['calmar']:5.2f}")
