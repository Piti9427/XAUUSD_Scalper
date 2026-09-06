import asyncio
import logging
import time
from datetime import datetime, timezone
from scripts.config_loader import load_config, setup_logging, ConfigError
from scripts.mt5_connector import MT5Connector
from scripts.smc.types import AccountState, OrderIntent, OrderIntentType, Direction
from scripts.smc.liquidity import compute_liquidity_levels
from scripts.smc.detection import detect_smc_setup
from scripts.smc.orchestrator import StrategyOrchestrator
from scripts.smc.mt5_adapter import SMCExecutionAdapter
from scripts.smc.news import NewsManager
from scripts.smc.risk import calculate_lot_size
from scripts.smc.chart import generate_setup_chart
from scripts.smc.notifier import (
    SMCTelegramNotifier,
    format_order_filled_card,
    format_be_moved_card,
    format_trade_closed_card,
    format_circuit_breaker_card,
)

logger = logging.getLogger(__name__)


async def run_smc_live_copilot():
    # 1. Load configuration
    try:
        config = load_config()
        setup_logging(config)
    except ConfigError as exc:
        logging.basicConfig(level=logging.ERROR)
        logger.error("Configuration error: %s", exc)
        return

    symbol = config.get("mt5", {}).get("symbol", "XAUUSD")
    max_spread = config.get("strategy", {}).get("max_spread", 0.35)
    logger.info("Initializing SMC v1 Live Engine for %s (Max Spread: $%.2f)", symbol, max_spread)

    # 2. Connectors and Adapters
    connector = MT5Connector(
        login=config["mt5"]["login"],
        password=config["mt5"]["password"],
        server=config["mt5"]["server"],
    )
    is_connected = connector.connect()
    dry_run = not is_connected

    adapter = SMCExecutionAdapter(symbol=symbol, dry_run=dry_run)
    orchestrator = StrategyOrchestrator()
    news_mgr = NewsManager()
    notifier = SMCTelegramNotifier(config)
    account = AccountState(balance=10000.0, equity=10000.0)

    last_processed_m5_time = None
    last_news_fetch_time = 0.0
    cached_news_events = []
    circuit_breaker_alerted = False

    logger.info("SMC v1 Live Loop Running (Dry Run: %s, Telegram: %s)", dry_run, notifier.enabled)

    try:
        while True:
            now_utc = datetime.now(timezone.utc)

            # 3. Auto-fetch ForexFactory Calendar (every 4 hours)
            if time.time() - last_news_fetch_time > 14400:
                try:
                    cached_news_events = news_mgr.fetch_forexfactory_calendar()
                    last_news_fetch_time = time.time()
                    logger.info("Refreshed economic news calendar: %d high-impact USD events", len(cached_news_events))
                except Exception as exc:
                    logger.warning("Could not refresh economic calendar: %s", exc)

            # 4. Check News Blackout Window (+/- 30 min)
            is_blackout, news_title = news_mgr.is_in_blackout(now_utc, cached_news_events, window_mins=30)
            if is_blackout:
                logger.warning("News Blackout active: %s. Skipping new setups.", news_title)

            # 5. Query Live Spread
            spread_raw = connector.get_spread(symbol)
            current_spread = None
            if spread_raw is not None:
                # If broker quotes in points (e.g. 15 or 25 points = $0.15 or $0.25)
                current_spread = (spread_raw * 0.01) if spread_raw > 1.0 else float(spread_raw)
            elif dry_run:
                current_spread = 0.15

            # 6. Fetch Multi-Timeframe Candles (500 M5 bars = ~41 hours to cover Asian Range & PDH/PDL)
            df_m5 = connector.get_candles(symbol, "M5", 500)
            df_h1 = connector.get_candles(symbol, "H1", 250)

            if df_m5 is not None and len(df_m5) >= 2:
                current_m5_time = df_m5.iloc[-1]["time"]

                if last_processed_m5_time is None or current_m5_time != last_processed_m5_time:
                    last_processed_m5_time = current_m5_time
                    last_closed_bar = df_m5.iloc[-2].to_dict()
                    bar_time = last_closed_bar["time"]

                    logger.info("Evaluating M5 Bar closed at %s (Spread: %s)", bar_time, f"${current_spread:.2f}" if current_spread else "N/A")

                    # Reset circuit breaker alert on new UTC day
                    bar_date_str = bar_time.date().isoformat() if hasattr(bar_time, "date") else now_utc.date().isoformat()
                    if account.current_utc_date != bar_date_str:
                        circuit_breaker_alerted = False

                    # Pre-News Safeguard Evaluation (ADR-010: 15 min before red news)
                    if account.open_position is not None and cached_news_events:
                        pre_action = news_mgr.evaluate_pre_news_position(
                            current_time=now_utc,
                            events=cached_news_events,
                            position=account.open_position,
                            current_price=last_closed_bar["close"],
                            pre_window_mins=15
                        )
                        if pre_action == OrderIntentType.MOVE_SL_TO_BE and not account.open_position.be_moved:
                            account.open_position.be_moved = True
                            account.open_position.sl_price = account.open_position.entry_price
                            adapter.execute_intent(OrderIntent(
                                intent_type=OrderIntentType.MOVE_SL_TO_BE,
                                direction=account.open_position.direction,
                                sl_price=account.open_position.entry_price,
                                reason="Pre-News Safeguard: Locked BE",
                            ))
                            if not account.open_position.be_alerted:
                                await notifier.send_message(format_be_moved_card(account.open_position, symbol))
                                account.open_position.be_alerted = True
                        elif pre_action == OrderIntentType.CLOSE_MARKET:
                            adapter.execute_intent(OrderIntent(
                                intent_type=OrderIntentType.CLOSE_MARKET,
                                direction=account.open_position.direction,
                                reason="Pre-News Safeguard: Closed (< 1.0R profit)",
                            ))
                            await notifier.send_message(format_trade_closed_card(
                                direction=account.open_position.direction,
                                exit_price=last_closed_bar["close"],
                                pnl_dollars=0.0,
                                pnl_r=0.0,
                                reason="Pre-News Safeguard Closure (< 1.0R profit)",
                                symbol=symbol,
                            ))
                            account.open_position = None

                    # Liquidity levels
                    target_date = bar_time.date() if hasattr(bar_time, "date") else now_utc.date()
                    liquidity = compute_liquidity_levels(df_m5, target_date)

                    # Pure Detection Seam (skip if blackout)
                    setup = None
                    if account.open_position is None and account.pending_order is None and not is_blackout:
                        setup = detect_smc_setup(
                            h1_candles=df_h1,
                            m5_candles=df_m5,
                            liquidity=liquidity,
                            current_time=bar_time,
                            current_spread=current_spread,
                            max_spread=max_spread,
                        )

                    if setup is not None:
                        logger.info("Found SMC Setup: %s at %s", setup.direction.value, setup.entry_price)
                        chart_path = generate_setup_chart(df_m5, setup)
                        lot_calc = calculate_lot_size(account.balance, setup.entry_price, setup.sweep_wick)
                        lot_val = lot_calc.lot_size if lot_calc.is_valid else 0.01
                        await notifier.send_alert(
                            signal=setup,
                            lot_size=lot_val,
                            risk_amount=account.balance * 0.005,
                            chart_image_path=chart_path,
                        )

                    # Step Orchestrator
                    intents = orchestrator.on_bar(
                        bar=last_closed_bar,
                        account=account,
                        setup_signal=setup,
                        current_spread=current_spread,
                        max_spread=max_spread,
                    )

                    for intent in intents:
                        logger.info("Executing OrderIntent: %s (%s)", intent.intent_type.value, intent.reason)
                        res = adapter.execute_intent(intent)
                        logger.info("Execution Result: %s", res.message)

                    # Check Milestone Notifications
                    if account.open_position is not None:
                        # Order Filled Alert
                        if not account.open_position.fill_alerted:
                            await notifier.send_message(format_order_filled_card(account.open_position, symbol))
                            account.open_position.fill_alerted = True

                        # Breakeven Alert
                        if account.open_position.be_moved and not account.open_position.be_alerted:
                            await notifier.send_message(format_be_moved_card(account.open_position, symbol))
                            account.open_position.be_alerted = True

                    # Circuit Breaker Alert
                    if account.daily_loss_count >= orchestrator.max_daily_losses and not circuit_breaker_alerted:
                        await notifier.send_message(
                            format_circuit_breaker_card(account.daily_loss_count, orchestrator.cooldown_minutes, symbol)
                        )
                        circuit_breaker_alerted = True

            await asyncio.sleep(10)

    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("SMC v1 Live Loop stopped.")
    finally:
        connector.disconnect()


if __name__ == "__main__":
    asyncio.run(run_smc_live_copilot())
