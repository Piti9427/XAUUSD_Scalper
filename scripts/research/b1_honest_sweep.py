import pandas as pd
import numpy as np
import json
from pathlib import Path
from itertools import product

DATA_DIR = Path("data/b1_hybrid_baseline_6mo_fixed_2026_09_28")
CAPITAL = 200.0
POSITION_SIZE = 1.0  # 1.0 for gold means $1 per point for 0.01 lot. (Contract 100 * 0.01 = 1)
COST_PER_TRADE = 0.30  # $0.30 spread + commission per trade for 0.01 lot XAUUSD

def load_signals():
    decisions = pd.read_csv(DATA_DIR / "continuous_decisions.csv")
    signals = decisions.copy()
    signals['signal_time'] = pd.to_datetime(signals['signal_time'])
    # Direction and entry already exist in continuous_decisions.csv
    return signals

def replay_with_bars(signals, bars, sl_mult, tp_mult, daily_limit_pct=0.40):
    balance = CAPITAL
    peak = CAPITAL
    max_dd = 0.0
    wins = 0
    losses = 0
    total_pnl = 0.0
    day_start_equity = {}
    
    bars = bars.sort_values('bar_open_utc').reset_index(drop=True)
    bar_times = bars['bar_open_utc'].values
    
    for _, sig in signals.iterrows():
        if balance <= 5.0:
            break  # Account blown
            
        direction = int(sig['direction'])
        atr = float(sig['atr'])
        entry = float(sig['entry'])
        
        sl_distance = atr * sl_mult
        tp_distance = atr * tp_mult
        
        # Daily loss limit
        day_key = sig['signal_time'].strftime('%Y-%m-%d')
        if day_key not in day_start_equity:
            day_start_equity[day_key] = balance
        day_start = day_start_equity[day_key]
        if day_start - balance >= day_start * daily_limit_pct:
            continue
            
        if direction == 1:
            stop = entry - sl_distance
            target = entry + tp_distance
        else:
            stop = entry + sl_distance
            target = entry - tp_distance
            
        signal_time = sig['signal_time']
        entry_idx = np.searchsorted(bar_times, np.datetime64(signal_time))
        
        outcome = None
        for i in range(entry_idx, len(bars)):
            bar = bars.iloc[i]
            high = float(bar['high'])
            low = float(bar['low'])
            
            if direction == 1:
                if low <= stop:
                    outcome = 'SL'
                    break
                if high >= target:
                    outcome = 'TP'
                    break
            else:
                if high >= stop:
                    outcome = 'SL'
                    break
                if low <= target:
                    outcome = 'TP'
                    break
                    
        if outcome is None:
            last_close = float(bars.iloc[-1]['close'])
            pnl = direction * (last_close - entry) * POSITION_SIZE - COST_PER_TRADE
        elif outcome == 'TP':
            pnl = tp_distance * POSITION_SIZE - COST_PER_TRADE
            wins += 1
        else:
            pnl = -sl_distance * POSITION_SIZE - COST_PER_TRADE
            losses += 1
            
        balance += pnl
        total_pnl += pnl
        peak = max(peak, balance)
        dd = (peak - balance) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)
        
    total_trades = wins + losses
    win_rate = wins / total_trades if total_trades > 0 else 0
    
    return {
        'sl_mult': sl_mult,
        'tp_mult': tp_mult,
        'final_balance': round(balance, 2),
        'return_pct': round((balance / CAPITAL - 1) * 100, 2),
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': round(win_rate * 100, 1),
        'max_dd_pct': round(max_dd * 100, 1),
        'profit_factor': round((wins * tp_distance) / (losses * sl_distance + COST_PER_TRADE*total_trades), 2) if losses > 0 else 0,
    }

def main():
    signals = load_signals()
    bars = pd.read_csv(DATA_DIR / "reference_bars.csv")
    bars['bar_open_utc'] = pd.to_datetime(bars['bar_open_utc'])
    
    sl_range = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5]
    tp_range = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.25]
    
    results = []
    for sl, tp in product(sl_range, tp_range):
        res = replay_with_bars(signals, bars, sl, tp)
        results.append(res)
        
    results.sort(key=lambda x: x['return_pct'], reverse=True)
    
    print("=" * 90)
    print(f"{'SL':>5} {'TP':>5} {'Return%':>10} {'Balance':>10} {'Trades':>8} {'WR%':>6} {'MaxDD%':>8} {'PF':>6}")
    print("=" * 90)
    for r in results[:15]:
        print(f"{r['sl_mult']:>5.2f} {r['tp_mult']:>5.2f} {r['return_pct']:>10.2f} {r['final_balance']:>10.2f} {r['total_trades']:>8} {r['win_rate']:>6.1f} {r['max_dd_pct']:>8.1f} {r['profit_factor']:>6.2f}")

    profitable = [r for r in results if r['return_pct'] > 0]
    print(f"\n🟢 PROFITABLE configs found: {len(profitable)}")

if __name__ == '__main__':
    main()
