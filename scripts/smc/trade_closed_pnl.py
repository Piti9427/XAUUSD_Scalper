"""TRADE_CLOSED PnL resolution — never invent live cash from reason text."""

from __future__ import annotations

from typing import Any, Optional, Tuple


def parse_optional_float(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def resolve_trade_closed_pnl(
    *,
    dry_run: bool,
    payload_pnl_r: Any = None,
    payload_pnl_dollar: Any = None,
    broker_pnl: Optional[float] = None,
    entry: float = 0.0,
    sl: float = 0.0,
    lot: float = 0.0,
    exit_price: float = 0.0,
    direction: str = "BUY",
) -> Tuple[Optional[float], Optional[float], str]:
    """
    Resolve (pnl_r, pnl_dollar, status).

    Live: broker deal cash preferred; never invent dollars from exit geometry.
    Dry-run: payload dollars ok; geometric R from exit only when dollars absent.
    status:
      - ok
      - live_broker_pnl_missing (caller should reconcile; both PnL None)
    """
    pnl_r = parse_optional_float(payload_pnl_r)
    pnl_dollar = parse_optional_float(payload_pnl_dollar)

    if not dry_run:
        if broker_pnl is not None:
            pnl_dollar = float(broker_pnl)
        else:
            # Live: never halt/notify on TradingView invent cash.
            return None, None, "live_broker_pnl_missing"

    initial_dist = abs(float(entry) - float(sl)) if entry and sl else 0.0
    if pnl_r is None and pnl_dollar is not None and initial_dist > 0 and float(lot) > 0:
        from scripts.smc.risk import frozen_initial_r

        pnl_r = frozen_initial_r(
            pnl_dollars=float(pnl_dollar),
            initial_sl_distance=initial_dist,
            filled_lot=float(lot),
        )
    elif dry_run and pnl_r is None and initial_dist > 0 and entry and exit_price:
        # Dry-run only: geometric R from TV exit (not live invent cash).
        signed = (
            (float(exit_price) - float(entry))
            if str(direction).upper() == "BUY"
            else (float(entry) - float(exit_price))
        )
        pnl_r = round(signed / initial_dist, 4)

    return pnl_r, pnl_dollar, "ok"
