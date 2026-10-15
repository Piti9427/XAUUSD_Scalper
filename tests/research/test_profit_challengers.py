"""Research selection must not leak primary-window performance."""

import copy
import unittest
from scripts.research.profit_challengers import select_candidate, parameters


class ProfitChallengerTests(unittest.TestCase):
    def rows(self):
        rows = []
        for window in ("early", "late", "pre_primary"):
            for name in ("B1", "B20"):
                for cost in (0.1, 0.15):
                    rows.append(
                        {
                            "window": window,
                            "strategy": name,
                            "cost_r": cost,
                            "trades": 40,
                            "pf": 1.3,
                            "return_pct": 10 if name == "B20" else 5,
                            "max_dd_pct_barclose": 5,
                            "total_r": 8,
                            "stop_triggered": False,
                        }
                    )
        return rows

    def test_primary_winner_cannot_override_locked_selection(self):
        rows = self.rows()
        rows.append({"window": "primary", "strategy": "B1", "cost_r": 0.15, "return_pct": 100000})
        self.assertEqual(select_candidate(rows, ["B20"])["selected"], "B20")

    def test_missing_cost_or_weak_inner_block_rejects(self):
        rows = self.rows()
        missing = [
            r
            for r in rows
            if not (r["strategy"] == "B20" and r["window"] == "pre_primary" and r["cost_r"] == 0.1)
        ]
        self.assertEqual(select_candidate(missing, ["B20"])["selected"], "B1")
        weak = copy.deepcopy(rows)
        next(
            r
            for r in weak
            if r["strategy"] == "B20" and r["window"] == "early" and r["cost_r"] == 0.15
        )["total_r"] = -1
        self.assertEqual(select_candidate(weak, ["B20"])["selected"], "B1")

    def test_high_profit_cannot_hide_drawdown_or_stop(self):
        for field, value in [("max_dd_pct_barclose", 12), ("stop_triggered", True)]:
            rows = self.rows()
            row = next(
                r
                for r in rows
                if r["strategy"] == "B20" and r["window"] == "pre_primary" and r["cost_r"] == 0.15
            )
            row["return_pct"] = 1000
            row[field] = value
            with self.subTest(field=field):
                self.assertEqual(select_candidate(rows, ["B20"])["selected"], "B1")

    def test_entry_challengers_preserve_baseline_exits(self):
        for name in ("B1", "B20", "B40", "P1", "B1_H1", "B1_BODY", "B1_SESSION"):
            self.assertEqual(parameters(name), (2.5, 3.5))
        self.assertEqual(parameters("B1_SL2"), (2.0, 3.5))
        self.assertEqual(parameters("B1_TP25"), (2.5, 2.5))


if __name__ == "__main__":
    unittest.main()
