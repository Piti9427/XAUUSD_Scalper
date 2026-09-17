import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI

from scripts.smc.mt5_adapter import SMCExecutionAdapter
from scripts.smc.broker_identity import BrokerIdentityReport
from scripts.smc.risk_halt import load_risk_halt_state, new_risk_halt_state
from scripts.webhook.auth import make_verify_auth
from scripts.webhook.clock_routes import register_clock_route
from scripts.webhook.idempotency import make_idempotency_helpers
from scripts.webhook.runtime import WebhookRuntime
from scripts.webhook.setup_registry_resolve import resolve_setup_registry
from scripts.webhook.tradingview_routes import register_tradingview_route

logger = logging.getLogger("webhook_bridge")


def create_app(
    auth_token: str = "XAUUSD_DEFAULT_SECRET",
    dry_run: bool = True,
    db_path: str = "data/smc_trades.db",
    account_balance: float = 10000.0,
    risk_pct: float = 0.005,
    max_daily_losses: int = 2,
    rollover_hour_utc: int = 20,
    rollover_minute_utc: int = 55,
    notifier: Optional[Any] = None,
    news_manager: Optional[Any] = None,
    commission_per_lot: Optional[float] = None,
    slippage_allowance: Optional[float] = None,
    tp_r: float = 2.5,
    partial_tp_r: float = 1.0,
    risk_halt_path: Optional[str] = None,
    require_broker_identity: Optional[bool] = None,
    identity_gate: Optional[Callable[[], BrokerIdentityReport]] = None,
    max_hold_bars: Optional[int] = None,
    bar_minutes: int = 5,
    order_ttl_bars: Optional[int] = 4,
    partial_tp_enabled: bool = False,
    be_enabled: bool = False,
    be_buffer: float = 0.10,
    terminal_path: Optional[str] = None,
    setup_registry_path: Optional[str] = None,
    mt5_login: Optional[int] = None,
    mt5_password: Optional[str] = None,
    mt5_server: Optional[str] = None,
) -> FastAPI:
    """
    Factory creating the FastAPI Webhook Bridge application with non-blocking async architecture.
    """
    app = FastAPI(
        title="XAUUSD Master Pro Webhook Bridge",
        version="1.1.0",
        description="Translates TradingView alerts into broker MT5 executions with strict async risk shields.",
    )

    start_time = time.time()
    adapter = SMCExecutionAdapter(
        symbol="XAUUSD",
        dry_run=dry_run,
        db_path=db_path,
        terminal_path=terminal_path,
        login=mt5_login,
        password=mt5_password,
        server=mt5_server,
    )
    app.state.adapter = adapter

    enforce_identity = (
        require_broker_identity
        if require_broker_identity is not None
        else (not dry_run or identity_gate is not None)
    )
    halt_path = Path(risk_halt_path) if risk_halt_path else None
    risk_halt = None
    if halt_path is not None:
        risk_halt = load_risk_halt_state(halt_path) or new_risk_halt_state(account_balance)
        app.state.risk_halt = risk_halt

    # Scenario 8: terminal SETUP_IDs survive restart (shared path with smc_main).
    setup_registry = resolve_setup_registry(setup_registry_path, dry_run=dry_run)
    app.state.setup_registry = setup_registry

    # Pattern C: Two-Tier In-Memory Idempotency Cache (ADR-024)
    memory_idempotency_cache: set[tuple[str, str]] = set()
    is_processed, mark_processed = make_idempotency_helpers(
        adapter, memory_idempotency_cache
    )
    verify_auth = make_verify_auth(auth_token)

    # Pattern B: Safe Non-Blocking Dispatcher for Side-Effects (Telegram Notifier)
    def _dispatch_tg_safe(card: str):
        if notifier and getattr(notifier, "enabled", False):
            try:
                notifier.send_message(card)
            except Exception as exc:
                logger.warning(f"Background Telegram dispatch error: {exc}")

    @app.get("/health")
    async def health_check():
        daily_losses = await asyncio.to_thread(adapter.get_daily_realized_losses)
        equity = (await asyncio.to_thread(adapter.get_account_equity)) or account_balance
        circuit_tripped = daily_losses >= max_daily_losses
        return {
            "status": "ok",
            "mode": "dry-run" if adapter.dry_run else "live",
            "mt5_connected": not adapter.dry_run and adapter.connected,
            "account_equity": equity,
            "daily_realized_losses": daily_losses,
            "circuit_breaker_tripped": circuit_tripped,
            "uptime_seconds": round(time.time() - start_time, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "max_hold_bars": max_hold_bars,
        }

    rt = WebhookRuntime(
        adapter=adapter,
        verify_auth=verify_auth,
        is_processed=is_processed,
        mark_processed=mark_processed,
        dispatch_tg_safe=_dispatch_tg_safe,
        setup_registry=setup_registry,
        account_balance=account_balance,
        risk_pct=risk_pct,
        max_daily_losses=max_daily_losses,
        rollover_hour_utc=rollover_hour_utc,
        rollover_minute_utc=rollover_minute_utc,
        notifier=notifier,
        news_manager=news_manager,
        commission_per_lot=commission_per_lot,
        slippage_allowance=slippage_allowance,
        tp_r=tp_r,
        partial_tp_r=partial_tp_r,
        risk_halt=risk_halt,
        halt_path=halt_path,
        enforce_identity=enforce_identity,
        identity_gate=identity_gate,
        max_hold_bars=max_hold_bars,
        bar_minutes=bar_minutes,
        order_ttl_bars=order_ttl_bars,
        partial_tp_enabled=partial_tp_enabled,
        be_enabled=be_enabled,
        be_buffer=be_buffer,
    )
    register_clock_route(app, rt)
    register_tradingview_route(app, rt)
    return app


if __name__ == "__main__":
    import uvicorn
    import os

    from scripts.smc.news import NewsManager

    secret = os.environ.get("WEBHOOK_SECRET", "DEV_SECRET_123")
    hold_raw = os.environ.get("SMC_MAX_HOLD_BARS")
    max_hold_bars = int(hold_raw) if hold_raw not in (None, "") else None
    bar_minutes = int(os.environ.get("SMC_BAR_MINUTES", "5"))
    news_mgr = NewsManager()
    news_mgr.events = None
    news_mgr.schedule_known = False
    app = create_app(
        auth_token=secret,
        dry_run=True,
        news_manager=news_mgr,
        max_hold_bars=max_hold_bars,
        bar_minutes=bar_minutes,
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)
