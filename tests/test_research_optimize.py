"""Chronology and selection tests for offline BotTradeGold optimization."""

import unittest

from scripts.research.matrix import BASE_NAMES
from scripts.research.optimize import build_custom_walkforward, build_walkforward


class WalkforwardTests(unittest.TestCase):
    def setUp(self):
        self.specs = []
        for base in BASE_NAMES:
            self.specs.append({"name": base, "family": base})
        for base in BASE_NAMES:
            for flt in ("rsi", "body", "fvg", "h1ema", "h1structure"):
                self.specs.append({"name": f"{base}__{flt}", "family": base, "filters": [flt]})
        self.years = list(range(2010, 2020))
        self.annual = {}
        for spec in self.specs:
            for year in self.years:
                self.annual[(spec["name"], "native", str(year))] = {
                    "trades": 10,
                    "net": 0.0,
                    "total_r": 0.0,
                    "pf": "",
                }

    def set_net(self, name, year, value):
        row = self.annual[(name, "native", str(year))]
        row["net"] = value
        row["total_r"] = value

    def test_selection_uses_prior_years_only(self):
        for year in range(2010, 2018):
            self.set_net("Donchian20", year, 1)
            self.set_net("Donchian20__rsi", year, 2)
        self.set_net("Donchian20", 2018, 1000)
        self.set_net("Donchian20__rsi", 2018, -10)
        _, selected, _, _ = build_walkforward(
            self.specs, self.annual, self.years, first_test_year=2018, last_test_year=2018
        )
        winner = next(row for row in selected if row["base"] == "Donchian20")
        self.assertEqual(winner["strategy"], "Donchian20__rsi")
        self.assertEqual(winner["train_last_year"], 2017)
        self.assertEqual(winner["test_net"], -10)
        self.assertEqual(winner["base_test_net"], 1000)
        self.set_net("Donchian20", 2018, -1000)
        _, revised, _, _ = build_walkforward(
            self.specs, self.annual, self.years, first_test_year=2018, last_test_year=2018
        )
        self.assertEqual(
            next(row for row in revised if row["base"] == "Donchian20")["strategy"],
            "Donchian20__rsi",
        )

    def test_family_and_global_folds_include_losses_and_never_promote(self):
        self.set_net("State20__body", 2018, -50)
        candidates, selected, summaries, aliases = build_walkforward(
            self.specs, self.annual, self.years, first_test_year=2018, last_test_year=2019
        )
        self.assertEqual(len(candidates), 102 * 2)
        self.assertEqual(len(selected), 18 * 2)
        self.assertEqual(len(summaries), 18)
        self.assertEqual(aliases, [])
        self.assertEqual(
            next(
                row
                for row in candidates
                if row["strategy"] == "State20__body" and row["test_year"] == 2018
            )["test_net"],
            -50,
        )
        self.assertTrue(all(row["production_ready"] is False for row in summaries))
        self.assertTrue(all(row["test_year"] > row["train_last_year"] for row in selected))

    def test_duplicate_contract_name_is_excluded_from_global_pool(self):
        self.specs.append(dict(self.specs[0], name="Donchian20Alias", reconstruction=True))
        for year in self.years:
            self.annual[("Donchian20Alias", "native", str(year))] = dict(
                self.annual[("Donchian20", "native", str(year))]
            )
        candidates, _, _, aliases = build_walkforward(
            self.specs, self.annual, self.years, first_test_year=2018, last_test_year=2018
        )
        self.assertEqual(len(candidates), 102)
        self.assertEqual(aliases, [{"alias": "Donchian20Alias", "canonical": "Donchian20"}])

    def test_partial_2026_and_missing_years_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Partial 2026"):
            build_walkforward(self.specs, self.annual, self.years, last_test_year=2026)
        with self.assertRaisesRegex(ValueError, "missing years"):
            build_walkforward(
                self.specs,
                self.annual,
                self.years[:-2] + [2020],
                first_test_year=2018,
                last_test_year=2020,
            )

    def test_declared_parameter_walkforward_uses_prior_years_only(self):
        first, second = "Donchian20", "Donchian20__rsi"
        for year in range(2010, 2018):
            self.set_net(first, year, 1)
            self.set_net(second, year, 2)
        self.set_net(first, 2018, 1000)
        self.set_net(second, 2018, -10)
        candidates, selected, summary = build_custom_walkforward(
            [first, second],
            self.annual,
            self.years,
            first_test_year=2018,
            last_test_year=2018,
        )
        self.assertEqual(len(candidates), 2)
        self.assertEqual(selected[0]["strategy"], second)
        self.assertEqual(selected[0]["train_last_year"], 2017)
        self.assertEqual(summary[0]["selected_test_net"], -10)
        self.assertFalse(summary[0]["production_ready"])
        self.set_net(first, 2018, -1000)
        _, revised, _ = build_custom_walkforward(
            [first, second],
            self.annual,
            self.years,
            first_test_year=2018,
            last_test_year=2018,
        )
        self.assertEqual(revised[0]["strategy"], second)


if __name__ == "__main__":
    unittest.main()
