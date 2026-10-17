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

m15['rsi'] = rsi(m15['close'], 14)
m15['ema50'] = ema(m15['close'], 50)
m15['atr'] = atr(m15['high'], m15['low'], m15['close'], 14)
m15['don_h30'] = m15['high'].rolling(30).max().shift(1)
m15['don_l30'] = m15['low'].rolling(30).min().shift(1)
m15 = m15.dropna().copy()

def test_signals(sig, name, start_date=None):
    df = m15 if start_date is None else m15[m15.index >= start_date]
    balance = 200.0
    peak = balance
    max_dd = 0.0
    trades = []
    in_trade = False
    trade_dir = 0
    trade_sl = 0.0
    trade_tp = 0.0
    risk = 0.0

    for idx, row in df.iterrows():
        if balance <= 0:
            break
        s = sig.loc[idx]
        if not in_trade:
            if s != 0:
                sl_d = 2.5 * row['atr']
                tp_d = 6.25 * row['atr']
                risk = sl_d * 1.0
                if risk > balance * 0.10:
                    continue
                in_trade = True
                trade_dir = s
                trade_sl = row['close'] - (s * sl_d)
                trade_tp = row['close'] + (s * tp_d)
        else:
            h, l = row['high'], row['low']
            hit_sl = (l <= trade_sl) if trade_dir == 1 else (h >= trade_sl)
            hit_tp = (h >= trade_tp) if trade_dir == 1 else (l <= trade_tp)
            if hit_sl or hit_tp:
                in_trade = False
                pnl = (risk * (6.25 / 2.5) - 0.30) if hit_tp else (-risk - 0.30)
                balance += pnl
                if balance > peak:
                    peak = balance
                dd = (peak - balance) / peak * 100.0
                if dd > max_dd:
                    max_dd = dd
                trades.append(hit_tp)
    w = sum(trades)
    t = len(trades)
    ret = ((balance - 200.0) / 200.0) * 100
    wr = (w / t * 100) if t > 0 else 0
    print(f"{name:<50} | End: ${balance:7.2f} ({ret:+6.1f}%) | Max DD: {max_dd:4.1f}% | WR: {wr:4.1f}% | Trades: {t:3d}")

# 1. Archived B1: RSI BUY <= 75, SELL >= 25, NO EMA50
sig_archived = pd.Series(0, index=m15.index)
sig_archived.loc[(m15['close'] > m15['don_h30']) & (m15['rsi'] <= 75)] = 1
sig_archived.loc[(m15['close'] < m15['don_l30']) & (m15['rsi'] >= 25)] = -1

# 2. Target B1: RSI 30..70, WITH EMA50
sig_target = pd.Series(0, index=m15.index)
sig_target.loc[(m15['close'] > m15['don_h30']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] > m15['ema50'])] = 1
sig_target.loc[(m15['close'] < m15['don_l30']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] < m15['ema50'])] = -1

# 3. Hybrid: RSI BUY <= 75, SELL >= 25, WITH EMA50
sig_hybrid = pd.Series(0, index=m15.index)
sig_hybrid.loc[(m15['close'] > m15['don_h30']) & (m15['rsi'] <= 75) & (m15['close'] > m15['ema50'])] = 1
sig_hybrid.loc[(m15['close'] < m15['don_l30']) & (m15['rsi'] >= 25) & (m15['close'] < m15['ema50'])] = -1

print("\n" + "="*95)
print("TEST A: FULL 2.7 YEARS (Jan 2024 - Aug 2026)")
print("="*95)
test_signals(sig_archived, "1. Archived (+342% base): RSI<=75/>=25, NO EMA50")
test_signals(sig_target,   "2. Target in CORE_STRATEGY: RSI 30-70, WITH EMA50")
test_signals(sig_hybrid,   "3. Hybrid: RSI<=75/>=25 + WITH EMA50")

print("\n" + "="*95)
print("TEST B: 6-MONTH ORIGINAL WINDOW (Mar 28, 2026 - Aug 31, 2026)")
print("="*95)
test_signals(sig_archived, "1. Archived (+342% base): RSI<=75/>=25, NO EMA50", start_date="2026-03-28")
test_signals(sig_target,   "2. Target in CORE_STRATEGY: RSI 30-70, WITH EMA50", start_date="2026-03-28")
test_signals(sig_hybrid,   "3. Hybrid: RSI<=75/>=25 + WITH EMA50", start_date="2026-03-28")
