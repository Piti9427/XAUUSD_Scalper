"""Agreed public candidate-selection and replay seams."""

import unittest

from scripts.research.strategy_campaign import qualifies


class CampaignSelectionTests(unittest.TestCase):
    def test_strict_rr_rejects_below_defined_parent_and_allows_undefined_core(self):
        parent = dict(
            trades=70,
            net_usd=50,
            max_dd_pct=25,
            realized_rr=2.5,
            win_rate=0.4,
            max_admitted_risk_pct=10,
        )
        candidate = dict(parent, net_usd=60, max_dd_pct=15, realized_rr=1.1, win_rate=0.5)
        undefined = dict(parent, realized_rr=None)
        self.assertFalse(
            qualifies(
                candidate,
                candidate,
                [(parent, parent), (undefined, undefined)],
                min_trades=60,
                require_rr_improvement=True,
            )
        )
        candidate["realized_rr"] = 2.6
        self.assertTrue(
            qualifies(
                candidate,
                candidate,
                [(parent, parent), (undefined, undefined)],
                min_trades=60,
                require_rr_improvement=True,
            )
        )

    def test_rr_floor_does_not_require_beating_baseline_rr(self):
        baseline = dict(
            trades=70,
            net_usd=50,
            max_dd_pct=25,
            realized_rr=2.5,
            win_rate=0.4,
            max_admitted_risk_pct=10,
        )
        candidate = dict(baseline, net_usd=60, max_dd_pct=15, realized_rr=1.1, win_rate=0.5)
        self.assertTrue(qualifies(candidate, candidate, [(baseline, baseline)] * 2, min_trades=60))
        for key, value in [
            ("max_dd_pct", 20.01),
            ("win_rate", 0.4),
            ("realized_rr", None),
            ("trades", 59),
            ("net_usd", 50),
        ]:
            with self.subTest(key=key):
                bad = dict(candidate, **{key: value})
                self.assertFalse(
                    qualifies(candidate, bad, [(baseline, baseline)] * 2, min_trades=60)
                )


class CampaignReplayTests(unittest.TestCase):
    def test_lower_cap_rejects_fixed_lot_including_exit_cost(self):
        from tests.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs

        frame, ticks = sample()
        frame["atr"] = 2.0
        result = replay(
            frame, ticks, BROKER, Rules(risk_cap=0.025), Costs(slippage=0.1), start=START, end=END
        )
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["rejections"]["risk_cap"], 1)

    def test_failed_breakout_reverses_only_after_close_back_inside(self):
        from tests.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs

        frame, ticks = sample()
        result = replay(
            frame, ticks, BROKER, Rules(entry_mode="failed_reverse"), Costs(), start=START, end=END
        )
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["ledger"][0]["direction"], -1)
        self.assertEqual(result["ledger"][0]["entry_time_utc"], "2026-04-01T00:30:00+00:00")
        self.assertAlmostEqual(result["ledger"][0]["entry"], 99.6)

    def test_parent_target_changes_exit_distance_without_changing_fixed_lot(self):
        from tests.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs

        frame, ticks = sample()
        result = replay(frame, ticks, BROKER, Rules(target_atr=6.25), Costs(), start=START, end=END)
        self.assertAlmostEqual(result["ledger"][0]["target"], 106.45)
        self.assertEqual(result["ledger"][0]["volume"], 0.01)


class UnseenEvidenceTests(unittest.TestCase):
    def test_empty_months_and_reused_validation_cannot_qualify_demo(self):
        from scripts.research.strategy_campaign import validation_readiness

        self.assertFalse(
            validation_readiness(
                first_tick="2026-03-28T00:00:00Z",
                last_tick="2026-09-28T00:00:00Z",
                nonempty_months=6,
                unseen_start="2026-06-28T00:00:00Z",
                unseen_end="2026-09-28T00:00:00Z",
                discovery_end="2026-09-28T00:00:00Z",
                unseen_trades=30,
            )
        )


class CampaignRiskTests(unittest.TestCase):
    def test_five_percent_daily_limit_blocks_second_entry_after_gap_loss(self):
        import numpy as np
        from tests.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs

        frame, _ = sample()
        frame["direction"] = [1, 1, 0]
        frame["atr"] = 5.0
        times = START.value // 10**6 + np.array([900000, 960000, 1800000, 2700000])
        bid = np.array([100.0, 87.0, 100.0, 100.0])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(daily_loss_limit=0.05),
            Costs(),
            start=START,
            end=END,
        )
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["rejections"]["daily_loss"], 1)
        self.assertAlmostEqual(result["final_balance"], 186.8)


class CampaignProtocolTests(unittest.TestCase):
    def test_selection_receives_384_unique_predeclared_configs(self):
        import json
        from dataclasses import asdict
        from scripts.research.run_strategy_campaign import candidates

        configs = [(p, json.dumps(asdict(r), sort_keys=True)) for p, _, r in candidates()]
        self.assertEqual(len(configs), 384)
        self.assertEqual(len(set(configs)), 384)


class StructuralCampaignTests(unittest.TestCase):
    def test_structural_campaign_has_unique_configs_and_fixed_parent_targets(self):
        from scripts.research.campaign_hypotheses import structure_candidates

        configs = structure_candidates()
        self.assertEqual(len(configs), 384)
        self.assertEqual(len({(p, r) for p, _, r in configs}), 384)
        for parent, _, rules in configs:
            self.assertEqual(rules.stop_mode, "structure")
            self.assertEqual(rules.target_atr, 6.25 if parent == "core" else 3.0)
            self.assertLessEqual(rules.risk_cap, 0.10)


class RiskDistanceTargetTests(unittest.TestCase):
    def test_target_rr_anchors_to_rounded_trigger_stop_without_lot_clamp(self):
        from tests.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs

        frame, ticks = sample()
        result = replay(
            frame,
            ticks,
            BROKER,
            Rules(stop_mode="trigger", target_rr=1.5),
            Costs(),
            start=START,
            end=END,
        )
        trade = result["ledger"][0]
        self.assertAlmostEqual(trade["initial_stop"], 98.999)
        self.assertAlmostEqual(trade["target"], 102.001)
        self.assertEqual(trade["volume"], 0.01)


class BoundaryStopTests(unittest.TestCase):
    def test_boundary_buffer_stop_is_behind_crossed_level(self):
        from tests.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs

        frame, ticks = sample()
        result = replay(
            frame,
            ticks,
            BROKER,
            Rules(stop_mode="boundary", target_rr=2.0),
            Costs(),
            start=START,
            end=END,
        )
        trade = result["ledger"][0]
        self.assertAlmostEqual(trade["initial_stop"], 99.5)
        self.assertAlmostEqual(trade["target"], 101.6)


class LossCooldownTests(unittest.TestCase):
    def test_loss_cooldown_blocks_fresh_signals_after_sl(self):
        import numpy as np
        from tests.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs

        frame, _ = sample()
        frame["direction"] = [1, 1, 1]
        times = START.value // 10**6 + np.array([900000, 960000, 1800000, 2700000])
        bid = np.array([100.0, 97.0, 100.0, 100.0])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(cooldown_bars=4),
            Costs(),
            start=START,
            end=END,
        )
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["rejections"]["cooldown"], 2)


class WickSweepTests(unittest.TestCase):
    def test_rejection_of_upper_range_trades_short_only_after_bar_close(self):
        import numpy as np
        import pandas as pd
        from tests.test_breakout_logic import BROKER, START
        from scripts.research.breakout_logic import replay, Rules, Costs
        from scripts.research.campaign_hypotheses import wick_sweep_features

        bars = pd.DataFrame(
            dict(
                open=[97.0] * 48 + [100.5],
                high=[100.0] * 48 + [101.0],
                low=[95.0] * 48 + [99.0],
                close=[97.0] * 48 + [99.5],
            ),
            index=pd.date_range(START, periods=49, freq="15min"),
        )
        frame = wick_sweep_features(bars)
        times = START.value // 10**6 + np.array([44100000, 45000000])
        result = replay(
            frame,
            (times, np.array([99.6, 99.6]), np.array([99.8, 99.8])),
            BROKER,
            Rules(stop_mode="structure", target_rr=1.5),
            Costs(),
            start=START,
            end=START + pd.Timedelta(hours=13),
        )
        self.assertEqual(result["trades"], 1)
        trade = result["ledger"][0]
        self.assertEqual(trade["direction"], -1)
        self.assertEqual(trade["entry_time_utc"], "2026-04-01T12:15:00+00:00")
        self.assertAlmostEqual(trade["initial_stop"], 101.001)


class TrendPullbackTests(unittest.TestCase):
    def test_bullish_reclaim_after_red_pullback_enters_only_after_close(self):
        import numpy as np
        import pandas as pd
        from tests.test_breakout_logic import BROKER, START
        from scripts.research.breakout_logic import replay, Rules, Costs
        from scripts.research.campaign_hypotheses import trend_pullback_features

        bars = pd.DataFrame(
            dict(
                open=[97.0] * 55 + [98.0, 97.0],
                high=[98.0] * 55 + [98.5, 100.0],
                low=[96.0] * 55 + [96.0, 96.5],
                close=[97.0] * 56 + [99.5],
            ),
            index=pd.date_range(START, periods=57, freq="15min"),
        )
        frame = trend_pullback_features(bars)
        times = START.value // 10**6 + np.array([51300000, 52200000])
        result = replay(
            frame,
            (times, np.array([99.6, 99.6]), np.array([99.8, 99.8])),
            BROKER,
            Rules(stop_mode="trigger", target_rr=1.5),
            Costs(),
            start=START,
            end=START + pd.Timedelta(hours=15),
        )
        self.assertEqual(result["trades"], 1)
        self.assertEqual(result["ledger"][0]["direction"], 1)
        self.assertEqual(result["ledger"][0]["entry_time_utc"], "2026-04-01T14:15:00+00:00")


class ProfitActivationTests(unittest.TestCase):
    def test_one_r_activation_does_not_move_stop_at_half_r(self):
        import numpy as np
        from tests.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs

        frame, _ = sample()
        times = START.value // 10**6 + np.array([900000, 1800000, 1860000, 2700000])
        bid = np.array([100.0, 101.7, 100.1, 100.1])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(protect_mode="break_even", protect_after_r=1.0),
            Costs(),
            start=START,
            end=END,
        )
        trade = result["ledger"][0]
        self.assertEqual(trade["stop_updates"], 0)
        self.assertAlmostEqual(trade["stop"], 97.7)
        self.assertEqual(trade["reason"], "END_OF_SAMPLE")


class DrawdownAdmissionTests(unittest.TestCase):
    def test_drawdown_steps_reject_high_risk_entry_after_two_losses(self):
        import numpy as np
        from tests.test_breakout_logic import sample, BROKER, START, END
        from scripts.research.breakout_logic import replay, Rules, Costs

        frame, _ = sample()
        frame["direction"] = [1, 1, 1]
        frame["atr"] = 5.0
        times = START.value // 10**6 + np.array(
            [900000, 960000, 1800000, 1860000, 2700000, 2760000]
        )
        bid = np.array([100.0, 87.7, 100.0, 87.7, 100.0, 87.7])
        result = replay(
            frame,
            (times, bid, bid + 0.2),
            BROKER,
            Rules(risk_mode="drawdown_steps"),
            Costs(),
            start=START,
            end=END,
        )
        self.assertEqual(result["trades"], 2)
        self.assertEqual(result["rejections"]["risk_cap"], 1)
        self.assertEqual([t["volume"] for t in result["ledger"]], [0.01, 0.01])
