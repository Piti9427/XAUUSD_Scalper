"""Startup-history provenance and native complete-H4 availability regressions."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from scripts.c22_selected.strategy import SelectedBarCache, SelectedStrategy
from scripts.demo_runtime.market_data import completed_m15_from_m1
from tests.demo.test_c22_selected_strategy import selected_config, signal_bars


FINGERPRINT = "0123456789abcdef"


def m1_for_quarters(stamps):
    """Actual native aggregation input; no EMA/indicator mocks."""
    rates = []
    for number, stamp in enumerate(stamps):
        price = 3000.0 + number / 1000
        rates.extend(dict(time=int(stamp.timestamp()) + minute * 60,
                          open=price, high=price + 0.02, low=price - 0.02,
                          close=price + 0.01) for minute in range(15))
    return rates


def h4_input(*, prior_partial=False, forming_quarters=10):
    closed = pd.Timestamp("2026-10-26T00:00:00Z")
    if prior_partial:
        # 220 complete historical H4, then Sunday's incomplete20:00 bucket.
        historical = pd.date_range(end=closed - pd.Timedelta(hours=4, minutes=15),
                                   periods=220 * 16, freq="15min", tz="UTC")
        previous = pd.date_range(closed - pd.Timedelta(hours=2), periods=7,
                                 freq="15min", tz="UTC")
    else:
        historical = pd.date_range(end=closed - pd.Timedelta(minutes=15),
                                   periods=220 * 16, freq="15min", tz="UTC")
        previous = pd.DatetimeIndex([], tz="UTC")
    forming = pd.date_range(closed, periods=forming_quarters, freq="15min", tz="UTC")
    stamps = historical.append(previous).append(forming)
    observed = (forming[-1] + pd.Timedelta(minutes=15)).to_pydatetime()
    return completed_m15_from_m1(m1_for_quarters(stamps), now=observed), observed


class NativeH4AvailabilityTests(unittest.TestCase):
    def test_many_complete_h4_but_latest_closed_bucket_partial_has_specific_blocker(self):
        bars, _ = h4_input(prior_partial=True)
        self.assertEqual(int((bars.close.resample("4h").count() == 16).sum()), 220)
        self.assertEqual(int(bars.close.resample("4h").count().loc["2026-10-25T20:00:00Z"]), 7)
        cache = SelectedBarCache()
        with self.assertRaisesRegex(ValueError, "^macro_latest_h4_incomplete$"):
            cache.append(bars)
        # Repeating an unchanged broker window must retain the precise cause.
        with self.assertRaisesRegex(ValueError, "^macro_latest_h4_incomplete$"):
            cache.append(bars.iloc[-100:])

    def test_forming_partial_h4_does_not_hide_previous_complete_closed_macro(self):
        bars, _ = h4_input(prior_partial=False)
        self.assertEqual(int(bars.close.resample("4h").count().iloc[-1]), 10)
        cache = SelectedBarCache()
        cache.append(bars)
        self.assertTrue(pd.notna(cache.row.macro_ema))
        completed = bars.close.resample("4h").agg(["last", "count"])
        expected = completed.loc[completed["count"] == 16, "last"].ewm(
            span=200, adjust=False, min_periods=200).mean().iloc[-1]
        self.assertAlmostEqual(float(cache.row.macro_ema), expected)

    def test_genuinely_short_history_keeps_count_warmup_blocker(self):
        bars, _ = h4_input(prior_partial=False, forming_quarters=1)
        bars = bars.iloc[:200 * 16]
        cache = SelectedBarCache()
        with self.assertRaisesRegex(ValueError, "^macro_warmup_insufficient$"):
            cache.append(bars)

    def test_missing_closed_m1_excludes_its_m15_and_keeps_h4_incomplete(self):
        stamps = pd.date_range("2026-10-25T20:00:00Z", periods=16, freq="15min")
        rates = m1_for_quarters(stamps)
        del rates[17]
        bars = completed_m15_from_m1(rates, now=datetime(2026, 10, 26, tzinfo=timezone.utc))
        self.assertEqual(len(bars), 15)
        self.assertNotIn(stamps[1], bars.index)
        self.assertEqual(int(bars.close.resample("4h").count().iloc[0]), 15)

    def test_short_bootstrap_retries_after_60_seconds_when_sdk_history_expands(self):
        full, observed = h4_input(prior_partial=False)
        short = full.iloc[:200 * 16]
        strategy = SelectedStrategy(selected_config())
        clock = {"seconds": 0.0}
        with patch("scripts.c22_selected.strategy.time.monotonic", side_effect=lambda: clock["seconds"]), patch(
            "scripts.c22_selected.strategy.copy_m1_rates",
            side_effect=[m1_for_quarters(short.index), m1_for_quarters(full.index)],
        ) as copy:
            with self.assertRaisesRegex(ValueError, "^macro_warmup_insufficient$"):
                strategy.frame(short.iloc[-100:], NS(), "XAUUSDm", observed)
            clock["seconds"] = 59
            with self.assertRaisesRegex(ValueError, "^macro_warmup_insufficient$"):
                strategy.frame(short.iloc[-100:], NS(), "XAUUSDm", observed)
            self.assertEqual(copy.call_count, 1)
            clock["seconds"] = 60
            frame = strategy.frame(full.iloc[-100:], NS(), "XAUUSDm", observed)
        self.assertEqual(copy.call_count, 2)
        self.assertTrue(pd.notna(frame.macro_ema.iloc[-1]))
        self.assertEqual(len(strategy.cache.bars), len(full))

    def test_latest_incomplete_h4_does_not_refetch_and_recovers_on_next_complete_h4(self):
        partial, observed = h4_input(prior_partial=True)
        completed, later = h4_input(prior_partial=True, forming_quarters=17)
        strategy = SelectedStrategy(selected_config())
        clock = {"seconds": 0.0}
        with patch("scripts.c22_selected.strategy.time.monotonic", side_effect=lambda: clock["seconds"]), patch(
            "scripts.c22_selected.strategy.copy_m1_rates",
            return_value=m1_for_quarters(partial.index),
        ) as copy:
            with self.assertRaisesRegex(ValueError, "^macro_latest_h4_incomplete$"):
                strategy.frame(partial.iloc[-100:], NS(), "XAUUSDm", observed)
            clock["seconds"] = 120
            with self.assertRaisesRegex(ValueError, "^macro_latest_h4_incomplete$"):
                strategy.frame(partial.iloc[-100:], NS(), "XAUUSDm", observed)
            self.assertEqual(copy.call_count, 1)
            frame = strategy.frame(completed.iloc[-100:], NS(), "XAUUSDm", later)
        self.assertEqual(copy.call_count, 1)
        self.assertTrue(pd.notna(frame.macro_ema.iloc[-1]))

    def test_retry_bootstrap_rejects_known_overlap_omission_and_changed_price(self):
        full, observed = h4_input(prior_partial=False)
        short = full.iloc[:200 * 16]
        all_rates = m1_for_quarters(full.index)
        cutoff = int((short.index[-1] + pd.Timedelta(minutes=15)).timestamp())
        short_rates = [r for r in all_rates if r["time"] < cutoff]
        changed_start = int(short.index[20].timestamp())
        for failure in ("omission", "changed_price"):
            with self.subTest(failure=failure):
                fresh = [dict(r) for r in all_rates]
                if failure == "omission":
                    fresh = [r for r in fresh if not changed_start <= r["time"] < changed_start + 900]
                else:
                    for row in fresh:
                        if changed_start <= row["time"] < changed_start + 900:
                            for field in ("open", "high", "low", "close"):
                                row[field] += 0.001
                strategy = SelectedStrategy(selected_config())
                clock = {"seconds": 0.0}
                with patch("scripts.c22_selected.strategy.time.monotonic", side_effect=lambda: clock["seconds"]), patch(
                    "scripts.c22_selected.strategy.copy_m1_rates", side_effect=[short_rates, fresh],
                ) as copy:
                    with self.assertRaisesRegex(ValueError, "^macro_warmup_insufficient$"):
                        strategy.frame(short.iloc[-100:], NS(), "XAUUSDm", observed)
                    clock["seconds"] = 60
                    with self.assertRaisesRegex(ValueError, "^bar_cache_divergence$"):
                        strategy.frame(full.iloc[-100:], NS(), "XAUUSDm", observed)
                self.assertEqual(copy.call_count, 2)
                self.assertIsNone(strategy.cache.bars)
                self.assertEqual(strategy.history_seed_status, "broker_overlap_divergence")

    def test_retry_bootstrap_retains_known_older_prefix_when_fresh_window_slides(self):
        full, observed = h4_input(prior_partial=False)
        short = full.iloc[:200 * 16]
        all_rates = m1_for_quarters(full.index)
        cutoff = int((short.index[-1] + pd.Timedelta(minutes=15)).timestamp())
        short_rates = [r for r in all_rates if r["time"] < cutoff]
        fresh_start = int(full.index[20 * 16].timestamp())
        fresh_rates = [r for r in all_rates if r["time"] >= fresh_start]
        strategy = SelectedStrategy(selected_config())
        clock = {"seconds": 0.0}
        with patch("scripts.c22_selected.strategy.time.monotonic", side_effect=lambda: clock["seconds"]), patch(
            "scripts.c22_selected.strategy.copy_m1_rates", side_effect=[short_rates, fresh_rates],
        ) as copy:
            with self.assertRaisesRegex(ValueError, "^macro_warmup_insufficient$"):
                strategy.frame(short.iloc[-100:], NS(), "XAUUSDm", observed)
            clock["seconds"] = 60
            frame = strategy.frame(full.iloc[-100:], NS(), "XAUUSDm", observed)
        self.assertEqual(copy.call_count, 2)
        self.assertTrue(pd.notna(frame.macro_ema.iloc[-1]))
        self.assertEqual(strategy.cache.bars.index[0], full.index[0])
        self.assertEqual(len(strategy.cache.bars), len(full))


class StartupHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "bars.csv"
        self.config = selected_config()
        self.full = signal_bars(-1)
        self.seed = self.full.iloc[:-4].copy()
        self.recent = self.full.iloc[-100:].copy()
        self.now = (self.full.index[-1] + pd.Timedelta(minutes=15)).to_pydatetime()

    def publish(self, bars=None, *, config=None, fingerprint=FINGERPRINT, observed=None):
        from scripts.c22_selected.history import save_manifest
        bars = self.seed if bars is None else bars
        bars.rename_axis("bar_open_utc").to_csv(self.path)
        save_manifest(self.path, bars=bars, fingerprint=fingerprint,
                      config=self.config if config is None else config,
                      now=self.now if observed is None else observed)

    def load(self, *, recent=None, config=None, fingerprint=FINGERPRINT, observed=None):
        from scripts.c22_selected.history import load_seed
        return load_seed(self.path, recent=self.recent if recent is None else recent,
                         fingerprint=fingerprint,
                         config=self.config if config is None else config,
                         now=self.now if observed is None else observed)

    def rejected(self, **kwargs):
        restored, diagnostic = self.load(**kwargs)
        self.assertIsNone(restored)
        self.assertIsInstance(diagnostic, str)
        self.assertTrue(diagnostic)

    def test_valid_manifest_restores_prefix_and_only_new_tail(self):
        self.publish()
        self.assertTrue(self.path.with_suffix(".csv.meta.json").exists())
        restored, diagnostic = self.load()
        self.assertIsInstance(diagnostic, str)
        pd.testing.assert_frame_equal(restored, self.full, check_names=False,
                                      check_freq=False, check_exact=True)
        self.assertFalse(restored.index.has_duplicates)

    def test_valid_seed_preserves_broker_datetime_resolution(self):
        from tests.demo.test_c22_selected_runner import SelectedBroker
        broker = SelectedBroker()
        recent = self.recent.copy()
        recent.index = recent.index.as_unit("s")
        recent.index.name = "time"  # Native completed_m15_from_m1 SDK index name.
        cold = SelectedStrategy(self.config)
        with patch("scripts.c22_selected.strategy.copy_m1_rates", return_value=broker.rates):
            expected = cold.frame(recent, broker, "XAUUSDm", broker.now)
        self.assertEqual(expected.index.unit, "s")
        self.publish(cold.cache.bars.iloc[:-4], observed=broker.now)
        warm = SelectedStrategy(self.config, cache_path=self.path, fingerprint=FINGERPRINT)
        with patch("scripts.c22_selected.strategy.copy_m1_rates", side_effect=AssertionError("unexpected full fetch")) as copy:
            actual = warm.frame(recent, broker, "XAUUSDm", broker.now)
        copy.assert_not_called()
        self.assertEqual(warm.history_seed_status, "restored")
        self.assertEqual(actual.index.dtype, expected.index.dtype)
        self.assertEqual(actual.index.name, expected.index.name)
        pd.testing.assert_series_equal(actual.direction, expected.direction,
                                       check_freq=False, check_exact=True)
        pd.testing.assert_series_equal(actual.macro_ema, expected.macro_ema,
                                       check_freq=False, check_exact=True)

    def test_missing_csv_or_manifest_falls_back_with_diagnostic(self):
        self.rejected()
        self.publish()
        self.path.with_suffix(".csv.meta.json").unlink()
        self.rejected()

    def test_account_rules_symbol_and_source_binding_mismatch_are_rejected(self):
        self.publish()
        self.rejected(fingerprint="fedcba9876543210")
        for key, value in (("contract_id", "other-rules"), ("symbol", "XAGUSDm")):
            with self.subTest(key=key):
                changed = deepcopy(self.config)
                changed[key] = value
                self.rejected(config=changed)
        changed = deepcopy(self.config)
        name = next(iter(changed["source_hashes"]))
        changed["source_hashes"][name] = "0" * 64
        self.rejected(config=changed)

    def test_csv_hash_and_corrupt_metadata_are_rejected(self):
        self.publish()
        self.path.write_text(self.path.read_text() + "external change\n")
        self.rejected()
        self.publish()
        self.path.with_suffix(".csv.meta.json").write_text("{not-json")
        self.rejected()

    def test_aggregation_version_range_and_future_manifest_clock_are_bound(self):
        mutations = {
            "aggregation": "DIRECT_TERMINAL_M15",
            "version": 2,
            "rows": len(self.seed) - 1,
            "first_bar_utc": self.seed.index[1].isoformat(),
            "last_bar_utc": self.seed.index[-2].isoformat(),
            "created_utc": (self.now + pd.Timedelta(seconds=1)).isoformat(),
        }
        for key, value in mutations.items():
            with self.subTest(field=key):
                self.publish()
                metadata_path = self.path.with_suffix(".csv.meta.json")
                metadata = json.loads(metadata_path.read_text())
                metadata[key] = value
                metadata_path.write_text(json.dumps(metadata))
                self.rejected()

    def test_non_object_json_metadata_falls_back_instead_of_crashing(self):
        self.publish()
        for value in ([], None, 1, "metadata"):
            with self.subTest(value=value):
                self.path.with_suffix(".csv.meta.json").write_text(json.dumps(value))
                self.rejected()

    def test_future_seed_rejected_even_when_manifest_and_csv_hash_match(self):
        future = self.seed.copy()
        future.index += pd.Timedelta(days=400)
        self.publish(future, observed=self.now + pd.Timedelta(days=401))
        # Keep metadata clock plausible so this tests the bar cutoff itself.
        metadata_path = self.path.with_suffix(".csv.meta.json")
        metadata = json.loads(metadata_path.read_text())
        metadata["created_utc"] = self.now.isoformat()
        metadata_path.write_text(json.dumps(metadata))
        self.rejected()

    def test_rehashed_malformed_csv_still_fails_price_and_chronology_validation(self):
        for kind in ("naive", "duplicate", "unordered", "unaligned", "invalid_high", "nan"):
            with self.subTest(kind=kind):
                self.publish()
                malformed = self.seed.copy()
                if kind == "naive":
                    malformed.index = malformed.index.tz_localize(None)
                elif kind == "duplicate":
                    malformed = pd.concat([malformed.iloc[[0]], malformed])
                elif kind == "unordered":
                    malformed = malformed.iloc[::-1]
                elif kind == "unaligned":
                    malformed.index += pd.Timedelta(minutes=1)
                elif kind == "invalid_high":
                    malformed.iloc[0, malformed.columns.get_loc("high")] = 0
                else:
                    malformed.iloc[0, malformed.columns.get_loc("close")] = float("nan")
                malformed.rename_axis("bar_open_utc").to_csv(self.path)
                metadata_path = self.path.with_suffix(".csv.meta.json")
                metadata = json.loads(metadata_path.read_text())
                metadata.update(sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),
                                rows=len(malformed), first_bar_utc=malformed.index[0].isoformat(),
                                last_bar_utc=malformed.index[-1].isoformat())
                metadata_path.write_text(json.dumps(metadata))
                self.rejected()

    def test_submillisecond_offset_rejected_before_publishing_or_restoring_seed(self):
        from scripts.c22_selected.history import save_manifest
        self.publish()
        metadata_path = self.path.with_suffix(".csv.meta.json")
        metadata = json.loads(metadata_path.read_text())
        shifted = self.seed.copy()
        shifted.index += pd.Timedelta(microseconds=500)
        shifted.rename_axis("bar_open_utc").to_csv(self.path)
        with self.assertRaisesRegex(ValueError, "unaligned M15"):
            save_manifest(self.path, bars=shifted, fingerprint=FINGERPRINT,
                          config=self.config, now=self.now)
        metadata.update(sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),
                        rows=len(shifted), first_bar_utc=shifted.index[0].isoformat(),
                        last_bar_utc=shifted.index[-1].isoformat())
        metadata_path.write_text(json.dumps(metadata))
        self.rejected()

    def test_manifest_publication_checks_actual_csv_and_preserves_old_metadata_on_failure(self):
        from scripts.c22_selected.history import save_manifest
        self.publish()
        metadata_path = self.path.with_suffix(".csv.meta.json")
        before = metadata_path.read_bytes()
        different = self.seed.copy()
        different.iloc[0] += 0.01
        with self.assertRaises(ValueError):
            save_manifest(self.path, bars=different, fingerprint=FINGERPRINT,
                          config=self.config, now=self.now)
        self.assertEqual(metadata_path.read_bytes(), before)
        restored, _ = self.load()
        self.assertIsNotNone(restored)

    def test_invalid_seed_triggers_real_cold_bootstrap_instead_of_being_accepted(self):
        from tests.demo.test_c22_selected_runner import SelectedBroker
        self.publish()
        self.path.write_text(self.path.read_text() + "unverified edit\n")
        strategy = SelectedStrategy(self.config, cache_path=self.path, fingerprint=FINGERPRINT)
        broker = SelectedBroker()
        with patch("scripts.c22_selected.strategy.copy_m1_rates", return_value=broker.rates) as copy:
            frame = strategy.frame(self.recent, broker, "XAUUSDm", broker.now)
        copy.assert_called_once_with(broker, "XAUUSDm")
        self.assertEqual(strategy.history_seed_status, "content_hash_mismatch")
        self.assertTrue(pd.notna(frame.macro_ema.iloc[-1]))
        actual, expected = strategy.cache.bars.copy(), self.full.copy()
        actual.index = actual.index.as_unit("ns")
        expected.index = expected.index.as_unit("ns")
        pd.testing.assert_frame_equal(actual, expected,
                                      check_names=False, check_freq=False, check_exact=True)

    def test_changed_or_missing_overlap_bar_rejected_without_merging(self):
        self.publish()
        changed = self.recent.copy()
        changed.iloc[0] += 0.001
        self.rejected(recent=changed)
        self.rejected(recent=self.recent.drop(self.recent.index[20]))

    def test_older_or_disjoint_broker_window_rejected(self):
        self.publish()
        self.rejected(recent=self.seed.iloc[-100:-1])
        disjoint = self.recent.copy()
        disjoint.index += pd.Timedelta(days=400)
        self.rejected(recent=disjoint, observed=self.now + pd.Timedelta(days=401))

    def test_invalid_recent_utc_and_ohlc_cannot_authorize_cached_seed(self):
        self.publish()
        naive = self.recent.copy()
        naive.index = naive.index.tz_localize(None)
        self.rejected(recent=naive)
        invalid = self.recent.copy()
        invalid.iloc[0, invalid.columns.get_loc("high")] = 0
        self.rejected(recent=invalid)

    def test_restored_strategy_matches_native_full_frame_without_full_history_fetch(self):
        from scripts.c22_selected.history import load_seed
        self.publish()
        expected = SelectedBarCache()
        expected.append(self.full)
        strategy = SelectedStrategy(self.config, cache_path=self.path, fingerprint=FINGERPRINT)
        broker = NS(copy_rates_from_pos=Mock(side_effect=AssertionError("unexpected bootstrap")))
        with patch("scripts.c22_selected.strategy.copy_m1_rates", side_effect=AssertionError("full fetch")) as copy, patch(
            "scripts.c22_selected.strategy.load_seed", wraps=load_seed,
        ) as restore:
            actual = strategy.frame(self.recent, broker, "XAUUSDm", self.now)
            again = strategy.frame(self.recent, broker, "XAUUSDm", self.now)
        copy.assert_not_called()
        restore.assert_called_once()
        broker.copy_rates_from_pos.assert_not_called()
        pd.testing.assert_series_equal(actual.direction, expected.frame.direction,
                                       check_names=False, check_freq=False, check_exact=True)
        pd.testing.assert_series_equal(actual.macro_ema, expected.frame.macro_ema,
                                       check_names=False, check_freq=False, check_exact=True)
        self.assertIs(actual, again)

    def test_checkpoint_write_failure_does_not_disable_owned_position_manager(self):
        from scripts.c22_selected.runner import SelectedDemoRunner
        from tests.demo.test_c22_selected_runner import SelectedBroker
        from tests.demo.test_trial30_demo import policy
        broker = SelectedBroker()
        costs = policy() | {"reviewed_utc": broker.now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()}
        runner = SelectedDemoRunner(mt5=broker, expected_login=123, expected_server="Exness-Demo",
                                   journal_path=Path(self.temp.name) / "owned.sqlite3",
                                   config=self.config, cost_policy=costs, execute=True,
                                   cache_output=self.path)
        self.addCleanup(runner.close)
        with patch("scripts.c22_selected.strategy.save_manifest", side_effect=OSError("disk failure")):
            filled = runner.cycle(now=broker.now)
            managed = runner.cycle(now=broker.now)
        self.assertEqual(filled["status"], "FILLED", filled)
        self.assertEqual(managed["status"], "MANAGING", managed)
        self.assertEqual(managed["owned_position_protection"], "confirmed", managed)
        self.assertIsNotNone(runner.journal.get("active"))
        self.assertEqual(runner.strategy.history_seed_status, "checkpoint_failed")
        self.assertEqual(broker.order_send.call_count, 1)


if __name__ == "__main__":
    unittest.main()
