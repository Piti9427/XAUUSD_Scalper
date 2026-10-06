"""Public research adapter/policy/storage regression seams; synthetic prices only."""

import unittest

import numpy as np
import pandas as pd

from scripts.research.c22_frequency_adapter import baseline_config, prepare, validate
from scripts.research.reward156_search import prepare_candidate, seeds


def bars(count=4000):
    close = 2000 + np.cumsum(np.random.default_rng(42).normal(0, 2, count))
    return pd.DataFrame(
        dict(open=close, high=close + 0.5, low=close - 0.5, close=close),
        index=pd.date_range("2024-09-01", periods=count, freq="15min", tz="UTC"),
    )


class AdapterTests(unittest.TestCase):
    def test_baseline_parity_and_buy_ema_changes_real_signals(self):
        source = bars()
        baseline = baseline_config()
        expected, rules = prepare_candidate(source, dict(seeds()[2], macro_span=200))
        actual, actual_rules = prepare(source, baseline)
        pd.testing.assert_frame_equal(actual[expected.columns], expected)
        self.assertEqual(actual_rules, rules)
        on, _ = prepare(source, dict(baseline, macro_span=0))
        off, _ = prepare(source, dict(baseline, macro_span=0, buy_ema=0))
        self.assertGreater(int((off.direction == 1).sum()), int((on.direction == 1).sum()))
        self.assertTrue((off.raw_direction != on.raw_direction).any())

    def test_reject_unknown_keys_and_out_of_domain_values(self):
        for delta in ({"typo": 1}, {"risk_cap": 0.2}, {"rsi_period": True}, {"buy_ema": 200}):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                validate(dict(baseline_config(), **delta))


class PolicyTests(unittest.TestCase):
    def test_monthly_entry_count_includes_zero_warmup_and_excludes_partial(self):
        from scripts.research.c22_frequency_policy import monthly

        ledger = [
            dict(
                entry_time_utc="2024-10-31T23:59:00+00:00",
                exit_time_utc="2024-11-01T00:01:00+00:00",
                net=12,
            ),
            dict(
                entry_time_utc="2024-12-02T00:00:00+00:00",
                exit_time_utc="2024-12-02T01:00:00+00:00",
                net=-2,
            ),
        ]
        result = monthly(
            ledger, pd.Timestamp("2024-09-01", tz="UTC"), pd.Timestamp("2024-12-06", tz="UTC")
        )
        self.assertEqual(result["full_month_entries"], {"2024-09": 0, "2024-10": 1, "2024-11": 0})
        self.assertEqual(result["mean_entries"], 1 / 3)
        self.assertEqual(result["partial_month_entries"], {"2024-12": 1})
        self.assertEqual(result["monthly_realized_net"]["2024-11"], 12)

    def test_cost_proxy_never_counts_extra_spread_twice(self):
        from scripts.research.c22_frequency_policy import cost_attribution

        ledger = [
            dict(
                quoted_spread_proxy_usd=0.4,
                modeled_extra_spread_proxy_usd=0.2,
                modeled_slippage_usd=0.2,
                commission_usd=0.07,
                swap_usd=-3,
            ),
            dict(
                quoted_spread_proxy_usd=0.4,
                modeled_extra_spread_proxy_usd=0.2,
                modeled_slippage_usd=0.1,
                commission_usd=0.07,
                swap_usd=1,
            ),
        ]
        costs = cost_attribution(ledger)
        self.assertAlmostEqual(costs["cost_proxy_per_trade"], 1.62)
        self.assertEqual(costs["swap_debit_usd"], 3)
        self.assertEqual(costs["swap_credit_usd"], 1)

    def test_qualification_requires_both_views_all_gates(self):
        from scripts.research.c22_frequency_policy import qualify

        base = dict(
            net_usd=300,
            max_dd_pct=40,
            mean_entries=15,
            min_equity=100,
            bankrupt=False,
            terminal_risk_blockage=False,
            max_admitted_risk_pct=10,
            fixed_lot=True,
        )
        rows = {"base-swap": base, "stress-swap": dict(base)}
        control = {"base-swap": dict(net_usd=300), "stress-swap": dict(net_usd=280)}
        self.assertTrue(qualify(rows, control)["qualified"])
        for delta in (
            {"mean_entries": 14.99},
            {"net_usd": 279},
            {"max_dd_pct": 40.001},
            {"min_equity": 0},
            {"terminal_risk_blockage": True},
            {"fixed_lot": False},
        ):
            with self.subTest(delta=delta):
                self.assertFalse(
                    qualify(rows | {"stress-swap": base | delta}, control)["qualified"]
                )
        with self.assertRaises(ValueError):
            qualify({"base-swap": base}, control)


class ResumeTests(unittest.TestCase):
    def test_resume_rejects_config_or_artifact_drift(self):
        import tempfile
        from pathlib import Path
        from scripts.research.c22_frequency_store import Store

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Store(root, {"source": "one"})
            store.put("cells/a.json", {"ledger": [1]})
            self.assertEqual(Store(root, {"source": "one"}).get("cells/a.json"), {"ledger": [1]})
            with self.assertRaisesRegex(ValueError, "protocol"):
                Store(root, {"source": "two"})
            (root / "cells/a.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "artifact"):
                Store(root, {"source": "one"})

    def test_pending_commit_recovery_and_unknown_artifacts(self):
        import tempfile
        from pathlib import Path
        from scripts.research.c22_frequency_store import Store
        from scripts.research.c22_context_campaign import write_checkpoint

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Store(root, {"source": "one"})
            state = store.state | {"pending": {"name": "cells/a.json", "value": {"complete": True}}}
            write_checkpoint(root / "checkpoint.json", state)
            recovered = Store(root, {"source": "one"})
            self.assertEqual(recovered.get("cells/a.json"), {"complete": True})
            (root / "unbound.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "unrecognized"):
                Store(root, {"source": "one"})


class SignalBoundaryTests(unittest.TestCase):
    def test_future_invariance_and_h4_diagnostics(self):
        source = bars(5000)
        config = baseline_config()
        prepared, _ = prepare(source, config)
        prefix, _ = prepare(source.iloc[:3600], config)
        pd.testing.assert_frame_equal(prepared.iloc[:3600], prefix)
        changed = source.copy()
        changed.loc[changed.index[3600] :, ["open", "high", "low", "close"]] += 1000
        pd.testing.assert_frame_equal(prepared.iloc[:3600], prepare(changed, config)[0].iloc[:3600])
        self.assertGreater(prepared.h4_warmup.sum(), 0)
        self.assertGreater(prepared.h4_directional_mismatch.sum(), 0)
        self.assertTrue(
            (prepared.macro_unavailable == (prepared.h4_warmup | prepared.h4_incomplete)).all()
        )
        # Drop one M15 from a mature H4. No use of its incomplete close.
        damaged = source.drop(source.index[4001])
        actual, _ = prepare(damaged, config)
        unavailable = actual.loc[
            (actual.index >= source.index[4015]) & (actual.index < source.index[4031])
        ]
        self.assertTrue((unavailable.direction == 0).all())
        self.assertTrue((unavailable.h4_incomplete == (unavailable.raw_direction != 0)).all())

    def test_catalog_round_one_covers_each_value_and_deduplicates(self):
        from scripts.research.c22_frequency_adapter import DOMAINS, config_id, next_round

        base = baseline_config()
        catalog = next_round([base], {config_id(base)}, 300)
        for key, domain in DOMAINS.items():
            self.assertEqual(
                {item["value"] for item in catalog if item["parameter"] == key},
                set(domain) - {base[key]},
            )
        self.assertEqual(catalog, next_round([base, base], {config_id(base)}, 300))
        self.assertEqual(catalog[:3], next_round([base], {config_id(base)}, 3))
        self.assertEqual(len({item["id"] for item in catalog}), len(catalog))


class SearchTests(unittest.TestCase):
    def test_real_cells_partial_resume_repeat_and_both_swap_views(self):
        import tempfile
        from pathlib import Path
        from scripts.research.c22_frequency_campaign import search
        from scripts.research.c22_frequency_store import Store
        from tests.test_breakout_logic import BROKER

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "input"
            (inputs / "tape").mkdir(parents=True)
            source = bars(3600)
            source.to_csv(inputs / "bars.csv", index_label="bar_open_utc")
            time = (source.index + pd.Timedelta(minutes=15)).as_unit("ms").asi8
            bid = source.close.to_numpy()
            for key, value in zip(("time", "bid", "ask"), (time, bid, bid + 0.2)):
                np.save(inputs / "tape" / (key + ".npy"), value)
            manifest = dict(
                broker=dict(
                    BROKER,
                    swap_mode=1,
                    swap_long=-1000,
                    swap_short=0.0,
                    point=0.001,
                    swap_rollover3days=3,
                ),
                requested_start_utc="2024-09-01T00:00:00+00:00",
                requested_end_utc="2024-11-01T00:00:00+00:00",
                actual_last_quote="2024-09-03T02:00:00+00:00",
                costs=dict(
                    base=dict(extra_spread=0.0, slippage=0.0, commission_per_lot=7.0),
                    stress=dict(extra_spread=0.2, slippage=0.1, commission_per_lot=7.0),
                ),
            )
            config = dict(max_variants=3, expand_top=3, repeat_top=5)
            store = Store(root / "search", {"test": "synthetic"})
            self.assertEqual(search(store, manifest, inputs, config, 1, 3)["status"], "PARTIAL")
            round_before = store.get("rounds/001.json")
            result = search(
                Store(root / "search", {"test": "synthetic"}), manifest, inputs, config, 1, None
            )
            self.assertEqual(result["status"], "NO_QUALIFIER")
            self.assertEqual(result["variants"], 3)
            self.assertGreater(result["controls"]["base-swap"]["trades"], 0)
            resumed = Store(root / "search", {"test": "synthetic"})
            self.assertEqual(resumed.get("rounds/001.json"), round_before)
            for item in round_before["catalog"]:
                for view in ("base-swap", "stress-swap"):
                    self.assertIn(
                        "swap_policy", resumed.get(f"cells/{item['id']}-{view}.json")["result"]
                    )
            self.assertEqual(search(resumed, manifest, inputs, config, 1, 0), result)

    def test_missing_or_unsupported_swap_blocks_worker(self):
        import tempfile
        from pathlib import Path
        from scripts.research.c22_frequency_campaign import execute_cell
        from tests.test_breakout_logic import BROKER

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tape").mkdir()
            source = bars(100)
            source.to_csv(root / "bars.csv", index_label="bar_open_utc")
            for key in ("time", "bid", "ask"):
                np.save(root / "tape" / f"{key}.npy", np.array([1]))
            with self.assertRaises(KeyError):
                execute_cell((str(root), baseline_config(), "base-swap", dict(broker=BROKER)))
            with self.assertRaisesRegex(ValueError, "points mode"):
                execute_cell(
                    (
                        str(root),
                        baseline_config(),
                        "base-swap",
                        dict(broker=BROKER | {"swap_mode": 2}),
                    )
                )


class RankingTests(unittest.TestCase):
    def test_rank_survival_gates_frequency_and_worst_case_ties(self):
        from scripts.research.c22_frequency_policy import search_rank, winner_rank

        good = dict(
            net_usd=300.0,
            max_dd_pct=39.0,
            mean_entries=15.0,
            min_equity=100.0,
            bankrupt=False,
            terminal_risk_blockage=False,
            max_admitted_risk_pct=10.0,
            fixed_lot=True,
            cost_proxy_per_trade=2.0,
            mean_admitted_risk_pct=5.0,
        )
        control = {v: dict(net_usd=280.0) for v in ("base-swap", "stress-swap")}
        rows = {v: dict(good) for v in control}
        dead = {v: dict(good, net_usd=10000.0, min_equity=0.0, bankrupt=True) for v in control}
        self.assertLess(search_rank("z", rows, control), search_rank("a", dead, control))
        sparse = {v: dict(good, mean_entries=14.0, net_usd=10000.0) for v in control}
        self.assertLess(search_rank("z", rows, control), search_rank("a", sparse, control))
        cheaper = {v: dict(good, cost_proxy_per_trade=1.0) for v in control}
        self.assertLess(winner_rank("z", cheaper), winner_rank("a", rows))
        low_risk = {v: dict(good, mean_admitted_risk_pct=4.0) for v in control}
        self.assertLess(winner_rank("z", low_risk), winner_rank("a", rows))

    def test_terminal_all_risk_without_exposure_only_and_utc_required(self):
        from scripts.research.reward156_tuning import blocking
        from scripts.research.c22_frequency_policy import monthly

        start, end = pd.Timestamp("2024-09-01", tz="UTC"), pd.Timestamp("2024-11-01", tz="UTC")
        event = dict(time_utc="2024-10-31T00:00:00+00:00", reason="risk_cap", position_open=False)
        self.assertTrue(blocking([event], [], start, end)["terminal_risk_blockage"])
        self.assertFalse(blocking([], [], start, end)["terminal_risk_blockage"])
        self.assertFalse(
            blocking([event, event | {"reason": "daily_loss"}], [], start, end)[
                "terminal_risk_blockage"
            ]
        )
        held = dict(
            entry_time_utc="2024-09-15T00:00:00+00:00", exit_time_utc="2024-10-15T00:00:00+00:00"
        )
        self.assertFalse(blocking([event], [held], start, end)["terminal_risk_blockage"])
        with self.assertRaisesRegex(ValueError, "aware UTC"):
            monthly([], pd.Timestamp("2024-09-01"), end)

    def test_three_hundred_unique_variants_without_early_stop(self):
        from scripts.research.c22_frequency_adapter import config_id, next_round

        base = baseline_config()
        configs = {config_id(base): base}
        expanded = set()
        while len(configs) - 1 < 300:
            parents = [k for k in sorted(configs) if k not in expanded][:3]
            batch = next_round([configs[k] for k in parents], configs, 301 - len(configs))
            self.assertTrue(batch)
            expanded.update(parents)
            configs.update({item["id"]: item["config"] for item in batch})
        self.assertEqual(len(configs) - 1, 300)


class ContractTests(unittest.TestCase):
    def test_public_campaign_cannot_finalize_reduced_search_budget(self):
        import json
        from pathlib import Path
        from scripts.research.c22_frequency_campaign import validate_config

        config = json.loads(Path("config/c22-frequency.json").read_text())
        validate_config(config)
        for count in (1, 3, 299, 301, True):
            with self.subTest(count=count), self.assertRaises(ValueError):
                validate_config(config | {"max_variants": count})

    def test_adapter_rejects_float_period_before_signal_generation(self):
        with self.assertRaises(ValueError):
            validate(baseline_config() | {"rsi_period": 14.0})


class LockTests(unittest.TestCase):
    def test_second_writer_cannot_change_existing_artifacts(self):
        import tempfile
        from pathlib import Path
        from scripts.research.c22_context_campaign import REPO, BASELINE, campaign_lock
        from scripts.research.c22_frequency_campaign import campaign

        with tempfile.TemporaryDirectory(
            dir=REPO / "runs", prefix="frequency-lock-test-"
        ) as directory:
            root = Path(directory)
            marker = root / "COMPLETE.json"
            marker.write_text("existing evidence")
            with campaign_lock(root):
                with self.assertRaisesRegex(ValueError, "already running"):
                    campaign(BASELINE, root)
                self.assertEqual(marker.read_text(), "existing evidence")
