"""Accounting/event regressions for reconstructed Dobby, not economic rankings."""

from dataclasses import replace
import unittest

import numpy as np
import pandas as pd

from scripts.research.breakout_models import Costs
from scripts.research.dobby_replay import DobbyRules, replay, wilder_rsi
from scripts.research.rollover import SwapPolicy


START = pd.Timestamp("2026-01-06T00:15:00Z")
BROKER = dict(
    point=0.001,
    trade_contract_size=100.0,
    volume_min=0.01,
    volume_max=200.0,
    volume_step=0.01,
    leverage=1000,
)
SWAP = SwapPolicy(-567.4, -10, 0.001)


def bars(start=START):
    return pd.DataFrame(
        dict(close=np.arange(100.0, 116.0)),
        index=pd.date_range(end=start - pd.Timedelta(minutes=15), periods=16, freq="15min"),
    )


def tape(prices, offsets=None, start=START, spreads=None):
    b = np.asarray(prices, dtype=float)
    offsets = np.arange(len(b)) * 1000 if offsets is None else np.asarray(offsets)
    spreads = np.full(len(b), 0.2) if spreads is None else np.asarray(spreads)
    return np.asarray(start.value // 10**6 + offsets, dtype=np.int64), b, b + spreads


class DobbyReplayTests(unittest.TestCase):
    def run_case(self, ticks, rules=None, costs=None, source=None, scalar=False):
        end = pd.Timestamp(int(ticks[0][-1]) + 1, unit="ms", tz="UTC")
        return replay(
            bars() if source is None else source,
            ticks,
            BROKER,
            rules or DobbyRules(),
            costs or Costs(),
            start=START,
            end=end,
            swap_policy=SWAP,
            scalar=scalar,
        )

    def test_rsi_seed_extremes_flat_and_prefix_causality(self):
        self.assertEqual(wilder_rsi(np.arange(100, 116))[-1], 100)
        self.assertEqual(wilder_rsi(np.arange(116, 100, -1))[-1], 0)
        self.assertEqual(wilder_rsi(np.full(16, 100))[-1], 50)
        prices = np.r_[np.arange(100, 116), [90, 120, 95]]
        np.testing.assert_equal(wilder_rsi(prices)[:16], wilder_rsi(prices[:16]))

    def test_grid_four_legs_and_tick_exit_reconcile_cash(self):
        result = self.run_case(tape([100, 103, 106, 109, 106]))
        self.assertEqual(result["trades"], 1)
        self.assertEqual([x["volume"] for x in result["leg_events"]], [0.01, 0.02, 0.04, 0.08])
        self.assertEqual(result["ledger"][0]["reason"], "BASKET_TP")
        self.assertAlmostEqual(result["net_usd"], 9)
        self.assertAlmostEqual(result["final_balance"], 209)
        self.assertAlmostEqual(sum(t["net"] for t in result["ledger"]), result["net_usd"])

    def test_gap_adds_only_one_leg_per_tick(self):
        result = self.run_case(tape([100, 110, 110, 110]))
        self.assertEqual(len(result["leg_events"]), 2)
        self.assertEqual(
            result["leg_events"][1]["entry_ms"] - result["leg_events"][0]["entry_ms"], 1000
        )

    def test_daily_sl_blocks_later_entry_and_restart_not_simulated(self):
        source = bars()
        source.loc[START] = 116
        result = self.run_case(
            tape([100, 156, 100], offsets=[0, 1000, 900000]),
            rules=replace(DobbyRules(), max_legs=1),
            source=source,
        )
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["ledger"][0]["reason"], "BASKET_SL")
        self.assertEqual(result["rejected"]["daily_sl"], 1)

    def test_management_continues_monday_before_new_entry_filter(self):
        start = pd.Timestamp("2026-01-04T23:45:00Z")  # Sunday
        ticks = tape([100, 103, 100], [0, 15 * 60000, 15 * 60000 + 1000], start=start)
        result = replay(
            bars(start),
            ticks,
            BROKER,
            DobbyRules(),
            Costs(),
            start=start,
            end=pd.Timestamp(int(ticks[0][-1]) + 1, unit="ms", tz="UTC"),
            swap_policy=SWAP,
        )
        self.assertEqual(len(result["leg_events"]), 2)
        self.assertTrue(result["leg_events"][1]["entry_time_utc"].startswith("2026-01-05"))

    def test_swap_and_commission_applied_once_per_leg(self):
        ticks = tape([100, 100], offsets=[0, 86400000])
        result = self.run_case(
            ticks, rules=replace(DobbyRules(), max_legs=1), costs=Costs(commission_per_lot=7)
        )
        self.assertAlmostEqual(result["commission_usd"], 0.07)
        self.assertAlmostEqual(result["swap_usd"], -0.01)
        self.assertAlmostEqual(result["net_usd"], -0.28)
        self.assertEqual(result["ledger"][0]["reason"], "END_OF_SAMPLE")

    def test_spread_retry_waits_for_acceptable_quote(self):
        result = self.run_case(tape([100, 100], spreads=[0.7, 0.2]))
        self.assertEqual(result["leg_events"][0]["entry_ms"], int(START.value // 10**6) + 1000)

    def test_missing_closed_bar_prevents_stale_rsi_entry(self):
        source = bars()
        ticks = tape([100, 100], offsets=[900000, 901000])
        result = self.run_case(ticks, source=source)
        self.assertEqual(result["trades"], 0)

    def test_margin_rejection_never_increases_initial_lot(self):
        result = self.run_case(tape([1_000_000, 1_000_001]))
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["rejected"]["margin"], 1)

    def test_price_gap_can_exceed_basket_stop_and_ruin(self):
        result = self.run_case(tape([100, 400]))
        self.assertTrue(result["bankrupt"])
        self.assertEqual(result["ledger"][0]["reason"], "BANKRUPT")
        self.assertLess(result["net_usd"], -55)

    def test_vectorized_events_match_scalar_oracle(self):
        prices = [100, 103, 106, 109, 106, 100, 104, 108, 112, 100]
        ticks = tape(prices, offsets=np.arange(10) * 200000)
        source = bars()
        source.loc[START] = 116
        source.loc[START + pd.Timedelta(minutes=15)] = 117
        for costs in (
            Costs(commission_per_lot=7),
            Costs(extra_spread=0.2, slippage=0.1, commission_per_lot=7),
        ):
            vector = self.run_case(ticks, source=source, costs=costs)
            scalar = self.run_case(ticks, source=source, costs=costs, scalar=True)
            for key in vector:
                if key != "equity":
                    self.assertEqual(vector[key], scalar[key], key)

    def test_missing_swap_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "swap required"):
            replay(
                bars(),
                tape([100]),
                BROKER,
                DobbyRules(),
                Costs(),
                start=START,
                end=START + pd.Timedelta(minutes=1),
                swap_policy=None,
            )


if __name__ == "__main__":
    unittest.main()
