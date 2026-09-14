#!/usr/bin/env python3
"""
Staging & Production Runner for XAUUSD Webhook Bridge (TradingView -> MT5).
Loads configuration from config/settings.yaml and starts the Uvicorn ASGI server.
"""

import sys
import os
import argparse
import logging
import yaml

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn
from scripts.webhook_bridge import create_app
from scripts.smc.notifier import SMCTelegramNotifier


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("staging_bridge")


def load_config(config_path: str = "config/settings.yaml") -> dict:
    """Loads configuration for the staging/webhook bridge."""
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def main():
    parser = argparse.ArgumentParser(description="Run XAUUSD TradingView Webhook Bridge")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to settings.yaml")
    parser.add_argument("--port", type=int, default=None, help="Port to bind (overrides config)")
    parser.add_argument("--dry-run", action="store_true", default=None, help="Force dry-run simulation mode")
    parser.add_argument("--balance", type=float, default=None, help="Account equity for lot sizing")
    parser.add_argument("--risk", type=float, default=None, help="Risk percentage per trade (e.g. 0.01)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    wh_cfg = cfg.get("webhook", {})

    host = wh_cfg.get("host", "0.0.0.0")
    port = args.port or wh_cfg.get("port", 8000)
    secret_token = os.environ.get("WEBHOOK_SECRET") or wh_cfg.get("secret_token", "XAUUSD_MASTER_SECRET_2026")
    dry_run = args.dry_run if args.dry_run is not None else wh_cfg.get("dry_run", True)
    account_balance = args.balance or wh_cfg.get("account_balance", 10000.0)
    risk_pct = args.risk or wh_cfg.get("risk_pct", 0.01)
    commission_per_lot = wh_cfg.get("commission_per_lot")
    slippage_allowance = wh_cfg.get("slippage_allowance")
    max_daily_losses = wh_cfg.get("max_daily_losses", 2)
    rollover_hour_utc = wh_cfg.get("rollover_hour_utc", 20)
    rollover_minute_utc = wh_cfg.get("rollover_minute_utc", 55)

    notifier = SMCTelegramNotifier(cfg) if cfg.get("telegram", {}).get("enabled") else None

    logger.info("=" * 60)
    logger.info("🚀 Starting XAUUSD Webhook Bridge Service")
    logger.info(f"📍 Binding: http://{host}:{port}")
    logger.info(f"🛡️ Security Token: {'*' * (len(secret_token) - 4) + secret_token[-4:]}")
    logger.info(f"💼 Mode: {'DRY-RUN (Simulated)' if dry_run else 'LIVE BROKER (MetaTrader 5)'}")
    logger.info(f"💰 Account Equity: ${account_balance:,.2f} | Risk per Trade: {risk_pct * 100:.1f}%")
    logger.info(f"🛑 Circuit Breaker: Max {max_daily_losses} daily losses (ADR-011)")
    logger.info(f"⏰ Rollover Cutoff: {rollover_hour_utc}:{rollover_minute_utc:02d} UTC (ADR-007)")
    logger.info(f"📱 Telegram Alerts: {'ENABLED' if notifier and notifier.enabled else 'DISABLED'}")
    logger.info("=" * 60)

    strategy_cfg = cfg.get("strategy", {})
    tp_r = float(strategy_cfg.get("tp_r", 2.5))
    partial_tp_r = float(strategy_cfg.get("partial_tp_r", 1.0))

    app = create_app(
        auth_token=secret_token,
        dry_run=dry_run,
        account_balance=account_balance,
        risk_pct=risk_pct,
        max_daily_losses=max_daily_losses,
        rollover_hour_utc=rollover_hour_utc,
        rollover_minute_utc=rollover_minute_utc,
        notifier=notifier,
        commission_per_lot=commission_per_lot,
        slippage_allowance=slippage_allowance,
        tp_r=tp_r,
        partial_tp_r=partial_tp_r,
    )

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
