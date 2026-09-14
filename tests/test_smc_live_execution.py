import asyncio
from contextlib import ExitStack
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import unittest
import threading
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import smc_main
from scripts.smc.mt5_adapter import SMCExecutionAdapter
from scripts.smc.types import AccountState, Direction, SetupSignal


class TestLiveExecution(unittest.IsolatedAsyncioTestCase):
    async def run_order(self, accepted, worker_threads=None, expect_cancel=True):
        now = datetime(2026, 3, 2, 8, 35, tzinfo=timezone.utc)
        signal = SetupSignal(Direction.BUY, 2010.0, 2008.5, 2014.0,
                             2014.0, 2008.2, 2025.6, 5.8, 2.0,
                             2015.0, 2013.0, "Test setup", now)
        bars = pd.DataFrame([
            {"time": now - timedelta(minutes=5), "open": 2016.0,
             "high": 2018.0, "low": 2015.0, "close": 2017.5},
            {"time": now, "open": 2017.5, "high": 2018.0,
             "low": 2017.0, "close": 2017.5},
        ])
        broker = Mock(TRADE_RETCODE_DONE=10009)
        broker.order_send.return_value = SimpleNamespace(
            retcode=10009 if accepted else 10019, order=42, comment="test response")
        connector = Mock()
        connector.connect.return_value = True
        connector.get_spread.return_value = 0.15
        connector.get_candles.return_value = bars
        news = Mock()
        def fetch_news():
            if worker_threads is not None:
                worker_threads.append(threading.get_ident())
            return []

        def chart(*args):
            if worker_threads is not None:
                worker_threads.append(threading.get_ident())
            return None

        news.fetch_forexfactory_calendar.side_effect = fetch_news
        news.is_in_blackout.return_value = (False, "")
        notifier = Mock(send_alert=AsyncMock(), send_message=AsyncMock())
        account = AccountState(balance=10000.0, equity=10000.0)
        config = {"mt5": {"login": 1, "password": "test", "server": "test"}}
        with ExitStack() as stack:
            stack.enter_context(patch("scripts.smc.mt5_adapter.mt5", broker))
            adapter = SMCExecutionAdapter(dry_run=False, db_path=":memory:")
            stack.callback(adapter.conn.close)
            for name, value in {
                "load_config": Mock(return_value=config), "setup_logging": Mock(),
                "MT5Connector": Mock(return_value=connector),
                "SMCExecutionAdapter": Mock(return_value=adapter),
                "NewsManager": Mock(return_value=news),
                "SMCTelegramNotifier": Mock(return_value=notifier),
                "AccountState": Mock(return_value=account),
                "compute_liquidity_levels": Mock(return_value=None),
                "detect_smc_setup": Mock(return_value=signal),
                "generate_setup_chart": Mock(side_effect=chart),
                "datetime": Mock(now=Mock(return_value=now)),
            }.items():
                stack.enter_context(patch.object(smc_main, name, value))
            stack.enter_context(patch.object(smc_main.asyncio, "sleep",
                                             AsyncMock(side_effect=asyncio.CancelledError)))
            if expect_cancel:
                with self.assertRaises(asyncio.CancelledError):
                    await smc_main.run_smc_live_copilot()
            else:
                await smc_main.run_smc_live_copilot()
        broker.order_send.assert_called_once()
        connector.disconnect.assert_called_once()
        return account, notifier

    async def test_news_and_chart_do_not_block_event_loop_thread(self):
        worker_threads = []
        await self.run_order(accepted=True, worker_threads=worker_threads)
        self.assertEqual(len(worker_threads), 2)
        self.assertTrue(all(t != threading.get_ident() for t in worker_threads))

    async def test_cancellation_propagates_after_disconnect(self):
        await self.run_order(accepted=True, expect_cancel=True)

    async def test_rejected_order_has_no_alert_or_pending_state(self):
        account, notifier = await self.run_order(accepted=False)
        notifier.send_alert.assert_not_awaited()
        notifier.send_message.assert_not_awaited()
        self.assertIsNone(account.pending_order)
        self.assertEqual(account.pending_bars_held, 0)

    async def test_accepted_order_keeps_pending_state_and_alerts(self):
        account, notifier = await self.run_order(accepted=True)
        self.assertIsNotNone(account.pending_order)
        notifier.send_alert.assert_awaited_once()
        self.assertEqual(notifier.send_alert.await_args.kwargs["lot_size"],
                         account.pending_order.lot_size)


if __name__ == "__main__":
    unittest.main()
