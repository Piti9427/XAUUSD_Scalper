import unittest
from datetime import datetime, timezone

from scripts.smc.setup_identity import SetupRegistry, make_setup_id
from scripts.smc.types import (
    AccountState,
    Direction,
    OrderIntentType,
    SetupSignal,
)
from scripts.smc.orchestrator import StrategyOrchestrator


class SetupIdentityTests(unittest.TestCase):
    def test_make_setup_id_is_stable(self):
        a = make_setup_id(
            direction="BUY",
            entry_price=2014.0,
            sl_price=2008.2,
            tp_price=2025.6,
            sweep_wick=2008.5,
            available_at="2026-03-02T08:05:00+00:00",
        )
        b = make_setup_id(
            direction="BUY",
            entry_price=2014.0,
            sl_price=2008.2,
            tp_price=2025.6,
            sweep_wick=2008.5,
            available_at="2026-03-02T08:05:00+00:00",
        )
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("SMC_"))

    def test_registry_blocks_revive_after_expiry(self):
        registry = SetupRegistry()
        orch = StrategyOrchestrator(setup_registry=registry)
        setup_id = make_setup_id(
            direction="BUY",
            entry_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            sweep_wick=2005.0,
            available_at="2026-03-02T08:00:00+00:00",
        )
        signal = SetupSignal(
            direction=Direction.BUY,
            sweep_price=2010.0,
            sweep_wick=2005.0,
            mss_price=2012.0,
            entry_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            sl_distance=5.0,
            risk_r=2.0,
            fvg_high=2011.0,
            fvg_low=2009.0,
            reason="test",
            timestamp=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            setup_id=setup_id,
        )
        account = AccountState(balance=10000.0, equity=10000.0)

        # Place pending
        bar0 = {
            "time": datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            "open": 2015,
            "high": 2016,
            "low": 2014,
            "close": 2015,
        }
        intents = orch.on_bar(bar0, account, signal)
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].intent_type, OrderIntentType.PLACE_LIMIT)
        self.assertEqual(intents[0].order_id, setup_id)

        # TTL expire over 4 bars without fill (foundation pending TTL)
        for i, minute in enumerate((5, 10, 15, 20), start=1):
            bar = {
                "time": datetime(2026, 3, 2, 8, minute, tzinfo=timezone.utc),
                "open": 2015,
                "high": 2016,
                "low": 2014,
                "close": 2015,
            }
            intents = orch.on_bar(bar, account, None)
            if i < 4:
                self.assertEqual(intents, [])
            else:
                self.assertEqual(intents[0].intent_type, OrderIntentType.CANCEL_LIMIT)
                self.assertIn("TTL", intents[0].reason)

        self.assertTrue(registry.is_blocked(setup_id))

        # Same SETUP_ID must not revive after expiry / restart of pending state
        revive = orch.on_bar(bar0, account, signal)
        self.assertEqual(revive, [])
        self.assertIsNone(account.pending_order)

    def test_h1_bias_flip_cancels_pending_and_blocks_revive(self):
        registry = SetupRegistry()
        orch = StrategyOrchestrator(setup_registry=registry)
        setup_id = make_setup_id(
            direction="BUY",
            entry_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            sweep_wick=2005.0,
            available_at="2026-03-02T08:00:00+00:00",
        )
        signal = SetupSignal(
            direction=Direction.BUY,
            sweep_price=2010.0,
            sweep_wick=2005.0,
            mss_price=2012.0,
            entry_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            sl_distance=5.0,
            risk_r=2.0,
            fvg_high=2011.0,
            fvg_low=2009.0,
            reason="test",
            timestamp=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            setup_id=setup_id,
        )
        account = AccountState(balance=10000.0, equity=10000.0)
        bar0 = {
            "time": datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            "open": 2015,
            "high": 2016,
            "low": 2014,
            "close": 2015,
        }
        place = orch.on_bar(
            bar0, account, signal, h1_bias=Direction.BUY, h1_bias_known=True
        )
        self.assertEqual(place[0].intent_type, OrderIntentType.PLACE_LIMIT)

        bar1 = {
            "time": datetime(2026, 3, 2, 8, 5, tzinfo=timezone.utc),
            "open": 2015,
            "high": 2016,
            "low": 2014,
            "close": 2015,
        }
        cancel = orch.on_bar(
            bar1, account, None, h1_bias=Direction.SELL, h1_bias_known=True
        )
        self.assertEqual(len(cancel), 1)
        self.assertEqual(cancel[0].intent_type, OrderIntentType.CANCEL_LIMIT)
        self.assertIn("h1_bias_invalidated", cancel[0].reason)
        self.assertTrue(registry.is_blocked(setup_id))
        self.assertEqual(registry.terminal_reason(setup_id), "h1_bias_invalidated")
        revive = orch.on_bar(
            bar0, account, signal, h1_bias=Direction.BUY, h1_bias_known=True
        )
        self.assertEqual(revive, [])

    def test_unknown_h1_bias_does_not_invent_cancel(self):
        from scripts.smc.setup_identity import pending_h1_bias_allows

        ok, reason = pending_h1_bias_allows(
            pending_direction=Direction.BUY,
            h1_bias=None,
            bias_known=False,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok_bias_unknown")
        ok_flat, reason_flat = pending_h1_bias_allows(
            pending_direction=Direction.BUY,
            h1_bias=None,
            bias_known=True,
        )
        self.assertFalse(ok_flat)
        self.assertEqual(reason_flat, "h1_bias_flat")

    def test_fill_marks_setup_terminal_blocks_revive(self):
        registry = SetupRegistry()
        orch = StrategyOrchestrator(setup_registry=registry)
        setup_id = make_setup_id(
            direction="BUY",
            entry_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            sweep_wick=2005.0,
            available_at="2026-03-02T08:00:00+00:00",
        )
        signal = SetupSignal(
            direction=Direction.BUY,
            sweep_price=2010.0,
            sweep_wick=2005.0,
            mss_price=2012.0,
            entry_price=2010.0,
            sl_price=2005.0,
            tp_price=2020.0,
            sl_distance=5.0,
            risk_r=2.0,
            fvg_high=2011.0,
            fvg_low=2009.0,
            reason="test",
            timestamp=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            setup_id=setup_id,
        )
        account = AccountState(balance=10000.0, equity=10000.0)
        bar0 = {
            "time": datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
            "open": 2015,
            "high": 2016,
            "low": 2014,
            "close": 2015,
        }
        orch.on_bar(bar0, account, signal)
        self.assertIsNotNone(account.pending_order)

        fill_bar = {
            "time": datetime(2026, 3, 2, 8, 5, tzinfo=timezone.utc),
            "open": 2011,
            "high": 2012,
            "low": 2009.5,  # touches limit 2010
            "close": 2010.5,
        }
        orch.on_bar(fill_bar, account, None)
        self.assertTrue(registry.is_blocked(setup_id))
        self.assertEqual(registry.terminal_reason(setup_id), "filled")

        # Clear local position (as if closed) — same SETUP_ID must not revive.
        account.open_position = None
        revive = orch.on_bar(bar0, account, signal)
        self.assertEqual(revive, [])
        self.assertIsNone(account.pending_order)

    def test_registry_survives_restart_after_ttl(self):
        import tempfile
        from pathlib import Path
        from scripts.smc.setup_identity import load_setup_registry, save_setup_registry

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "setup_registry.json"
            registry = load_setup_registry(path)
            orch = StrategyOrchestrator(setup_registry=registry)
            setup_id = make_setup_id(
                direction="BUY",
                entry_price=2010.0,
                sl_price=2005.0,
                tp_price=2020.0,
                sweep_wick=2005.0,
                available_at="2026-03-02T08:00:00+00:00",
            )
            signal = SetupSignal(
                direction=Direction.BUY,
                sweep_price=2010.0,
                sweep_wick=2005.0,
                mss_price=2012.0,
                entry_price=2010.0,
                sl_price=2005.0,
                tp_price=2020.0,
                sl_distance=5.0,
                risk_r=2.0,
                fvg_high=2011.0,
                fvg_low=2009.0,
                reason="test",
                timestamp=datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
                setup_id=setup_id,
            )
            account = AccountState(balance=10000.0, equity=10000.0)
            bar0 = {
                "time": datetime(2026, 3, 2, 8, 0, tzinfo=timezone.utc),
                "open": 2015,
                "high": 2016,
                "low": 2014,
                "close": 2015,
            }
            orch.on_bar(bar0, account, signal)
            for minute in (5, 10, 15, 20):
                bar = {
                    "time": datetime(2026, 3, 2, 8, minute, tzinfo=timezone.utc),
                    "open": 2015,
                    "high": 2016,
                    "low": 2014,
                    "close": 2015,
                }
                orch.on_bar(bar, account, None)
            self.assertTrue(path.is_file())
            self.assertEqual(registry.terminal_reason(setup_id), "ttl_expired")

            # Simulate process restart: new registry + orchestrator from disk.
            restarted = load_setup_registry(path)
            orch2 = StrategyOrchestrator(setup_registry=restarted)
            account2 = AccountState(balance=10000.0, equity=10000.0)
            revive = orch2.on_bar(bar0, account2, signal)
            self.assertEqual(revive, [])
            self.assertTrue(restarted.is_blocked(setup_id))


if __name__ == "__main__":
    unittest.main()
