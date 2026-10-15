"""Deterministic behavioral checks; no source downloads or broker connectivity."""

import unittest
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from scripts.research.data import bars, validate_side
from scripts.research.strategies import Spec, registry, features, signals, structure
from scripts.research.engine import Costs, first_exit, simulate, metrics
from scripts.research.run import classify


def quotes(rows, start="2025-01-01 00:15", spread=0.2):
    bid = pd.DataFrame(
        rows,
        columns=["open", "high", "low", "close"],
        index=pd.date_range(start, periods=len(rows), freq="min", tz="UTC"),
    )
    return bid.add_prefix("bid_").join((bid + spread).add_prefix("ask_"))


def run_one(
    rows,
    direction=1,
    costs=None,
    entry="market",
    limit=np.nan,
    start="2025-01-01 00:15",
):
    m1 = quotes(rows, start)
    signal_time = m1.index[0] - pd.Timedelta(minutes=15)
    f = pd.DataFrame({"atr": [1.0], "regime": ["trend"]}, index=[signal_time])
    sig = pd.DataFrame({"direction": [direction], "limit": [limit]}, index=f.index)
    return simulate(m1, f, sig, Spec("test", "donchian", entry=entry), costs or Costs())


class RegistryAndCausalityTests(unittest.TestCase):
    def test_registry_contains_all_17_bases_and_named_variants(self):
        bases = {
            "Donchian20",
            "Donchian30",
            "Donchian40",
            "State15",
            "State20",
            "State25",
            "ATR1.25",
            "ATR1.5",
            "EMA10x30",
            "EMA20x50",
            "ORB30",
            "ORB60",
            "AsianBreak",
            "AsianRetest",
            "SweepReversal",
            "SweepMSS",
            "GSS_OTE",
        }
        named = {
            "A_TrendStructure",
            "B_Donchian30_RSI",
            "C_State25_RSI_FVG",
            "D_ATR1.5_RSI_FVG",
            "Asian_RSI_H1EMA",
            "SweepCHOCH",
            "SweepMSS_FVG",
            "SweepMSS_FVG_CE50",
            "Structure_OB",
            "TurtleSweep20",
            "TrendStructure25",
            "TrendStructure30",
        }
        specs = registry()
        names = {s.name for s in specs}
        self.assertEqual(len(specs), len(names))
        self.assertTrue(bases | named <= names)
        for base in bases:
            for filt in ("rsi", "body", "fvg", "h1ema", "h1structure"):
                self.assertIn(f"{base}__{filt}", names)
        self.assertEqual(sum(s.timeframe == 240 for s in specs), 6)
        self.assertEqual(len(specs), 120)

    def test_all_strategy_signals_and_features_are_prefix_causal(self):
        rng = np.random.default_rng(717)
        close = 2000 + np.cumsum(rng.normal(0, 0.8, 15 * 24 * 60))
        opening = np.r_[close[0], close[:-1]]
        m1 = quotes(
            np.c_[
                opening,
                np.maximum(opening, close) + 0.3,
                np.minimum(opening, close) - 0.3,
                close,
            ],
            start="2025-01-01",
        )
        all_frames = {tf: features(m1, tf) for tf in (15, 240)}
        prefix_frames = {tf: features(m1.iloc[: 12 * 24 * 60 + 37], tf) for tf in (15, 240)}
        for tf, short in prefix_frames.items():
            assert_frame_equal(short, all_frames[tf].loc[short.index])
        for spec in registry():
            with self.subTest(strategy=spec.name):
                short = signals(prefix_frames[spec.timeframe], spec)
                full = signals(all_frames[spec.timeframe], spec)
                assert_frame_equal(short, full.loc[short.index])

    def test_fractal_only_available_after_two_right_bars(self):
        f = pd.DataFrame({"high": [2, 3, 9, 4, 3, 2], "low": [1, 2, 3, 2, 1, 0]})
        _, high, _ = structure(f)
        self.assertTrue(np.isnan(high[:4]).all())
        np.testing.assert_array_equal(high[4:], [9, 9])
        self.assertTrue(np.isnan(structure(f.iloc[:4])[1]).all())


def pattern(rows, start="2025-01-01 07:00", direction=1):
    """Handcrafted completed bars; known prior structure supplied as a test seam."""
    f = pd.DataFrame(
        rows,
        columns=["open", "high", "low", "close"],
        index=pd.date_range(start, periods=len(rows), freq="15min", tz="UTC"),
    )
    if direction == -1:
        old = f.copy()
        f["open"], f["close"] = 200 - old.open, 200 - old.close
        f["high"], f["low"] = 200 - old.low, 200 - old.high
    f["atr"] = 2.0
    f["body"] = (f.close - f.open).abs() / (f.high - f.low)
    f["rsi"] = 50.0
    f["fvg_up"] = f.low - f.high.shift(2)
    f["fvg_down"] = f.low.shift(2) - f.high
    f["swing_high"], f["swing_low"] = 101.0, 99.0
    f["structure"] = -direction
    f["h1structure"], f["h1ema"] = direction, direction
    return f


class EntryPatternTests(unittest.TestCase):
    def test_session_breakout_requires_signal_close_before_1700_utc(self):
        for family, start, count, lookback in (
            ("asian", "2025-01-01", 67, 20),
            ("asian_retest", "2025-01-01", 67, 20),
            ("orb", "2025-01-01 07:00", 39, 30),
        ):
            rows = [[100, 101, 99, 100]] * count
            if family == "asian_retest":
                rows[-1] = [100, 103, 100, 102]  # 16:30 breakout arms retest
                final = [102, 103, 100.5, 102.5]
            else:
                final = [100, 103, 100, 102]
            f = pattern(rows + [final], start)
            spec = Spec("fixture", family, lookback=lookback)
            self.assertEqual(signals(f, spec).direction.iloc[-1], 0, family)

    def test_h4_ote_requires_signal_close_inside_session(self):
        rows = [[100, 110, 100, 109]] + [[108, 109, 106, 108]] * 5 + [[103, 104, 102, 103.8]]
        f = pattern(rows, "2025-01-01 08:00")
        f.index = pd.date_range("2025-01-01 08:00", periods=len(f), freq="4h", tz="UTC")
        self.assertFalse(signals(f, Spec("fixture", "ote", timeframe=240)).direction.any())

    def test_state_and_atr_wait_for_pullback_then_continuation(self):
        rows = [[100, 101, 99, 100]] * 2 + [
            [100, 104, 99.5, 103],
            [103, 103.5, 101, 102],
            [102, 105, 101.5, 104.5],
        ]
        for family in ("state", "expansion"):
            for direction in (1, -1):
                with self.subTest(family=family, direction=direction):
                    spec = Spec("fixture", family, lookback=2)
                    self.assertEqual(
                        signals(pattern(rows, direction=direction), spec).direction.tolist(),
                        [0, 0, 0, 0, direction],
                    )
                    invalid = [list(r) for r in rows]
                    invalid[3][2] = 99
                    self.assertFalse(
                        signals(pattern(invalid, direction=direction), spec).direction.any()
                    )
                    no_pullback = [list(r) for r in rows]
                    no_pullback[3][0] = 101.5
                    self.assertFalse(
                        signals(pattern(no_pullback, direction=direction), spec).direction.any()
                    )

    def test_asian_and_orb_require_complete_range_and_take_only_first_break(self):
        for family, count, start, lookback in [
            ("asian", 28, "2025-01-01", 20),
            ("orb", 2, "2025-01-01 07:00", 30),
            ("orb", 4, "2025-01-01 07:00", 60),
        ]:
            for direction in (1, -1):
                with self.subTest(family=family, count=count, direction=direction):
                    f = pattern(
                        [[100, 101, 99, 100]] * count + [[100, 103, 100, 102]] * 3,
                        start,
                        direction,
                    )
                    spec = Spec("fixture", family, lookback=lookback)
                    self.assertFalse(signals(f.iloc[:count], spec).direction.any())
                    self.assertEqual(
                        signals(f, spec).direction.tolist(),
                        [0] * count + [direction, 0, 0],
                    )
                    self.assertFalse(signals(f.drop(f.index[0]), spec).direction.any())

    def test_asian_retest_requires_prior_break_and_later_range_touch(self):
        rows = [[100, 101, 99, 100]] * 28 + [
            [100, 103, 100, 102],
            [102, 104, 101.5, 103],
            [102, 103, 100.5, 102.5],
            [102, 103, 100, 102],
        ]
        for direction in (1, -1):
            with self.subTest(direction=direction):
                f = pattern(rows, "2025-01-01", direction)
                spec = Spec("fixture", "asian_retest")
                self.assertEqual(signals(f, spec).direction.tolist(), [0] * 30 + [direction, 0])
                self.assertFalse(signals(f.iloc[:30], spec).direction.any())

    def test_sweep_mss_choch_and_fvg_have_distinct_confirmation_times(self):
        rows = [[100, 101, 99, 100]] * 2 + [
            [100, 100.8, 98, 100.5],
            [100.5, 103, 100, 102.5],
            [102.5, 104, 102, 103.5],
        ]
        for direction in (1, -1):
            f = pattern(rows, direction=direction)
            for family, index in [
                ("sweep", 2),
                ("mss", 3),
                ("choch", 3),
                ("mss_fvg", 4),
            ]:
                with self.subTest(family=family, direction=direction):
                    spec = Spec("fixture", family, lookback=2)
                    expected = [0] * 5
                    expected[index] = direction
                    result = signals(f, spec)
                    self.assertEqual(result.direction.tolist(), expected)
                    if family == "mss_fvg":
                        self.assertAlmostEqual(
                            result.limit.iloc[4], 101.4 if direction == 1 else 98.6
                        )
                    if family == "choch":
                        neutral = f.copy()
                        neutral["structure"] = 0
                        self.assertFalse(signals(neutral, spec).direction.any())
            no_sweep = [list(r) for r in rows]
            no_sweep[2][2] = 99
            for family in ("sweep", "mss", "choch", "mss_fvg"):
                self.assertFalse(
                    signals(
                        pattern(no_sweep, direction=direction),
                        Spec("fixture", family, lookback=2),
                    ).direction.any()
                )

    def test_order_block_requires_opposing_candle_and_uses_body_midpoint(self):
        rows = [[100, 101, 99, 100], [100.8, 101, 99.5, 100], [100, 103, 99.8, 102.5]]
        for direction in (1, -1):
            with self.subTest(direction=direction):
                spec = Spec("fixture", "ob", entry="ob")
                result = signals(pattern(rows, direction=direction), spec)
                self.assertEqual(result.direction.tolist(), [0, 0, direction])
                self.assertAlmostEqual(result.limit.iloc[2], 100.4 if direction == 1 else 99.6)
                no_opposition = [list(r) for r in rows]
                no_opposition[1][0] = 99.8
                self.assertFalse(
                    signals(pattern(no_opposition, direction=direction), spec).direction.any()
                )

    def test_ote_requires_session_impulse_and_618_786_retracement(self):
        rows = [[100, 110, 100, 109], [103, 104, 102, 103.8]]
        for direction in (1, -1):
            with self.subTest(direction=direction):
                spec = Spec("fixture", "ote")
                self.assertEqual(
                    signals(pattern(rows, direction=direction), spec).direction.tolist(),
                    [0, direction],
                )
                self.assertFalse(
                    signals(pattern(rows, "2025-01-01 05:00", direction), spec).direction.any()
                )
                no_touch = [rows[0], [106, 108, 105, 107]]
                self.assertFalse(
                    signals(pattern(no_touch, direction=direction), spec).direction.any()
                )
                invalidated = [rows[0], [101, 104, 99, 103]]
                self.assertFalse(
                    signals(pattern(invalidated, direction=direction), spec).direction.any()
                )


class DataTests(unittest.TestCase):
    def valid(self):
        return pd.DataFrame(
            {
                "timestamp": [1735689600000, 1735689660000],
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
            }
        )

    def test_valid_input_is_utc_and_preserves_prices(self):
        out = validate_side(self.valid())
        self.assertEqual(str(out.index.tz), "UTC")
        self.assertEqual(out.close.tolist(), [101.0, 102.0])
        self.assertEqual(out.index[1] - out.index[0], pd.Timedelta(minutes=1))

    def test_invalid_prices_geometry_duplicates_and_order_fail_closed(self):
        for column, value in [
            ("high", 99.0),
            ("low", 102.0),
            ("close", np.nan),
            ("open", np.inf),
            ("low", 0.0),
            ("timestamp", 1735689600000),
        ]:
            with self.subTest(column=column, value=value):
                frame = self.valid()
                frame.loc[1, column] = value
                with self.assertRaises(ValueError):
                    validate_side(frame)
        with self.assertRaises(ValueError):
            validate_side(self.valid().iloc[::-1])
        with self.assertRaises(ValueError):
            validate_side(self.valid().drop(columns="low"))
        frame = self.valid()
        frame.loc[0, "timestamp"] += 1000
        with self.assertRaises(ValueError):
            validate_side(frame)

    def test_incomplete_resample_is_removed_not_filled(self):
        m1 = quotes([[100, 101, 99, 100]] * 31, start="2025-01-01")
        complete = bars(m1, 15)
        self.assertEqual(list(complete.index), list(m1.index[[0, 15]]))
        incomplete = bars(m1.drop(m1.index[4]), 15)
        self.assertEqual(list(incomplete.index), [m1.index[15]])
        self.assertEqual(
            incomplete.iloc[0].to_dict(),
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0},
        )


class ExecutionTests(unittest.TestCase):
    def test_long_ask_entry_bid_exit_and_short_bid_entry_ask_exit(self):
        for d, entry, exit_price in [(1, 100.2, 100.0), (-1, 100.0, 100.2)]:
            with self.subTest(direction=d):
                log, dd = run_one([[100, 100.5, 99.5, 100]], direction=d)
                trade = log.iloc[0]
                self.assertAlmostEqual(trade.entry, entry)
                self.assertAlmostEqual(trade.exit, exit_price)
                self.assertAlmostEqual(trade.net, -0.2)
                self.assertAlmostEqual(dd, 0.2)
                self.assertEqual(trade.entry_time, trade.signal_time)

    def test_intraminute_collision_is_stop_first_both_directions(self):
        for d, stop, target in [(1, 98, 104), (-1, 102, 96)]:
            self.assertEqual(
                first_exit(np.array([[100.0, 105.0, 95.0, 100.0]]), 0, d, stop, target),
                (0, stop, "SL"),
            )

    def test_open_gap_stop_executes_at_open_not_stop(self):
        for d, opened, stop, target in [(1, 95, 98, 104), (-1, 105, 102, 96)]:
            result = first_exit(
                np.array([[opened, opened + 1, opened - 1, opened]], float),
                0,
                d,
                stop,
                target,
            )
            self.assertEqual(result, (0, opened, "SL_GAP"))

    def test_range_limit_fill_cannot_take_earlier_same_minute_tp(self):
        log, _ = run_one([[101, 105, 99.7, 100], [100, 101, 99, 100]], entry="ce50", limit=100)
        trade = log.iloc[0]
        self.assertEqual(trade.reason, "END_OF_SAMPLE")
        self.assertEqual(trade.exit_time, trade.entry_time + pd.Timedelta(minutes=1))
        self.assertEqual(trade.net, 0)

    def test_range_limit_fill_stop_collision_is_conservative(self):
        log, _ = run_one([[101, 105, 97, 100]], entry="ce50", limit=100)
        self.assertEqual(log.iloc[0].reason, "SL_FILL_AMBIGUOUS")
        self.assertEqual(log.iloc[0].net, -2)

    def test_costs_include_units_slippage_commission_and_midnight_swap(self):
        costs = Costs(
            units=2,
            commission_per_unit_roundtrip=0.1,
            slippage=0.05,
            swap_per_unit_night=0.3,
        )
        log, dd = run_one([[100, 100.5, 99.5, 100]] * 2, costs=costs, start="2025-01-01 23:59")
        trade = log.iloc[0]
        self.assertAlmostEqual(trade.entry, 100.25)
        self.assertAlmostEqual(trade.exit, 99.95)
        self.assertAlmostEqual(trade.gross, -0.6)
        self.assertAlmostEqual(trade.fees, 0.8)
        self.assertAlmostEqual(trade.net, -1.4)
        self.assertAlmostEqual(trade.r, -0.35)
        self.assertAlmostEqual(dd, 1.4)

    def test_missing_exact_next_open_does_not_execute_later(self):
        m1 = quotes([[100, 101, 99, 100]], start="2025-01-01 00:16")
        f = pd.DataFrame({"atr": [1.0], "regime": ["trend"]}, index=[m1.index[0].normalize()])
        sig = pd.DataFrame({"direction": [1], "limit": [np.nan]}, index=f.index)
        log, dd = simulate(m1, f, sig, Spec("test", "donchian"))
        self.assertTrue(log.empty)
        self.assertEqual(dd, 0)

    def test_invalid_costs_and_delay_fail_closed(self):
        for kwargs in [
            {"units": 0},
            {"units": np.nan},
            {"slippage": -1},
            {"commission_per_unit_roundtrip": -1},
            {"swap_per_unit_night": -1},
        ]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Costs(**kwargs)
        with self.assertRaises(ValueError):
            simulate(None, None, None, None, delay_minutes=-1)

    def test_native_sideway_gate_and_explicit_delay(self):
        m1 = quotes([[100, 101, 99, 100], [101, 102, 100, 101]])
        f = pd.DataFrame(
            {"atr": [1.0], "regime": ["sideway"]},
            index=[m1.index[0] - pd.Timedelta(minutes=15)],
        )
        sig = pd.DataFrame({"direction": [1], "limit": [np.nan]}, index=f.index)
        spec = Spec("test", "donchian")
        native, _ = simulate(m1, f, sig, spec, native=True)
        common, _ = simulate(m1, f, sig, spec, delay_minutes=1)
        self.assertTrue(native.empty)
        self.assertEqual(len(common), 1)
        self.assertEqual(common.iloc[0].entry_time, m1.index[1])
        self.assertAlmostEqual(common.iloc[0].entry, 101.2)


class ScreeningTests(unittest.TestCase):
    def test_initial_loss_drawdown_includes_starting_equity(self):
        trades = pd.DataFrame(
            {
                "net": [-5, -2, 10, -3],
                "r": [-1, -0.4, 2, -0.6],
                "direction": [1, -1, 1, -1],
            }
        )
        out = metrics(trades, 8.0)
        self.assertEqual(out["max_closed_dd"], 7)
        self.assertEqual(out["max_loss_streak"], 2)
        self.assertEqual(out["net"], 0)
        self.assertEqual(out["pf"], 1)
        self.assertEqual(out["long_pf"], 2)
        self.assertEqual(out["short_pf"], 0)
        self.assertEqual(out["win_rate"], 0.25)

    def test_empty_metrics_and_insufficient_evidence_do_not_promote(self):
        out = metrics(pd.DataFrame())
        self.assertEqual(out["trades"], 0)
        self.assertIsNone(out["pf"])
        self.assertIsNone(out["expectancy_r"])
        self.assertEqual(classify([]), "INSUFFICIENT")
        self.assertEqual(classify([{"trades": 100, "net": 1}] * 4), "INSUFFICIENT")
        self.assertEqual(classify([{"trades": 39, "net": 1}] * 5), "INSUFFICIENT")

    def test_loss_and_profit_concentration_screen(self):
        self.assertEqual(classify([{"trades": 40, "net": -1}] * 5), "REJECT_RESEARCH")
        self.assertEqual(classify([{"trades": 40, "net": 1}] * 5), "REVIEW_CANDIDATE")
        concentrated = [{"trades": 40, "net": 100}] + [{"trades": 40, "net": 1}] * 4
        self.assertEqual(classify(concentrated), "WATCH")


if __name__ == "__main__":
    unittest.main()
