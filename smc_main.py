import asyncio
import logging
import time
from datetime import datetime, timezone
from scripts.config_loader import load_config, setup_logging, ConfigError
from scripts.mt5_connector import MT5Connector
from scripts.smc.types import AccountState, OrderIntent, OrderIntentType, Direction
from scripts.smc.liquidity import compute_liquidity_levels
from scripts.smc.detection import evaluate_smc_setup
from scripts.smc.real_money_approval import require_real_money_approval
from scripts.smc.orchestrator import StrategyOrchestrator
from scripts.smc.mt5_adapter import SMCExecutionAdapter
from scripts.smc.news import NewsManager
from scripts.smc.risk import calculate_lot_size
from scripts.smc.risk_halt import (
    load_risk_halt_state,
    new_risk_halt_state,
    observe_equity,
    record_net_losing_trade,
    save_risk_halt_state,
)
from scripts.smc.halt_actions import plan_halt_flatten_intents
from scripts.smc.warmup import H1_WARMUP_BARS, h1_warmup_ok
from scripts.smc.account_sync import apply_broker_capital
from pathlib import Path
from scripts.smc.notifier import (
    SMCTelegramNotifier,
    format_order_filled_card,
    format_be_moved_card,
    format_partial_tp_card,
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
    if is_connected:
        # This loop mutates local position state before broker confirmation and
        # sizes orders from a fixed account balance. Keep it offline-only until
        # broker reconciliation owns the full order lifecycle.
        connector.disconnect()
        raise RuntimeError("SMC legacy loop live execution is disabled; use the broker-reconciled webhook bridge for demo validation")
    dry_run = not is_connected
    # Story 49: Demo readiness ≠ real-money. Live non-demo needs dual approval.
    allow_demo_only = bool(config.get("mt5", {}).get("allow_demo_only", True))
    real_money_cfg = config.get("real_money", {}) or {}
    require_real_money_approval(
        dry_run=dry_run,
        allow_demo_only=allow_demo_only,
        config_approved=bool(real_money_cfg.get("approved", False)),
    )

    strat_cfg = config.get("strategy", {})
    adapter = SMCExecutionAdapter(symbol=symbol, dry_run=dry_run)
    orchestrator = StrategyOrchestrator(
        max_daily_losses=strat_cfg.get("max_daily_losses", 2),
        cooldown_minutes=strat_cfg.get("cooldown_mins", 30),
        ttl_expire_bars=strat_cfg.get("order_ttl_bars", 4),
        max_sl_cap=strat_cfg.get("max_sl_cap", 25.0),
        partial_tp_enabled=strat_cfg.get("partial_tp_enabled", False),
        partial_tp_r=strat_cfg.get("partial_tp_r", 1.0),
        partial_tp_ratio=strat_cfg.get("partial_tp_ratio", 0.5),
        be_enabled=bool(strat_cfg.get("be_enabled", False)),
        be_trigger_r=strat_cfg.get("be_trigger_r", 1.0),
        risk_pct=float(strat_cfg.get("risk_pct", 0.005)),
    )
    news_mgr = NewsManager()
    notifier = SMCTelegramNotifier({"telegram": {"enabled": False}})
    account = AccountState(balance=10000.0, equity=10000.0)
    risk_halt_path = Path(strat_cfg.get("risk_halt_path", "data/risk_halt_state.json"))
    risk_halt = load_risk_halt_state(risk_halt_path) or new_risk_halt_state(account.equity)
    if risk_halt.halted:
        logger.error("Persistent risk halt active on startup: drawdown=%s daily=%s losses=%s",
                     risk_halt.drawdown_halt, risk_halt.daily_equity_halt, risk_halt.net_losing_trades_today)

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
                    cached_news_events = await asyncio.to_thread(news_mgr.fetch_forexfactory_calendar)
                    last_news_fetch_time = time.time()
                    logger.info("Refreshed economic news calendar: %d high-impact USD events", len(cached_news_events))
                except Exception as exc:
                    logger.warning("Could not refresh economic calendar: %s", exc)

            # 4. Foundation news admission: unknown schedule or USD HIGH blackout blocks new risk
            schedule_known = last_news_fetch_time > 0
            allowed_news, news_reason = news_mgr.new_risk_allowed(
                now_utc,
                cached_news_events,
                schedule_known=schedule_known,
                window_mins=30,
            )
            is_blackout = not allowed_news
            news_title = news_reason
            if is_blackout:
                logger.warning("News admission blocked: %s. Skipping new setups.", news_title)

            # 5. Query Live Spread
            spread_raw = connector.get_spread(symbol)
            current_spread = None
            if spread_raw is not None:
                # MT5Connector.get_spread returns ask−bid in price units (not points).
                current_spread = float(spread_raw)
            elif dry_run:
                current_spread = 0.15

            # 6. Fetch Multi-Timeframe Candles (M5 covers Asian/PDH-PDL; H1 uses locked warmup)
            df_m5 = connector.get_candles(symbol, "M5", 500)
            df_h1 = connector.get_candles(symbol, "H1", H1_WARMUP_BARS)

            if df_m5 is not None and len(df_m5) >= 2:
                current_m5_time = df_m5.iloc[-1]["time"]

                if last_processed_m5_time is None or current_m5_time != last_processed_m5_time:
                    last_processed_m5_time = current_m5_time
                    last_closed_bar = df_m5.iloc[-2].to_dict()
                    bar_time = last_closed_bar["time"]

                    logger.info("Evaluating M5 Bar closed at %s (Spread: %s)", bar_time, f"${current_spread:.2f}" if current_spread else "N/A")

                    h1_ready = df_h1 is not None and h1_warmup_ok(len(df_h1))
                    if not h1_ready:
                        logger.warning(
                            "H1 warmup insufficient (have=%s need>=%s); block new setups",
                            0 if df_h1 is None else len(df_h1),
                            H1_WARMUP_BARS,
                        )

                    # Foundation BaselinePlay: hold open positions through news.
                    # Do NOT pre-news BE / force-close (Legacy ADR-010 path stays in NewsManager
                    # for explicit Legacy runners only). Pending cancel is handled below via
                    # news_mgr.should_cancel_pending → orchestrator.

                    # Reset circuit breaker alert on new UTC day
                    bar_date_str = bar_time.date().isoformat() if hasattr(bar_time, "date") else now_utc.date().isoformat()
                    if account.current_utc_date != bar_date_str:
                        circuit_breaker_alerted = False

                    # Liquidity levels
                    target_date = bar_time.date() if hasattr(bar_time, "date") else now_utc.date()
                    liquidity = compute_liquidity_levels(df_m5, target_date)

                    # Pure Detection Seam (skip if blackout / incomplete H1 warmup)
                    setup = None
                    if (
                        account.open_position is None
                        and account.pending_order is None
                        and not is_blackout
                        and h1_ready
                    ):
                        decision = evaluate_smc_setup(
                            h1_candles=df_h1,
                            m5_candles=df_m5,
                            liquidity=liquidity,
                            current_time=bar_time,
                            current_spread=current_spread,
                            max_spread=max_spread,
                            max_sl_cap=strat_cfg.get("max_sl_cap", 25.0),
                            extended_killzones=strat_cfg.get("extended_killzones", True),
                            tp_r=strat_cfg.get("tp_r", 2.5),
                            min_body_ratio=strat_cfg.get("min_body_ratio", 0.45),
                            max_sweep_pierce=strat_cfg.get("max_sweep_pierce", 8.0),
                            sweep_lookback=strat_cfg.get("sweep_lookback", 25),
                            max_sweep_to_mss_bars=strat_cfg.get("max_sweep_to_mss_bars", 8),
                            max_mss_to_fvg_bars=strat_cfg.get("max_mss_to_fvg_bars", 4),
                            require_choch=strat_cfg.get("require_choch", True),
                        )
                        setup = decision.signal if decision.accepted else None
                        if not decision.accepted and decision.reject_reason:
                            logger.debug("Setup rejected: %s", decision.reject_reason)

                    # Snapshot position before orchestrator step to detect trade close
                    pos_before = account.open_position

                    # Persistent equity gates (5% DD / 1% daily) before new risk.
                    # Incomplete broker equity must not invent a fresh high-water / day start.
                    equity_raw = adapter.get_account_equity()
                    history_ready = dry_run or equity_raw is not None
                    equity_now = float(equity_raw) if equity_raw is not None else account.equity
                    snap = adapter.get_risk_snapshot()
                    if snap is not None:
                        apply_broker_capital(
                            account,
                            balance=snap.get("balance"),
                            equity=snap.get("equity"),
                        )
                        equity_now = float(account.equity)
                    elif equity_raw is not None:
                        apply_broker_capital(account, equity=equity_now)
                    observe_equity(
                        risk_halt,
                        equity_now,
                        now=now_utc,
                        history_ready=history_ready,
                    )
                    save_risk_halt_state(risk_halt_path, risk_halt)
                    if risk_halt.halted:
                        pending_ids = []
                        open_ids = []
                        if account.pending_order is not None and account.pending_order.order_id:
                            pending_ids.append(account.pending_order.order_id)
                        # Local simulation has no broker ticket list; clear local bot state.
                        if account.open_position is not None:
                            open_ids.append(getattr(account.open_position, "order_id", None) or "LOCAL_OPEN")
                        for flatten_intent in plan_halt_flatten_intents(
                            pending_order_ids=pending_ids,
                            open_position_ids=[i for i in open_ids if i != "LOCAL_OPEN"],
                            reason="foundation_risk_halt",
                        ):
                            adapter.execute_intent(flatten_intent)
                        if account.pending_order is not None:
                            account.pending_order = None
                            account.pending_bars_held = 0
                        if account.open_position is not None:
                            account.open_position = None
                        logger.warning(
                            "Risk halt active — flattened local bot exposure "
                            "(dd=%s daily=%s losses=%s)",
                            risk_halt.drawdown_halt,
                            risk_halt.daily_equity_halt,
                            risk_halt.net_losing_trades_today,
                        )

                    # Step Orchestrator — cancel unfilled pending on news gate (not open positions)
                    news_cancel = False
                    news_cancel_reason = ""
                    if account.pending_order is not None:
                        news_cancel, news_cancel_reason = news_mgr.should_cancel_pending(
                            now_utc,
                            cached_news_events,
                            schedule_known=schedule_known,
                            window_mins=30,
                        )
                    # Wall-clock TIME_EXIT when M5 feed stalls (scenario 19).
                    # Emit CLOSE_MARKET only; clear local position after adapter evidence.
                    clock_intents = orchestrator.on_clock(account, now_utc)
                    last_close_broker_ok = False
                    for intent in clock_intents:
                        logger.info(
                            "Executing clock OrderIntent: %s (%s)",
                            intent.intent_type.value,
                            intent.reason,
                        )
                        res = adapter.execute_intent(intent)
                        logger.info("Clock execution result: %s", res.message)
                        if (
                            res.success
                            and intent.intent_type == OrderIntentType.CLOSE_MARKET
                            and account.open_position is not None
                        ):
                            account.open_position = None
                            last_close_broker_ok = True

                    intents = orchestrator.on_bar(
                        bar=last_closed_bar,
                        account=account,
                        setup_signal=setup,
                        current_spread=current_spread,
                        max_spread=max_spread,
                        risk_halt=risk_halt,
                        news_cancel_pending=news_cancel,
                        news_cancel_reason=news_cancel_reason,
                    )

                    from scripts.smc.notification_policy import may_notify_close, may_notify_execution
                    from scripts.smc.notification_policy import (
                        may_use_ohlc_invented_close_pnl,
                        require_broker_cash_for_live_close,
                    )

                    for intent in intents:
                        logger.info("Executing OrderIntent: %s (%s)", intent.intent_type.value, intent.reason)
                        res = adapter.execute_intent(intent)
                        logger.info("Execution Result: %s", res.message)

                        if not res.success:
                            if intent.intent_type == OrderIntentType.PLACE_LIMIT:
                                account.pending_order = None
                                account.pending_bars_held = 0
                            continue

                        if intent.intent_type == OrderIntentType.CLOSE_MARKET:
                            last_close_broker_ok = True

                        # Notify only after the execution adapter accepts placement.
                        if intent.intent_type == OrderIntentType.PLACE_LIMIT and setup is not None:
                            if not may_notify_execution(success=True, status=getattr(res, "status", "OK")):
                                continue
                            logger.info("Orchestrator approved SMC Setup: %s at %s (Lot: %s)", setup.direction.value, setup.entry_price, intent.lot_size)
                            chart_path = await asyncio.to_thread(generate_setup_chart, df_m5, setup)
                            risk_usd = round(intent.lot_size * abs(intent.limit_price - intent.sl_price) * 100.0, 2)
                            await notifier.send_alert(
                                signal=setup,
                                lot_size=intent.lot_size,
                                risk_amount=risk_usd,
                                chart_image_path=chart_path,
                            )

                    # Check Milestone Notifications: Trade Closed
                    # Dry-run OHLC exits clear position inside on_bar; treat that as broker evidence in dry_run.
                    # Live must never invent dollars from OHLC — broker deal cashflow only.
                    if pos_before is not None and account.open_position is None:
                        if not may_notify_close(
                            broker_close_success=last_close_broker_ok or dry_run,
                            already_flat_on_broker=False,
                        ):
                            logger.warning("TRADE CLOSED notify suppressed — no broker close evidence")
                        else:
                            from scripts.smc.risk import frozen_initial_r

                            order_id = getattr(pos_before, "order_id", None)
                            broker_pnl = None
                            if not dry_run and order_id:
                                broker_pnl = adapter.get_realized_pnl_for_order(str(order_id))

                            if not require_broker_cash_for_live_close(
                                dry_run=dry_run, broker_pnl=broker_pnl
                            ):
                                logger.warning(
                                    "TRADE CLOSED notify suppressed — live broker cashflow missing "
                                    "(order_id=%s)",
                                    order_id,
                                )
                            elif may_use_ohlc_invented_close_pnl(dry_run=dry_run):
                                if pos_before.direction == Direction.BUY:
                                    if float(last_closed_bar["low"]) <= pos_before.sl_price:
                                        exit_price = pos_before.sl_price
                                        exit_reason = (
                                            "Hit Breakeven Stop Loss"
                                            if pos_before.be_moved
                                            else "Hit Stop Loss"
                                        )
                                    elif float(last_closed_bar["high"]) >= pos_before.tp_price:
                                        exit_price = pos_before.tp_price
                                        exit_reason = "Hit Take Profit Target"
                                    else:
                                        exit_price = float(last_closed_bar["close"])
                                        exit_reason = "Market / Rollover Closure"
                                    pnl_dollars = round(
                                        (exit_price - pos_before.entry_price)
                                        * pos_before.lot_size
                                        * 100.0,
                                        2,
                                    )
                                else:  # SELL
                                    if float(last_closed_bar["high"]) >= pos_before.sl_price:
                                        exit_price = pos_before.sl_price
                                        exit_reason = (
                                            "Hit Breakeven Stop Loss"
                                            if pos_before.be_moved
                                            else "Hit Stop Loss"
                                        )
                                    elif float(last_closed_bar["low"]) <= pos_before.tp_price:
                                        exit_price = pos_before.tp_price
                                        exit_reason = "Hit Take Profit Target"
                                    else:
                                        exit_price = float(last_closed_bar["close"])
                                        exit_reason = "Market / Rollover Closure"
                                    pnl_dollars = round(
                                        (pos_before.entry_price - exit_price)
                                        * pos_before.lot_size
                                        * 100.0,
                                        2,
                                    )
                                pnl_r = frozen_initial_r(
                                    pnl_dollars=pnl_dollars,
                                    initial_sl_distance=pos_before.initial_sl_distance,
                                    filled_lot=pos_before.lot_size,
                                )

                                await notifier.send_message(
                                    format_trade_closed_card(
                                        direction=pos_before.direction,
                                        exit_price=exit_price,
                                        pnl_dollars=pnl_dollars,
                                        pnl_r=pnl_r,
                                        reason=exit_reason,
                                        symbol=symbol,
                                    )
                                )
                                if pnl_r < 0 or pnl_dollars < 0:
                                    record_net_losing_trade(risk_halt)
                                    save_risk_halt_state(risk_halt_path, risk_halt)
                            else:
                                # Live with broker cash: notify from deal PnL + frozen R.
                                pnl_dollars = float(broker_pnl)
                                pnl_r = frozen_initial_r(
                                    pnl_dollars=pnl_dollars,
                                    initial_sl_distance=pos_before.initial_sl_distance,
                                    filled_lot=pos_before.lot_size,
                                )
                                exit_price = float(last_closed_bar["close"])
                                await notifier.send_message(
                                    format_trade_closed_card(
                                        direction=pos_before.direction,
                                        exit_price=exit_price,
                                        pnl_dollars=pnl_dollars,
                                        pnl_r=pnl_r,
                                        reason="Broker-confirmed close",
                                        symbol=symbol,
                                    )
                                )
                                if pnl_r < 0 or pnl_dollars < 0:
                                    record_net_losing_trade(risk_halt)
                                    save_risk_halt_state(risk_halt_path, risk_halt)

                    # Check Milestone Notifications
                    if account.open_position is not None:
                        # Order Filled Alert
                        if not account.open_position.fill_alerted:
                            await notifier.send_message(format_order_filled_card(account.open_position, symbol))
                            account.open_position.fill_alerted = True

                        # Partial Take Profit Alert
                        if account.open_position.partial_closed and not account.open_position.partial_alerted:
                            await notifier.send_message(format_partial_tp_card(
                                direction=account.open_position.direction,
                                closed_lot=round(account.open_position.lot_size, 2),
                                remaining_lot=round(account.open_position.lot_size, 2),
                                r_multiple=strat_cfg.get("partial_tp_r", 1.0),
                                entry_price=account.open_position.entry_price,
                                symbol=symbol,
                            ))
                            account.open_position.partial_alerted = True

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

    except asyncio.CancelledError:
        logger.info("SMC v1 Live Loop cancelled.")
        raise
    except KeyboardInterrupt:
        logger.info("SMC v1 Live Loop stopped.")
    finally:
        connector.disconnect()
        adapter.conn.close()


if __name__ == "__main__":
    asyncio.run(run_smc_live_copilot())
