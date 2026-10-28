"""Causal joint selector and daily MTM seams,not profitability claims."""

import unittest
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pandas as pd

from scripts.research.c22_daily_addon import joint_frame, daily_mtm, attribute_joint
from scripts.research.rollover import SwapPolicy
from scripts.research.c22_risk_replay import replay
from scripts.research.breakout_models import Costs
from tests.research.test_c22_risk_replay import BROKER, VALID_SWAP, native_rules, tape_at
from scripts.research.c22_daily_addon_verify import independent_selector, audit_daily


def bars_fixture():
    index = pd.date_range("2026-01-01", periods=3233, freq="15min", tz="UTC")
    close = 100 + np.arange(len(index)) * 0.01
    close[-1] += 2
    bars = pd.DataFrame(
        dict(open=close - 0.01, high=close + 0.1, low=close - 0.1, close=close), index=index
    )
    frame = bars.assign(
        atr=1.0,
        hh=bars.high.rolling(48).max().shift(1),
        ll=bars.low.rolling(48).min().shift(1),
        direction=0,
    )
    return bars, frame


class JointAddonTests(unittest.TestCase):
    def test_current_high_excluded_prefix_causal_and_disabled_control_exact(self):
        bars, core = bars_fixture()
        selected, witness = joint_frame(bars, core, enabled=True)
        self.assertEqual(selected.direction.iloc[-1], 1)
        self.assertEqual(witness.origin.iloc[-1], "addon")
        bars.loc[bars.index[-1], "high"] = 1e9
        core.loc[core.index[-1], "high"] = 1e9
        changed, _ = joint_frame(bars, core, enabled=True)
        self.assertEqual(changed.direction.iloc[-1], 1)
        future = bars.iloc[-16:].copy()
        future.index += pd.Timedelta(hours=4)
        future[["open", "high", "low", "close"]] += 10000
        extended = pd.concat([bars, future])
        extended_core = pd.concat([core, future.assign(atr=1, hh=1, ll=1, direction=0)])
        full, w = joint_frame(extended, extended_core, enabled=True)
        pd.testing.assert_frame_equal(full.loc[core.index], changed)
        disabled, _ = joint_frame(bars, core, enabled=False)
        pd.testing.assert_frame_equal(disabled, core)

    def test_native_priority_retains_anchors_and_no_second_admission_fallback(self):
        bars, core = bars_fixture()
        core.loc[core.index[-1], "direction"] = -1
        core.loc[core.index[-1], "atr"] = 1000.0
        selected, witness = joint_frame(bars, core, enabled=True)
        self.assertTrue(witness.addon_eligible.iloc[-1])
        self.assertEqual(witness.origin.iloc[-1], "native")
        pd.testing.assert_series_equal(selected.iloc[-1], core.iloc[-1])
        close = core.index[-1] + pd.Timedelta(minutes=15)
        ticks = tape_at([close, close + pd.Timedelta(seconds=1)], [134.0, 134.0])
        result = replay(
            selected,
            ticks,
            BROKER,
            native_rules(),
            Costs(),
            start=close.normalize(),
            end=close + pd.Timedelta(seconds=2),
            swap_policy=VALID_SWAP,
            capture_events=True,
            capture_context=True,
        )
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["signal_count"], 1)
        self.assertEqual(result["rejections"]["risk_cap"], 1)

    def test_incomplete_latest_h4_and_warmup_are_not_carried(self):
        bars, core = bars_fixture()
        short, _ = joint_frame(bars.iloc[:100], core.iloc[:100], enabled=True)
        self.assertFalse(short.direction.any())
        missing = bars.index[-3]
        selected, w = joint_frame(bars.drop(missing), core.drop(missing), enabled=True)
        self.assertFalse(w.addon_eligible.iloc[-1])
        self.assertTrue(pd.isna(w.macro_ema.iloc[-1]))
        self.assertEqual(selected.direction.iloc[-1], 0)

    def test_strict_identity_and_chronology_reject_mismatched_frames(self):
        bars, core = bars_fixture()
        with self.assertRaises(ValueError):
            joint_frame(bars, core.iloc[1:], enabled=True)
        with self.assertRaises(ValueError):
            joint_frame(bars, core, enabled=1)

    def test_joint_account_blocks_native_while_addon_held_and_reconciles_real_contributions(self):
        bars, core = bars_fixture()
        bars.loc[bars.index[-5], ["open", "high", "low", "close"]] += 1.0
        core[["open", "high", "low", "close"]] = bars
        core.loc[core.index[-3], "direction"] = -1
        selected, witness = joint_frame(bars, core, enabled=True)
        self.assertEqual(witness.origin.iloc[-5], "addon")
        first = core.index[-5] + pd.Timedelta(minutes=15)
        middle = core.index[-3] + pd.Timedelta(minutes=15)
        last = core.index[-1] + pd.Timedelta(minutes=15)
        ticks = tape_at(
            [first, first + pd.Timedelta(seconds=1), middle, last, last + pd.Timedelta(seconds=1)],
            [133.3, 133.3, 133.5, 134.3, 134.3],
        )
        kwargs = dict(
            start=first.normalize(),
            end=last + pd.Timedelta(seconds=2),
            swap_policy=VALID_SWAP,
            capture_events=True,
            capture_context=True,
        )
        result = replay(selected, ticks, BROKER, native_rules(), Costs(), **kwargs)
        control = replay(core, ticks, BROKER, native_rules(), Costs(), **kwargs)
        attributed = attribute_joint(result, witness, control=control)
        self.assertEqual(result["trades"], 1)
        self.assertEqual(attributed["entries"][0]["origin"], "addon")
        self.assertEqual(attributed["known_busy_with_addon"], 1)
        self.assertEqual(len(attributed["missed_control_native"]), 1)
        self.assertEqual(attributed["closed_net_by_source"]["native"], 0)
        self.assertAlmostEqual(attributed["closed_net_by_source"]["addon"], result["net_usd"])
        self.assertFalse(attributed["counterfactual_pnl_added"])

    def test_unbound_context_and_overlapping_trade_intervals_refuse_attribution(self):
        _, witness = joint_frame(*bars_fixture(), enabled=True)
        result = dict(
            context_events=[
                dict(
                    signal_close_utc="2020-01-01T00:00Z",
                    direction=1,
                    reason="admitted",
                    time_utc="2020-01-01T00:00Z",
                )
            ],
            ledger=[],
            final_balance=200.0,
        )
        with self.assertRaises(ValueError):
            attribute_joint(result, witness)


class DailyMtmTests(unittest.TestCase):
    def fixture(self, *, stale=False):
        born = pd.Timestamp("2026-04-06T12:00Z")
        closed = pd.Timestamp("2026-04-08T12:00Z")
        stamps = (
            [born, closed]
            if stale
            else [
                born,
                pd.Timestamp("2026-04-06T23:59:59.999Z"),
                pd.Timestamp("2026-04-07T23:59:59.999Z"),
                closed,
            ]
        )
        ticks = tape_at(stamps, [100.0, 105.0] if stale else [100.0, 101.0, 103.0, 105.0])
        trade = dict(
            entry_ms=int(born.value // 10**6),
            entry_time_utc=born.isoformat(),
            exit_time_utc=closed.isoformat(),
            direction=1,
            entry=100.2,
            exit=105.0,
            volume=0.01,
            net=3.8,
            commission_usd=0.2,
            swap_usd=-0.8,
            reason="TP",
        )
        result = dict(
            start_utc="2026-04-06T00:00:00+00:00",
            end_exclusive_utc="2026-04-09T00:00:00+00:00",
            initial_balance=200.0,
            final_balance=203.8,
            net_usd=3.8,
            ledger=[trade],
            costs={"extra_spread": 0.0, "slippage": 0.0, "commission_per_lot": 20.0},
        )
        return result, ticks

    def test_signed_swap_fee_and_partial_daily_marks_telescope_actual_net(self):
        result, ticks = self.fixture()
        report = daily_mtm(
            result,
            ticks,
            BROKER,
            SwapPolicy(-0.4, -0.4, 1.0),
            origins={result["ledger"][0]["entry_ms"]: "addon"},
        )
        days = report["days"]
        self.assertEqual(len(days), 3)
        for row, net in zip(days, [0.6, 1.6, 1.6]):
            self.assertAlmostEqual(row["net_usd"], net)
        self.assertAlmostEqual(days[0]["end_equity_usd"], 200.6)
        self.assertAlmostEqual(days[1]["end_equity_usd"], 202.2)
        self.assertAlmostEqual(days[-1]["end_equity_usd"], 203.8)
        self.assertFalse(days[-1]["full_calendar_day"])
        self.assertEqual(days[0]["addon_entries"], 1)
        self.assertTrue(days[1]["no_entry_day"])
        self.assertAlmostEqual(report["net_reconciliation_usd"], 3.8)

    def test_stale_actual_price_is_modelled_and_excluded_from_verified_day_stats(self):
        result, ticks = self.fixture(stale=True)
        report = daily_mtm(
            result,
            ticks,
            BROKER,
            SwapPolicy(-0.4, -0.4, 1.0),
            origins={result["ledger"][0]["entry_ms"]: "native"},
        )
        self.assertFalse(report["days"][0]["end_price_verified"])
        self.assertEqual(report["days"][0]["end_coverage"], "STALE_ACTUAL_QUOTE_MODEL")
        self.assertEqual(report["distribution"]["verified_complete"]["count"], 0)
        self.assertAlmostEqual(report["net_reconciliation_usd"], 3.8)

    def test_sell_marks_use_ask_and_signed_funding(self):
        result, ticks = self.fixture()
        result["ledger"][0].update(direction=-1, entry=100.0, exit=95.2)
        ticks = (ticks[0], np.array([100.0, 99.0, 97.0, 95.0]), np.array([100.2, 99.2, 97.2, 95.2]))
        report = daily_mtm(
            result,
            ticks,
            BROKER,
            SwapPolicy(-0.4, -0.4, 1.0),
            origins={result["ledger"][0]["entry_ms"]: "native"},
        )
        self.assertAlmostEqual(report["days"][0]["end_equity_usd"], 200.6)
        self.assertAlmostEqual(report["days"][1]["end_equity_usd"], 202.2)
        self.assertAlmostEqual(report["net_reconciliation_usd"], 3.8)

    def test_flat_no_quote_days_are_known_cash_without_fake_price(self):
        ticks = tape_at(["2026-04-03T12:00Z", "2026-04-06T12:00Z"], [100.0, 100.0])
        result = dict(
            start_utc="2026-04-03T00:00:00+00:00",
            end_exclusive_utc="2026-04-07T00:00:00+00:00",
            initial_balance=200.0,
            final_balance=200.0,
            net_usd=0.0,
            ledger=[],
            costs={"extra_spread": 0.0, "slippage": 0.0, "commission_per_lot": 0.0},
        )
        report = daily_mtm(result, ticks, BROKER, SwapPolicy(-0.4, -0.4, 1.0), origins={})
        self.assertTrue(
            all(
                d["no_entry_day"] and d["end_coverage"] == "FLAT_REALIZED_CASH"
                for d in report["days"]
            )
        )
        self.assertTrue(
            all(d["end_quote_utc"] is None and d["net_usd"] == 0 for d in report["days"])
        )

    def test_missing_swap_or_overlapping_capacity_never_reports_daily_profit(self):
        result, ticks = self.fixture()
        with self.assertRaises(ValueError):
            daily_mtm(result, ticks, BROKER, None, origins={})
        result["ledger"].append(dict(result["ledger"][0]))
        with self.assertRaises(ValueError):
            daily_mtm(result, ticks, BROKER, SwapPolicy(-0.4, -0.4, 1.0), origins={})


class IndependentAddonAuditTests(unittest.TestCase):
    def test_separate_recursive_selector_matches_causal_choices_and_core_priority(self):
        bars, core = bars_fixture()
        core.loc[core.index[-1], "direction"] = -1
        _, witness = joint_frame(bars, core, enabled=True)
        independent = independent_selector(bars, core, True)
        self.assertEqual(
            [x["addon_eligible"] for x in independent], witness.addon_eligible.tolist()
        )
        self.assertEqual([x["origin"] for x in independent], witness.origin.tolist())
        self.assertEqual(independent[-1]["direction"], -1)

    def test_independent_boundary_vectors_reconcile_and_reject_tampered_day_profit(self):
        result, ticks = DailyMtmTests().fixture()
        entries = [dict(entry_ms=result["ledger"][0]["entry_ms"], origin="addon")]
        report = daily_mtm(
            result,
            ticks,
            BROKER,
            SwapPolicy(-0.4, -0.4, 1.0),
            origins={entries[0]["entry_ms"]: "addon"},
        )

        def swap(trade, stamps):
            return -0.4 * (np.asarray(stamps) // 86400000 - trade["entry_ms"] // 86400000)

        auditor = SimpleNamespace(
            times=ticks[0], tape={"bid": ticks[1], "ask": ticks[2]}, broker=BROKER, swap_value=swap
        )
        proof = audit_daily(auditor, result, report, entries)
        self.assertEqual(proof["days"], 3)
        self.assertEqual(proof["verified_complete_days"], 2)
        bad = deepcopy(report)
        bad["days"][0]["net_usd"] += 1
        with self.assertRaises(AssertionError):
            audit_daily(auditor, result, bad, entries)


if __name__ == "__main__":
    unittest.main()
