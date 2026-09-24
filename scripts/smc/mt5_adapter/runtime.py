"""Optional MetaTrader5 runtime binding shared across adapter mixins."""

from __future__ import annotations

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - platform without MT5 package
    mt5 = None
