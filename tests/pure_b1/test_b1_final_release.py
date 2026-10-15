"""B1-FINAL release evidence: parity on identical bars, reconciliation, exit gate."""

import unittest

import numpy as np
import pandas as pd

from scripts.research.b1_final_release import (
    signal_parity,
    ledger_from_events,
    reconcile,
    metrics,
    block_returns,
    exit_gate,
    exit_attribution,
    verdicts,
)


def close_event(req, net, risk, reason="SL", exit_state=0, utc="2026-06-01T00:00:00.000Z"):
    return {
        "type": "CLOSE_CONFIRMED",
        "confirmed": True,
        "utc": utc,
        "fields": {
            "request_id": req,
            "net_profit": net,
            "position_risk_money": risk,
            "net_r": net / risk,
            "reason": reason,
            "exit_state": exit_state,
            "volume": 0.1,
        },
    }


def mark(day, equity):
    return {"type": "EQUITY_MARK", "utc": f"{day}T00:00:01.000Z", "fields": {"equity": equity}}


class ReleaseTests(unittest.TestCase):
    def bars(self, n=130):
        close = np.where(np.arange(n) % 2 == 0, 100.0, 101.0)
        frame = pd.DataFrame(
            {
                "bar_open_epoch": 1778112000 + 900 * np.arange(n),
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close,
            }
        )
        frame.loc[n - 1, ["close", "high"]] = [103.0, 103.5]
        return frame

    def test_signal_parity_on_identical_bars(self):
        bars = self.bars()
        t = int(bars.bar_open_epoch.iloc[-1])
        ok = [{"type": "SIGNAL", "fields": {"bar_open_utc_epoch": t, "direction": 1}}]
        result = signal_parity(bars, ok, first_live_epoch=t)
        self.assertTrue(result["passed"])
        self.assertEqual(result["reference_signals"], 1)
        flipped = [{"type": "SIGNAL", "fields": {"bar_open_utc_epoch": t, "direction": -1}}]
        self.assertFalse(signal_parity(bars, flipped, first_live_epoch=t)["passed"])
        self.assertFalse(signal_parity(bars, [], first_live_epoch=t)["passed"])

    def test_reconcile_event_net_with_equity_and_deals(self):
        events = [close_event("a", -10.0, 10.0), close_event("b", 35.0, 10.0, "TP")]
        for e, pid in zip(events, [1, 2]):
            e["event_id"] = f"close-{pid}"
            e["fields"]["position_identifier"] = pid
        deals = pd.DataFrame(
            {
                "entry": [0, 0, 1, 0, 1],
                "profit": [100.0, 0.0, -10.0, 0.0, 35.0],
                "commission": [0.0] * 5,
                "swap": [0.0] * 5,
                "type": [2, 0, 1, 1, 0],
                "position": [0, 1, 1, 2, 2],
                "volume": [0.0, 0.1, 0.1, 0.1, 0.1],
            }
        )
        ledger = ledger_from_events(events)
        self.assertTrue(reconcile(ledger, deals, deposit=100.0, final_equity=125.0)["passed"])
        self.assertFalse(reconcile(ledger, deals, deposit=100.0, final_equity=126.0)["passed"])

    def test_metrics_and_reserve_sensitivity(self):
        ledger = ledger_from_events(
            [close_event("a", -10.0, 10.0), close_event("b", 35.0, 10.0, "TP")]
        )
        base = metrics(ledger, deposit=1000.0, max_dd=0.02, hard_stop=False, reserve_r=0.0)
        self.assertAlmostEqual(base["total_net_r"], 2.5)
        self.assertAlmostEqual(base["profit_factor"], 3.5)
        self.assertAlmostEqual(base["return_pct"], 2.5)
        stressed = metrics(ledger, deposit=1000.0, max_dd=0.02, hard_stop=False, reserve_r=0.2)
        self.assertAlmostEqual(stressed["total_net_r"], 2.1)
        self.assertAlmostEqual(stressed["return_pct"], 2.1)
        adverse = metrics(
            ledger,
            deposit=1000.0,
            max_dd=0.02,
            hard_stop=False,
            reserve_r=0.0,
            adverse_per_oz=0.1,
            contract=100.0,
        )
        # $0.10/oz x 100 oz x 0.1 lot x (entry+exit) = $2 per trade = 0.2R at $10 risk
        self.assertAlmostEqual(adverse["net_profit"], 21.0)
        self.assertAlmostEqual(adverse["total_net_r"], 2.1)
        empty = metrics(ledger.iloc[:0], deposit=1000.0, max_dd=0.0, hard_stop=False, reserve_r=0.0)
        self.assertEqual(empty["trades"], 0)
        self.assertIsNone(empty["profit_factor"])

    def test_block_returns_use_boundary_equity_with_floating(self):
        events = [mark("2026-05-14", 1000.0), mark("2026-07-01", 1100.0), mark("2026-09-01", 990.0)]
        blocks = block_returns(
            events, final_equity=1089.0, ledger=ledger_from_events([]), reserve_r=0.0
        )
        self.assertAlmostEqual(blocks["May14-Jun"], 10.0)
        self.assertAlmostEqual(blocks["Jul-Aug"], -10.0)
        self.assertAlmostEqual(blocks["Sep1-25"], 10.0)

    def test_exit_gate_requires_every_condition(self):
        base = {
            "total_net_r": 5.0,
            "return_pct": 5.0,
            "expectancy_r": 0.1,
            "profit_factor": 1.2,
            "max_dd_pct": 8.0,
            "hard_stop": False,
            "blocks": {"a": 1.0, "b": 1.0, "c": 1.0},
            "trades": 50,
        }
        better = dict(
            base,
            total_net_r=6.0,
            return_pct=6.0,
            max_dd_pct=7.0,
            blocks={"a": 2.0, "b": 2.0, "c": 0.0},
        )
        self.assertTrue(exit_gate(base, better)["passed"])
        for change in (
            {"total_net_r": 5.0},
            {"max_dd_pct": 9.0},
            {"profit_factor": 1.0},
            {"hard_stop": True},
            {"blocks": {"a": 2.0, "b": 0.0, "c": 0.0}},
            {"max_dd_pct": 12.0},
            {"expectancy_r": 0.0},
        ):
            with self.subTest(change=change):
                self.assertFalse(exit_gate(base, dict(better, **change))["passed"])
        worse_base = dict(base, max_dd_pct=13.0)
        self.assertFalse(exit_gate(worse_base, dict(better, max_dd_pct=12.5))["passed"])
        self.assertFalse(exit_gate(dict(base, trades=0), dict(better, trades=0))["passed"])

    def test_exit_attribution_counts_saved_losers_displaced_winners_changed_entries(self):
        base = ledger_from_events(
            [
                close_event("B1F1|1|1", -10.0, 10.0),
                close_event("B1F1|2|1", 35.0, 10.0, "TP"),
                close_event("B1F1|3|-1", 35.0, 10.0, "TP"),
            ]
        )
        variant = ledger_from_events(
            [
                close_event("B1F11|1|1", 0.5, 10.0, "SL", 3),
                close_event("B1F11|2|1", 0.5, 10.0, "SL", 3),
                close_event("B1F11|4|1", -10.0, 10.0),
            ]
        )
        result = exit_attribution(base, variant)
        self.assertEqual(result["saved_losers"], 1)
        self.assertEqual(result["displaced_winners"], 1)
        self.assertEqual(result["only_in_baseline"], ["3|-1"])
        self.assertEqual(result["only_in_variant"], ["4|1"])

    def test_zero_risk_trade_does_not_divide_by_zero(self):
        ledger = ledger_from_events([close_event("a", -10.0, 10.0)])
        ledger.loc[0, "position_risk_money"] = 0.0
        m = metrics(
            ledger, deposit=1000.0, max_dd=0.0, hard_stop=False, reserve_r=0.1, adverse_per_oz=0.1
        )
        self.assertTrue(np.isfinite(m["total_net_r"]))

    def test_parity_counts_reference_signals_before_first_ea_signal(self):
        bars = self.bars()
        t = int(bars.bar_open_epoch.iloc[-1])
        result = signal_parity(bars, [], first_live_epoch=t - 900 * 5)
        self.assertEqual(result["missing"], [t])

    def test_engine_test_csv_with_commas_in_check_names(self):
        import tempfile
        from pathlib import Path
        from scripts.research.b1_final_release import engine_tests_passed

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "t.csv"
            path.write_text("test,check,result\na,x, y and z,PASS\nSUMMARY,1 passed,0 failed\n")
            self.assertTrue(engine_tests_passed(path))
            path.write_text("test,check,result\na,x, y,FAIL\nSUMMARY,0 passed,1 failed\n")
            self.assertFalse(engine_tests_passed(path))

    def test_verdicts_are_separate(self):
        v = verdicts(
            implementation_ok=True,
            account_verdict="ACCOUNT_BLOCKED",
            baseline=None,
            exit_passed=False,
            costs_measured=False,
        )
        self.assertEqual(v["implementation"], "IMPLEMENTATION_VERIFIED")
        self.assertEqual(v["account"], "ACCOUNT_BLOCKED")
        self.assertEqual(v["strategy"], "STRATEGY_NO_GO")
        self.assertEqual(v["exit"], "FIXED_EXIT_FROZEN_BE_DISABLED")
        self.assertEqual(v["deployment"], "NO_GO")


if __name__ == "__main__":
    unittest.main()
