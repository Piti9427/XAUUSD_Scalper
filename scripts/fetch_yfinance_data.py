import yfinance as yf
import os


def fetch_gold_data():
    symbol = "GC=F"  # Gold Futures
    # symbol = "XAUUSD=X" # Spot Gold (Yahoo symbol)

    print(f"Fetching data for {symbol}...")

    # Target: 1 hour data for the last 730 days
    # (yfinance limit for 1h is 730 days)
    data = yf.download(symbol, period="725d", interval="1h")

    if data.empty:
        print("Failed to fetch 1h data. Trying daily data...")
        data = yf.download(symbol, period="2y", interval="1d")
        filename = "XAUUSD_D1.csv"
    else:
        filename = "XAUUSD_H1.csv"

    if not data.empty:
        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)

        filepath = os.path.join("data", filename)
        data.to_csv(filepath)
        print(f"Successfully saved data to {filepath}")
        print(f"Total rows: {len(data)}")
        print(f"Data range: {data.index[0]} to {data.index[-1]}")

    # Also fetch M15 data for the last 59 days (Yahoo limit)
    print(f"\nFetching M15 data for {symbol} (last 59 days)...")
    m15_data = yf.download(symbol, period="59d", interval="15m")
    if not m15_data.empty:
        m15_filepath = os.path.join("data", "XAUUSD_M15.csv")
        m15_data.to_csv(m15_filepath)
        print(f"Successfully saved M15 data to {m15_filepath}")
        print(f"Total rows: {len(m15_data)}")
        print(f"Data range: {m15_data.index[0]} to {m15_data.index[-1]}")
    else:
        print("Could not fetch M15 data.")


if __name__ == "__main__":
    fetch_gold_data()
