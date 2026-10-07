"""Candidate public cycle through complete broker API, both directions."""

from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import Mock
import json
import unittest

import numpy as np
import pandas as pd

from scripts.c22h4.runner import C22H4DemoRunner, MAGIC
from test_trial30_demo import Broker, policy
from test_c22h4_strategy import bars


def buy_bars():
    x = np.arange(3393)
    c = 100 + x * 0.03 + 0.5 * np.sin(x * 2 * np.pi / 40)
    return pd.DataFrame(
        dict(open=c, high=c + 0.5, low=c - 0.5, close=c),
        index=pd.date_range("2026-08-01", periods=len(c), freq="15min", tz="UTC"),
    )


class CandidateBroker(Broker):
    def __init__(self, direction=-1):
        super().__init__()
        source = buy_bars() if direction == 1 else bars()
        self.now = (source.index[-1] + pd.Timedelta(minutes=15, milliseconds=500)).to_pydatetime()
        self.account.leverage = 2000
        self.tick.time_msc = int(self.now.timestamp() * 1000) - 400
        self.tick.bid = float(source.close.iloc[-1])
        self.tick.ask = self.tick.bid + 0.2
        self.deals[0].time_msc = int((self.now - timedelta(days=2)).timestamp() * 1000)
        self.deals[0].time = self.deals[0].time_msc // 1000
        self.rates = []
        for stamp, row in source.iterrows():
            self.rates.extend(
                dict(
                    time=int(stamp.timestamp()) + minute * 60,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    tick_volume=1,
                )
                for minute in range(15)
            )

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        end = len(self.rates) - start
        begin = end - count
        if end <= 0 or begin >= end:
            return None
        return self.rates[max(0, begin) : end]

    def send(self, req):
        if req.get("position") and req["action"] == 1:
            p = next(p for p in self.positions if p.ticket == req["position"])
            self.positions.remove(p)
            self.deals.append(
                NS(
                    ticket=len(self.deals) + 1,
                    time_msc=self.tick.time_msc,
                    time=self.tick.time_msc // 1000,
                    type=req["type"],
                    entry=1,
                    volume=req["volume"],
                    position_id=p.identifier,
                    profit=-1.0,
                    commission=0.0,
                    swap=0.0,
                    fee=0.0,
                    magic=0,
                    comment="[sl]",
                    price=req["price"],
                )
            )
            self.account.balance -= 1.0
            self.account.equity = self.account.balance
            return NS(retcode=10009)
        result = super().send(req)
        if req["action"] == 1:
            self.positions[-1].type = req["type"]
            self.deals[-1].type = req["type"]
            self.deals[-1].time_msc = self.tick.time_msc
            self.deals[-1].time = self.tick.time_msc // 1000
        return result

    def next_bar(self):
        start = pd.Timestamp(self.now).floor("15min")
        for minute in range(15):
            self.rates.append(
                dict(
                    time=int(start.timestamp()) + minute * 60,
                    open=self.tick.bid,
                    high=self.tick.bid + 0.5,
                    low=self.tick.bid - 0.5,
                    close=self.tick.bid,
                    tick_volume=1,
                )
            )
        self.now += timedelta(minutes=15)
        self.tick.time_msc = int(self.now.timestamp() * 1000) - 400


class CandidateLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "demo.sqlite3"
        self.events = []

    def runner(self, broker, **changes):
        costs = policy() | {
            "reviewed_utc": broker.now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
        }
        runner = C22H4DemoRunner(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=self.path,
            cost_policy=costs,
            execute=True,
            notify=self.events.append,
            **changes,
        )
        self.addCleanup(runner.close)
        return runner

    def test_buy_uses_ask_1_5_atr_and_rounded_2r_never_be(self):
        broker = CandidateBroker(1)
        runner = self.runner(broker)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "FILLED", result)
        req = broker.order_send.call_args.args[0]
        self.assertEqual(req["type"], 0)
        self.assertEqual(req["price"], broker.tick.ask)
        self.assertEqual(req["magic"], MAGIC)
        from scripts.research.breakout_entry import prepare_entry
        from scripts.research.breakout_models import Costs

        frame = runner.strategy.cache
        expected = prepare_entry(
            frame.row,
            broker.tick.bid,
            broker.tick.ask,
            dict(trade_tick_size=0.001, trade_contract_size=100, leverage=2000),
            frame.rules,
            Costs(slippage=0.1),
            200,
            200,
        )
        self.assertEqual((req["sl"], req["tp"]), (expected.stop, expected.target))
        broker.tick.bid += 10
        broker.tick.ask += 10
        broker.next_bar()
        self.assertEqual(runner.cycle(now=broker.now)["status"], "MANAGING")
        self.assertEqual(broker.order_send.call_count, 1)
        self.assertEqual([e["kind"] for e in self.events], ["FILLED"])

    def test_fill_and_close_append_entry_price_and_exit_review(self):
        broker = CandidateBroker()
        runner = self.runner(broker)
        filled = runner.cycle(now=broker.now)
        self.assertEqual(filled["status"], "FILLED")
        note = runner.trade_log_path.read_text()
        fill = runner.journal.get("active")["fill"]
        self.assertIn(f"{fill:.3f}", note)
        self.assertIn("เพราะ", note)
        self.assertIn("SELL", note)
        broker.send(dict(action=1, position=777, type=0, volume=0.01, price=broker.tick.ask))
        closed = runner.cycle(now=broker.now)
        self.assertEqual(closed["status"], "CLOSED")
        text = runner.trade_log_path.read_text()
        self.assertIn("EXIT", text)
        self.assertIn("ขาดทุน", text)
        self.assertIn("รอบหน้า", text)

    def test_sell_be_only_after_new_closed_bar(self):
        broker = CandidateBroker()
        runner = self.runner(broker)
        self.assertEqual(runner.cycle(now=broker.now)["status"], "FILLED")
        broker.tick.bid -= 5
        broker.tick.ask -= 5
        self.assertEqual(runner.cycle(now=broker.now)["status"], "MANAGING")
        broker.next_bar()
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "BE_MOVED", result)
        self.assertEqual([e["kind"] for e in self.events], ["FILLED", "BE_MOVED"])

    def test_buy_timeout_exception_and_restart_never_resubmit_without_evidence(self):
        self.test_timeout_exception_and_restart_never_resubmit_without_evidence(side=1)

    def test_timeout_exception_and_restart_never_resubmit_without_evidence(self, side=-1):
        for response in (None, NS(retcode=10012), RuntimeError("offline")):
            with self.subTest(response=response):
                self.path = Path(self.temp.name) / (str(id(response)) + ".sqlite3")
                broker = CandidateBroker(side)
                broker.order_send.side_effect = (
                    response if isinstance(response, Exception) else lambda req: response
                )
                runner = self.runner(broker)
                self.assertEqual(runner.cycle(now=broker.now)["status"], "UNKNOWN")
                runner.close()
                restart = self.runner(broker)
                self.assertEqual(restart.cycle(now=broker.now)["status"], "UNKNOWN")
                self.assertEqual(broker.order_send.call_count, 1)
                self.assertEqual(self.events, [])
                restart.close()

    def test_missing_opening_deal_never_announces_fill(self):
        broker = CandidateBroker(1)
        original = broker.send

        def no_deal(req):
            result = original(req)
            broker.deals.pop()
            return result

        broker.order_send.side_effect = no_deal
        result = self.runner(broker).cycle(now=broker.now)
        self.assertEqual(result["reason"], "awaiting_fill_deal_costs")
        self.assertEqual(self.events, [])

    def test_partial_or_over_cap_fill_safety_closes_only_owned_ticket(self):
        for side in (-1, 1):
            for failure in ("partial", "risk"):
                with self.subTest(side=side, failure=failure):
                    self.path = Path(self.temp.name) / f"{side}-{failure}.sqlite3"
                    broker = CandidateBroker(side)
                    original = broker.send

                    def bad(req):
                        result = original(req)
                        if not req.get("position"):
                            if failure == "partial":
                                broker.positions[-1].volume = 0.005
                                broker.deals[-1].volume = 0.005
                                return NS(retcode=10010)
                            broker.positions[-1].price_open += side * 30
                        return result

                    broker.order_send.side_effect = bad
                    runner = self.runner(broker)
                    result = runner.cycle(now=broker.now)
                    self.assertEqual(result["status"], "SAFETY_CLOSED", result)
                    self.assertEqual(broker.order_send.call_args.args[0]["position"], 777)
                    self.assertNotIn("FILLED", [e["kind"] for e in self.events])
                    runner.close()

    def test_buy_close_ledger_with_magic_zero_and_costs_blocks_one_loss_after_restart(self):
        self.test_close_ledger_with_magic_zero_and_costs_blocks_one_loss_after_restart(side=1)

    def test_close_ledger_with_magic_zero_and_costs_blocks_one_loss_after_restart(self, side=-1):
        broker = CandidateBroker(side)
        runner = self.runner(broker)
        self.assertEqual(runner.cycle(now=broker.now)["status"], "FILLED")
        broker.send(
            dict(
                action=1,
                position=777,
                type=0 if side == -1 else 1,
                volume=0.01,
                price=broker.tick.ask,
            )
        )
        broker.deals[-1].commission = -0.1
        broker.deals[-1].swap = -0.2
        broker.account.balance -= 0.3
        broker.account.equity = broker.account.balance
        self.assertAlmostEqual(runner.cycle(now=broker.now)["net"], -1.3)
        runner.close()
        restart = self.runner(broker)
        # Fresh completed SELL bar on same UTC exit day, not duplicate intent.
        if side == -1:
            broker.tick.bid -= 4
            broker.tick.ask -= 4
            broker.next_bar()
        else:
            # Replay same known BUY admission after restart to exercise ledger circuit.
            restart.journal.put("last_bar", None)
        result = restart.cycle(now=broker.now)
        self.assertEqual(result["reason"], "max_daily_losses", result)
        self.assertEqual(broker.order_send.call_count, 1)

    def test_daily_10_percent_blocks_below_old_20_percent(self):
        broker = CandidateBroker()
        broker.account.equity = 179
        runner = self.runner(broker)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["reason"], "daily_loss_limit", result)
        broker.order_send.assert_not_called()

    def test_source_drift_blocks_entries_but_reconciles_open_trade(self):
        broker = CandidateBroker()
        config = json.loads(Path("config/c22h4-demo.json").read_text()) | {"source_hashes": None}
        runner = self.runner(broker, config=config)
        self.assertEqual(runner.cycle(now=broker.now)["reason"], "source_drift")
        runner.close()
        runner = self.runner(broker)
        self.assertEqual(runner.cycle(now=broker.now)["status"], "FILLED")
        runner.close()
        restart = self.runner(broker, config=config)
        self.assertEqual(restart.cycle(now=broker.now)["status"], "MANAGING")
        self.assertEqual(broker.order_send.call_count, 1)

    def test_warmup_and_foreign_trial30_exposure_block(self):
        broker = CandidateBroker()
        broker.rates = broker.rates[-48000:]
        runner = self.runner(broker)
        self.assertEqual(runner.cycle(now=broker.now)["reason"], "macro_warmup_insufficient")
        runner.close()
        self.path = Path(self.temp.name) / "foreign.sqlite3"
        broker = CandidateBroker()
        broker.positions.append(
            NS(identifier=8, type=1, volume=0.01, magic=30261001, symbol="XAUUSDm")
        )
        broker.deals.append(
            NS(
                ticket=2,
                time_msc=broker.tick.time_msc,
                type=1,
                volume=0.01,
                position_id=8,
                profit=0.0,
                commission=0.0,
                fee=0.0,
                swap=0.0,
                entry=0,
                magic=30261001,
                comment="T30_x",
            )
        )
        self.assertEqual(self.runner(broker).cycle(now=broker.now)["reason"], "foreign_exposure")
        broker.order_send.assert_not_called()

    def test_outbox_retries_without_resubmission(self):
        broker = CandidateBroker(1)
        notify = Mock(side_effect=RuntimeError("offline"))
        runner = C22H4DemoRunner(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=self.path,
            cost_policy=policy() | {"reviewed_utc": broker.now.isoformat()},
            execute=True,
            notify=notify,
        )
        self.addCleanup(runner.close)
        self.assertEqual(runner.cycle(now=broker.now)["notification"], "pending_retry")
        notify.side_effect = None
        runner.cycle(now=broker.now)
        self.assertEqual(notify.call_count, 2)
        self.assertEqual(broker.order_send.call_count, 1)

    def test_trial30_and_candidate_cannot_share_account_concurrently(self):
        from scripts.trial30.runner import Trial30DemoRunner

        broker = CandidateBroker()
        runner = self.runner(broker)
        with self.assertRaisesRegex(ValueError, "another trial30 writer"):
            Trial30DemoRunner(
                mt5=broker,
                expected_login=123,
                expected_server="Exness-Demo",
                journal_path=self.path.parent / "trial30.sqlite3",
                cost_policy=policy(),
            )
        runner.close()
        rollback = Trial30DemoRunner(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=self.path.parent / "trial30.sqlite3",
            cost_policy=policy(),
        )
        rollback.close()

    def test_definitive_rejection_never_notifies_fill_both_directions(self):
        for side in (-1, 1):
            self.path = Path(self.temp.name) / f"rejected-{side}.sqlite3"
            broker = CandidateBroker(side)
            broker.order_send.side_effect = lambda req: NS(retcode=10019)
            runner = self.runner(broker)
            self.assertEqual(runner.cycle(now=broker.now)["status"], "REJECTED")
            self.assertIsNone(runner.journal.get("active"))
            runner.close()
        self.assertEqual(self.events, [])

    def test_buy_rechecks_ask_before_send(self):
        broker = CandidateBroker(1)

        def moved(req):
            broker.tick.ask += 0.2
            return NS(retcode=0)

        broker.order_check.side_effect = moved
        result = self.runner(broker).cycle(now=broker.now)
        self.assertEqual(result["reason"], "quote_changed_before_send", result)
        broker.order_send.assert_not_called()

    def test_buy_restart_sending_intent_not_closed_on_empty_ledger(self):
        self.test_restart_sending_intent_not_closed_on_empty_ledger(side=1)

    def test_restart_sending_intent_not_closed_on_empty_ledger(self, side=-1):
        broker = CandidateBroker(side)
        runner = self.runner(broker)
        broker.order_send.side_effect = lambda req: NS(retcode=10012)
        runner.cycle(now=broker.now)
        active = runner.journal.get("active")
        active["status"] = "SENDING"
        runner.journal.put("active", active)
        runner.close()
        restart = self.runner(broker)
        self.assertEqual(restart.cycle(now=broker.now)["status"], "UNKNOWN")
        self.assertIsNotNone(restart.journal.get("active"))
        self.assertEqual(self.events, [])

    def test_missing_bars_does_not_prevent_fill_or_closed_reconciliation(self):
        broker = CandidateBroker()
        runner = self.runner(broker)
        self.assertEqual(runner.cycle(now=broker.now)["status"], "FILLED")
        broker.rates = []
        self.assertEqual(runner.cycle(now=broker.now)["status"], "MANAGING")
        broker.send(dict(action=1, position=777, type=0, volume=0.01, price=broker.tick.ask))
        self.assertEqual(runner.cycle(now=broker.now)["status"], "CLOSED")

    def test_post_fill_cap_uses_fresh_entry_equity(self):
        broker = CandidateBroker(1)
        original_account = NS(**vars(broker.account))
        fresh_account = NS(**(vars(broker.account) | {"equity": 190.0}))
        count = [0]

        def account():
            count[0] += 1
            return original_account if count[0] == 1 else fresh_account

        broker.account_info = account
        original_profit = broker.order_calc_profit

        def profit(*args):
            return -19.15 if broker.positions else original_profit(*args)

        broker.order_calc_profit = profit
        result = self.runner(broker).cycle(now=broker.now)
        self.assertEqual(result["status"], "SAFETY_CLOSED", result)
        self.assertEqual(result["reason"], "filled_risk_violation")
