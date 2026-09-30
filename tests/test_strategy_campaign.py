"""Agreed public candidate-selection and replay seams."""

import unittest

from scripts.research.strategy_campaign import qualifies


class CampaignSelectionTests(unittest.TestCase):
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
