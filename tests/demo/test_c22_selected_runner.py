"""Selected C22 public cycles with a broker boundary fixture."""

import hashlib
from types import SimpleNamespace as NS
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.c22_selected.runner import SelectedDemoRunner
from scripts.c22_selected.strategy import (
    CONTRACT,
    CANDIDATE_ID,
    MAGIC,
    ROOT,
    SNAPSHOT,
    SOURCE_PATHS,
)
from tests.demo.test_c22h4_demo import CandidateBroker
from tests.demo.test_trial30_demo import policy
from tests.demo.test_c22_selected_strategy import signal_bars

import pandas as pd


def selected_config():
    return {
        "snapshot": SNAPSHOT,
        "contract_id": CANDIDATE_ID,
        "contract": CONTRACT,
        "symbol": "XAUUSDm",
        "volume": 0.01,
        "real_money": "PROHIBITED",
        "research_only": True,
        "commission_unit": "USD_per_lot_round_trip",
        "source_hashes": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_PATHS
        },
    }


class SelectedBroker(CandidateBroker):
    def __init__(self, direction=-1):
        super().__init__(direction)
        source = signal_bars(direction)
        self.now = (source.index[-1] + pd.Timedelta(minutes=15, milliseconds=500)).to_pydatetime()
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

    def closed_loss(self, exit_ms, *, ident=99, net=-0.1):
        for number, entry, side, stamp in [(1, 0, 1, exit_ms - 60000), (2, 1, 0, exit_ms)]:
            self.deals.append(
                NS(
                    ticket=ident * 10 + number,
                    position_id=ident,
                    time_msc=stamp,
                    time=stamp // 1000,
                    entry=entry,
                    type=side,
                    volume=0.01,
                    magic=MAGIC if entry == 0 else 0,
                    comment="C22_fixture" if entry == 0 else "[be]",
                    price=self.tick.bid,
                    profit=0.0,
                    commission=0.0,
                    swap=net if entry == 1 else 0.0,
                    fee=0.0,
                )
            )
        self.account.balance += net
        self.account.equity = self.account.balance


class SelectedRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "selected.sqlite3"

    def runner(self, broker, *, execute=False):
        costs = policy() | {
            "reviewed_utc": broker.now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
        }
        runner = SelectedDemoRunner(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=self.path,
            config=selected_config(),
            cost_policy=costs,
            execute=execute,
        )
        self.addCleanup(runner.close)
        return runner

    def test_shadow_selected_sell_has_native_target_and_never_sends(self):
        broker = SelectedBroker()
        runner = self.runner(broker)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)
        request = result["request"]
        self.assertEqual(request["magic"], MAGIC)
        self.assertEqual(request["volume"], 0.01)
        self.assertAlmostEqual(
            (request["price"] - request["tp"]) / (request["sl"] - request["price"]), 1.35, delta=0.2
        )
        broker.order_send.assert_not_called()
        self.assertEqual(runner.strategy.max_daily_losses, 1)
        self.assertTrue(runner.strategy.protects(1))

    def test_ambiguous_selected_send_remains_unknown_after_restart(self):
        broker = SelectedBroker()
        broker.order_send.side_effect = lambda req: None
        first = self.runner(broker, execute=True)
        self.assertEqual(first.cycle(now=broker.now)["status"], "UNKNOWN")
        first.close()
        second = self.runner(broker, execute=True)
        self.assertEqual(second.cycle(now=broker.now + timedelta(seconds=1))["status"], "UNKNOWN")
        self.assertEqual(broker.order_send.call_count, 1)

    def test_buy_and_sell_move_be_only_after_a_new_closed_bar(self):
        for side in (1, -1):
            with self.subTest(side=side):
                self.path = Path(self.temp.name) / f"be-{side}.sqlite3"
                broker = SelectedBroker(side)
                runner = self.runner(broker, execute=True)
                self.assertEqual(runner.cycle(now=broker.now)["status"], "FILLED")
                request = broker.order_send.call_args.args[0]
                self.assertEqual(request["type"], 0 if side == 1 else 1)
                broker.tick.bid += side * 10
                broker.tick.ask += side * 10
                self.assertEqual(runner.cycle(now=broker.now)["status"], "MANAGING")
                broker.next_bar()
                result = runner.cycle(now=broker.now)
                self.assertEqual(result["status"], "BE_MOVED", result)
                self.assertEqual(broker.order_send.call_count, 2)
                runner.close()

    def test_cooldown_compares_first_quote_not_later_poll_and_consumes_bar(self):
        broker = SelectedBroker()
        broker.closed_loss(broker.tick.time_msc - 30 * 60 * 1000 + 1)
        runner = self.runner(broker)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result.get("reason"), "max_daily_losses", result)
        runner.close()
        restarted = self.runner(broker)
        duplicate = restarted.cycle(now=broker.now + timedelta(seconds=1))
        self.assertEqual(duplicate.get("reason"), "duplicate_bar", duplicate)
        broker.order_send.assert_not_called()

    def test_exact_elapsed_cooldown_boundary_admits_after_restart(self):
        broker = SelectedBroker()
        broker.closed_loss(broker.tick.time_msc - 30 * 60 * 1000)
        first = self.runner(broker)
        first.close()
        restarted = self.runner(broker)
        result = restarted.cycle(now=broker.now)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertEqual(result.get("reason"), "max_daily_losses", result)
        broker.order_send.assert_not_called()

    def test_two_net_losses_block_new_entry(self):
        broker = SelectedBroker()
        broker.closed_loss(broker.tick.time_msc - 60 * 60 * 1000, ident=98)
        broker.closed_loss(broker.tick.time_msc - 45 * 60 * 1000, ident=99)
        result = self.runner(broker).cycle(now=broker.now)
        self.assertEqual(result.get("reason"), "max_daily_losses", result)
        broker.order_send.assert_not_called()

    def test_negative_swap_cooldown_survives_utc_day_reset(self):
        broker = SelectedBroker()
        # Shift the complete source by a multiple of four hours so H4 boundaries
        # remain unchanged while the signal closes at UTC midnight.
        hours = (24 - broker.now.hour) % 24
        self.assertEqual(hours % 4, 0)
        delta_ms = hours * 3600 * 1000
        broker.now += timedelta(hours=hours)
        broker.tick.time_msc += delta_ms
        for rate in broker.rates:
            rate["time"] += delta_ms // 1000
        for deal in broker.deals:
            deal.time_msc += delta_ms
            deal.time = deal.time_msc // 1000
        broker.closed_loss(broker.tick.time_msc - 30 * 60 * 1000 + 1)
        runner = self.runner(broker)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result.get("reason"), "cooldown", result)
        self.assertLess(
            datetime.fromtimestamp(broker.deals[-1].time_msc / 1000, timezone.utc).date(),
            broker.now.date(),
        )
        broker.order_send.assert_not_called()

    def test_shadow_export_preserves_exact_causal_cache(self):
        broker = SelectedBroker()
        runner = self.runner(broker)
        result = runner.cycle(now=broker.now)
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)
        output = Path(self.temp.name) / "bars.csv"
        runner.export_cache(output)
        readback = pd.read_csv(output, parse_dates=["bar_open_utc"]).set_index("bar_open_utc")
        expected = runner.strategy.cache.bars.copy()
        readback.index = readback.index.as_unit("ns")
        expected.index = expected.index.as_unit("ns")
        pd.testing.assert_frame_equal(
            readback, expected, check_freq=False, check_names=False, check_exact=False, rtol=1e-12
        )
        broker.order_send.assert_not_called()
