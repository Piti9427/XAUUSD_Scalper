"""Broker bars, captured Bid ticks, and reference bars must expose mismatches."""

import unittest

import pandas as pd

from scripts.pure_b1.parity import (
    build_parity_ledger,
    compare_bars,
    compare_signals,
    prove_warmup,
    ticks_to_m15,
)


class PureB1ParityTests(unittest.TestCase):
    def test_tick_bid_ohlc_matches_reference_and_reports_one_changed_close(self):
        ticks = pd.DataFrame(
            {
                "time_msc": [
                    int(pd.Timestamp(f"2026-09-29 00:{minute:02d}:00Z").timestamp() * 1000)
                    for minute in (0, 2, 4, 14)
                ],
                "bid": [3000.0, 3001.0, 2999.0, 3000.5],
                "ask": [3000.2, 3001.2, 2999.2, 3000.7],
            }
        )
        tick_bars = ticks_to_m15(ticks)
        same_millisecond = pd.concat([ticks.iloc[:1], ticks.iloc[:1], ticks.iloc[1:]])
        self.assertEqual(ticks_to_m15(same_millisecond).iloc[0]["close"], 3000.5)
        reference = tick_bars.copy()
        result = compare_bars(tick_bars, reference, tolerance=0.001)
        self.assertEqual(result["overlap_bars"], 1)
        self.assertEqual(result["mismatch_bars"], 0)
        reference.iloc[0, reference.columns.get_loc("close")] += 0.02
        mismatch = compare_bars(tick_bars, reference, tolerance=0.001)
        self.assertEqual(mismatch["mismatch_bars"], 1)
        self.assertEqual(mismatch["mismatches"][0]["field"], "close")
        outer_reference = pd.concat(
            [
                tick_bars,
                tick_bars.set_axis(tick_bars.index + pd.Timedelta(minutes=30)),
            ]
        )
        missing = compare_bars(
            pd.concat(
                [
                    outer_reference.iloc[:1],
                    tick_bars.set_axis(tick_bars.index + pd.Timedelta(minutes=15)),
                    outer_reference.iloc[1:],
                ]
            ),
            outer_reference,
            tolerance=0.001,
        )
        self.assertEqual(missing["status"], "FAIL")
        self.assertEqual(missing["broker_only_bars"], 1)

    def test_signal_parity_fails_when_broker_has_one_extra_closed_bar(self):
        opens = pd.date_range("2026-01-01", periods=600, freq="15min", tz="UTC")
        close = [100.0 + i % 2 for i in range(len(opens))]
        broker = pd.DataFrame(
            {
                "open": close,
                "high": [price + 1 for price in close],
                "low": [price - 1 for price in close],
                "close": close,
            },
            index=opens,
        )
        reference = broker.drop(opens[300])
        result = compare_signals(broker, reference)
        self.assertEqual(result["status"], "FAIL")

    def test_warmup_comparison_failure_cannot_pass(self):
        opens = pd.date_range("2026-01-01", periods=40, freq="15min", tz="UTC")
        close = [100.0 + (0 if i == 0 else i % 2) for i in range(len(opens))]
        close[0] = 180.0
        bars = pd.DataFrame(
            {
                "open": close,
                "high": [price + 1 for price in close],
                "low": [price - 1 for price in close],
                "close": close,
            },
            index=opens,
        )
        warmup = prove_warmup(bars)
        self.assertFalse(warmup["proven"])
        self.assertIn(warmup["cause"], {"warmup_comparison_absent", "warmup_comparison_failed"})
        result = compare_signals(bars, bars.copy())
        self.assertEqual(result["status"], "FAIL")
        self.assertNotEqual(result["status"], "PASS")
        self.assertNotIn("warmup_excluded_broker_bars", result)

    def test_long_identical_history_passes_only_with_warmup_proof(self):
        opens = pd.date_range("2026-01-01", periods=800, freq="15min", tz="UTC")
        close = [100.0 + i % 2 for i in range(len(opens))]
        bars = pd.DataFrame(
            {
                "open": close,
                "high": [price + 1 for price in close],
                "low": [price - 1 for price in close],
                "close": close,
            },
            index=opens,
        )
        result = compare_signals(bars, bars.copy())
        self.assertTrue(result["warmup"]["broker"]["proven"])
        self.assertEqual(result["status"], "PASS")

    def test_ledger_blocks_missing_equity_and_records_price_mismatch(self):
        opens = pd.date_range("2026-01-01", periods=80, freq="15min", tz="UTC")
        close = [100.0 + i % 2 for i in range(len(opens))]
        bars = pd.DataFrame(
            {
                "open": close,
                "high": [price + 1 for price in close],
                "low": [price - 1 for price in close],
                "close": close,
            },
            index=opens,
        )
        blocked = build_parity_ledger(bars, bars.copy(), cost_policy_verified=False)
        self.assertFalse(blocked["shadow_passed"])
        self.assertEqual(blocked["gate"], "BLOCKED")
        self.assertGreater(blocked["counts"]["blocked"], 0)
        self.assertIn("cost_snapshot_unverified", blocked["blocked_causes"])
        changed = bars.copy()
        changed.iloc[10, changed.columns.get_loc("close")] += 0.05
        changed.iloc[10, changed.columns.get_loc("high")] += 0.05
        mismatch = build_parity_ledger(changed, bars, cost_policy_verified=False)
        price_rows = [
            row["fields"]["close"]
            for row in mismatch["rows"]
            if row["fields"].get("close", {}).get("status") == "mismatch"
        ]
        self.assertTrue(price_rows)
        self.assertEqual(price_rows[0]["cause"], "price_delta")
        self.assertAlmostEqual(price_rows[0]["abs_diff"], 0.05)
        self.assertFalse(mismatch["shadow_passed"])
        self.assertEqual(mismatch["order_api_called"], False)


if __name__ == "__main__":
    unittest.main()
