"""Shared runtime state for webhook route modules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class WebhookRuntime:
    adapter: Any
    verify_auth: Callable
    is_processed: Callable
    mark_processed: Callable
    dispatch_tg_safe: Callable
    setup_registry: Any
    account_balance: float
    risk_pct: float
    max_daily_losses: int
    rollover_hour_utc: int
    rollover_minute_utc: int
    notifier: Optional[Any]
    news_manager: Optional[Any]
    commission_per_lot: Optional[float]
    slippage_allowance: Optional[float]
    tp_r: float
    partial_tp_r: float
    risk_halt: Any
    halt_path: Optional[Path]
    enforce_identity: bool
    identity_gate: Optional[Callable]
    max_hold_bars: Optional[int]
    bar_minutes: int
    order_ttl_bars: Optional[int]
    partial_tp_enabled: bool
    be_enabled: bool
    be_buffer: float
