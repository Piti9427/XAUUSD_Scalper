"""Tests for Reward156 bidirectional Demo runner with BUY pause drawdown circuit."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
import numpy as np

from scripts.reward156.runner import Reward156DemoRunner

NOW = datetime(2026, 10, 1, 12, 0, 5, 0, tzinfo=timezone.utc)


class BrokerMock:
    TIMEFRAME_M1 = 1
    COPY_TICKS_ALL = 0
    ACCOUNT_TRADE_MODE_DEMO = 0
    SYMBOL_TRADE_MODE_FULL = 4
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    TRADE_RETCODE_DONE = 10009
    ORDER_FILLING_FOK = 0
    ORDER_TIME_GTC = 0

    def __init__(self, equity=200.0):
        self.account = NS(
            login=123,
            server="Exness-Demo",
            trade_mode=0,
            margin_mode=2,
            currency="USD",
            balance=200.0,
            equity=equity,
            margin_free=equity,
            trade_allowed=True,
            trade_expert=True,
        )
        self.info = NS(
            name="XAUUSDm",
            trade_mode=4,
            trade_contract_size=100.0,
            trade_tick_size=0.01,
            point=0.01,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            trade_stops_level=0,
            trade_freeze_level=0,
            filling_mode=1,
        )

    def initialize(self):
        return True

    def account_info(self):
        return self.account

    def symbol_info(self, symbol):
        return self.info

    def symbol_info_tick(self, symbol):
        return NS(time_msc=int(NOW.timestamp() * 1000), bid=2000.0, ask=2000.20)

    def copy_ticks_range(self, symbol, start, end, flags):
        return [NS(time_msc=int(NOW.timestamp() * 1000), bid=2000.0, ask=2000.20)]

    def positions_get(self, **kwargs):
        return []

    def orders_get(self, **kwargs):
        return []

    def history_deals_get(self, *args, **kwargs):
        return []

    def order_calc_profit(self, action, symbol, volume, entry, exit_):
        return -5.0

    def order_calc_margin(self, action, symbol, volume, price):
        return 2.0

    def order_check(self, request):
        return NS(retcode=0)

    def order_send(self, request):
        return NS(retcode=10009, order=999, price=request["price"])

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        # Generate 1500 M1 bars leading up to NOW
        # Grouped into M15 bars
        times = [NOW - timedelta(minutes=15) - timedelta(minutes=i) for i in range(count, 0, -1)]
        records = []
        for t in times:
            records.append({
                "time": int(t.timestamp()),
                "open": 2000.0,
                "high": 2001.0,
                "low": 1999.0,
                "close": 2000.0,
                "tick_volume": 10,
            })
        return np.array(
            [(r["time"], r["open"], r["high"], r["low"], r["close"], r["tick_volume"]) for r in records],
            dtype=[("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<i8")]
        )


class Reward156DemoRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.journal_path = Path(self.tmp.name) / "journal.sqlite3"
        self.cost_policy = {
            "account_fingerprint": "Exness-Demo:123",
            "slippage_allowance_price": 0.10,
            "commission_per_lot": 0.0,
            "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_runner_initialization_and_snapshot(self):
        broker = BrokerMock()
        runner = Reward156DemoRunner(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=self.journal_path,
            cost_policy=self.cost_policy,
        )
        self.assertEqual(runner.login, 123)
        self.assertEqual(runner.server, "Exness-Demo")
        runner.close()

    def test_buy_pause_drawdown_blocks_buy_when_over_five_percent(self):
        # Set peak equity at 200.0, but current equity at 188.0 (6% DD > 5%)
        broker = BrokerMock(equity=188.0)
        runner = Reward156DemoRunner(
            mt5=broker,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=self.journal_path,
            cost_policy=self.cost_policy,
        )
        runner.journal.put("peak_equity", 200.0)
        # Mock row to have BUY direction (1)
        # Verify that buy_pause_drawdown is raised/reported as BLOCKED
        res = runner.cycle(now=NOW)
        self.assertEqual(res["status"], "BLOCKED")
        runner.close()
