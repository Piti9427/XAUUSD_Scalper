import os
import pandas as pd
import numpy as np
from pathlib import Path
from scripts.research.data import acquire, load_year, bars

def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    roll_up = up.ewm(span=period, adjust=False).mean()
    roll_down = down.ewm(span=period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))

def ema(series, period=50):
    return series.ewm(span=period, adjust=False).mean()

def atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def prepare_m15_data():
    cache_dir = Path("data/research_cache")
    acquire(cache_dir, [2024, 2025, 2026], download=True)
    dfs = {}
    for y in [2024, 2025, 2026]:
        paired, _ = load_year(cache_dir, y)
        m15 = bars(paired, minutes=15)
        m15['donchian_high'] = m15['high'].rolling(30).max().shift(1)
        m15['donchian_low'] = m15['low'].rolling(30).min().shift(1)
        m15['rsi'] = rsi(m15['close'], 14)
        m15['ema50'] = ema(m15['close'], 50)
        m15['atr'] = atr(m15['high'], m15['low'], m15['close'], 14)
        m15 = m15.dropna().copy()
        
        buy_cond = (m15['close'] > m15['donchian_high']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] > m15['ema50'])
        sell_cond = (m15['close'] < m15['donchian_low']) & (m15['rsi'] > 30) & (m15['rsi'] < 70) & (m15['close'] < m15['ema50'])
        
        m15['signal'] = 0
        m15.loc[buy_cond, 'signal'] = 1
        m15.loc[sell_cond, 'signal'] = -1
        m15['year'] = y
        dfs[y] = m15
    return dfs

def simulate(m15_df, initial_balance=200.0, fixed_lot=0.01, cost_per_trade=0.30):
    balance = initial_balance
    peak = balance
    max_dd_pct = 0.0
    equity_curve = [balance]
    
    trades = []
    in_trade = False
    trade_dir = 0
    trade_sl = 0.0
    trade_tp = 0.0
    min_lot_risk = 0.0
    entry_price = 0.0
    entry_time = None
    
    max_risk_cap = 0.10
    
    for idx, row in m15_df.iterrows():
        if balance <= 0:
            break
            
        current_time = idx
        
        if not in_trade:
            if row['signal'] != 0:
                sl_dist = 2.5 * row['atr']
                tp_dist = 6.25 * row['atr']
                # 0.01 lot = $1/point
                min_lot_risk = sl_dist * 1.0
                
                # Risk Cap: if risk > 10% of equity, reject
                if min_lot_risk > balance * max_risk_cap:
                    continue
                    
                in_trade = True
                trade_dir = row['signal']
                entry_price = row['close']
                entry_time = current_time
                trade_sl = entry_price - (trade_dir * sl_dist)
                trade_tp = entry_price + (trade_dir * tp_dist)
        else:
            high, low = row['high'], row['low']
            hit_sl = False
            hit_tp = False
            
            if trade_dir == 1:
                if low <= trade_sl:
                    hit_sl = True
                elif high >= trade_tp:
                    hit_tp = True
            else:
                if high >= trade_sl:
                    hit_sl = True
                elif low <= trade_tp:
                    hit_tp = True
                    
            if hit_sl or hit_tp:
                in_trade = False
                if hit_tp:
                    pnl = (min_lot_risk * (6.25 / 2.5)) - cost_per_trade
                    win = True
                else:
                    pnl = -min_lot_risk - cost_per_trade
                    win = False
                    
                balance += pnl
                if balance > peak:
                    peak = balance
                dd = (peak - balance) / peak * 100.0
                if dd > max_dd_pct:
                    max_dd_pct = dd
                    
                equity_curve.append(balance)
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': current_time,
                    'win': win,
                    'pnl': pnl,
                    'balance': balance,
                    'dir': trade_dir
                })

    trade_count = len(trades)
    wins = sum(1 for t in trades if t['win'])
    losses = trade_count - wins
    gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    wr = (wins / trade_count * 100.0) if trade_count > 0 else 0.0
    ret_pct = ((balance - initial_balance) / initial_balance) * 100.0

    return {
        'initial_balance': initial_balance,
        'final_balance': balance,
        'net_profit': balance - initial_balance,
        'return_pct': ret_pct,
        'trades': trade_count,
        'wins': wins,
        'losses': losses,
        'win_rate': wr,
        'profit_factor': pf,
        'max_dd_pct': max_dd_pct,
        'peak': peak
    }

def main():
    print("Preparing data...")
    dfs = prepare_m15_data()
    
    print("\n" + "="*80)
    print("PER-YEAR ISOLATED TEST (แต่ละปีเริ่มต้นพอร์ตใหม่ที่ $200)")
    print("="*80)
    
    for y in [2024, 2025, 2026]:
        res = simulate(dfs[y], initial_balance=200.0)
        print(f"--- YEAR {y} ---")
        print(f"  Trades: {res['trades']} | Win Rate: {res['win_rate']:.2f}% ({res['wins']}W / {res['losses']}L)")
        print(f"  Profit Factor: {res['profit_factor']:.2f}")
        print(f"  Start: ${res['initial_balance']:.2f} -> End: ${res['final_balance']:.2f} ({res['return_pct']:+.2f}%)")
        print(f"  Max Drawdown: {res['max_dd_pct']:.2f}% | Max Peak: ${res['peak']:.2f}\n")

    print("="*80)
    print("CONTINUOUS ACCUMULATION (เริ่มต้น $200 ม.ค. 2024 ถือต่อเนื่องถึง ส.ค. 2026)")
    print("="*80)
    all_df = pd.concat([dfs[2024], dfs[2025], dfs[2026]])
    res_all = simulate(all_df, initial_balance=200.0)
    print(f"  Total Trades: {res_all['trades']} | Win Rate: {res_all['win_rate']:.2f}% ({res_all['wins']}W / {res_all['losses']}L)")
    print(f"  Profit Factor: {res_all['profit_factor']:.2f}")
    print(f"  Start: ${res_all['initial_balance']:.2f} -> End: ${res_all['final_balance']:.2f} ({res_all['return_pct']:+.2f}%)")
    print(f"  Max Drawdown: {res_all['max_dd_pct']:.2f}% | Max Peak: ${res_all['peak']:.2f}\n")

    print("="*80)
    print("HALF-YEAR (6-MONTH) BREAKDOWN")
    print("="*80)
    # Split into 6-month chunks
    all_df['period'] = all_df.index.to_period('6M')
    for period, chunk in all_df.groupby('period'):
        res_p = simulate(chunk, initial_balance=200.0)
        print(f"--- Period {period} ---")
        print(f"  Trades: {res_p['trades']} | WR: {res_p['win_rate']:.1f}% | PF: {res_p['profit_factor']:.2f} | Return: {res_p['return_pct']:+.1f}% | Max DD: {res_p['max_dd_pct']:.1f}%")

if __name__ == '__main__':
    main()
