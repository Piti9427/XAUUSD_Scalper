import unittest
import asyncio
from unittest.mock import AsyncMock, Mock, patch

import smc_main


class TestLiveExecution(unittest.IsolatedAsyncioTestCase):
    async def test_connected_legacy_loop_refuses_live_execution(self):
        connector = Mock()
        connector.connect.return_value = True
        config = {"mt5": {"login": 1, "password": "test", "server": "test"}}
        with patch.object(smc_main, "load_config", return_value=config), \
             patch.object(smc_main, "setup_logging"), \
             patch.object(smc_main, "MT5Connector", return_value=connector), \
             patch.object(smc_main, "SMCExecutionAdapter") as adapter, \
             patch.object(smc_main, "SMCTelegramNotifier") as notifier:
            with self.assertRaisesRegex(RuntimeError, "live execution is disabled"):
                await smc_main.run_smc_live_copilot()
        connector.disconnect.assert_called_once()
        adapter.assert_not_called()
        notifier.assert_not_called()

    async def test_disconnected_legacy_loop_disables_external_alerts(self):
        connector = Mock()
        connector.connect.return_value = False
        connector.get_spread.return_value = None
        connector.get_candles.return_value = None
        adapter = Mock()
        adapter.conn.close = Mock()
        config = {"mt5": {"login": 1, "password": "test", "server": "test"},
                  "telegram": {"enabled": True, "token": "test"}}
        with patch.object(smc_main, "load_config", return_value=config), \
             patch.object(smc_main, "setup_logging"), \
             patch.object(smc_main, "MT5Connector", return_value=connector), \
             patch.object(smc_main, "SMCExecutionAdapter", return_value=adapter), \
             patch.object(smc_main, "SMCTelegramNotifier") as notifier, \
             patch.object(smc_main.NewsManager, "fetch_forexfactory_calendar", return_value=[]), \
             patch.object(smc_main.asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):
                await smc_main.run_smc_live_copilot()
        self.assertFalse(notifier.call_args.args[0]["telegram"]["enabled"])
        adapter.execute_intent.assert_not_called()
        connector.disconnect.assert_called_once()


if __name__ == "__main__":
    unittest.main()
