"""Public replay and training-selection seams; synthetic quotes, no broker."""

import unittest
import json

import numpy as np
import pandas as pd

from scripts.research.breakout_logic import Costs, Rules, replay, dominates
from scripts.research.tune_breakout_logic import choose_training

BROKER = dict(
    trade_contract_size=100.0,
    trade_tick_size=0.001,
    leverage=1000.0,
    volume_min=0.01,
    volume_max=200.0,
    volume_step=0.01,
)
START = pd.Timestamp("2026-04-01", tz="UTC")
END = START + pd.Timedelta(hours=1)


def sample():
    frame = pd.DataFrame(
        dict(
            open=[100.0, 100.0, 100.0],
            high=[101.0, 100.0, 100.0],
            low=[99.0, 99.0, 99.0],
            close=[100.5, 99.5, 99.5],
            hh=[100.0, 100.0, 100.0],
            ll=[95.0, 95.0, 95.0],
            atr=[1.0, 1.0, 1.0],
            direction=[1, 0, 0],
        ),
        index=pd.date_range(START, periods=3, freq="15min"),
    )
    times = START.value // 10**6 + np.array([900000, 1800000, 2700000])
    return frame, (times, np.array([100.0, 99.6, 99.4]), np.array([100.2, 99.8, 99.6]))


class BreakoutLogicTests(unittest.TestCase):
    def test_zero_spread_replay_bounds_allocation_and_checks_chunk_boundaries(self):
        import tracemalloc

        frame, _ = sample()
        size = 1_000_005
        times = START.value // 10**6 + 900000 + np.arange(size)
        bid = np.full(size, 100.0)
        ask = np.full(size, 100.2)
        bid.flags.writeable = ask.flags.writeable = False
        tracemalloc.start()
        try:
            result = replay(
                frame, (times, bid, ask), BROKER, Rules(), Costs(), start=START, end=END
            )
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(result["trades"], 1)
        self.assertAlmostEqual(result["net_usd"], -0.2)
        # Allow unchanged 100k-tick held-position buffers plus frame/ledger overhead.
        self.assertLess(peak, 6 * 2**20, "zero-spread replay must not copy the full input tape")
        self.assertTrue(np.all(bid == 100.0) and np.all(ask == 100.2))
        # Reject out-of-order timestamp exactly across validation chunk boundary.
        times[100000] = times[99999] - 1
        with self.assertRaisesRegex(ValueError, "invalid ticks"):
            replay(frame, (times, bid, ask), BROKER, Rules(), Costs(), start=START, end=END)
        times[100000] = times[99999] + 1
        corrupt = ask.copy()
        corrupt[100000] = np.nan
        with self.assertRaisesRegex(ValueError, "invalid ticks"):
            replay(frame, (times, bid, corrupt), BROKER, Rules(), Costs(), start=START, end=END)
        corrupt[100000] = 99.9
        with self.assertRaisesRegex(ValueError, "invalid ticks"):
            replay(frame, (times, bid, corrupt), BROKER, Rules(), Costs(), start=START, end=END)

    def test_short_buy_stop_changes_admission_but_preserves_sell_and_cost_cap(self):
        frame, ticks = sample()
        frame["atr"] = 13.3
        cost = Costs(commission_per_lot=10)
        shared = replay(frame, ticks, BROKER, Rules(buy_stop_atr=1.5), cost, start=START, end=END)
        rules = Rules(buy_stop_atr=1.0, buy_target_rr=2.0)
        short = replay(frame, ticks, BROKER, rules, cost, start=START, end=END)
        self.assertEqual(shared["trades"], 0)
        self.assertEqual(short["trades"], 1)
        trade = short["ledger"][0]
        self.assertAlmostEqual(trade["initial_stop"], 86.9)
        self.assertAlmostEqual(trade["target"], 126.8)
        self.assertAlmostEqual(trade["risk_usd"], 13.4)
        self.assertEqual(trade["volume"], 0.01)
        frame["direction"] = [-1, 0, 0]
        sell = replay(frame, ticks, BROKER, rules, cost, start=START, end=END)
        self.assertEqual(sell["trades"], 0)
        self.assertEqual(sell["rejections"]["risk_cap"], 1)
        frame["direction"] = [1, 0, 0]
        frame["atr"] = 20.0
        rejected = replay(frame, ticks, BROKER, rules, cost, start=START, end=END)
        self.assertEqual(rejected["trades"], 0)
        self.assertEqual(rejected["rejections"]["risk_cap"], 1)

    def test_buy_protection_off_keeps_sell_break_even_lifecycle_identical(self):
        frame, _ = sample()
        times = START.value // 10**6 + np.array([900000, 1800000, 1860000, 2700000])
        buy_bid = np.array([100.0, 101.8, 100.1, 100.1])
        profile = Rules(
            protect_mode="break_even",
            protect_after_r=1.0,
            buy_stop_atr=1.5,
            buy_target_rr=1.35,
            buy_protect_mode="off",
        )
        result = replay(
            frame, (times, buy_bid, buy_bid + 0.2), BROKER, profile, Costs(), start=START, end=END
        )
        trade = result["ledger"][0]
        self.assertEqual(trade["stop_updates"], 0)
        self.assertAlmostEqual(trade["stop"], 98.7)
        self.assertEqual(trade["reason"], "END_OF_SAMPLE")
        frame["direction"] = [-1, 0, 0]
        sell_bid = np.array([100.0, 97.2, 100.0, 100.0])
        ticks = (times, sell_bid, sell_bid + 0.2)
        expected = replay(
            frame,
            ticks,
            BROKER,
            Rules(protect_mode="break_even", protect_after_r=1.0),
            Costs(),
            start=START,
            end=END,
        )
        actual = replay(frame, ticks, BROKER, profile, Costs(), start=START, end=END)
        self.assertEqual(actual["ledger"], expected["ledger"])
        self.assertEqual(actual["ledger"][0]["stop_updates"], 1)
        self.assertAlmostEqual(actual["ledger"][0]["stop"], 100.0)
        self.assertEqual(actual["ledger"][0]["reason"], "SL")

    def test_buy_exit_profile_preserves_sell_parent_and_cost_inclusive_cap(self):
        frame, _ = sample()
        frame.loc[frame.index[1], "direction"] = -1
        times = START.value // 10**6 + np.array([900000, 960000, 1800000, 1860000])
        bid = np.array([100.0, 110.0, 100.0, 90.0])
        rules = Rules(buy_stop_atr=1.5, buy_target_rr=1.35)
        result = replay(
            frame, (times, bid, bid + 0.2), BROKER, rules, Costs(), start=START, end=END
        )
        self.assertEqual([p["direction"] for p in result["ledger"]], [1, -1])
        buy, sell = result["ledger"]
        self.assertAlmostEqual(buy["initial_stop"], 98.7)
        self.assertAlmostEqual(buy["target"], 102.225)
        self.assertAlmostEqual(sell["initial_stop"], 102.5)
        self.assertAlmostEqual(sell["target"], 97.0)
        self.assertTrue(all(p["volume"] == 0.01 for p in result["ledger"]))
        frame, ticks = sample()
        frame["atr"] = 13.3
        accepted = replay(frame, ticks, BROKER, rules, Costs(), start=START, end=END)
        rejected = replay(
            frame, ticks, BROKER, rules, Costs(commission_per_lot=10), start=START, end=END
        )
        self.assertEqual(accepted["trades"], 1)
        self.assertAlmostEqual(accepted["ledger"][0]["risk_usd"], 19.95)
        self.assertEqual(rejected["trades"], 0)
        self.assertEqual(rejected["rejections"]["risk_cap"], 1)
        with self.assertRaises(ValueError):
            Rules(buy_stop_atr=1.5, stop_mode="structure")

    def test_entry_spread_is_in_trade_mae_and_account_drawdown(self):
        frame, ticks = sample()
        # First quote has larger spread than any subsequent adverse movement.
        ticks = (ticks[0], np.array([99.0, 100.1, 100.1]), np.array([100.2, 100.3, 100.3]))
        result = replay(frame, ticks, BROKER, Rules(), Costs(), start=START, end=END)
        self.assertAlmostEqual(result["ledger"][0]["mae_usd"], -1.2)
        self.assertGreaterEqual(result["max_dd_pct"], 0.6 - 1e-9)

    def test_reset_cannot_use_bar_that_closed_before_stop_fill(self):
        frame, ticks = sample()
        frame.loc[frame.index[1], "direction"] = -1
        ticks = (ticks[0], np.array([100.0, 97.0, 97.0]), np.array([100.2, 97.2, 97.2]))
        result = replay(
            frame, ticks, BROKER, Rules(reset_after_exit=True), Costs(), start=START, end=END
        )
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["rejections"]["reset"], 1)

    def test_failed_breakout_exits_on_next_quote_without_new_signal(self):
        frame, ticks = sample()
        result = replay(frame, ticks, BROKER, Rules(failed_closes=1), Costs(), start=START, end=END)
        trade = result["ledger"][0]
        self.assertEqual(trade["reason"], "FAILED_BREAKOUT")
        self.assertAlmostEqual(trade["exit"], 99.6)
        self.assertAlmostEqual(trade["net"], -0.6)
        self.assertEqual(trade["exit_time_utc"], "2026-04-01T00:30:00+00:00")

    def test_cost_inclusive_risk_rejects_instead_of_clamping_lot(self):
        frame, ticks = sample()
        frame["atr"] = 7.96
        base = replay(frame, ticks, BROKER, Rules(), Costs(), start=START, end=END)
        costly = replay(
            frame, ticks, BROKER, Rules(), Costs(commission_per_lot=20.0), start=START, end=END
        )
        self.assertEqual(base["trades"], 1)
        self.assertEqual(base["ledger"][0]["volume"], 0.01)
        self.assertEqual(costly["trades"], 0)
        self.assertEqual(costly["rejections"]["risk_cap"], 1)
        self.assertEqual(costly["final_balance"], 200.0)

    def test_rr_and_dd_use_realized_tp_not_favorable_tick_overshoot(self):
        frame, ticks = sample()
        frame.loc[frame.index[1], "direction"] = 1
        t = START.value // 10**6 + np.array([900000, 960000, 1800000, 1860000, 2700000])
        b = np.array([100.0, 110.0, 100.0, 97.7, 100.0])
        result = replay(frame, (t, b, b + 0.2), BROKER, Rules(), Costs(), start=START, end=END)
        self.assertEqual(result["trades"], 2)
        self.assertAlmostEqual(result["net_usd"], 0.5)
        self.assertAlmostEqual(result["realized_rr"], 1.2)
        self.assertAlmostEqual(result["ledger"][0]["mfe_usd"], 3.0)
        self.assertAlmostEqual(result["max_dd_pct"], 2.5 / 203 * 100)

    def test_commission_and_both_market_slippages_are_charged(self):
        frame, ticks = sample()
        result = replay(
            frame,
            ticks,
            BROKER,
            Rules(failed_closes=1),
            Costs(slippage=0.1, commission_per_lot=10),
            start=START,
            end=END,
        )
        self.assertAlmostEqual(result["net_usd"], -0.9)
        self.assertAlmostEqual(result["commission_usd"], 0.1)
        self.assertAlmostEqual(result["modeled_slippage_usd"], 0.2)
        self.assertAlmostEqual(result["ledger"][0]["risk_usd"], 2.7)

    def test_gate_rejects_rr_regression_even_when_profit_increases(self):
        base = dict(trades=30, realized_rr=1.2, net_usd=50, max_dd_pct=40, max_admitted_risk_pct=10)
        improved = dict(base, realized_rr=1.3, net_usd=60, max_dd_pct=30)
        self.assertTrue(dominates(improved, base, improved, base, min_trades=20))
        for change in [
            dict(realized_rr=1.1),
            dict(realized_rr=None),
            dict(trades=19),
            dict(max_dd_pct=41),
            dict(max_admitted_risk_pct=10.01),
        ]:
            with self.subTest(change=change):
                self.assertFalse(
                    dominates(dict(improved, **change), base, improved, base, min_trades=20)
                )
        self.assertFalse(dominates(improved, base, base, base, min_trades=20))

    def test_naive_window_rejected(self):
        frame, ticks = sample()
        with self.assertRaisesRegex(ValueError, "aware UTC"):
            replay(frame, ticks, BROKER, Rules(), Costs(), start=START.tz_localize(None), end=END)

    def test_numpy_metric_gate_result_can_be_persisted(self):
        base = dict(
            trades=30,
            realized_rr=1.2,
            net_usd=np.float64(50),
            max_dd_pct=40,
            max_admitted_risk_pct=np.float64(10),
        )
        improved = dict(base, realized_rr=1.3, net_usd=np.float64(60), max_dd_pct=30)
        result = dominates(improved, base, improved, base, min_trades=20)
        self.assertEqual(json.dumps({"passed": result}), '{"passed": true}')

    def test_late_quote_does_not_discard_failed_breakout_exit(self):
        frame, ticks = sample()
        times = ticks[0].copy()
        times[1] += 120000
        result = replay(
            frame,
            (times, ticks[1], ticks[2]),
            BROKER,
            Rules(failed_closes=1),
            Costs(),
            start=START,
            end=END,
        )
        self.assertEqual(result["ledger"][0]["reason"], "FAILED_BREAKOUT")
        self.assertEqual(result["ledger"][0]["exit_time_utc"], "2026-04-01T00:32:00+00:00")

    def test_confirm_entry_waits_for_following_closed_bar(self):
        frame, ticks = sample()
        frame.loc[frame.index[1], "close"] = 100.6
        result = replay(
            frame, ticks, BROKER, Rules(entry_mode="confirm"), Costs(), start=START, end=END
        )
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["ledger"][0]["entry_time_utc"], "2026-04-01T00:30:00+00:00")
        self.assertEqual(result["ledger"][0]["boundary"], 100.0)

    def test_retest_requires_touch_and_reclaim_after_breakout(self):
        frame, ticks = sample()
        frame.loc[frame.index[1], ["close", "low"]] = [100.6, 100.1]
        frame.loc[frame.index[2], ["close", "low"]] = [100.4, 99.9]
        result = replay(
            frame, ticks, BROKER, Rules(entry_mode="retest"), Costs(), start=START, end=END
        )
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["ledger"][0]["entry_time_utc"], "2026-04-01T00:45:00+00:00")

    def test_cross_midnight_position_requires_day_start_snapshot(self):
        frame, _ = sample()
        frame.index = pd.DatetimeIndex(
            [
                START + pd.Timedelta(hours=23, minutes=30),
                START + pd.Timedelta(days=1),
                START + pd.Timedelta(days=1, minutes=15),
            ]
        )
        frame["direction"] = [1, 1, 0]
        stamps = [
            START + pd.Timedelta(hours=23, minutes=45),
            START + pd.Timedelta(days=1, seconds=2),
            START + pd.Timedelta(days=1, minutes=5),
            START + pd.Timedelta(days=1, minutes=15),
            START + pd.Timedelta(days=1, minutes=30),
        ]
        times = np.array([t.value // 10**6 for t in stamps])
        bid = np.array([100.0, 100.0, 97.0, 100.0, 100.0])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=START + pd.Timedelta(days=1, hours=1),
        )
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["ledger"][0]["reason"], "SL")
        self.assertEqual(result["rejections"]["day_start_unknown"], 1)

    def test_late_entry_is_rejected_and_no_future_bar_changes_past_trades(self):
        frame, ticks = sample()
        delayed = ticks[0].copy()
        delayed[0] += 91000
        result = replay(
            frame, (delayed, ticks[1], ticks[2]), BROKER, Rules(), Costs(), start=START, end=END
        )
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["rejections"]["late_quote"], 1)
        original = replay(frame, ticks, BROKER, Rules(), Costs(), start=START, end=END)
        future = frame.iloc[[-1]].copy()
        future.index = pd.DatetimeIndex([END])
        future["direction"] = -1
        future["close"] = 1.0
        extended = replay(
            pd.concat([frame, future]), ticks, BROKER, Rules(), Costs(), start=START, end=END
        )
        self.assertEqual(original, extended)

    def test_structure_stop_uses_candle_extreme_and_still_rejects_excess_risk(self):
        frame, ticks = sample()
        result = replay(
            frame, ticks, BROKER, Rules(stop_mode="structure"), Costs(), start=START, end=END
        )
        self.assertAlmostEqual(result["ledger"][0]["stop"], 98.999)
        self.assertLess(result["ledger"][0]["risk_usd"], 2.5)
        frame.loc[frame.index[0], "low"] = 70.0
        rejected = replay(
            frame, ticks, BROKER, Rules(stop_mode="structure"), Costs(), start=START, end=END
        )
        self.assertEqual(rejected["trades"], 0)
        self.assertEqual(rejected["rejections"]["risk_cap"], 1)

    def test_sell_structure_stop_and_failed_exit_use_ask(self):
        frame, ticks = sample()
        frame["direction"] = [-1, 0, 0]
        frame["close"] = [94.5, 95.5, 95.5]
        frame.loc[frame.index[0], ["high", "low"]] = [96.0, 94.0]
        bid = np.array([94.8, 95.3, 95.3])
        result = replay(
            frame,
            (ticks[0], bid, bid + 0.2),
            BROKER,
            Rules(failed_closes=1, stop_mode="structure"),
            Costs(),
            start=START,
            end=END,
        )
        trade = result["ledger"][0]
        self.assertAlmostEqual(trade["stop"], 96.001)
        self.assertAlmostEqual(trade["entry"], 94.8)
        self.assertAlmostEqual(trade["exit"], 95.5)
        self.assertAlmostEqual(trade["net"], -0.7)
        self.assertEqual(trade["reason"], "FAILED_BREAKOUT")

    def test_daily_loss_gate_blocks_new_entry_after_losses(self):
        frame = pd.DataFrame(
            dict(
                open=[100.0] * 8,
                high=[101.0] * 8,
                low=[99.0] * 8,
                close=[100.5] * 8,
                hh=[100.0] * 8,
                ll=[95.0] * 8,
                atr=[5.0] * 8,
                direction=[1] * 8,
            ),
            index=pd.date_range(START, periods=8, freq="15min"),
        )
        offsets = np.array([v for n in range(1, 9) for v in (n * 900000, n * 900000 + 60000)])
        times = START.value // 10**6 + offsets
        bid = np.tile([100.0, 87.7], 8)
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=START + pd.Timedelta(hours=3),
        )
        self.assertEqual(result["trades"], 7)
        self.assertEqual(result["rejections"]["daily_loss"], 1)
        self.assertAlmostEqual(result["final_balance"], 112.5)
        self.assertLessEqual(result["max_admitted_risk_pct"], 10.0)

    def test_break_even_activates_after_closed_bar_and_covers_costs(self):
        frame, _ = sample()
        times = START.value // 10**6 + np.array([900000, 1800000, 1860000, 2700000])
        bid = np.array([100.0, 101.7, 100.1, 100.1])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(protect_mode="break_even"),
            Costs(),
            start=START,
            end=END,
        )
        trade = result["ledger"][0]
        self.assertEqual(trade["reason"], "SL")
        self.assertAlmostEqual(trade["stop"], 100.2)
        self.assertAlmostEqual(trade["initial_stop"], 97.7)
        self.assertEqual(trade["stop_updates"], 1)
        self.assertEqual(trade["exit_time_utc"], "2026-04-01T00:31:00+00:00")
        self.assertAlmostEqual(trade["risk_usd"], 2.5)

    def test_protection_does_not_apply_to_earlier_ticks_or_widen_stop(self):
        frame, _ = sample()
        frame["low"] = [99.0, 101.0, 98.0]
        times = START.value // 10**6 + np.array([900000, 1200000, 1800000, 2700000, 2760000])
        bid = np.array([100.0, 99.0, 101.7, 101.6, 100.9])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(protect_mode="candle_trail"),
            Costs(),
            start=START,
            end=END,
        )
        trade = result["ledger"][0]
        self.assertAlmostEqual(trade["stop"], 100.999)
        self.assertEqual(trade["stop_updates"], 1)
        self.assertEqual(trade["exit_time_utc"], "2026-04-01T00:46:00+00:00")

    def test_runner_disables_target_only_after_protection_and_retains_initial_risk(self):
        frame, _ = sample()
        times = START.value // 10**6 + np.array([900000, 1800000, 1860000, 2700000])
        bid = np.array([100.0, 101.7, 105.0, 104.0])
        runner = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(protect_mode="runner"),
            Costs(),
            start=START,
            end=END,
        )
        fixed = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(protect_mode="break_even"),
            Costs(),
            start=START,
            end=END,
        )
        self.assertEqual(runner["ledger"][0]["reason"], "END_OF_SAMPLE")
        self.assertAlmostEqual(runner["net_usd"], 3.8)
        self.assertEqual(fixed["ledger"][0]["reason"], "TP")
        self.assertAlmostEqual(fixed["net_usd"], 3.0)
        self.assertAlmostEqual(runner["ledger"][0]["risk_usd"], 2.5)

    def test_sell_break_even_covers_commission_and_slippage(self):
        frame, _ = sample()
        frame["direction"] = [-1, 0, 0]
        times = START.value // 10**6 + np.array([900000, 1800000, 1860000, 2700000])
        bid = np.array([100.0, 98.0, 99.5, 99.5])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(protect_mode="break_even"),
            Costs(slippage=0.1, commission_per_lot=10.0),
            start=START,
            end=END,
        )
        trade = result["ledger"][0]
        self.assertAlmostEqual(trade["stop"], 99.7)
        self.assertAlmostEqual(trade["net"], 0.0)
        self.assertEqual(trade["stop_updates"], 1)

    def test_buy_pause_blocks_buy_under_peak_and_still_admits_sell(self):
        frame, _ = sample()
        frame = pd.concat([frame, frame.iloc[[0]].copy()])
        frame.index = pd.date_range(START, periods=4, freq="15min")
        frame["direction"] = [1, 0, 1, -1]
        frame["atr"] = 1.0
        times = (START.value // 10**6) + np.array([900000, 960000, 2700000, 3600000])
        bid = np.array([100.0, 50.0, 50.0, 50.0])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(buy_pause_drawdown=0.20),
            Costs(),
            start=START,
            end=START + pd.Timedelta(hours=2),
        )
        self.assertEqual([trade["direction"] for trade in result["ledger"]], [1, -1])
        self.assertEqual(result["rejections"]["buy_pause"], 1)

    def test_direction_control_rejects_buy_and_does_not_change_risk(self):
        frame, ticks = sample()
        result = replay(
            frame, ticks, BROKER, Rules(entry_guard="sell_only"), Costs(), start=START, end=END
        )
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["rejections"]["entry_guard"], 1)

    def test_body_guard_rejects_wick_dominated_breakout(self):
        frame, ticks = sample()
        frame.loc[frame.index[0], ["open", "close", "high", "low"]] = [100.4, 100.5, 101.0, 99.0]
        result = replay(
            frame, ticks, BROKER, Rules(entry_guard="body_dominant"), Costs(), start=START, end=END
        )
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["rejections"]["entry_guard"], 1)

    def test_prior_day_guard_uses_only_previous_calendar_day(self):
        frame, ticks = sample()
        prior = frame.iloc[[0]].copy()
        prior.index = pd.DatetimeIndex([START - pd.Timedelta(minutes=15)])
        prior["open"] = 99.0
        prior["close"] = 100.0
        data = pd.concat([prior, frame])
        accepted = replay(
            data, ticks, BROKER, Rules(entry_guard="prior_day"), Costs(), start=START, end=END
        )
        self.assertEqual(accepted["trades"], 1)
        future = frame.iloc[[-1]].copy()
        future.index = pd.DatetimeIndex([START + pd.Timedelta(hours=20)])
        future["close"] = 1.0
        unchanged = replay(
            pd.concat([data, future]),
            ticks,
            BROKER,
            Rules(entry_guard="prior_day"),
            Costs(),
            start=START,
            end=END,
        )
        self.assertEqual(accepted, unchanged)
        prior.index = pd.DatetimeIndex([START - pd.Timedelta(days=2)])
        rejected = replay(
            pd.concat([prior, frame]),
            ticks,
            BROKER,
            Rules(entry_guard="prior_day"),
            Costs(),
            start=START,
            end=END,
        )
        self.assertEqual(rejected["trades"], 0)
        self.assertEqual(rejected["rejections"]["entry_guard"], 1)

    def test_midnight_admission_uses_day_that_just_completed(self):
        frame, _ = sample()
        frame.index = pd.DatetimeIndex(
            [START - pd.Timedelta(minutes=15), START, START + pd.Timedelta(minutes=15)]
        )
        frame["direction"] = [-1, 0, 0]
        frame.loc[frame.index[0], ["open", "close"]] = [100.0, 99.0]
        previous = frame.iloc[[0]].copy()
        previous.index = pd.DatetimeIndex([START - pd.Timedelta(days=1, minutes=15)])
        previous["open"] = 99.0
        previous["close"] = 100.0
        times = START.value // 10**6 + np.array([0, 900000, 1800000])
        bid = np.array([99.0, 99.0, 99.0])
        result = replay(
            pd.concat([previous, frame]),
            (times, bid, bid + 0.2),
            BROKER,
            Rules(entry_guard="prior_day"),
            Costs(),
            start=START,
            end=END,
        )
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["ledger"][0]["entry_time_utc"], "2026-04-01T00:00:00+00:00")

    def test_training_choice_ignores_validation_and_never_falls_back(self):
        rows = [
            dict(
                trial=1,
                training_pass=True,
                base=dict(max_dd_pct=20, net_usd=50),
                validation_net=-500,
            ),
            dict(
                trial=2,
                training_pass=True,
                base=dict(max_dd_pct=30, net_usd=100),
                validation_net=500,
            ),
            dict(trial=3, training_pass=False, base=dict(max_dd_pct=1, net_usd=900)),
        ]
        self.assertEqual(choose_training(rows)["trial"], 1)
        self.assertIsNone(choose_training(rows[2:]))


if __name__ == "__main__":
    unittest.main()
