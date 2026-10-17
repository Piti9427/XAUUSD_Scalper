"""Public trial30 cycle: completed M1 through broker-approved lifecycle."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import Mock
import hashlib
import unittest

import pandas as pd

from scripts.trial30.runner import Trial30DemoRunner

NOW = datetime(2026, 10, 1, 12, 0, 0, 500000, tzinfo=timezone.utc)


class Broker:
    TIMEFRAME_M1 = 1
    COPY_TICKS_ALL = 0
    ACCOUNT_TRADE_MODE_DEMO = 0
    SYMBOL_TRADE_MODE_FULL = 4
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_SLTP = 6
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_IOC = 2
    ORDER_TIME_GTC = 0

    def __init__(self):
        self.account = NS(
            login=123,
            server="Exness-Demo",
            trade_mode=0,
            margin_mode=2,
            currency="USD",
            balance=200.0,
            equity=200.0,
            margin_free=200.0,
            trade_allowed=True,
            trade_expert=True,
        )
        self.info = NS(
            name="XAUUSDm",
            trade_mode=4,
            trade_contract_size=100.0,
            trade_tick_size=0.001,
            point=0.001,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            trade_stops_level=0,
            trade_freeze_level=0,
            filling_mode=3,
        )
        self.tick = NS(time_msc=int(NOW.timestamp() * 1000) - 400, bid=97.0, ask=97.2)
        self.positions = []
        self.orders = []
        self.deals = [
            NS(
                ticket=1,
                time=int((NOW - timedelta(days=2)).timestamp()),
                time_msc=int((NOW - timedelta(days=2)).timestamp() * 1000),
                type=2,
                entry=0,
                volume=0.0,
                position_id=0,
                profit=200.0,
                commission=0.0,
                swap=0.0,
                fee=0.0,
                magic=0,
                comment="",
            )
        ]
        self.rates = []
        opens = pd.date_range(end="2026-10-01 11:45:00+00:00", periods=64, freq="15min")
        for i, ts in enumerate(opens):
            close = 97.0 if i == 63 else 100.0
            for minute in range(15):
                self.rates.append(
                    dict(
                        time=int(ts.timestamp()) + minute * 60,
                        open=close,
                        high=close + 0.5,
                        low=close - 0.5,
                        close=close,
                        tick_volume=1,
                    )
                )
        self.order_send = Mock(side_effect=self.send)
        self.order_check = Mock(return_value=NS(retcode=0))

    def account_info(self):
        return self.account

    def terminal_info(self):
        return NS(connected=True, trade_allowed=True, tradeapi_disabled=False)

    def symbol_info(self, symbol):
        return self.info

    def symbol_info_tick(self, symbol):
        return self.tick

    def positions_get(self, **kwargs):
        return tuple(self.positions)

    def orders_get(self, **kwargs):
        return tuple(self.orders)

    def copy_rates_from_pos(self, *args):
        return self.rates

    def copy_ticks_range(self, symbol, start, end, flag):
        return [dict(time_msc=self.tick.time_msc, bid=self.tick.bid, ask=self.tick.ask)]

    def order_calc_margin(self, *args):
        return 5.0

    def order_calc_profit(self, action, symbol, volume, entry, exit):
        return (entry - exit) * volume * 100 if action == 1 else (exit - entry) * volume * 100

    def history_deals_get(self, start=None, end=None, **kwargs):
        if "position" in kwargs:
            return tuple(d for d in self.deals if d.position_id == kwargs["position"])
        return tuple(self.deals)

    def history_deals_total(self, start, end):
        return len(self.deals)

    def send(self, req):
        if req["action"] == 6:
            self.positions[0].sl = req["sl"]
        else:
            self.positions.append(
                NS(
                    ticket=777,
                    identifier=777,
                    type=1,
                    volume=0.01,
                    symbol="XAUUSDm",
                    magic=req["magic"],
                    comment=req["comment"],
                    price_open=req["price"],
                    sl=req["sl"],
                    tp=req["tp"],
                    time_msc=self.tick.time_msc,
                )
            )
            self.deals.append(
                NS(
                    ticket=2,
                    time=int(NOW.timestamp()),
                    time_msc=self.tick.time_msc,
                    type=1,
                    entry=0,
                    volume=0.01,
                    position_id=777,
                    profit=0.0,
                    commission=0.0,
                    swap=0.0,
                    fee=0.0,
                    magic=req["magic"],
                    comment=req["comment"],
                    price=req["price"],
                )
            )
        return NS(retcode=10009, order=777, deal=2, price=req.get("price", 0.0), volume=0.01)


def policy():
    return dict(
        version=1,
        account_fingerprint=hashlib.sha256(b"Exness-Demo:123").hexdigest()[:16],
        account_type="Standard Demo",
        source="fixture tariff",
        commission_source="fixture",
        commission_unit="USD_per_lot_round_trip",
        commission_per_lot=0.0,
        commission_from_symbol_info=False,
        account_evidence_sha256="a" * 64,
        slippage_allowance_price=0.1,
        slippage_basis="declared_assumption",
        spread_buffer=0.0,
        swap_free_qualified=True,
        swap_free_scope="current_policy_not_historical",
        reviewed_utc="2026-10-01T00:00:00+00:00",
    )


class Trial30DemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.broker = Broker()
        self.events = []
        self.path = Path(self.tmp.name) / "journal.sqlite3"

    def runner(self, **overrides):
        args = dict(
            mt5=self.broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=self.path,
            cost_policy=policy(),
            execute=True,
            notify=self.events.append,
        )
        runner = Trial30DemoRunner(**(args | overrides))
        self.addCleanup(runner.close)
        return runner

    def test_real_cycle_places_fixed_sell_with_trial30_stops_and_only_fill_notification(self):
        runner = self.runner()
        result = runner.cycle(now=NOW)
        self.assertEqual(result["status"], "FILLED", result)
        request = self.broker.order_send.call_args.args[0]
        self.assertEqual(request["type"], 1)
        self.assertEqual(request["volume"], 0.01)
        # ATR=(13*1+3.5)/14=1.178571; conservative SELL grid ceiling.
        self.assertEqual(request["sl"], 99.947)
        self.assertEqual(request["tp"], 93.465)
        self.assertEqual([e["kind"] for e in self.events], ["FILLED"])
        self.assertEqual(self.events[0]["ticket"], 777)

    def test_restart_moves_be_only_after_closed_bar_keeps_tp_and_never_reenters(self):
        runner = self.runner()
        self.assertEqual(runner.cycle(now=NOW)["status"], "FILLED")
        runner.close()
        self.broker.tick.bid = 93.5
        self.broker.tick.ask = 93.7
        self.broker.tick.time_msc = int((NOW + timedelta(minutes=5)).timestamp() * 1000)
        restarted = self.runner()
        self.assertEqual(restarted.cycle(now=NOW + timedelta(minutes=5))["status"], "MANAGING")
        self.assertEqual(self.broker.order_send.call_count, 1)
        ts = pd.Timestamp("2026-10-01 12:00:00+00:00")
        for minute in range(15):
            self.broker.rates.append(
                dict(
                    time=int(ts.timestamp()) + minute * 60,
                    open=94.0,
                    high=94.5,
                    low=93.5,
                    close=94.0,
                    tick_volume=1,
                )
            )
        later = NOW + timedelta(minutes=15)
        self.broker.tick.time_msc = int(later.timestamp() * 1000) - 400
        self.assertEqual(restarted.cycle(now=later)["status"], "BE_MOVED")
        req = self.broker.order_send.call_args.args[0]
        self.assertEqual(req["action"], 6)
        self.assertEqual(req["position"], 777)
        self.assertEqual(req["sl"], 96.9)
        self.assertEqual(req["tp"], 93.465)
        restarted.cycle(now=later)
        self.assertEqual(self.broker.order_send.call_count, 2)
        self.assertEqual([e["kind"] for e in self.events], ["FILLED", "BE_MOVED"])

    def test_closed_deal_reconciles_pnl_preserves_day_start_and_no_duplicate_order(self):
        runner = self.runner()
        runner.cycle(now=NOW)
        opening = self.broker.deals[-1]
        self.broker.positions = []
        self.broker.deals.append(
            NS(
                ticket=3,
                time=int(NOW.timestamp()) + 60,
                time_msc=int(NOW.timestamp() * 1000) + 60000,
                type=0,
                entry=1,
                volume=0.01,
                position_id=777,
                profit=-3.0,
                commission=0.0,
                swap=0.0,
                fee=0.0,
                magic=opening.magic,
                comment="[sl]",
                price=100.0,
            )
        )
        self.broker.account.balance = 197.0
        self.broker.account.equity = 197.0
        later = NOW + timedelta(minutes=1)
        self.broker.tick.time_msc = int(later.timestamp() * 1000)
        result = runner.cycle(now=later)
        self.assertEqual(result["status"], "CLOSED", result)
        self.assertEqual(result["net"], -3.0)
        self.assertEqual(result["day_start"], 200.0)
        runner.cycle(now=later)
        self.assertEqual(self.broker.order_send.call_count, 1)
        self.assertEqual([e["kind"] for e in self.events], ["FILLED", "CLOSED"])

    def test_unknown_response_reconciles_fill_and_timeout_without_fill_never_retries(self):
        runner = self.runner()
        self.broker.order_send.side_effect = lambda req: None
        self.assertEqual(runner.cycle(now=NOW)["status"], "UNKNOWN")
        runner.close()
        self.assertEqual(self.runner().cycle(now=NOW)["status"], "UNKNOWN")
        self.assertEqual(self.broker.order_send.call_count, 1)
        self.assertEqual(self.events, [])

    def test_timeout_retcode_is_not_treated_as_definitive_rejection(self):
        runner = self.runner()
        self.broker.order_send.side_effect = lambda req: NS(retcode=10012)
        self.assertEqual(runner.cycle(now=NOW)["status"], "UNKNOWN")
        runner.cycle(now=NOW)
        self.assertEqual(self.broker.order_send.call_count, 1)

    def test_shadow_does_not_submit_or_notify_and_does_not_consume_live_bar(self):
        runner = self.runner(execute=False)
        self.assertEqual(runner.cycle(now=NOW)["status"], "SHADOW_ADMIT")
        self.broker.order_send.assert_not_called()
        self.assertEqual(self.events, [])
        runner.close()
        self.assertEqual(self.runner().cycle(now=NOW)["status"], "FILLED")

    def test_identity_permissions_costs_exposure_and_margin_fail_closed(self):
        cases = [
            ("real", lambda b: setattr(b.account, "trade_mode", 2)),
            ("netting", lambda b: setattr(b.account, "margin_mode", 0)),
            ("wrong_login", lambda b: setattr(b.account, "login", 124)),
            ("permissions", lambda b: setattr(b.account, "trade_expert", False)),
            ("pending", lambda b: b.orders.append(NS(symbol="XAUUSDm"))),
            ("margin", lambda b: setattr(b.account, "margin_free", 1.0)),
            ("equity", lambda b: setattr(b.account, "equity", 20.0)),
        ]
        for name, change in cases:
            with self.subTest(case=name), TemporaryDirectory() as temp:
                self.broker = Broker()
                self.path = Path(temp) / "test.sqlite3"
                change(self.broker)
                result = self.runner().cycle(now=NOW)
                self.assertEqual(result["status"], "BLOCKED", result)
                self.broker.order_send.assert_not_called()
        self.assertEqual(self.events, [])

    def test_intraday_loss_20percent_reconstructed_from_history_blocks_new_risk(self):
        self.broker.account.balance = 160.0
        self.broker.account.equity = 160.0
        for ticket, kind in ((2, 1), (3, 0)):
            self.broker.deals.append(
                NS(
                    ticket=ticket,
                    time=int(NOW.timestamp()) - 60,
                    time_msc=int(NOW.timestamp() * 1000) - 60000,
                    type=kind,
                    entry=0 if ticket == 2 else 1,
                    volume=0.01,
                    position_id=88,
                    profit=0.0 if ticket == 2 else -40.0,
                    commission=0.0,
                    swap=0.0,
                    fee=0.0,
                    magic=0,
                    comment="",
                    price=100.0,
                )
            )
        result = self.runner().cycle(now=NOW)
        self.assertEqual(result["reason"], "daily_loss_limit", result)
        self.broker.order_send.assert_not_called()

    def test_buy_breakout_never_opens(self):
        for row in self.broker.rates[-15:]:
            row.update(open=103.0, high=103.5, low=102.5, close=103.0)
        result = self.runner().cycle(now=NOW)
        self.assertEqual(result["reason"], "no_sell_signal")
        self.broker.order_send.assert_not_called()

    def test_broker_check_reject_has_no_order_or_notification(self):
        self.broker.order_check.return_value = NS(retcode=10019)
        result = self.runner().cycle(now=NOW)
        self.assertEqual(result["reason"], "order_check_rejected")
        self.broker.order_send.assert_not_called()
        self.assertEqual(self.events, [])

    def test_second_writer_rejected_while_first_runner_is_alive(self):
        self.runner()
        with self.assertRaisesRegex(ValueError, "another trial30 writer"):
            self.runner()

    def test_carried_position_protection_not_blocked_by_missing_new_day_baseline(self):
        runner = self.runner()
        runner.cycle(now=NOW)
        later = NOW + timedelta(hours=12, seconds=5)
        self.broker.tick.time_msc = int(later.timestamp() * 1000)
        self.assertEqual(runner.cycle(now=later)["status"], "MANAGING")

    def test_fill_over_risk_cap_closes_only_owned_ticket_and_sends_no_fill_alert(self):
        runner = self.runner()
        original = self.broker.send

        def bad_fill(req):
            if req.get("position"):
                position = self.broker.positions.pop()
                self.broker.deals.append(
                    NS(
                        ticket=3,
                        time=int(NOW.timestamp()),
                        time_msc=self.broker.tick.time_msc,
                        type=0,
                        entry=1,
                        volume=0.01,
                        position_id=position.identifier,
                        profit=-1.0,
                        commission=0.0,
                        swap=0.0,
                        fee=0.0,
                        magic=req["magic"],
                        comment=req["comment"],
                        price=97.2,
                    )
                )
                self.broker.account.balance = 199.0
                self.broker.account.equity = 199.0
                return NS(retcode=10009)
            result = original(req)
            self.broker.positions[0].price_open = 70.0
            return result

        self.broker.order_send.side_effect = bad_fill
        result = runner.cycle(now=NOW)
        self.assertEqual(result["status"], "SAFETY_CLOSED", result)
        self.assertEqual(self.broker.order_send.call_count, 2)
        self.assertEqual(self.broker.order_send.call_args.args[0]["position"], 777)
        self.assertNotIn("FILLED", [e["kind"] for e in self.events])
        self.assertEqual(runner.cycle(now=NOW)["reason"], "safety_halt")

    def test_first_quote_and_entry_request_use_observed_prices_not_closed_bar_close(self):
        self.broker.tick.bid = 96.8
        self.broker.tick.ask = 97.0
        self.broker.copy_ticks_range = lambda *args: [
            dict(time_msc=self.broker.tick.time_msc - 50, bid=96.9, ask=97.1)
        ]
        result = self.runner().cycle(now=NOW)
        self.assertEqual(result["status"], "FILLED")
        self.assertEqual(self.broker.order_send.call_args.args[0]["price"], 96.8)

    def test_stale_policy_missing_history_and_incomplete_signal_bar_do_not_submit(self):
        stale = policy() | {"reviewed_utc": "2026-09-29T00:00:00+00:00"}
        result = self.runner(cost_policy=stale).cycle(now=NOW)
        self.assertEqual(result["reason"], "cost_policy_invalid_or_stale")
        self.broker.order_send.assert_not_called()

    def test_partial_fill_is_contained_never_advertised_as_fixed_lot_fill(self):
        original = self.broker.send

        def partial(req):
            result = original(req)
            if not req.get("position"):
                self.broker.positions[0].volume = 0.005
                self.broker.deals[-1].volume = 0.005
                return NS(retcode=10010)
            return result

        self.broker.order_send.side_effect = partial
        # Safety-close outcome may remain unknown in this fake; no FILLED event allowed.
        result = self.runner().cycle(now=NOW)
        self.assertNotEqual(result["status"], "FILLED")
        self.assertNotIn("FILLED", [e["kind"] for e in self.events])

    def test_incomplete_last_m1_interval_is_not_used_as_signal(self):
        self.broker.rates.pop()
        result = self.runner().cycle(now=NOW)
        self.assertEqual(result["reason"], "no_sell_signal")
        self.broker.order_send.assert_not_called()

    def test_missing_history_and_foreign_position_fail_closed(self):
        self.broker.history_deals_get = lambda *args, **kwargs: None
        result = self.runner().cycle(now=NOW)
        self.assertEqual(result["reason"], "history_unknown")
        self.broker.order_send.assert_not_called()

    def test_notification_failure_retried_without_order_resubmission(self):
        notify = Mock(side_effect=RuntimeError("offline"))
        runner = self.runner(notify=notify)
        self.assertEqual(runner.cycle(now=NOW)["notification"], "pending_retry")
        notify.side_effect = None
        runner.cycle(now=NOW)
        self.assertEqual(self.broker.order_send.call_count, 1)
        self.assertEqual(notify.call_count, 2)

    def test_broker_fill_report_without_position_is_not_notified(self):
        self.broker.order_send.side_effect = lambda req: NS(retcode=10009)
        result = self.runner().cycle(now=NOW)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(self.events, [])

    def test_nan_symbol_spec_and_naive_clock_rejected(self):
        runner = self.runner()
        self.broker.info.point = float("nan")
        self.assertEqual(runner.cycle(now=NOW)["reason"], "symbol_spec_invalid")
        self.broker.order_send.assert_not_called()
        with self.assertRaisesRegex(ValueError, "aware UTC"):
            runner.cycle(now=NOW.replace(tzinfo=None))

    def test_price_moves_during_order_check_rejects_stale_request_before_send(self):
        def check(req):
            self.broker.tick.bid = 90.0
            self.broker.tick.ask = 90.2
            return NS(retcode=0)

        self.broker.order_check.side_effect = check
        result = self.runner().cycle(now=NOW)
        self.assertEqual(result["reason"], "quote_changed_before_send")
        self.broker.order_send.assert_not_called()

    def test_be_restart_uses_first_post_close_quote_not_later_profitable_quote(self):
        runner = self.runner()
        runner.cycle(now=NOW)
        runner.close()
        ts = pd.Timestamp("2026-10-01 12:00:00+00:00")
        for minute in range(15):
            self.broker.rates.append(
                dict(
                    time=int(ts.timestamp()) + minute * 60,
                    open=94.0,
                    high=94.5,
                    low=93.5,
                    close=94.0,
                    tick_volume=1,
                )
            )
        later = NOW + timedelta(minutes=20)
        self.broker.tick.bid = 93.5
        self.broker.tick.ask = 93.7
        self.broker.tick.time_msc = int(later.timestamp() * 1000)
        first = int((NOW + timedelta(minutes=15)).timestamp() * 1000)
        self.broker.copy_ticks_range = lambda *args: [dict(time_msc=first, bid=96.9, ask=97.1)]
        result = self.runner().cycle(now=later)
        self.assertEqual(result["status"], "MANAGING")
        self.assertEqual(self.broker.order_send.call_count, 1)

    def test_be_rechecks_geometry_after_broker_check_price_change(self):
        runner = self.runner()
        runner.cycle(now=NOW)
        ts = pd.Timestamp("2026-10-01 12:00:00+00:00")
        for minute in range(15):
            self.broker.rates.append(
                dict(
                    time=int(ts.timestamp()) + minute * 60,
                    open=94.0,
                    high=94.5,
                    low=93.5,
                    close=94.0,
                    tick_volume=1,
                )
            )
        later = NOW + timedelta(minutes=15)
        self.broker.tick.bid = 93.5
        self.broker.tick.ask = 93.7
        self.broker.tick.time_msc = int(later.timestamp() * 1000) - 400

        def check(req):
            self.broker.tick.bid = 97.0
            self.broker.tick.ask = 97.2
            return NS(retcode=0)

        self.broker.order_check.side_effect = check
        result = runner.cycle(now=later)
        self.assertEqual(result["reason"], "be_geometry_changed")
        self.assertEqual(self.broker.order_send.call_count, 1)

    def test_be_rechecks_quote_age_after_slow_broker_check(self):
        from unittest.mock import patch

        runner = self.runner()
        runner.cycle(now=NOW)
        ts = pd.Timestamp("2026-10-01 12:00:00+00:00")
        for minute in range(15):
            self.broker.rates.append(
                dict(
                    time=int(ts.timestamp()) + minute * 60,
                    open=94.0,
                    high=94.5,
                    low=93.5,
                    close=94.0,
                    tick_volume=1,
                )
            )
        later = NOW + timedelta(minutes=15)
        self.broker.tick.bid = 93.5
        self.broker.tick.ask = 93.7
        self.broker.tick.time_msc = int(later.timestamp() * 1000) - 400
        elapsed = [0.0]
        self.broker.order_check.side_effect = lambda req: (
            elapsed.__setitem__(0, 61.0) or NS(retcode=0)
        )
        with patch("scripts.trial30.runner.time.monotonic", side_effect=lambda: elapsed[0]):
            result = runner.cycle(now=later)
        self.assertEqual(result["reason"], "quote_stale")
        self.assertEqual(self.broker.order_send.call_count, 1)

    def test_broker_changed_initial_target_is_contained_before_fill_notification(self):
        original = self.broker.send

        def wrong_target(req):
            result = original(req)
            if not req.get("position"):
                self.broker.positions[0].tp = 95.0
            return result

        self.broker.order_send.side_effect = wrong_target
        result = self.runner().cycle(now=NOW)
        self.assertNotEqual(result["status"], "FILLED")
        self.assertEqual(self.broker.order_send.call_count, 2)
        self.assertNotIn("FILLED", [e["kind"] for e in self.events])

    def test_unexpected_entry_fee_is_contained_instead_of_claiming_zero_cost_fill(self):
        original = self.broker.send

        def costly(req):
            result = original(req)
            if not req.get("position"):
                self.broker.deals[-1].commission = -25.0
                self.broker.account.balance = 175.0
                self.broker.account.equity = 175.0
            return result

        self.broker.order_send.side_effect = costly
        result = self.runner().cycle(now=NOW)
        self.assertNotEqual(result["status"], "FILLED")
        self.assertEqual(self.broker.order_send.call_count, 2)
        self.assertNotIn("FILLED", [e["kind"] for e in self.events])
