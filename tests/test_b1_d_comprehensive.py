"""Selection leakage, signal-clock and cached tick-replay regression checks."""

import unittest
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from scripts.research.b1_d_comprehensive import rank_development, filtered_signal, COST
from scripts.research.b1_d_ticks import replay
from scripts.research.strategies import Spec


class ComprehensiveTests(unittest.TestCase):
    def row(self, policy, cost, net=20, stage="development"):
        return {
            "policy_id": policy,
            "stage": stage,
            "cost_r": cost,
            "trades": 40,
            "net": net,
            "pf": 1.3,
            "max_tick_equity_dd_pct": 2.0,
            "risk_pct": 0.01,
        }

    def test_validation_results_cannot_change_development_ranking(self):
        rows = [self.row("A", c, 20) for c in COST] + [self.row("B", c, 10) for c in COST]
        before = rank_development(rows)
        rows += [self.row("B", c, 10000, "validation") for c in COST]
        self.assertEqual(rank_development(rows), before)
        self.assertEqual(before[0]["policy_id"], "A")

    def test_missing_cost_scenario_cannot_pass_selection(self):
        self.assertEqual(rank_development([self.row("A", 0), self.row("A", 0.1)]), [])

    def test_drawdown_failure_cannot_outrank_passing_policy(self):
        rows = [self.row("A", c, 20) for c in COST]
        for cost in COST:
            r = self.row("B", cost, 1000)
            r["max_tick_equity_dd_pct"] = 6
            rows.append(r)
        ranked = rank_development(rows)
        self.assertEqual(ranked[0]["policy_id"], "A")
        self.assertFalse(ranked[1]["research_screen_pass"])

    def test_session_filter_uses_signal_close_and_excludes_cutoff(self):
        idx = pd.DatetimeIndex(
            ["2026-06-01T06:45Z", "2026-06-01T10:15Z", "2026-06-01T12:15Z", "2026-06-01T16:15Z"]
        )
        f = pd.DataFrame(index=idx)
        raw = pd.DataFrame({"direction": [1, 1, 1, 1]}, index=idx)
        sig = filtered_signal(
            f,
            raw,
            pd.Timestamp("2026-06-01T00:00Z"),
            pd.Timestamp("2026-06-02T00:00Z"),
            "london_ny",
        )
        self.assertEqual(sig.direction.tolist(), [1, 0, 1, 0])

    def test_cache_preserves_account_and_tick_outcomes_across_costs(self):
        times = (
            np.arange(4, dtype=np.int64) * 1000 + pd.Timestamp("2026-06-01T00:15Z").value // 1000000
        )
        bid = np.array([100.0, 102.0, 99.0, 97.0])
        ask = bid + 0.2
        f = pd.DataFrame({"atr": [1.0]}, index=pd.DatetimeIndex(["2026-06-01T00:00Z"]))
        sig = pd.DataFrame({"direction": [1]}, index=f.index)
        broker = {
            "trade_contract_size": 100.0,
            "volume_step": 0.01,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "trade_tick_size": 0.001,
            "point": 0.001,
            "swap_long": 0.0,
            "swap_short": 0.0,
            "swap_mode": 1,
            "swap_rollover3days": 3,
        }
        cache = {}
        for cost in COST:
            original, stats = replay(
                times, bid, ask, f, sig, Spec("x", "donchian"), broker, 1000, cost
            )
            cached, cstats = replay(
                times,
                bid,
                ask,
                f,
                sig,
                Spec("x", "donchian"),
                broker,
                1000,
                cost,
                _exit_cache=cache,
            )
            assert_frame_equal(original, cached)
            self.assertEqual(stats, cstats)
            # Peak 1003.60 followed by final stop-gap loss to 993.60, sized 0.02.
            if cost == 0:
                self.assertAlmostEqual(stats["max_tick_equity_dd_pct"], 10 / 1003.6 * 100)
        self.assertEqual(len(cache), 1)

    def test_latency_and_slippage_change_executable_entry(self):
        times = (
            np.arange(4, dtype=np.int64) * 1000 + pd.Timestamp("2026-06-01T00:15Z").value // 1000000
        )
        bid = np.array([100.0, 101.0, 102.0, 110.0])
        ask = bid + 0.2
        f = pd.DataFrame({"atr": [1.0]}, index=pd.DatetimeIndex(["2026-06-01T00:00Z"]))
        sig = pd.DataFrame({"direction": [1]}, index=f.index)
        broker = {
            "trade_contract_size": 100.0,
            "volume_step": 0.01,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "trade_tick_size": 0.001,
            "point": 0.001,
            "swap_long": 0.0,
            "swap_short": 0.0,
            "swap_mode": 1,
            "swap_rollover3days": 3,
        }
        log, _ = replay(
            times,
            bid,
            ask,
            f,
            sig,
            Spec("x", "donchian"),
            broker,
            1000,
            delay_ms=2000,
            slippage=0.1,
        )
        self.assertAlmostEqual(log.iloc[0].entry, 102.3)
        self.assertEqual(log.iloc[0].entry_time.value // 1000000, times[2])

    def test_robustness_accepts_mixed_timestamp_precision_and_repeats_seed(self):
        from scripts.research.b1_d_robustness import robustness

        log = pd.DataFrame(
            {
                "entry_time": ["2026-05-14 10:00:00.123000+00:00", "2026-06-01 10:00:00+00:00"],
                "exit_time": ["2026-05-14 10:10:00.123000+00:00", "2026-06-01 10:10:00+00:00"],
                "reason": ["SL", "TP"],
                "r": [-1.0, 2.0],
                "net": [-10.0, 20.0],
                "balance": [990.0, 1010.0],
            }
        )
        first = robustness(log, seed=17, draws=100)
        second = robustness(log, seed=17, draws=100)
        self.assertEqual(first, second)
        self.assertEqual(first["closed_trades"], 2)
        self.assertTrue(np.isfinite(first["bonferroni_320_policy_lower_r"]))


if __name__ == "__main__":
    unittest.main()
