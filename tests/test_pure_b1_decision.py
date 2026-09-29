"""Pure B1 admission on a completed bar, broker quote, and account state."""

from datetime import datetime, timezone
import unittest

import numpy as np
import pandas as pd

from scripts.pure_b1.decision import decide


class PureB1DecisionTests(unittest.TestCase):
    def setUp(self):
        close = np.array([100.0 + i % 2 for i in range(80)])
        close[-1] = 103.0
        self.bars = pd.DataFrame(
            {"open": close, "high": close + 1, "low": close - 1, "close": close},
            index=pd.date_range("2026-09-28 04:00", periods=80, freq="15min", tz="UTC"),
        )
        self.bars.iloc[-1, 1] = 103.0
        self.now = datetime(2026, 9, 29, 0, 1, tzinfo=timezone.utc)
        self.inputs = {
            "bars": self.bars,
            "bid": 103.0,
            "ask": 103.2,
            "quote_time": datetime(2026, 9, 29, 0, 0, 10, tzinfo=timezone.utc),
            "now": self.now,
            "equity": 200.0,
            "day_start_equity": 200.0,
            "contract_size": 100.0,
            "tick_size": 0.01,
            "min_lot": 0.01,
            "max_lot": 10.0,
            "lot_step": 0.01,
            "commission_per_lot": 0.0,
            "cost_policy_source": "Exness Standard tariff 2026-09-29",
            "slippage_allowance": 0.5,
            "margin_required": 5.0,
            "free_margin": 200.0,
            "open_positions": 0,
            "pending_orders": 0,
            "broker_trade_mode": 4,
            "broker_full_trade_mode": 4,
            "stops_level": 0,
            "freeze_level": 0,
            "point": 0.01,
        }

    def test_accepted_buy_uses_same_detector_and_broker_ask(self):
        result = decide(**self.inputs)
        self.assertEqual(result["direction"], 1)
        self.assertTrue(result["admit"], result)
        self.assertEqual(result["entry"], 103.2)
        self.assertLess(result["stop"], result["entry"])
        self.assertLessEqual(result["risk_amount"], 20)

    def test_missing_cost_or_day_start_fails_closed(self):
        for overrides, reason in (
            ({"cost_policy_source": ""}, "cost_model_missing"),
            ({"slippage_allowance": None}, "cost_model_missing"),
            ({"day_start_equity": None}, "day_start_unknown"),
        ):
            with self.subTest(reason=reason):
                result = decide(**(self.inputs | overrides))
                self.assertFalse(result["admit"])
                self.assertEqual(result["reason"], reason)

    def test_any_existing_exposure_or_daily_limit_blocks_signal(self):
        for overrides, reason in (
            ({"open_positions": 1}, "symbol_exposure"),
            ({"pending_orders": 1}, "symbol_exposure"),
            ({"equity": 120.0}, "daily_loss_limit"),
        ):
            with self.subTest(reason=reason):
                result = decide(**(self.inputs | overrides))
                self.assertFalse(result["admit"])
                self.assertEqual(result["reason"], reason)

    def test_stale_quote_and_ten_percent_risk_are_rejected(self):
        stale = decide(
            **(self.inputs | {"now": datetime(2026, 9, 29, 0, 2, 30, tzinfo=timezone.utc)})
        )
        self.assertEqual(stale["reason"], "stale_quote")
        over_risk = decide(**(self.inputs | {"equity": 40.0, "day_start_equity": 40.0}))
        self.assertEqual(over_risk["reason"], "risk_cap")

    def test_broker_mode_and_stop_distance_block_signal(self):
        for override, expected in (
            ({"broker_trade_mode": 0}, "market_unavailable"),
            ({"stops_level": 10000}, "broker_stops_invalid"),
            ({"freeze_level": float("nan")}, "broker_stops_unknown"),
        ):
            with self.subTest(override=override):
                result = decide(**(self.inputs | override))
                self.assertFalse(result["admit"])
                self.assertEqual(result["reason"], expected)


if __name__ == "__main__":
    unittest.main()
