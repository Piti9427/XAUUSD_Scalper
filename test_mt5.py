from scripts.config_loader import ConfigError, load_config, setup_logging
from scripts.mt5_connector import MT5Connector

def test_connection():
    # Load settings
    try:
        config = load_config()
        setup_logging(config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return
    
    # Initialize connector
    connector = MT5Connector(
        login=config['mt5']['login'],
        password=config['mt5']['password'],
        server=config['mt5']['server']
    )
    
    if connector.connect():
        # Test fetching data
        df = connector.get_candles(config['mt5']['symbol'], config['mt5']['timeframe'], 10)
        if df is not None:
            print("\nLatest 10 Candles:")
            print(df[['time', 'open', 'high', 'low', 'close']])
            
            spread = connector.get_spread(config['mt5']['symbol'])
            print(f"\nCurrent Spread: {spread} points")
        
        connector.disconnect()

if __name__ == "__main__":
    test_connection()
