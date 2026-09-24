"""Sync AccountState capital fields from broker snapshots."""

from __future__ import annotations

from typing import Optional

from scripts.smc.types import AccountState


def apply_broker_capital(
    account: AccountState,
    *,
    balance: Optional[float] = None,
    equity: Optional[float] = None,
) -> None:
    """
    Update local account capital from broker-reported values.

    Used so lot sizing (min(balance, equity)) cannot keep a hardcoded research balance
    after a live/Demo session is connected.
    """
    if balance is not None:
        account.balance = float(balance)
    if equity is not None:
        account.equity = float(equity)
