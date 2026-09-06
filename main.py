import logging
import time
import asyncio
from scripts.config_loader import ConfigError, load_config, setup_logging
from scripts.mt5_connector import MT5Connector
from scripts.strategy import XAUUSDSniperStrategy
from scripts.notifier import TelegramNotifier
from scripts.backtester import XAUUSDSniperBacktester
from scripts.news_service import NewsIntelligenceService
from scripts.gws_logger import GWSLogger
from scripts.insight_formatter import build_trade_insight


logger = logging.getLogger(__name__)


async def main():
    # 1. Load Configuration
    try:
        config = load_config()
        setup_logging(config)
    except ConfigError as exc:
        logging.basicConfig(level=logging.ERROR, format="%(levelname)s %(name)s - %(message)s")
        logger.error("Configuration error: %s", exc)
        return
    
    # 2. Initialize Components
    connector = MT5Connector(
        login=config['mt5']['login'],
        password=config['mt5']['password'],
        server=config['mt5']['server']
    )
    
    strategy = XAUUSDSniperStrategy(config)
    notifier = TelegramNotifier(config.get('telegram', {}))
    news_service = NewsIntelligenceService(config)
    gws_logger = GWSLogger(config)
    
    logger.info("XAUUSD Pro Sniper V2 starting")
    
    if not connector.connect():
        return

    # 3. Initial Multi-Timeframe Backtest
    logger.info("Running initial MTF backtest for last 500 candles")
    df_m15 = connector.get_candles(config['mt5']['symbol'], "M15", 500)
    df_h1 = connector.get_candles(config['mt5']['symbol'], "H1", 500)
    df_h4 = connector.get_candles(config['mt5']['symbol'], "H4", 500)
    
    if df_m15 is not None:
        backtester = XAUUSDSniperBacktester(strategy)
        backtester.run(df_m15, df_h1, df_h4)
        backtester.summary()

    # 4. Main Alert Loop
    logger.info("Monitoring %s with MTF filters", config['mt5']['symbol'])
    last_processed_time = None
    
    try:
        while True:
            # Check News Safety
            is_safe, news_event = news_service.is_safe_to_trade()
            if not is_safe:
                logger.warning("Trading paused: upcoming high-impact news (%s)", news_event)
                time.sleep(60)
                continue

            # Fetch Multi-Timeframe Data
            df_m15 = connector.get_candles(config['mt5']['symbol'], "M15", 100)
            df_h1 = connector.get_candles(config['mt5']['symbol'], "H1", 100)
            df_h4 = connector.get_candles(config['mt5']['symbol'], "H4", 100)
            
            if df_m15 is None or df_m15.empty:
                time.sleep(10)
                continue
            
            # Check for new candle
            current_candle_time = df_m15.iloc[-1]['time']
            if last_processed_time is None or current_candle_time != last_processed_time:
                logger.info("Candle check at %s", current_candle_time)
                
                df_m15 = strategy.calculate_indicators(df_m15)
                spread = connector.get_spread(config['mt5']['symbol'])
                signal = strategy.check_signals(df_m15, df_h1, df_h4, spread)
                
                if signal in ["BUY", "SELL"]:
                    last_closed = df_m15.iloc[-2]
                    entry_price = last_closed['close']
                    tp, sl = strategy.get_tp_sl(entry_price, signal, atr_value=last_closed.get('atr'))
                    
                    logger.info("%s signal found. Entry=%s TP=%s SL=%s", signal, entry_price, tp, sl)
                    
                    # 5. Sync to GWS & Notify Telegram
                    trade_data = {
                        "time": current_candle_time,
                        "symbol": config['mt5']['symbol'],
                        "type": signal,
                        "entry": entry_price,
                        "tp": tp,
                        "sl": sl,
                        "spread": spread,
                        "rsi": last_closed.get('rsi'),
                        "atr": last_closed.get('atr'),
                        "rationale": f"MTF align + MSS wick rejection + RSI {round(last_closed['rsi'], 2)}"
                    }
                    insight = build_trade_insight(trade_data)
                    logger.info(
                        "Insight: %s | %s | %s",
                        insight["headline"],
                        insight["risk"]["rr"],
                        insight["action"],
                    )
                    
                    await notifier.send_trade_insight(trade_data)
                    gws_logger.log_trade_to_sheets(trade_data)
                    gws_logger.log_journal_to_docs(trade_data)
                else:
                    logger.info("No trade signal: %s", signal)
                
                last_processed_time = current_candle_time
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        logger.info("Stopping XAUUSD Pro Sniper V2")
    finally:
        connector.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
