"""Resolve MT5 type_filling from symbol filling_mode (Exness / IC / Pepperstone)."""

from __future__ import annotations

from typing import Any


def _mt5_int(mt5_mod: Any, attr: str, default: int) -> int:
    val = getattr(mt5_mod, attr, default)
    if isinstance(val, (int, float)):
        return int(val)
    return default


def resolve_type_filling(
    filling_mode: int,
    *,
    for_pending: bool,
    mt5_mod: Any,
) -> int:
    """
    Map symbol filling_mode bitmask to ORDER_FILLING_* for order_send.

    Pending limits use RETURN when supported; market deals prefer IOC then FOK.
    """
    order_return = _mt5_int(mt5_mod, "ORDER_FILLING_RETURN", 2)
    order_ioc = _mt5_int(mt5_mod, "ORDER_FILLING_IOC", 1)
    order_fok = _mt5_int(mt5_mod, "ORDER_FILLING_FOK", 0)
    sym_ioc = _mt5_int(mt5_mod, "SYMBOL_FILLING_IOC", 2)
    sym_fok = _mt5_int(mt5_mod, "SYMBOL_FILLING_FOK", 1)

    if for_pending:
        return order_return
    if int(filling_mode) & sym_ioc:
        return order_ioc
    if int(filling_mode) & sym_fok:
        return order_fok
    return order_return
