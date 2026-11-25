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


HELD_TICK_SOURCE = "reconstructed_held_boundary_from_broker_ticks"
DAY_BASELINE_SOURCES = (
    "captured_at_utc_boundary",
    "reconstructed_flat_midnight_from_reconciled_history",
    HELD_TICK_SOURCE,
)
# Broker tick at or before 00:00:00.000 UTC must be at most this old.
BOUNDARY_TICK_MAX_AGE_MS = 60_000
BOUNDARY_TICK_LOOKBACK_SECONDS = 120
# Profit formula must reproduce the broker's own realized/floating profit.
PROFIT_CHECK_TOLERANCE = 0.011
RECONSTRUCT_RETRY_SECONDS = 60.0


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

    def identity(self, *, require_trade_permissions=True, observation_clock=None):
        self.identity_diagnostics = {}
        self.account_observation = None
        requested = observation_clock() if observation_clock is not None else None
        if requested is not None:
            self.identity_diagnostics["account_read_request_started_utc"] = requested.isoformat()
            self.identity_diagnostics["account_read_observed_utc"] = None
        account = self.mt5.account_info()
        observed = observation_clock() if observation_clock is not None else None
        if observed is not None:
            self.identity_diagnostics["account_read_observed_utc"] = observed.isoformat()
        # Preserve the actual account return interval while terminal/identity
        # checks complete. No baseline proof is accepted or persisted yet.
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
        self.identity_diagnostics.update(dict(
            identity_account_present=account is not None,
            identity_terminal_present=terminal is not None,
            identity_require_trade_permissions=bool(require_trade_permissions),
            identity_terminal_connected=flag(terminal, "connected"),
            identity_terminal_trade_allowed=flag(terminal, "trade_allowed"),
            identity_terminal_tradeapi_disabled=flag(terminal, "tradeapi_disabled"),
            identity_account_trade_allowed=flag(account, "trade_allowed"),
            identity_account_trade_expert=flag(account, "trade_expert"),
            identity_blockers=[],
        ))
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
        if requested is not None and observed is not None:
            # AccountInfo is the same returned named tuple checked above.
            # Only verified identity/terminal/capital reaches this candidate.
            self.account_observation = dict(
                request_started=requested, observed=observed, account=account,
            )
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
            ) not in DAY_BASELINE_SOURCES:
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
                # Fail-closed broker-tick fallback; raises day_start_floating_unknown
                # unless every consistency check passes.
                baseline, evidence = self._reconstruct_held_boundary(
                    account, positions, deals, midnight, day)
                self.journal.put("day", {
                    "day": day, "equity": baseline, "source": HELD_TICK_SOURCE,
                    "account_fingerprint": self.fingerprint,
                    "boundary_tick_time_msc": evidence["tick"]["time_msc"],
                })
                return baseline
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

    def _reconstruct_held_boundary(self, account, positions, deals, midnight, day):
        """Day-start equity when a position was held across 00:00 UTC but no
        first-second account mark exists. Fail-closed: any gap or inconsistency
        raises day_start_floating_unknown.

        baseline = balance at boundary
                   + sum(floating P/L of each held position valued at the broker's
                         last tick at/before 00:00:00.000 UTC, close side:
                         BUY at bid, SELL at ask)
                   + sum(max(0, unrealized swap of each held position))

        Conservatism: admission blocks when baseline - equity >= 10% * baseline,
        so a HIGHER baseline triggers the daily stop EARLIER. Every ambiguous
        term is therefore resolved upward, never downward:
          * swap: the share accrued before 00:00 is unknown, so a negative swap
            is ignored (adds 0 instead of a loss) and a positive swap is added in
            full; both are >= the true pre-boundary accrual.
          * close-side valuation equals the terminal's own equity definition;
            no spread or tick is chosen in our favour.
          * exit commission is excluded (not part of equity before the close).
        """
        retry = getattr(self, "_reconstruct_retry", None)
        if retry and retry[0] == day and time.monotonic() < retry[1]:
            raise ValueError("day_start_floating_unknown")
        try:
            baseline, evidence = self._held_boundary_value(account, positions, deals, midnight)
        except ValueError as exc:
            reason = str(exc)
            self._reconstruct_retry = (day, time.monotonic() + RECONSTRUCT_RETRY_SECONDS)
            if self.journal.get("held_boundary_reconstruct_last") != day + "|" + reason:
                self.journal.audit("BOUNDARY_RECONSTRUCT_BLOCKED", day=day, reason=reason)
                self.journal.put("held_boundary_reconstruct_last", day + "|" + reason)
            raise ValueError("day_start_floating_unknown") from None
        self.journal.audit("BOUNDARY_RECONSTRUCTED", day=day, source=HELD_TICK_SOURCE,
                           baseline=baseline, evidence=evidence)
        return baseline, evidence

    def _held_boundary_value(self, account, positions, deals, midnight):
        boundary = int(midnight.timestamp() * 1000)
        if str(getattr(account, "currency", "")) != "USD":
            raise ValueError("held_boundary_currency")
        info = self._spec()
        if str(getattr(info, "currency_profit", "")) != "USD":
            raise ValueError("held_boundary_profit_currency")
        contract = float(info.trade_contract_size)
        balance_b = float(account.balance) - sum(
            _cash(d) for d in deals if int(d.time_msc) >= boundary)
        if not _finite(balance_b, positive=True):
            raise ValueError("held_boundary_balance")
        by_id: dict[int, list] = {}
        for d in deals:
            if int(d.type) in (0, 1):
                by_id.setdefault(int(d.position_id), []).append(d)
        live = {int(p.identifier): p for p in positions}
        held = []
        for ident, rows in by_id.items():
            pre = [d for d in rows if int(d.time_msc) < boundary]
            net = sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in pre)
            if abs(net) <= 1e-8:
                continue
            # Only a plain open held over midnight: one side, IN deals only,
            # on this symbol. Partial closes/reversals before 00:00 -> unknown.
            if (any(int(d.entry) != 0 for d in pre)
                    or len({int(d.type) for d in pre}) != 1
                    or any(str(d.symbol) != self.symbol for d in rows)):
                raise ValueError("held_boundary_unsupported_position")
            side = 1 if int(pre[0].type) == 0 else -1
            volume = sum(float(d.volume) for d in pre)
            open_price = sum(float(d.price) * float(d.volume) for d in pre) / volume
            if not (_finite(volume, positive=True) and _finite(open_price, positive=True)):
                raise ValueError("held_boundary_open_invalid")
            post = [d for d in rows if int(d.time_msc) >= boundary]
            if ident in live:
                p = live[ident]
                if post or abs(float(p.volume) - volume) > 1e-8 or abs(float(p.price_open) - open_price) > 1e-9:
                    raise ValueError("held_boundary_live_mismatch")
                expected = side * (float(p.price_current) - open_price) * volume * contract
                if abs(float(p.profit) - expected) > PROFIT_CHECK_TOLERANCE:
                    raise ValueError("held_boundary_profit_formula_mismatch")
                swap = float(p.swap)
            else:
                exits = [d for d in post if int(d.entry) in (1, 3)]
                if not exits or any(int(d.entry) not in (1, 3) or int(d.type) == int(pre[0].type) for d in post):
                    raise ValueError("held_boundary_exit_mismatch")
                if abs(sum(float(d.volume) for d in exits) - volume) > 1e-8:
                    raise ValueError("held_boundary_exit_volume")
                for d in exits:
                    expected = side * (float(d.price) - open_price) * float(d.volume) * contract
                    if abs(float(d.profit) - expected) > PROFIT_CHECK_TOLERANCE:
                        raise ValueError("held_boundary_profit_formula_mismatch")
                swap = sum(float(d.swap) for d in exits)
            if not _finite(swap):
                raise ValueError("held_boundary_swap_invalid")
            held.append(dict(position_id=ident, side="BUY" if side == 1 else "SELL",
                             volume=volume, open_price=open_price, swap_unrealized=swap,
                             still_open=ident in live))
        if not held:
            raise ValueError("held_boundary_none")
        ticks = self.mt5.copy_ticks_range(
            self.symbol,
            int(midnight.timestamp()) - BOUNDARY_TICK_LOOKBACK_SECONDS,
            int(midnight.timestamp()) + 1,
            self.mt5.COPY_TICKS_ALL,
        )
        if ticks is None or len(ticks) == 0:
            raise ValueError("held_boundary_ticks_missing")
        last = None
        for t in ticks:
            stamp = int(t["time_msc"])
            bid, ask = float(t["bid"]), float(t["ask"])
            if not (_finite(bid, positive=True) and _finite(ask, positive=True) and ask >= bid):
                continue  # flag-only/invalid rows never supply a valuation
            if stamp <= boundary and (last is None or stamp >= last[0]):
                last = (stamp, bid, ask)
        if last is None:
            raise ValueError("held_boundary_ticks_missing")
        stamp, bid, ask = last
        if not (_finite(bid, positive=True) and _finite(ask, positive=True) and ask >= bid):
            raise ValueError("held_boundary_tick_invalid")
        if boundary - stamp > BOUNDARY_TICK_MAX_AGE_MS:
            raise ValueError("held_boundary_tick_stale")
        floating = 0.0
        for h in held:
            side = 1 if h["side"] == "BUY" else -1
            price = bid if side == 1 else ask
            h["boundary_price"] = price
            h["floating"] = side * (price - h["open_price"]) * h["volume"] * contract
            h["swap_added"] = max(0.0, h["swap_unrealized"])
            floating += h["floating"] + h["swap_added"]
        baseline = balance_b + floating
        if not _finite(baseline, positive=True):
            raise ValueError("held_boundary_baseline_invalid")
        evidence = dict(
            boundary_utc=midnight.isoformat(), balance_at_boundary=round(balance_b, 2),
            contract_size=contract, tick=dict(time_msc=stamp, bid=bid, ask=ask,
                                               age_ms=boundary - stamp),
            positions=held, conservative_rules="swap=max(0,unrealized); close-side tick; higher baseline stops earlier",
        )
        return baseline, evidence

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
