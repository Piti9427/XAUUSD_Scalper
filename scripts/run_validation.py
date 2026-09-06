import pandas as pd
import yaml
import os
from scripts.strategy import XAUUSDSniperStrategy
from scripts.backtester import XAUUSDSniperBacktester

def run_validation():
    # 1. Load Configuration
    config_path = "config/settings.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # 2. Load Data
    data_path = "data/XAUUSD_M15.csv"
    h1_path = "data/XAUUSD_H1.csv"
    
    if not os.path.exists(data_path):
        print(f"❌ Error: Data file {data_path} not found.")
        return

    # yfinance M15 CSV has 3 header rows: Price, Ticker, Datetime
    # We'll skip the first 3 rows and manually name the columns
    def load_clean_data(path):
        try:
            # Read all lines to find where data starts
            with open(path, 'r') as f:
                lines = f.readlines()
            
            # Find the line that starts with a date pattern (e.g. 2026-)
            start_idx = 0
            for i, line in enumerate(lines):
                if line.startswith('20'): # Matches '2026-...'
                    start_idx = i
                    break
            
            # Column names based on head inspection: Datetime, Close, High, Low, Open, Volume
            df = pd.read_csv(path, skiprows=start_idx, header=None, 
                             names=['time', 'close', 'high', 'low', 'open', 'tick_volume'])
            df['time'] = pd.to_datetime(df['time'])
            
            # Sort by time just in case
            df = df.sort_values('time').reset_index(drop=True)
            return df
        except Exception as e:
            print(f"❌ Error loading {path}: {e}")
            return None

    df_m15 = load_clean_data(data_path)
    if df_m15 is None: return
    
    # Load H1 for MTF filters
    if os.path.exists(h1_path):
        df_h1 = load_clean_data(h1_path)
    else:
        df_h1 = df_m15.copy()
        
    df_h4 = df_h1.copy() # Strategy expects H4, using H1 as proxy for baseline

    # 3. Initialize Strategy and Backtester
    strategy = XAUUSDSniperStrategy(config)
    backtester = XAUUSDSniperBacktester(strategy)

    print(f"🚀 Starting Validation Backtest on {len(df_m15)} candles...")
    print(f"Strategy: Omni-Sniper (Sweep + MSS)")
    print(f"Timeframe: M15 | Focus: NY Session (11:00-16:00 UTC)")
    
    # 4. Run Simulation
    trades = backtester.run(df_m15, df_h1, df_h4)
    
    # 5. Calculate & Report Metrics
    if trades:
        trades_df = backtester.summary()
        
        # Calculate additional metrics
        wins = trades_df[trades_df['result'] == 'TP']
        losses = trades_df[trades_df['result'] == 'SL']
        
        total_wins = len(wins)
        total_losses = len(losses)
        
        # Approximate profit in points (Gold: 1 pip = 0.1 points)
        tp_points = config['strategy']['tp_pips'] * 0.1
        sl_points = config['strategy']['sl_pips'] * 0.1
        
        gross_profit = total_wins * tp_points
        gross_loss = total_losses * sl_points
        net_profit_points = gross_profit - gross_loss
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        expectancy = net_profit_points / (total_wins + total_losses) if (total_wins + total_losses) > 0 else 0
        
        print("\n" + "="*30)
        print("📈 DETAILED PERFORMANCE")
        print("="*30)
        print(f"Profit Factor:  {profit_factor:.2f}")
        print(f"Expectancy:     {expectancy:.2f} points/trade")
        print(f"Net Points:     {net_profit_points:.2f}")
        print(f"Est. Profit:    ${net_profit_points * 10:.2f} (per 0.10 lot)") # Simplified
        print("="*30 + "\n")
        
        # Print a sample of trades
        print("📝 Last 5 Trades Sample:")
        print(trades_df.tail(5)[['time', 'type', 'entry', 'result']])
    else:
        print("⚠️ No trades triggered. Check strategy filters (Time/Spread) or Data overlap.")

if __name__ == "__main__":
    run_validation()
