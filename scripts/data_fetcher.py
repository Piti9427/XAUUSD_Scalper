import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import os

def fetch_data(symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M15, count=10000):
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        return None

    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    mt5.shutdown()
    
    if rates is None:
        print("Failed to fetch rates")
        return None
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

if __name__ == "__main__":
    df = fetch_data()
    if df is not None:
        os.makedirs("data", exist_ok=True)
        df.to_csv("data/XAUUSD_M15.csv", index=False)
        print(f"Fetched {len(df)} rows and saved to data/XAUUSD_M15.csv")
