import pandas as pd
import numpy as np

df = pd.read_csv('data/feedback_comparison_2026-09-28/continuous_B1_TP25_0.1.csv')
net_001 = (df['net'] / df['volume'] * 0.01).to_numpy()
reasons = df['reason'].to_numpy()

# Scenario 1: Original B1_TP25 (Target 2.5R, SL 2.5 ATR)
bal1 = 200.0
peak1 = 200.0
max_dd1 = 0.0
for n in net_001:
    bal1 += n
    if bal1 > peak1:
        peak1 = bal1
    dd = (peak1 - bal1) / peak1 * 100.0
    if dd > max_dd1:
        max_dd1 = dd

# Scenario 2: Truncate loss at -$30 (Basket SL cap of $30 on loss)
bal2 = 200.0
peak2 = 200.0
max_dd2 = 0.0
losses_capped = 0
for n in net_001:
    trade_net = max(n, -30.0) # Cap loss at -$30
    if n < -30.0:
        losses_capped += 1
    bal2 += trade_net
    if bal2 > peak2:
        peak2 = bal2
    dd = (peak2 - bal2) / peak2 * 100.0
    if dd > max_dd2:
        max_dd2 = dd

# Scenario 3: Basket TP logic (Take small profit e.g. +$10 or +$15 instead of waiting for full +$54 2.5R)
# What if winning trades were closed early at e.g. +$15 average (typical basket close)?
bal3 = 200.0
peak3 = 200.0
max_dd3 = 0.0
for n in net_001:
    if n > 0:
        trade_net = min(n, 15.0) # Early basket exit
    else:
        trade_net = max(n, -30.0) # Basket SL cap
    bal3 += trade_net
    if bal3 > peak3:
        peak3 = bal3
    dd = (peak3 - bal3) / peak3 * 100.0
    if dd > max_dd3:
        max_dd3 = dd

print("=" * 70)
print("COMPARISON: PROFIT & DRAWDOWN UNDER DIFFERENT MANAGEMENT RULES")
print("=" * 70)
print(f"1. Pure B1_TP25 (No Cap, Full 2.5R Targets):")
print(f"   Final Balance: ${bal1:.2f} (Profit: +${bal1-200:.2f} / +{(bal1/200-1)*100:.1f}%) | Max DD: {max_dd1:.2f}%")
print(f"\n2. B1_TP25 with $30 Hard Loss Cap (Keep 2.5R Targets):")
print(f"   Final Balance: ${bal2:.2f} (Profit: +${bal2-200:.2f} / +{(bal2/200-1)*100:.1f}%) | Max DD: {max_dd2:.2f}%")
print(f"   (Trades that hit cap: {losses_capped})")
print(f"\n3. Basket TP Mode (Early profit take +$15 avg, $30 SL cap):")
print(f"   Final Balance: ${bal3:.2f} (Profit: +${bal3-200:.2f} / +{(bal3/200-1)*100:.1f}%) | Max DD: {max_dd3:.2f}%")
print("=" * 70)
