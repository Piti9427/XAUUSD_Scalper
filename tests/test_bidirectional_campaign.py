"""Agreed replay -> qualification/resume seams; no broker access."""

import unittest

from scripts.research.bidirectional_campaign import qualifies_trial30, candidate_frame
from scripts.research.breakout_logic import Costs, Rules, replay
from tests.test_breakout_logic import sample, BROKER, START, END


class BidirectionalCampaignTests(unittest.TestCase):
    def test_horizon_signals_execute_both_sides_without_future_bars(self):
        import numpy as np
        import pandas as pd
        from scripts.research.breakout_logic import features

        bars = pd.DataFrame(
            dict(open=100.0, high=101.0, low=99.0, close=100.0),
            index=pd.date_range(START, periods=18, freq="15min"),
        )
        # Only prior 12 bars set the channel; current extrema must not enter it.
        bars.iloc[14] = [100.0, 103.0, 99.0, 102.0]
        bars.iloc[16] = [100.0, 101.0, 97.0, 98.0]
        frame = features(bars)
        spec = dict(buy_lookback=12, sell_lookback=12, trend_span=0)
        prepared = candidate_frame(frame, "off", 0.0, signal_spec=spec)
        cut = candidate_frame(frame.iloc[:15], "off", 0.0, signal_spec=spec)
        pd.testing.assert_frame_equal(prepared.iloc[:15], cut)
        self.assertEqual(prepared.direction.tolist(), [0] * 14 + [1, 0, -1, 0])
        self.assertEqual(prepared.hh.iloc[14], 101.0)
        self.assertEqual(prepared.ll.iloc[16], 99.0)
        times = START.value // 10**6 + np.array([13500000, 13560000, 15300000, 15360000])
        bid = np.array([102.0, 113.0, 98.0, 87.0])
        result = replay(
            prepared,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=START + pd.Timedelta(hours=5),
        )
        self.assertEqual([p["direction"] for p in result["ledger"]], [1, -1])
        self.assertTrue(all(p["volume"] == 0.01 and p["risk_pct"] <= 10 for p in result["ledger"]))

    def test_horizon_trend_warmup_and_opposite_trend_block_replay_entries(self):
        import numpy as np
        import pandas as pd
        from scripts.research.breakout_logic import features

        for prior_price, span, expected in ((90.0, 50, [1]), (90.0, 200, []), (110.0, 50, [])):
            with self.subTest(prior_price=prior_price, span=span):
                bars = pd.DataFrame(
                    dict(
                        open=prior_price,
                        high=prior_price + 1,
                        low=prior_price - 1,
                        close=prior_price,
                    ),
                    index=pd.date_range(START, periods=61, freq="15min"),
                )
                bars.iloc[48:60] = [100.0, 101.0, 99.0, 100.0]
                bars.iloc[60] = [100.0, 103.0, 99.0, 102.0]
                prepared = candidate_frame(
                    features(bars),
                    "off",
                    0.0,
                    signal_spec=dict(buy_lookback=12, sell_lookback=12, trend_span=span),
                )
                entry_time = START + pd.Timedelta(minutes=61 * 15)
                ticks = (
                    np.array([entry_time.value // 10**6]),
                    np.array([102.0]),
                    np.array([102.2]),
                )
                result = replay(
                    prepared,
                    ticks,
                    BROKER,
                    Rules(),
                    Costs(),
                    start=START,
                    end=entry_time + pd.Timedelta(minutes=1),
                )
                self.assertEqual([p["direction"] for p in result["ledger"]], expected)

    def test_compression_uses_prior_range_and_prior_atr_at_exact_boundary(self):
        import numpy as np
        import pandas as pd

        frame = pd.DataFrame(
            dict(
                open=100.0,
                high=105.0,
                low=95.0,
                close=100.0,
                hh=105.0,
                ll=95.0,
                atr=1.0,
                direction=0,
            ),
            index=pd.date_range(START, periods=18, freq="15min"),
        )
        frame.iloc[14, frame.columns.get_indexer(["high", "low", "close"])] = [107, 104, 106]
        frame.iloc[16, frame.columns.get_indexer(["high", "low", "close"])] = [96, 93, 94]
        times = START.value // 10**6 + np.array([13500000, 13560000, 15300000, 15360000])
        bid = np.array([106.0, 110.0, 94.0, 90.0])
        for maximum, expected in ((6.0, []), (9.0, []), (12.0, [1, -1])):
            with self.subTest(maximum=maximum):
                spec = dict(buy_lookback=12, sell_lookback=12, trend_span=0, max_range_atr=maximum)
                prepared = candidate_frame(frame, "off", 0.0, signal_spec=spec)
                cut = candidate_frame(frame.iloc[:15], "off", 0.0, signal_spec=spec)
                pd.testing.assert_frame_equal(prepared.iloc[:15], cut)
                result = replay(
                    prepared,
                    (times, bid, bid + 0.2),
                    BROKER,
                    Rules(),
                    Costs(),
                    start=START,
                    end=START + pd.Timedelta(hours=5),
                )
                self.assertEqual([p["direction"] for p in result["ledger"]], expected)
                # Inflating current ATR cannot turn a rejected signal into admission.
                changed = frame.copy()
                changed.loc[changed.index[14], "atr"] = 100.0
                self.assertEqual(
                    candidate_frame(changed, "off", 0.0, signal_spec=spec).direction.iloc[14],
                    prepared.direction.iloc[14],
                )

    def test_rsi_recross_executes_both_sides_after_warmup_without_future_data(self):
        import numpy as np
        import pandas as pd

        prices = np.array(list(range(100, 85, -1)) + list(range(92, 107)) + [100], dtype=float)
        frame = pd.DataFrame(
            dict(
                open=prices,
                high=prices + 0.1,
                low=prices - 0.1,
                close=prices,
                hh=120.0,
                ll=70.0,
                atr=1.0,
                direction=0,
            ),
            index=pd.date_range(START, periods=len(prices), freq="15min"),
        )
        spec = dict(period=14, threshold=30, trend_span=0)
        prepared = candidate_frame(frame, "off", 0.0, oscillator_spec=spec)
        self.assertEqual(list(np.flatnonzero(prepared.direction)), [15, 30])
        self.assertEqual(prepared.direction.iloc[[15, 30]].tolist(), [1, -1])
        pd.testing.assert_frame_equal(
            prepared.iloc[:16], candidate_frame(frame.iloc[:16], "off", 0.0, oscillator_spec=spec)
        )
        times = START.value // 10**6 + np.array([14400000, 14460000, 27900000, 27960000])
        bid = np.array([92.0, 100.0, 100.0, 92.0])
        result = replay(
            prepared,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=START + pd.Timedelta(hours=8),
        )
        self.assertEqual([p["direction"] for p in result["ledger"]], [1, -1])
        self.assertEqual([p["volume"] for p in result["ledger"]], [0.01, 0.01])
        self.assertTrue(all(p["risk_pct"] <= 10 for p in result["ledger"]))

    def test_rsi_expiring_losses_without_price_reversal_cannot_open_trade(self):
        import numpy as np
        import pandas as pd

        prices = np.array(list(range(100, 85, -1)) + [86] * 16, dtype=float)
        frame = pd.DataFrame(
            dict(
                open=prices,
                high=prices + 0.1,
                low=prices - 0.1,
                close=prices,
                hh=120.0,
                ll=70.0,
                atr=1.0,
                direction=0,
            ),
            index=pd.date_range(START, periods=len(prices), freq="15min"),
        )
        prepared = candidate_frame(
            frame, "off", 0.0, oscillator_spec=dict(period=14, threshold=30, trend_span=0)
        )
        times = (frame.index.as_unit("ns").view("int64") // 1000000) + 900000
        ticks = (times, prices, prices + 0.2)
        result = replay(
            prepared,
            ticks,
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=START + pd.Timedelta(hours=8),
        )
        self.assertEqual(result["trades"], 0)

    def test_hybrid_rsi_buy_preserves_parent_sell_and_parent_wins_conflict(self):
        import numpy as np
        import pandas as pd

        prices = np.array(list(range(100, 85, -1)) + list(range(92, 107)) + [100], dtype=float)
        frame = pd.DataFrame(
            dict(
                open=prices,
                high=prices + 0.1,
                low=prices - 0.1,
                close=prices,
                hh=120.0,
                ll=70.0,
                atr=1.0,
                direction=0,
            ),
            index=pd.date_range(START, periods=len(prices), freq="15min"),
        )
        frame.loc[frame.index[16], "direction"] = -1
        spec = dict(period=14, threshold=30, trend_span=0, side="buy")
        prepared = candidate_frame(frame, "off", 0.0, oscillator_spec=spec)
        self.assertEqual(list(np.flatnonzero(prepared.direction)), [15, 16])
        self.assertEqual(prepared.direction.iloc[[15, 16]].tolist(), [1, -1])
        self.assertEqual(prepared.ll.iloc[16], 70.0)
        self.assertEqual(prepared.hh.iloc[15], 92.0)
        times = START.value // 10**6 + np.array([14400000, 14460000, 15300000, 15360000])
        bid = np.array([92.0, 100.0, 100.0, 92.0])
        result = replay(
            prepared,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=START + pd.Timedelta(hours=8),
        )
        self.assertEqual([p["direction"] for p in result["ledger"]], [1, -1])
        frame.loc[frame.index[15], "direction"] = -1
        conflict = candidate_frame(frame, "off", 0.0, oscillator_spec=spec)
        self.assertEqual(conflict.direction.iloc[15], -1)
        self.assertEqual(conflict.ll.iloc[15], 70.0)

        frame.loc[frame.index[15], "direction"] = 0
        mirrored = frame.copy()
        for key, inverse in (
            ("open", "open"),
            ("close", "close"),
            ("high", "low"),
            ("low", "high"),
            ("hh", "ll"),
            ("ll", "hh"),
        ):
            mirrored[key] = 200.0 - frame[inverse]
        mirrored["direction"] = -frame.direction
        spec["side"] = "sell"
        prepared = candidate_frame(mirrored, "off", 0.0, oscillator_spec=spec)
        self.assertEqual(prepared.direction.iloc[[15, 16]].tolist(), [-1, 1])
        self.assertEqual(prepared.hh.iloc[16], 130.0)
        result = replay(
            prepared,
            (times, 200.0 - bid, 200.2 - bid),
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=START + pd.Timedelta(hours=8),
        )
        self.assertEqual([p["direction"] for p in result["ledger"]], [-1, 1])

    def test_daily_loss_count_blocks_both_sides_and_resets_at_utc_midnight(self):
        import numpy as np
        import pandas as pd

        frame, _ = sample()
        frame = pd.concat([frame, frame.iloc[:2]]).copy()
        frame.index = pd.DatetimeIndex(
            [
                START,
                START + pd.Timedelta(minutes=15),
                START + pd.Timedelta(minutes=30),
                START + pd.Timedelta(days=1),
                START + pd.Timedelta(days=1, minutes=15),
            ]
        )
        frame["direction"] = [1, -1, 1, 1, -1]
        closes = frame.index.as_unit("ms").asi8 + 900000
        times = np.column_stack([closes, closes + 60000]).ravel()
        bid = np.array([100.0, 97.0, 100.0, 103.0, 100.0, 97.0, 100.0, 97.0, 100.0, 103.0])
        for losses, expected in ((1, [1, 1]), (2, [1, -1, 1, -1])):
            with self.subTest(losses=losses):
                result = replay(
                    frame,
                    (times, bid, bid + 0.2),
                    BROKER,
                    Rules(max_daily_losses=losses),
                    Costs(),
                    start=START,
                    end=START + pd.Timedelta(days=1, hours=1),
                )
                self.assertEqual([t["direction"] for t in result["ledger"]], expected)
                self.assertEqual(result["rejections"]["daily_loss_count"], 5 - len(expected))
                self.assertEqual(result["ledger"][-1]["entry_time_utc"][:10], "2026-04-02")

    def test_parent_sell_trend_filters_countertrend_without_blocking_bearish_entry(self):
        import numpy as np
        import pandas as pd
        from scripts.research.breakout_logic import features

        for initial_price, expected in ((50.0, 0), (150.0, 1)):
            with self.subTest(initial_price=initial_price):
                prices = np.array([initial_price] * 30 + [100.0] * 24 + [98.0])
                bars = pd.DataFrame(
                    dict(open=prices, high=prices + 1, low=prices - 1, close=prices),
                    index=pd.date_range(START, periods=55, freq="15min"),
                )
                prepared = candidate_frame(
                    features(bars),
                    "off",
                    0.0,
                    oscillator_spec=dict(
                        period=7,
                        threshold=30,
                        trend_span=50,
                        side="buy",
                        parent_lookback=24,
                        parent_trend_span=50,
                    ),
                )
                times = START.value // 10**6 + np.array([49500000, 49560000])
                bid = np.array([98.0, 90.0])
                result = replay(
                    prepared,
                    (times, bid, bid + 0.2),
                    BROKER,
                    Rules(),
                    Costs(),
                    start=START,
                    end=START + pd.Timedelta(hours=14),
                )
                self.assertEqual(result["trades"], expected)
                if expected:
                    self.assertEqual(result["ledger"][0]["direction"], -1)
                    self.assertEqual(result["ledger"][0]["boundary"], 99.0)
                    self.assertEqual(result["ledger"][0]["volume"], 0.01)

    def test_rsi_buy_executes_before_parent_ema200_and_horizon_warmup(self):
        import numpy as np
        import pandas as pd
        from scripts.research.breakout_logic import features

        prices = np.array(list(range(50, 131)) + list(range(129, 115, -1)) + [122.0])
        bars = pd.DataFrame(
            dict(open=prices, high=prices + 0.1, low=prices - 0.1, close=prices),
            index=pd.date_range(START, periods=96, freq="15min"),
        )
        prepared = candidate_frame(
            features(bars),
            "off",
            0.0,
            oscillator_spec=dict(
                period=14,
                threshold=30,
                trend_span=50,
                side="buy",
                parent_lookback=96,
                parent_trend_span=200,
            ),
        )
        times = START.value // 10**6 + np.array([86400000, 86460000])
        bid = np.array([122.0, 135.0])
        result = replay(
            prepared,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=START + pd.Timedelta(days=1, minutes=2),
        )
        self.assertEqual(result["trades"], 1)
        trade = result["ledger"][0]
        self.assertEqual(trade["direction"], 1)
        self.assertEqual(trade["entry_time_utc"], "2026-04-02T00:00:00+00:00")
        self.assertEqual(trade["volume"], 0.01)
        self.assertLessEqual(result["max_admitted_risk_pct"], 10.0)

    def test_parent_sell_24_executes_after_24_natural_bars_before_48(self):
        import numpy as np
        import pandas as pd
        from scripts.research.breakout_logic import features

        bars = pd.DataFrame(
            dict(
                open=[100.0] * 24 + [99.0],
                high=[101.0] * 24 + [100.0],
                low=[99.0] * 24 + [97.0],
                close=[100.0] * 24 + [98.0],
            ),
            index=pd.date_range(START, periods=25, freq="15min"),
        )
        prepared = candidate_frame(
            features(bars),
            "off",
            0.0,
            oscillator_spec=dict(
                period=7, threshold=30, trend_span=50, side="buy", parent_lookback=24
            ),
        )
        times = START.value // 10**6 + np.array([22500000, 22560000])
        bid = np.array([98.0, 90.0])
        result = replay(
            prepared,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=START + pd.Timedelta(hours=7),
        )
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["ledger"][0]["direction"], -1)
        self.assertEqual(result["ledger"][0]["boundary"], 99.0)
        self.assertEqual(result["ledger"][0]["entry_time_utc"], "2026-04-01T06:15:00+00:00")
        self.assertEqual(result["ledger"][0]["volume"], 0.01)
        self.assertEqual(result["rejections"]["risk_cap"], 0)

    def test_rsi_buy_with_parent_horizon_uses_prior_lows_and_defers_sell(self):
        import numpy as np
        import pandas as pd

        frame = pd.DataFrame(
            dict(
                open=[100.0] * 96 + [85.0, 79.0],
                high=110.0,
                low=[80.0] * 48 + [90.0] * 48 + [84.0, 78.0],
                close=[100.0] * 96 + [85.0, 79.0],
                hh=110.0,
                ll=90.0,
                atr=1.0,
                direction=[0] * 96 + [-1, -1],
            ),
            index=pd.date_range(START, periods=98, freq="15min"),
        )
        closes = frame.index[-2:].as_unit("ms").asi8 + 900000
        times = np.column_stack([closes, closes + 60000]).ravel()
        bid = np.array([85.0, 80.0, 79.0, 74.0])
        for lookback, expected_entries in ((48, [85.0, 79.0]), (96, [79.0])):
            with self.subTest(lookback=lookback):
                prepared = candidate_frame(
                    frame,
                    "off",
                    0.0,
                    oscillator_spec=dict(
                        period=7, threshold=30, trend_span=0, side="buy", parent_lookback=lookback
                    ),
                )
                result = replay(
                    prepared,
                    (times, bid, bid + 0.2),
                    BROKER,
                    Rules(),
                    Costs(),
                    start=START,
                    end=START + pd.Timedelta(hours=25),
                )
                self.assertEqual([t["entry"] for t in result["ledger"]], expected_entries)
                self.assertTrue(all(t["direction"] == -1 for t in result["ledger"]))
                # Current low84 would change D48 boundary if included prematurely.
                self.assertEqual(result["ledger"][0]["boundary"], 90.0 if lookback == 48 else 80.0)
                self.assertTrue(
                    all(t["volume"] == 0.01 and t["risk_pct"] <= 10 for t in result["ledger"])
                )

    def test_existing_positional_rules_keep_default_atr_stop_and_target(self):
        # Existing 18 constructor arguments retain their original meanings.
        rules = Rules(
            0,
            False,
            0,
            "immediate",
            "atr",
            "off",
            "off",
            0.0,
            "static",
            0.10,
            0.40,
            3.0,
            0.0,
            1.5,
            0,
            "all",
            0,
            0.5,
        )
        frame, ticks = sample()
        result = replay(frame, ticks, BROKER, rules, Costs(), start=START, end=END)
        self.assertEqual(result["trades"], 1)
        self.assertAlmostEqual(result["ledger"][0]["initial_stop"], 97.7)
        self.assertAlmostEqual(result["ledger"][0]["target"], 103.95)
        self.assertEqual(result["ledger"][0]["volume"], 0.01)

    def test_configured_atr_stop_changes_both_orders_without_resizing_lot(self):
        import numpy as np

        for stop_atr, buy_stop, buy_target, sell_stop, sell_target in (
            (1.5, 98.7, 102.225, 101.5, 97.975),
            (2.0, 98.2, 102.9, 102.0, 97.3),
            (2.5, 97.7, 103.575, 102.5, 96.625),
        ):
            with self.subTest(stop_atr=stop_atr):
                frame, _ = sample()
                frame.loc[frame.index[1], "direction"] = -1
                times = START.value // 10**6 + np.array([900000, 960000, 1800000, 1860000])
                bid = np.array([100.0, 110.0, 100.0, 90.0])
                result = replay(
                    frame,
                    (times, bid, bid + 0.2),
                    BROKER,
                    Rules(stop_atr=stop_atr, target_rr=1.35),
                    Costs(),
                    start=START,
                    end=END,
                )
                self.assertEqual([t["direction"] for t in result["ledger"]], [1, -1])
                self.assertAlmostEqual(result["ledger"][0]["initial_stop"], buy_stop)
                self.assertAlmostEqual(result["ledger"][0]["target"], buy_target)
                self.assertAlmostEqual(result["ledger"][1]["initial_stop"], sell_stop)
                self.assertAlmostEqual(result["ledger"][1]["target"], sell_target)
                self.assertTrue(
                    all(t["volume"] == 0.01 and t["risk_pct"] <= 10 for t in result["ledger"])
                )

    def test_tighter_atr_config_still_rejects_over_cap_without_lot_clamping(self):
        frame, ticks = sample()
        frame["atr"] = 9.0
        old = replay(frame, ticks, BROKER, Rules(), Costs(), start=START, end=END)
        tight = replay(frame, ticks, BROKER, Rules(stop_atr=1.5), Costs(), start=START, end=END)
        self.assertEqual(old["trades"], 0)
        self.assertEqual(old["rejections"]["risk_cap"], 1)
        self.assertEqual(tight["ledger"][0]["volume"], 0.01)
        self.assertAlmostEqual(tight["ledger"][0]["risk_usd"], 13.5)
        frame["atr"] = 15.0
        rejected = replay(frame, ticks, BROKER, Rules(stop_atr=1.5), Costs(), start=START, end=END)
        self.assertEqual(rejected["trades"], 0)
        self.assertEqual(rejected["rejections"]["risk_cap"], 1)
        self.assertEqual(rejected["final_balance"], 200.0)

    def test_intermediate_reward_uses_rounded_stop_for_both_directions(self):
        import numpy as np

        for reward, expected_buy, expected_sell in (
            (1.25, 103.325, 96.875),
            (1.35, 103.575, 96.625),
            (1.40, 103.7, 96.5),
            (1.45, 103.825, 96.375),
        ):
            with self.subTest(reward=reward):
                frame, _ = sample()
                frame.loc[frame.index[1], "direction"] = -1
                times = START.value // 10**6 + np.array([900000, 960000, 1800000, 1860000])
                bid = np.array([100.0, 110.0, 100.0, 90.0])
                result = replay(
                    frame,
                    (times, bid, bid + 0.2),
                    BROKER,
                    Rules(target_rr=reward),
                    Costs(),
                    start=START,
                    end=END,
                )
                self.assertEqual([t["direction"] for t in result["ledger"]], [1, -1])
                self.assertAlmostEqual(result["ledger"][0]["target"], expected_buy)
                self.assertAlmostEqual(result["ledger"][1]["target"], expected_sell)
                self.assertTrue(
                    all(t["volume"] == 0.01 and t["risk_pct"] <= 10 for t in result["ledger"])
                )

    def test_rollover_filter_blocks_utc_21_entry_and_keeps_next_day_sell(self):
        import numpy as np
        import pandas as pd

        prices = np.array(list(range(100, 85, -1)) + list(range(92, 107)) + [100], dtype=float)
        frame = pd.DataFrame(
            dict(
                open=prices,
                high=prices + 0.1,
                low=prices - 0.1,
                close=prices,
                hh=120.0,
                ll=70.0,
                atr=1.0,
                direction=0,
            ),
            index=pd.date_range(START + pd.Timedelta(hours=17), periods=len(prices), freq="15min"),
        )
        ticks_ms = START.value // 10**6 + np.array([75600000, 75660000, 89100000, 89160000])
        bid = np.array([92.0, 100.0, 100.0, 92.0])
        for session, expected in (("all", [1, -1]), ("avoid_rollover", [-1])):
            with self.subTest(session=session):
                prepared = candidate_frame(
                    frame,
                    "off",
                    0.0,
                    oscillator_spec=dict(period=14, threshold=30, trend_span=0),
                    entry_session=session,
                )
                result = replay(
                    prepared,
                    (ticks_ms, bid, bid + 0.2),
                    BROKER,
                    Rules(),
                    Costs(),
                    start=START,
                    end=START + pd.Timedelta(hours=26),
                )
                self.assertEqual([p["direction"] for p in result["ledger"]], expected)
                self.assertTrue(all(p["volume"] == 0.01 for p in result["ledger"]))

        # Already-open trades still consume blocked-session quotes and broker TP.
        frame.index = frame.index - pd.Timedelta(minutes=15)
        ticks_ms = START.value // 10**6 + np.array([74700000, 75660000, 88200000, 88260000])
        prepared = candidate_frame(
            frame,
            "off",
            0.0,
            oscillator_spec=dict(period=14, threshold=30, trend_span=0),
            entry_session="avoid_rollover",
        )
        result = replay(
            prepared,
            (ticks_ms, bid, bid + 0.2),
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=START + pd.Timedelta(hours=26),
        )
        self.assertEqual([p["direction"] for p in result["ledger"]], [1, -1])
        self.assertEqual(result["ledger"][0]["exit_time_utc"], "2026-04-01T21:01:00+00:00")

    def test_geometry_targets_use_frozen_stop_distance_with_fixed_lot(self):
        for stop_mode, stop, target in (
            ("atr", 97.7, 103.95),
            ("trigger", 98.999, 102.001),
            ("boundary", 99.5, 101.25),
        ):
            with self.subTest(stop_mode=stop_mode):
                frame, ticks = sample()
                result = replay(
                    candidate_frame(frame, "off", 0.0),
                    ticks,
                    BROKER,
                    Rules(stop_mode=stop_mode, target_rr=1.5),
                    Costs(),
                    start=START,
                    end=END,
                )
                trade = result["ledger"][0]
                self.assertAlmostEqual(trade["initial_stop"], stop)
                self.assertAlmostEqual(trade["target"], target)
                self.assertEqual(trade["volume"], 0.01)
                self.assertLessEqual(trade["risk_pct"], 10)

    def test_tuning_cli_freezes_catalog_budget_and_verifies_resumed_scenarios(self):
        import contextlib
        import io
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from scripts.research.bidirectional_campaign import main

        frame, ticks = sample()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "scripts.research.bidirectional_campaign.load_data",
                return_value=(frame, ticks, BROKER, {"synthetic": True}),
            ),
            patch("scripts.research.bidirectional_campaign.START", START),
            patch("scripts.research.bidirectional_campaign.TRAIN_END", START + (END - START) / 2),
            patch("scripts.research.bidirectional_campaign.END", END),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            for catalog, budget in (
                ("tuning", 288),
                ("admission", 96),
                ("horizons", 384),
                ("horizon_quality", 128),
                ("compression", 216),
                ("oscillator", 72),
                ("hybrid_oscillator", 144),
                ("hybrid_admission", 108),
                ("hybrid_invalidation", 108),
                ("hybrid_reward", 594),
                ("hybrid_reward_session", 108),
                ("hybrid_reward_admission", 324),
                ("hybrid_reward_quality", 108),
                ("hybrid_reward_geometry", 216),
                ("hybrid_atr_stop", 432),
                ("hybrid_parent_horizon", 192),
                ("hybrid_parent_trend", 288),
                ("hybrid_parent_quality", 24),
                ("hybrid_parent_reward_fine", 48),
                ("hybrid_parent_reward_pause", 12),
                ("hybrid_parent_risk", 36),
                ("hybrid_parent_atr", 72),
                ("hybrid_parent_protection", 144),
                ("hybrid_parent_invalidation", 36),
            ):
                with self.subTest(catalog=catalog):
                    output = Path(directory) / catalog
                    args = ["--output", str(output), "--catalog", catalog, "--limit", "1"]
                    initial = main(args)
                    self.assertEqual(initial["verification"], "INITIAL_REPLAY")
                    resumed = main(args + ["--resume"])
                    self.assertEqual(resumed["verified_scenarios"], 12)
                    self.assertEqual(resumed["verification"], "FRESH_REPLAY_MATCH")
                    self.assertEqual(resumed["total_contracts"], budget)
                    self.assertEqual(resumed["status"], "DISCOVERY_INCOMPLETE")
                    protocol = json.loads((output / "protocol.json").read_text())
                    self.assertEqual(len(protocol["candidates"]), budget)
                    self.assertEqual(
                        len({json.dumps(c, sort_keys=True) for c in protocol["candidates"]}), budget
                    )

    def test_symmetric_close_extreme_guard_accepts_both_edges_and_rejects_inside(self):
        import numpy as np

        for buy_close, sell_close, expected in (
            (100.5, 99.25, [1, -1]),
            (100.49, 99.25, [-1]),
            (100.5, 99.26, [1]),
        ):
            with self.subTest(buy_close=buy_close, sell_close=sell_close):
                frame, _ = sample()
                frame.loc[frame.index[0], "close"] = buy_close
                frame.loc[frame.index[1], ["direction", "close"]] = [-1, sell_close]
                times = START.value // 10**6 + np.array([900000, 960000, 1800000, 1860000, 2700000])
                bid = np.array([100.0, 104.0, 100.0, 96.0, 96.0])
                result = replay(
                    candidate_frame(frame, "off", 0.0),
                    (times, bid, bid + 0.2),
                    BROKER,
                    Rules(entry_guard="close_extreme"),
                    Costs(),
                    start=START,
                    end=END,
                )
                self.assertEqual([p["direction"] for p in result["ledger"]], expected)
                self.assertTrue(all(p["volume"] == 0.01 for p in result["ledger"]))

    def test_trend_pullback_buy_reaches_replay_after_ema_warmup(self):
        import numpy as np
        import pandas as pd

        prices = 100 + np.arange(60) * 0.1
        frame = pd.DataFrame(
            dict(
                open=prices,
                high=prices + 0.2,
                low=prices - 0.2,
                close=prices + 0.1,
                hh=120.0,
                ll=90.0,
                atr=1.0,
                direction=0,
            ),
            index=pd.date_range(START, periods=60, freq="15min"),
        )
        frame.loc[frame.index[-2], ["open", "high", "low", "close"]] = [106, 106.1, 105.5, 105.8]
        frame.loc[frame.index[-1], ["open", "high", "low", "close"]] = [106, 106.4, 105.8, 106.2]
        prepared = candidate_frame(frame, "off", 0.0, "trend_pullback")
        self.assertEqual(prepared.direction.iloc[-1], 1)
        self.assertEqual(prepared.hh.iloc[-1], 106.1)
        entry_time = START + pd.Timedelta(hours=15)
        ticks = (np.array([entry_time.value // 10**6]), np.array([106.2]), np.array([106.4]))
        result = replay(
            prepared,
            ticks,
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=entry_time + pd.Timedelta(minutes=1),
        )
        self.assertEqual([p["direction"] for p in result["ledger"]], [1])
        self.assertEqual(result["ledger"][0]["volume"], 0.01)

    def test_lower_wick_buy_setup_and_sell_breakout_both_reach_replay(self):
        import numpy as np

        frame, _ = sample()
        frame.loc[frame.index[0], ["low", "ll", "direction"]] = [94.0, 95.0, 0]
        frame.loc[frame.index[0], "hh"] = 110.0
        frame.loc[frame.index[1], "direction"] = -1
        prepared = candidate_frame(frame, "off", 0.0, "lower_wick")
        self.assertEqual(prepared.direction.tolist(), [1, -1, 0])
        times = START.value // 10**6 + np.array([900000, 960000, 1800000, 1860000, 2700000])
        bid = np.array([100.0, 104.0, 100.0, 96.0, 96.0])
        result = replay(
            prepared, (times, bid, bid + 0.2), BROKER, Rules(), Costs(), start=START, end=END
        )
        self.assertEqual([p["direction"] for p in result["ledger"]], [1, -1])
        self.assertEqual([p["volume"] for p in result["ledger"]], [0.01, 0.01])

    def test_unfiltered_candidate_replay_executes_buy_and_sell_with_fixed_lot(self):
        import numpy as np

        frame, _ = sample()
        frame.loc[frame.index[1], "direction"] = -1
        times = START.value // 10**6 + np.array([900000, 960000, 1800000, 1860000, 2700000])
        bid = np.array([100.0, 104.0, 100.0, 96.0, 96.0])
        result = replay(
            candidate_frame(frame, "off", 0.0),
            (times, bid, bid + 0.2),
            BROKER,
            Rules(),
            Costs(),
            start=START,
            end=END,
        )
        self.assertEqual([p["direction"] for p in result["ledger"]], [1, -1])
        self.assertEqual([p["volume"] for p in result["ledger"]], [0.01, 0.01])
        self.assertAlmostEqual(result["net_usd"], 6.0)

    def test_prior_day_filter_uses_completed_day_at_midnight_close(self):
        import pandas as pd

        frame, _ = sample()
        frame.index = pd.date_range(START - pd.Timedelta(minutes=30), periods=3, freq="15min")
        frame["direction"] = [0, 1, 1]
        frame["close"] = [100.5, 101.0, 99.0]
        filtered = candidate_frame(frame, "prior_day", 0.0)
        self.assertEqual(filtered.direction.tolist(), [0, 1, 1])
        changed = frame.copy()
        changed.loc[changed.index[-1], "close"] = 10000
        self.assertEqual(candidate_frame(changed, "prior_day", 0.0).direction.tolist(), [0, 1, 1])

    def test_campaign_resume_rejects_changed_artifact_and_never_opens_broker(self):
        import contextlib
        import io
        import json
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from scripts.research.bidirectional_campaign import main

        frame, ticks = sample()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "campaign"
            args = ["--output", str(output), "--limit", "1"]
            with (
                patch(
                    "scripts.research.bidirectional_campaign.load_data",
                    return_value=(frame, ticks, BROKER, {"synthetic": True}),
                ),
                patch("scripts.research.bidirectional_campaign.START", START),
                patch(
                    "scripts.research.bidirectional_campaign.TRAIN_END", START + (END - START) / 2
                ),
                patch("scripts.research.bidirectional_campaign.END", END),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                main(args)
                marker = output / "trial-001" / "result.json"
                first = marker.read_bytes()
                main(args + ["--resume"])
                self.assertEqual(marker.read_bytes(), first)
                verdict = json.loads((output / "verdict.json").read_text())
                self.assertEqual(verdict["completed_trials"], 1)
                self.assertEqual(verdict["deployment"], "UNCHANGED")
                with patch(
                    "scripts.research.bidirectional_campaign.qualifies_trial30", return_value=True
                ):
                    partial = main(args + ["--resume"])
                self.assertEqual(partial["status"], "DISCOVERY_INCOMPLETE")
                self.assertIsNone(partial["frozen_discovery_winner"])
                artifact = output / "trial-001" / "full-base.json"
                data = json.loads(artifact.read_text())
                data["net_usd"] = 999
                artifact.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, "artifact"):
                    main(args + ["--resume"])
                # A forged metric with matching hash/marker must still fail fresh replay.
                import hashlib

                completion = json.loads(marker.read_text())
                completion["artifact_hashes"]["full-base.json"] = hashlib.sha256(
                    artifact.read_bytes()
                ).hexdigest()
                completion["metrics"]["full"][0]["net_usd"] = 999
                marker.write_text(json.dumps(completion))
                with self.assertRaisesRegex(ValueError, "replay"):
                    main(args + ["--resume"])

    def test_buy_filter_keeps_sell_executable_and_future_bar_cannot_change_prefix(self):
        import pandas as pd

        frame, ticks = sample()
        frame.loc[frame.index[0], "direction"] = -1
        frame.loc[frame.index[1], "direction"] = 1
        filtered = candidate_frame(frame, "ema50", 0.0)
        self.assertEqual(filtered.direction.tolist(), [-1, 0, 0])
        result = replay(filtered, ticks, BROKER, Rules(), Costs(), start=START, end=END)
        self.assertEqual(result["ledger"][0]["direction"], -1)
        changed = frame.copy()
        changed.loc[changed.index[-1], "close"] = 10000
        pd.testing.assert_frame_equal(
            candidate_frame(changed, "ema50", 0.0).iloc[:2], filtered.iloc[:2]
        )

    def test_both_sides_and_each_cost_scenario_must_improve_trial30(self):
        baseline = dict(net_usd=100, win_rate=0.5, realized_rr=1.2, max_dd_pct=26)
        candidate = dict(
            net_usd=110,
            win_rate=0.6,
            realized_rr=1.3,
            max_dd_pct=25,
            max_admitted_risk_pct=10,
            trades=60,
            buy_trades=20,
            sell_trades=40,
        )
        self.assertTrue(qualifies_trial30([candidate, candidate], [baseline, baseline], 60))
        for changed in (
            dict(buy_trades=0),
            dict(sell_trades=0),
            dict(net_usd=100),
            dict(win_rate=0.5),
            dict(realized_rr=1.2),
            dict(max_dd_pct=26.01),
            dict(max_admitted_risk_pct=10.01),
            dict(trades=59),
            dict(net_usd=float("nan")),
        ):
            with self.subTest(changed=changed):
                self.assertFalse(
                    qualifies_trial30(
                        [candidate, dict(candidate, **changed)], [baseline, baseline], 60
                    )
                )


if __name__ == "__main__":
    unittest.main()
