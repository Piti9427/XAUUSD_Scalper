"""Broker account/symbol identity checks for Demo qualification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from scripts.smc.account_mode import verify_account_mode


@dataclass(frozen=True)
class BrokerIdentityReport:
    ok: bool
    broker_server: Optional[str]
    account_login: Optional[int]
    currency: Optional[str]
    trade_mode: Optional[str]
    symbol: Optional[str]
    reasons: tuple[str, ...]
    margin_mode: Optional[str] = None


def verify_broker_identity(
    *,
    expected_server_substring: str = "Exness",
    expected_currency: str = "USD",
    expected_symbol: str = "XAUUSD",
    allow_demo_only: bool = True,
    require_hedging: bool = True,
    account_info: Optional[Any] = None,
    symbol_info: Optional[Any] = None,
) -> BrokerIdentityReport:
    """
    Verify connected account/symbol metadata before Demo orders.

    Missing objects fail closed. Does not place trades.
    Hedging margin mode is required by default so comment-scoped ownership works.
    """
    reasons: list[str] = []
    broker_server = getattr(account_info, "server", None) if account_info is not None else None
    account_login = getattr(account_info, "login", None) if account_info is not None else None
    currency = getattr(account_info, "currency", None) if account_info is not None else None
    trade_mode = getattr(account_info, "trade_mode", None) if account_info is not None else None
    symbol = getattr(symbol_info, "name", None) if symbol_info is not None else None

    if account_info is None:
        reasons.append("missing_account_info")
    if symbol_info is None:
        reasons.append("missing_symbol_info")
    if broker_server is None or expected_server_substring.lower() not in str(broker_server).lower():
        reasons.append("broker_server_mismatch")
    if currency != expected_currency:
        reasons.append("currency_mismatch")
    if symbol is None or expected_symbol not in str(symbol):
        reasons.append("symbol_mismatch")
    if allow_demo_only:
        # MT5 ACCOUNT_TRADE_MODE_DEMO is typically 0; accept explicit 'demo' strings too.
        mode_ok = trade_mode in (0, "demo", "DEMO", "account_trade_mode_demo")
        if not mode_ok:
            reasons.append("demo_required")

    mode_report = verify_account_mode(
        account_info=account_info,
        require_hedging=require_hedging,
    )
    # Avoid duplicating missing_account_info from the mode check.
    for reason in mode_report.reasons:
        if reason == "missing_account_info" and "missing_account_info" in reasons:
            continue
        reasons.append(reason)

    return BrokerIdentityReport(
        ok=len(reasons) == 0,
        broker_server=str(broker_server) if broker_server is not None else None,
        account_login=int(account_login) if account_login is not None else None,
        currency=str(currency) if currency is not None else None,
        trade_mode=str(trade_mode) if trade_mode is not None else None,
        symbol=str(symbol) if symbol is not None else None,
        margin_mode=mode_report.margin_mode,
        reasons=tuple(reasons),
    )
