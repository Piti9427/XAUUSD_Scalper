"""Live broker reads: equity, quotes, exposure, realized PnL."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from scripts.smc.mt5_filling import resolve_type_filling

from . import runtime


class BrokerMixin:
    def get_account_equity(self) -> Optional[float]:
        """Fetches real-time equity from MT5 terminal or None if offline/dry-run."""
        if self.dry_run or runtime.mt5 is None or not self.connected:
            return None
        info = runtime.mt5.account_info()
        return float(info.equity) if info else None

    def _type_filling_for_symbol(self, *, for_pending: bool) -> Optional[int]:
        if runtime.mt5 is None or not self.connected:
            return None
        sym = runtime.mt5.symbol_info(self.symbol)
        if sym is None:
            return None
        raw_mode = getattr(sym, "filling_mode", 0)
        if isinstance(raw_mode, (int, float)):
            filling_mode = int(raw_mode)
        else:
            filling_mode = 0
        return resolve_type_filling(
            filling_mode,
            for_pending=for_pending,
            mt5_mod=runtime.mt5,
        )

    def get_risk_snapshot(self) -> Optional[Dict[str, float]]:
        """Return current broker account and XAUUSD sizing rules, or None."""
        if self.dry_run or runtime.mt5 is None or not self.connected:
            return None
        account = runtime.mt5.account_info()
        symbol = runtime.mt5.symbol_info(self.symbol)
        if account is None or symbol is None:
            return None
        margin_free = getattr(account, "margin_free", None)
        if margin_free is None:
            return None
        trade_allowed = getattr(account, "trade_allowed", None)
        point = getattr(symbol, "point", None)
        stops_level = getattr(symbol, "trade_stops_level", None)
        freeze_level = getattr(symbol, "trade_freeze_level", None)
        if point is None or stops_level is None or freeze_level is None:
            return None
        try:
            snapshot = {
                "balance": float(account.balance),
                "equity": float(account.equity),
                "min_lot": float(symbol.volume_min),
                "max_lot": float(symbol.volume_max),
                "lot_step": float(symbol.volume_step),
                "contract_size": float(symbol.trade_contract_size),
                "margin_free": float(margin_free),
                "point": float(point),
                "stops_level": float(stops_level),
                "freeze_level": float(freeze_level),
            }
        except (TypeError, ValueError):
            return None
        if trade_allowed is not None:
            snapshot["trade_allowed"] = 1.0 if bool(trade_allowed) else 0.0
        return snapshot

    def get_market_quotes(self) -> Optional[Dict[str, float]]:
        """Return current bid/ask for freeze-level SL checks, or None if unknown."""
        if self.dry_run or runtime.mt5 is None or not self.connected:
            return None
        tick = runtime.mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return None
        bid = getattr(tick, "bid", None)
        ask = getattr(tick, "ask", None)
        try:
            if bid is None or ask is None:
                return None
            return {"bid": float(bid), "ask": float(ask)}
        except (TypeError, ValueError):
            return None

    def get_open_exposure(self) -> Optional[List[Any]]:
        """Return all XAUUSD pending orders and positions; None means broker unknown."""
        if self.dry_run or runtime.mt5 is None or not self.connected:
            return None
        orders = runtime.mt5.orders_get(symbol=self.symbol)
        positions = runtime.mt5.positions_get(symbol=self.symbol)
        if orders is None or positions is None:
            return None
        return list(orders) + list(positions)

    def get_matching_position(self, order_id: str) -> Optional[Any]:
        """Find open position matching SMC_{order_id} comment on broker."""
        if self.dry_run or runtime.mt5 is None or not self.connected:
            return None
        positions = runtime.mt5.positions_get(symbol=self.symbol)
        if not positions:
            return None
        for pos in positions:
            if getattr(pos, "comment", "") == f"SMC_{order_id}":
                return pos
        return None

    def get_matching_pending_order(self, order_id: str) -> Optional[Any]:
        """Find open pending order matching SMC_{order_id} comment on broker."""
        if self.dry_run or runtime.mt5 is None or not self.connected:
            return None
        orders = runtime.mt5.orders_get(symbol=self.symbol)
        if not orders:
            return None
        for order in orders:
            if getattr(order, "comment", "") == f"SMC_{order_id}":
                return order
        return None

    def get_realized_pnl_for_order(self, order_id: str) -> Optional[float]:
        """Calculate net realized PnL (profit + swap + commission + fee) from broker deal history."""
        if self.dry_run or runtime.mt5 is None or not self.connected:
            return None
        now = datetime.now(timezone.utc)
        from_date = None
        cursor = self.conn.execute("SELECT created_at FROM setup_inbox WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        if row and row[0]:
            try:
                from_date = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
                if from_date.tzinfo is None:
                    from_date = from_date.replace(tzinfo=timezone.utc)
                from_date = from_date - timedelta(hours=1)
            except Exception:
                from_date = None
        if from_date is None:
            from_date = now - timedelta(days=7)

        deals = runtime.mt5.history_deals_get(from_date, now)
        if deals is None:
            return None
        from scripts.smc.cost_accounting import aggregate_deal_cashflows

        target_comment = f"SMC_{order_id}"
        partial_comment = f"SMC_Partial_{order_id}"
        matching = [
            d
            for d in deals
            if getattr(d, "comment", "") in {target_comment, partial_comment}
        ]
        return aggregate_deal_cashflows(matching)

