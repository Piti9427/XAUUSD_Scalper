"""Verified broker reads and UTC account baseline for trial30 Demo."""

from datetime import datetime, timedelta, timezone
import math
import time

from scripts.smc.account_mode import verify_account_mode
from scripts.demo_runtime.boundary import capture, read_mark


def _finite(value, *, positive=False):
    try:
        return math.isfinite(float(value)) and (float(value) > 0 if positive else True)
    except (TypeError, ValueError, OverflowError):
        return False


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
        self.identity_diagnostics = {}

    def identity(self, *, require_trade_permissions=True):
        self.identity_diagnostics = {}
        account = self.mt5.account_info()
        terminal = self.mt5.terminal_info()

        def flag(source, key):
            try:
                value = getattr(source, key, None)
                return None if value is None else bool(value)
            except Exception:
                # Optional diagnostics cannot introduce a new admission/manager
                # prerequisite. The original required checks still run below.
                return None

        # Reuse the exact reads checked below. Never log account/terminal objects
        # or probe the SDK again to explain a failed mutation prerequisite.
        self.identity_diagnostics = dict(
            identity_account_present=account is not None,
            identity_terminal_present=terminal is not None,
            identity_require_trade_permissions=bool(require_trade_permissions),
            identity_terminal_connected=flag(terminal, "connected"),
            identity_terminal_trade_allowed=flag(terminal, "trade_allowed"),
            identity_terminal_tradeapi_disabled=flag(terminal, "tradeapi_disabled"),
            identity_account_trade_allowed=flag(account, "trade_allowed"),
            identity_account_trade_expert=flag(account, "trade_expert"),
            identity_blockers=[],
        )
        if (
            account is None
            or int(account.login) != self.login
            or str(account.server) != self.server
            or int(account.trade_mode) != 0
            or str(account.currency) != "USD"
            or not verify_account_mode(account_info=account).ok
        ):
            self.identity_diagnostics["identity_blockers"] = [
                "account_missing" if account is None else "demo_identity_mismatch"
            ]
            raise ValueError("demo_identity_required")
        if (
            terminal is None
            or not terminal.connected
            or (
                require_trade_permissions
                and (
                    not terminal.trade_allowed
                    or terminal.tradeapi_disabled
                    or not account.trade_allowed
                    or not account.trade_expert
                )
            )
        ):
            observed = self.identity_diagnostics
            blockers = observed["identity_blockers"]
            if terminal is None:
                blockers.append("terminal_missing")
            else:
                if observed["identity_terminal_connected"] is False:
                    blockers.append("terminal_disconnected")
                if require_trade_permissions:
                    if observed["identity_terminal_trade_allowed"] is False:
                        blockers.append("terminal_trade_disabled")
                    if observed["identity_terminal_tradeapi_disabled"] is True:
                        blockers.append("external_trade_api_disabled")
                    if observed["identity_account_trade_allowed"] is False:
                        blockers.append("account_trade_disabled")
                    if observed["identity_account_trade_expert"] is False:
                        blockers.append("account_expert_disabled")
            if not blockers:
                blockers.append("permission_check_failed")
            raise ValueError("algo_permissions_required")
        if not all(_finite(getattr(account, k), positive=True) for k in ("equity", "balance")):
            self.identity_diagnostics["identity_blockers"] = ["invalid_capital"]
            raise ValueError("invalid_capital")
        prior = self.journal.get("identity")
        if prior is not None and prior != self.fingerprint:
            self.identity_diagnostics["identity_blockers"] = ["journal_account_mismatch"]
            raise ValueError("journal_account_mismatch")
        self.journal.put("identity", self.fingerprint)
        self.last_equity = float(account.equity)
        return account

    def _exposure(self):
        positions = self.mt5.positions_get()
        orders = self.mt5.orders_get()
        self.position_count = None if positions is None else len(positions)
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
        if any(
            not all(_finite(getattr(d, k, None)) for k in ("profit", "commission", "swap", "fee"))
            for d in deals
        ):
            self.journal.audit(
                "BROKER_HISTORY_INVALID", observed=deals, reason="invalid_history_cashflow"
            )
            raise ValueError("invalid_history_cashflow")
        if any(
            int(d.type) in (0, 1)
            and (not _finite(d.volume, positive=True) or int(d.entry) not in (0, 1, 3))
            for d in deals
        ):
            self.journal.audit(
                "BROKER_HISTORY_INVALID", observed=deals, reason="invalid_history_volume"
            )
            raise ValueError("invalid_history_volume")
        return deals

    def capture_boundary(self, account, *, request_started, observed):
        self._boundary_observed = observed
        return capture(self.journal, account, fingerprint=self.fingerprint,
                       request_started=request_started, observed=observed)

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
        if state and state["day"] == day:
            if state.get("account_fingerprint", self.fingerprint) != self.fingerprint or state.get(
                "source"
            ) not in (
                "captured_at_utc_boundary",
                "reconstructed_flat_midnight_from_reconciled_history",
            ):
                raise ValueError("unproven_day_baseline")
            if not _finite(state["equity"], positive=True):
                raise ValueError("invalid_day_baseline")
            return float(state["equity"])
        boundary_proof = None
        if held:
            boundary_proof = read_mark(self.journal, fingerprint=self.fingerprint, day=day)
            if boundary_proof is None:
                # Direct callers retain the existing first-second contract. The
                # running sampler also bounds actual SDK response time.
                capture(self.journal, account, fingerprint=self.fingerprint,
                        request_started=now, observed=getattr(self, "_boundary_observed", now))
                boundary_proof = read_mark(self.journal, fingerprint=self.fingerprint, day=day)
            if boundary_proof is None:
                raise ValueError("day_start_floating_unknown")
            baseline = float(boundary_proof["equity"])
            source = "captured_at_utc_boundary"
        else:
            baseline = float(account.balance) - sum(
                _cash(d) for d in deals if int(d.time_msc) >= boundary
            )
            source = "reconstructed_flat_midnight_from_reconciled_history"
        if not _finite(baseline, positive=True):
            raise ValueError("invalid_day_baseline")
        self.journal.put(
            "day",
            {
                "day": day,
                "equity": baseline,
                "source": source,
                "account_fingerprint": self.fingerprint,
                **({"boundary_observed_utc": boundary_proof["observed_utc"]}
                   if boundary_proof else {}),
            },
        )
        return baseline

    def _quote(self, now):
        self.quote_diagnostics = {}
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise ValueError("quote_clock_invalid")
        started = time.monotonic()
        tick = self.mt5.symbol_info_tick(self.symbol)
        elapsed = time.monotonic() - started
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("quote_clock_invalid")
        # `now` is the caller's current UTC observation, not a broker timestamp.
        # Include time spent inside the SDK before judging future/stale quotes.
        observed = now + timedelta(seconds=elapsed)
        self.quote_diagnostics = dict(quote_requested_utc=now.isoformat(),
                                      quote_observed_utc=observed.isoformat())
        if tick is None:
            self.quote_diagnostics["quote_rejection"] = "missing"
            raise ValueError("quote_unknown")
        stamp = datetime.fromtimestamp(int(tick.time_msc) / 1000, timezone.utc)
        age = (observed - stamp).total_seconds()
        self.quote_diagnostics.update(quote_time_utc=stamp.isoformat(), quote_age_seconds=age)
        if (
            not all(_finite(getattr(tick, k), positive=True) for k in ("bid", "ask"))
            or tick.ask < tick.bid
        ):
            self.quote_diagnostics["quote_rejection"] = "invalid_bid_ask"
            raise ValueError("quote_invalid")
        if not 0 <= age <= 60:
            self.quote_diagnostics["quote_rejection"] = "future" if age < 0 else "stale"
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
