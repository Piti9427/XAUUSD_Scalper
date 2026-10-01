"""Agreed replay -> qualification/resume seams; no broker access."""

import unittest

from scripts.research.bidirectional_campaign import qualifies_trial30, candidate_frame
from scripts.research.breakout_logic import Costs, Rules, replay
from tests.test_breakout_logic import sample, BROKER, START, END


class BidirectionalCampaignTests(unittest.TestCase):
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
