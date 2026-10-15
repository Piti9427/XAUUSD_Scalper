"""Frozen B1-FINAL-v1 oracle and equity-risk regression cases."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.b1_final import (
    RiskState,
    reference_bars,
    signal_direction,
    normalize_price,
    load_contract,
    compare_mql,
    resolve_initial_equity,
)
from scripts.research.b1_d_ticks import replay
from scripts.research.strategies import Spec


class B1FinalTests(unittest.TestCase):
    def test_explicit_simulated_deposit_preserves_broker_snapshot(self):
        account = {"equity": 1173.46, "balance": 1173.46}
        self.assertEqual(resolve_initial_equity(account, None), 1173.46)
        self.assertEqual(resolve_initial_equity(account, 100.0), 100.0)
        self.assertEqual(account, {"equity": 1173.46, "balance": 1173.46})
        for invalid in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                resolve_initial_equity(account, invalid)

    def test_parity_gate_detects_indicator_signal_and_timestamp_drift(self):
        reference = reference_bars(self.bars())
        observed = reference[["atr", "rsi", "hh30", "ll30", "direction"]].reset_index(drop=True)
        observed.insert(0, "bar_open_epoch", reference.index.as_unit("ns").asi8 // 10**9)
        self.assertTrue(compare_mql(reference, observed)["passed"])
        changed = observed.copy()
        changed.loc[99, "rsi"] += 1e-6
        self.assertFalse(compare_mql(reference, changed)["passed"])
        changed = observed.copy()
        changed.loc[99, "direction"] = 1
        self.assertEqual(compare_mql(reference, changed)["mismatches"]["direction"], 1)
        changed = observed.copy()
        changed.loc[99, "bar_open_epoch"] += 900
        self.assertEqual(compare_mql(reference, changed)["reason"], "BAR_ALIGNMENT")

    def test_manifest_drift_refuses_modified_alpha_or_risk(self):
        approved = Path("config/B1-FINAL-v1.yaml")
        self.assertEqual(load_contract(approved)["strategy"]["target_rr"], 3.5)
        with tempfile.TemporaryDirectory() as folder:
            changed = Path(folder) / "contract.yaml"
            changed.write_text(
                approved.read_text().replace("donchian_period: 30", "donchian_period: 31")
            )
            with self.assertRaises(ValueError):
                load_contract(changed)

    def bars(self, count=110):
        close = np.full(count, 100.0)
        return pd.DataFrame(
            {"open": close, "high": close + 1, "low": close - 1, "close": close},
            index=pd.date_range("2026-01-01", periods=count, freq="15min", tz="UTC"),
        )

    def test_known_flat_rsi_and_atr_vector(self):
        f = reference_bars(self.bars())
        self.assertTrue(f.atr.iloc[:13].isna().all())
        np.testing.assert_allclose(f.atr.iloc[13:], 2.0, atol=1e-12)
        np.testing.assert_allclose(f.rsi.iloc[13:], 50.0, atol=1e-12)

    def test_wilder_seed_and_recursive_known_vector(self):
        b = self.bars(110)
        b.loc[b.index[14], ["high", "close"]] = [103.0, 102.0]
        f = reference_bars(b)
        self.assertAlmostEqual(f.atr.iloc[14], 30 / 14)
        self.assertEqual(f.rsi.iloc[14], 100.0)
        self.assertAlmostEqual(f.rsi.iloc[15], 100 * (13 / 14) / (1 + 13 / 14))

    def test_previous_30_excludes_signal_bar_and_requires_100_bar_warmup(self):
        b = self.bars()
        b.loc[b.index[99], "high"] = 150.0
        f = reference_bars(b)
        self.assertEqual(f.hh30.iloc[99], 101.0)
        self.assertEqual(f.hh30.iloc[100], 150.0)
        self.assertFalse(f.ready.iloc[98])
        self.assertTrue(f.ready.iloc[99])

    def test_strict_breakout_and_rsi_boundaries(self):
        for close, rsi, expected in [
            (102, 75, 1),
            (102, 75.0001, 0),
            (101, 50, 0),
            (98, 25, -1),
            (98, 24.9999, 0),
            (99, 50, 0),
        ]:
            with self.subTest(close=close, rsi=rsi):
                self.assertEqual(signal_direction(close, 101, 99, rsi, True), expected)
        self.assertEqual(signal_direction(102, 101, 99, 50, False), 0)

    def test_missing_invalid_or_non_utc_data_fails_closed(self):
        for kind in ("naive", "nan", "geometry", "duplicate", "alignment"):
            b = self.bars()
            if kind == "naive":
                b.index = b.index.tz_localize(None)
            elif kind == "nan":
                b.iloc[5, 0] = np.nan
            elif kind == "geometry":
                b.iloc[5, 1] = 50.0
            elif kind == "duplicate":
                b.index = pd.DatetimeIndex([b.index[0]] + list(b.index[:-1]))
            else:
                b.index += pd.Timedelta(minutes=1)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                reference_bars(b)

    def test_completed_gap_bars_preserve_prior_completed_bar_indexing(self):
        b = self.bars().drop(self.bars().index[40])
        f = reference_bars(b)
        self.assertEqual(len(f), 109)
        self.assertEqual(f.hh30.iloc[99], 101.0)

    def test_causal_prefix_does_not_change_with_future_bars(self):
        b = self.bars()
        a = reference_bars(b.iloc[:100])
        b.loc[b.index[100] :, "close"] = 200.0
        b.loc[b.index[100] :, "high"] = 201.0
        b.loc[b.index[100] :, "open"] = 200.0
        pd.testing.assert_frame_equal(a, reference_bars(b).iloc[:100])

    def test_all_risk_tier_boundaries(self):
        for dd, risk in [
            (2.9999, 0.01),
            (3.0, 0.0075),
            (5.9999, 0.0075),
            (6.0, 0.005),
            (8.9999, 0.005),
            (9.0, 0.0025),
            (11.9999, 0.0025),
            (12.0, 0.0),
        ]:
            s = RiskState(10000.0)
            s.observe(np.array([10000 * (1 - dd / 100)]))
            with self.subTest(dd=dd):
                self.assertEqual(s.risk_pct, risk)

    def test_tick_equity_hwm_and_hard_stop_latch_survive_recovery(self):
        s = RiskState(100.0)
        s.observe(np.array([120.0, 105.0, 130.0]))
        self.assertEqual(s.hwm, 130.0)
        self.assertTrue(s.hard_stop)
        self.assertEqual(s.risk_pct, 0.0)
        self.assertAlmostEqual(s.max_dd, 0.125)

    def test_restart_preserves_hwm_stop_and_detects_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "state.json"
            s = RiskState(100.0)
            s.observe(np.array([110.0, 95.0]))
            s.save(p, "test-hash")
            restored = RiskState.load(p, "test-hash")
            self.assertEqual(restored.hwm, 110.0)
            self.assertTrue(restored.hard_stop)
            with self.assertRaises(ValueError):
                RiskState.load(p, "other-hash")
            p.write_text("{}")
            with self.assertRaises(ValueError):
                RiskState.load(p, "test-hash")

    def test_half_tick_rounding_contract(self):
        self.assertEqual(normalize_price(100.125, 0.25), 100.25)
        self.assertEqual(normalize_price(100.375, 0.25), 100.5)

    def run_replay(self, balance=1000.0, quotes=None, state=None, decisions=None):
        index = pd.date_range("2026-01-01", periods=2, freq="15min", tz="UTC")
        frame = pd.DataFrame({"atr": [1.0, 1.0]}, index=index)
        sig = pd.DataFrame({"direction": [1, 1]}, index=index)
        times = np.array(
            [
                (index[0] + pd.Timedelta(minutes=15)).value // 10**6,
                (index[0] + pd.Timedelta(minutes=15, seconds=1)).value // 10**6,
                (index[1] + pd.Timedelta(minutes=15)).value // 10**6,
            ]
        )
        bid = np.array(quotes or [100.0, 109.0, 109.0])
        ask = bid + 0.2
        broker = {
            "trade_contract_size": 100.0,
            "volume_step": 0.01,
            "volume_min": 0.01,
            "volume_max": 200.0,
            "trade_tick_size": 0.001,
            "point": 0.001,
            "swap_long": 0.0,
            "swap_short": 0.0,
            "swap_mode": 1,
            "swap_rollover3days": 3,
        }
        state = state or RiskState(balance)
        log, stats = replay(
            times,
            bid,
            ask,
            frame,
            sig,
            Spec("B1-FINAL-v1", "donchian", sl=2.5, tp=3.5),
            broker,
            balance,
            risk_state=state,
            price_normalizer=normalize_price,
            entry_window_ms=900000,
            decision_log=decisions,
        )
        return log, stats, state

    def test_restored_hwm_controls_sizing_and_reported_drawdown(self):
        state = RiskState(1100.0, equity=1000.0, max_dd=100 / 1100)
        log, stats, state = self.run_replay(state=state)
        self.assertAlmostEqual(log.iloc[0].risk_pct, 0.0025)
        self.assertAlmostEqual(log.iloc[0].entry_dd_pct, 10000 / 1100)
        self.assertGreaterEqual(stats["max_tick_equity_dd_pct"], 10000 / 1100)

    def test_reference_ask_entry_stop_target_and_equity_budget(self):
        log, stats, state = self.run_replay()
        self.assertAlmostEqual(log.iloc[0].entry, 100.2)
        self.assertAlmostEqual(log.iloc[0].stop, 97.7)
        self.assertAlmostEqual(log.iloc[0].target, 108.95)
        self.assertAlmostEqual(log.iloc[0].risk_budget, 10.0)
        self.assertAlmostEqual(log.iloc[0].volume, 0.04)
        self.assertAlmostEqual(log.iloc[0].net, 35.0)
        self.assertAlmostEqual(log.iloc[1].risk_budget, 10.35)
        self.assertFalse(state.hard_stop)

    def test_minimum_lot_rejection_remains_risk_safe(self):
        log, stats, state = self.run_replay(balance=100.0)
        self.assertTrue(log.empty)
        self.assertEqual(stats["rejections"]["risk_below_min"], 2)

    def test_decision_ledger_explains_rejections_without_changing_trades(self):
        decisions = []
        log, stats, state = self.run_replay(balance=100.0, decisions=decisions)
        self.assertEqual(len(decisions), 2)
        self.assertEqual(decisions[0]["outcome"], "RISK_BELOW_MINIMUM_LOT")
        self.assertGreater(decisions[0]["minimum_lot_stop_risk"], decisions[0]["risk_budget"])
        self.assertEqual(decisions[0]["normalized_volume"], 0.0)
        accepted = []
        observed, _, _ = self.run_replay(decisions=accepted)
        expected, _, _ = self.run_replay()
        pd.testing.assert_frame_equal(observed, expected)
        self.assertEqual(sum(x["outcome"] == "REPLAY_EXECUTED" for x in accepted), len(observed))

    def test_intratrade_hard_dd_does_not_panic_close_but_blocks_next_entry(self):
        log, stats, state = self.run_replay(quotes=[100.0, 60.0, 100.0])
        self.assertEqual(len(log), 1)
        self.assertEqual(log.iloc[0].reason, "SL")
        self.assertTrue(state.hard_stop)
        self.assertEqual(stats["rejections"]["hard_dd_stop"], 1)


if __name__ == "__main__":
    unittest.main()
