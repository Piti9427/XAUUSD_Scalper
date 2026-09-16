import pandas as pd
import logging

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from scripts.smc.mt5_init import initialize_mt5


logger = logging.getLogger(__name__)

TIMEFRAMES = {
    "M1": getattr(mt5, "TIMEFRAME_M1", 1) if mt5 else 1,
    "M5": getattr(mt5, "TIMEFRAME_M5", 5) if mt5 else 5,
    "M15": getattr(mt5, "TIMEFRAME_M15", 15) if mt5 else 15,
    "M30": getattr(mt5, "TIMEFRAME_M30", 30) if mt5 else 30,
    "H1": getattr(mt5, "TIMEFRAME_H1", 60) if mt5 else 60,
    "H4": getattr(mt5, "TIMEFRAME_H4", 240) if mt5 else 240,
}


class MT5Connector:
    def __init__(self, login, password, server, terminal_path=None):
        self.login = login
        self.password = password
        self.server = server
        self.terminal_path = terminal_path

    def connect(self):
        """Initializes MT5 and logs into the account."""
        if mt5 is None:
            logger.error("MetaTrader5 package is not installed. Run pip install -r requirements.txt.")
            return False

        init = initialize_mt5(mt5, path=self.terminal_path)
        if not init.ok:
            logger.error(
                "MT5 initialize failed (%s), error code: %s",
                init.detail,
                init.last_error,
            )
            return False

        # Already logged in via initialize(login=...) when credentials passed there;
        # otherwise explicit login for account switch (Exness Demo).
        if self.login:
            authorized = mt5.login(self.login, password=self.password, server=self.server)
            if not authorized:
                logger.error(
                    "Failed to connect to account %s, error code: %s",
                    self.login,
                    mt5.last_error(),
                )
                return False

        logger.info("Successfully connected to MT5 account %s", self.login)
        return True

    def get_candles(self, symbol, timeframe_str, count):
        """Fetches candle data for a given symbol and timeframe."""
        if timeframe_str not in TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe {timeframe_str!r}. Supported: {', '.join(TIMEFRAMES)}")

        if mt5 is None:
            logger.warning("MetaTrader5 package is not installed; cannot fetch live candles.")
            return None

        tf = TIMEFRAMES[timeframe_str]
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        
        if rates is None:
            logger.warning("No rates found for %s %s, error code: %s", symbol, timeframe_str, mt5.last_error())
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        logger.debug("Fetched %s candles for %s %s", len(df), symbol, timeframe_str)
        return df

    def get_spread(self, symbol):
        """Gets the current spread for the symbol."""
        if mt5 is None:
            return None
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.warning("No symbol info found for %s", symbol)
            return None
        ask = getattr(symbol_info, "ask", None)
        bid = getattr(symbol_info, "bid", None)
        if ask is not None and bid is not None and ask > 0 and bid > 0:
            return round(float(ask) - float(bid), 4)
        return symbol_info.spread

    def disconnect(self):
        """Shuts down MT5 connection."""
        if mt5 is not None:
            mt5.shutdown()
