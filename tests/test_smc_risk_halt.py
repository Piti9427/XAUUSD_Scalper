import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.smc.risk_halt import (
    load_risk_halt_state,
    new_risk_halt_state,
    observe_equity,
    record_net_losing_trade,
    save_risk_halt_state,
)


class RiskHaltPersistenceTests(unittest.TestCase):
    def test_drawdown_halt_persists_across_reload_and_day_rollover(self):
        state = new_risk_halt_state(500.0, now=datetime(2026, 3, 2, 8, tzinfo=timezone.utc))
        observe_equity(state, 470.0, now=datetime(2026, 3, 2, 9, tzinfo=timezone.utc))
        self.assertTrue(state.drawdown_halt)
        self.assertTrue(state.halted)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "risk_halt.json"
            save_risk_halt_state(path, state)
            restored = load_risk_halt_state(path)
            self.assertIsNotNone(restored)
            self.assertTrue(restored.drawdown_halt)

            observe_equity(
                restored, 480.0, now=datetime(2026, 3, 3, 1, tzinfo=timezone.utc),
            )
            self.assertTrue(
                restored.drawdown_halt,
                "5% drawdown halt must survive UTC day rollover and restart",
            )
            self.assertEqual(restored.net_losing_trades_today, 0)

    def test_two_net_losses_or_one_percent_daily_decline_halt(self):
        state = new_risk_halt_state(500.0, now=datetime(2026, 3, 2, 8, tzinfo=timezone.utc))
        record_net_losing_trade(state)
        self.assertFalse(state.halted)
        record_net_losing_trade(state)
        self.assertTrue(state.halted)

        state2 = new_risk_halt_state(500.0, now=datetime(2026, 3, 2, 8, tzinfo=timezone.utc))
        observe_equity(state2, 494.0, now=datetime(2026, 3, 2, 10, tzinfo=timezone.utc))
        self.assertTrue(state2.daily_equity_halt)
        self.assertTrue(state2.halted)


if __name__ == "__main__":
    unittest.main()
