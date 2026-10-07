"""Verified broker reads and UTC account baseline for trial30 Demo."""

from datetime import datetime, timedelta, timezone
import math

from scripts.smc.account_mode import verify_account_mode


def _finite(value, *, positive=False):
    return math.isfinite(float(value)) and (float(value) > 0 if positive else True)


def _cash(deal):
    return sum(float(getattr(deal, k)) for k in ("profit", "commission", "swap", "fee"))


class BrokerView:
    def __init__(
        self, mt5, login, server, symbol, fingerprint, journal, *, restart_unknown_baseline=False
    ):
        self.mt5 = mt5
        self.login = login
        self.server = server
        self.symbol = symbol
        self.fingerprint = fingerprint
        self.journal = journal
        self.restart_unknown_baseline = restart_unknown_baseline
        self._restart_baseline_latched = False

    def identity(self):
        account = self.mt5.account_info()
        terminal = self.mt5.terminal_info()
        if (
            account is None
            or int(account.login) != self.login
            or str(account.server) != self.server
            or int(account.trade_mode) != 0
            or str(account.currency) != "USD"
            or not verify_account_mode(account_info=account).ok
        ):
            raise ValueError("demo_identity_required")
        if (
            terminal is None
            or not terminal.connected
            or not terminal.trade_allowed
            or terminal.tradeapi_disabled
            or not account.trade_allowed
            or not account.trade_expert
        ):
            raise ValueError("algo_permissions_required")
        if not all(_finite(getattr(account, k), positive=True) for k in ("equity", "balance")):
            raise ValueError("invalid_capital")
        prior = self.journal.get("identity")
        if prior is not None and prior != self.fingerprint:
            raise ValueError("journal_account_mismatch")
        self.journal.put("identity", self.fingerprint)
        return account

    def _exposure(self):
        positions = self.mt5.positions_get()
        orders = self.mt5.orders_get()
        if positions is None or orders is None:
            raise ValueError("exposure_unknown")
        return positions, orders

    def _history(self, now):
        start = datetime(1970, 1, 1, tzinfo=timezone.utc)
        deals = self.mt5.history_deals_get(start, now)
        count = self.mt5.history_deals_total(start, now)
        if deals is None or count is None or len(deals) != count:
            raise ValueError("history_unknown")
        if len({int(d.ticket) for d in deals}) != len(deals):
            raise ValueError("history_duplicate")
        if any(not _finite(_cash(d)) for d in deals):
            raise ValueError("invalid_history_cashflow")
        return deals

    def _baseline(self, account, positions, deals, now):
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        boundary = int(midnight.timestamp() * 1000)
        if abs(sum(_cash(d) for d in deals) - float(account.balance)) > 0.02:
            raise ValueError("history_balance_mismatch")
        before: dict[int, float] = {}
        current: dict[int, float] = {}
        for d in deals:
            if int(d.type) in (0, 1):
                delta = float(d.volume) * (1 if int(d.type) == 0 else -1)
                ident = int(d.position_id)
                current[ident] = current.get(ident, 0.0) + delta
                if int(d.time_msc) < boundary:
                    before[ident] = before.get(ident, 0.0) + delta
            elif int(d.time_msc) >= boundary:
                raise ValueError("intraday_cash_adjustment")
        live = {
            int(p.identifier): float(p.volume) * (1 if int(p.type) == 0 else -1) for p in positions
        }
        if any(
            abs(current.get(k, 0.0) - live.get(k, 0.0)) > 1e-8 for k in current.keys() | live.keys()
        ):
            raise ValueError("history_position_mismatch")
        state = self.journal.get("day")
        day = now.date().isoformat()
        held = any(abs(v) > 1e-8 for v in before.values())
        if (
            self.restart_unknown_baseline
            and not self._restart_baseline_latched
            and held
            and now - midnight >= timedelta(seconds=1)
        ):
            baseline = float(account.equity)
            if not _finite(baseline, positive=True):
                raise ValueError("invalid_day_baseline")
            self.journal.put("day", {"day": day, "equity": baseline, "source": "restart_equity"})
            self._restart_baseline_latched = True
            return baseline
        if state and state["day"] == day:
            if not _finite(state["equity"], positive=True):
                raise ValueError("invalid_day_baseline")
            return float(state["equity"])
        if held:
            if now - midnight >= timedelta(seconds=1):
                raise ValueError("day_start_floating_unknown")
            baseline = float(account.equity)
            source = "captured_at_utc_boundary"
        else:
            baseline = float(account.balance) - sum(
                _cash(d) for d in deals if int(d.time_msc) >= boundary
            )
            source = "reconstructed_flat_midnight_from_reconciled_history"
        if not _finite(baseline, positive=True):
            raise ValueError("invalid_day_baseline")
        self.journal.put("day", {"day": day, "equity": baseline, "source": source})
        return baseline

    def _quote(self, now):
        tick = self.mt5.symbol_info_tick(self.symbol)
        if tick is None:
            raise ValueError("quote_unknown")
        stamp = datetime.fromtimestamp(int(tick.time_msc) / 1000, timezone.utc)
        if (
            not all(_finite(getattr(tick, k), positive=True) for k in ("bid", "ask"))
            or tick.ask < tick.bid
        ):
            raise ValueError("quote_invalid")
        if not timedelta(0) <= now - stamp <= timedelta(seconds=60):
            raise ValueError("quote_stale")
        return tick

    def _spec(self):
        info = self.mt5.symbol_info(self.symbol)
        if info is None or info.name != self.symbol or int(info.trade_mode) != 4:
            raise ValueError("symbol_unavailable")
        for key in (
            "trade_contract_size",
            "trade_tick_size",
            "point",
            "volume_min",
            "volume_max",
            "volume_step",
        ):
            if not _finite(getattr(info, key), positive=True):
                raise ValueError("symbol_spec_invalid")
        for key in ("trade_stops_level", "trade_freeze_level"):
            if not _finite(getattr(info, key)) or getattr(info, key) < 0:
                raise ValueError("symbol_stops_invalid")
        return info
