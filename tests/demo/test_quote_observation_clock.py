"""Quote freshness uses elapsed SDK time without changing strategy/day clocks."""

from datetime import timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from scripts.c22_selected.runner import SelectedDemoRunner
from scripts.demo_runtime.broker import BrokerView
from tests.demo.test_c22_selected_runner import SelectedBroker, selected_config
from tests.demo.test_trial30_demo import NOW, policy


class QuoteObservationClockTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = 100.0

    def runner(self, sdk, *, execute=False):
        costs = policy() | {
            "reviewed_utc": sdk.now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        }
        runner = SelectedDemoRunner(
            mt5=sdk,
            expected_login=123,
            expected_server="Exness-Demo",
            journal_path=Path(self.temp.name) / "clock.sqlite3",
            config=selected_config(),
            cost_policy=costs,
            execute=execute,
        )
        self.addCleanup(runner.close)
        return runner

    def view(self, *, latency, age):
        observed = NOW + timedelta(seconds=latency)
        tick = NS(
            bid=4000.0,
            ask=4000.24,
            time_msc=int((observed - timedelta(seconds=age)).timestamp() * 1000),
        )

        def quote(_symbol):
            self.clock += latency
            return tick

        view = BrokerView(
            NS(symbol_info_tick=quote), 123, "Exness-Demo", "XAUUSDm", "fixture", None
        )
        return view, tick, observed

    def test_sdk_read_latency_accepts_fresh_tick_after_request_started(self):
        view, tick, _ = self.view(latency=0.25, age=0.05)
        with patch("scripts.demo_runtime.broker.time.monotonic", side_effect=lambda: self.clock):
            self.assertIs(view._quote(NOW), tick)

    def test_public_cycle_counts_pre_quote_sdk_latency_without_resetting_day_clock(self):
        sdk = SelectedBroker()
        original_spec = sdk.symbol_info
        first_tick = dict(time_msc=sdk.tick.time_msc, bid=sdk.tick.bid, ask=sdk.tick.ask)
        # Current quote advances; historical first quote remains a real earlier tick.
        sdk.copy_ticks_range = lambda *args: [first_tick]

        def slow_spec(symbol):
            self.clock += 0.2
            sdk.tick.time_msc = int((sdk.now + timedelta(milliseconds=100)).timestamp() * 1000)
            return original_spec(symbol)

        sdk.symbol_info = slow_spec
        runner = self.runner(sdk)
        with patch("scripts.demo_runtime.runner.time.monotonic", side_effect=lambda: self.clock):
            result = runner.cycle(now=sdk.now)
        self.assertEqual(result["status"], "SHADOW_ADMIT", result)
        self.assertEqual(result["captured_utc"], sdk.now.isoformat())
        self.assertEqual(runner.journal.get("day")["day"], sdk.now.date().isoformat())
        sdk.order_send.assert_not_called()

    def test_presend_accepts_fresh_quote_created_during_sdk_read(self):
        sdk = SelectedBroker()
        runner = self.runner(sdk, execute=True)
        calls = 0

        def quote(_symbol):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.clock += 0.25
                return NS(
                    time_msc=int((sdk.now + timedelta(milliseconds=200)).timestamp() * 1000),
                    bid=sdk.tick.bid,
                    ask=sdk.tick.ask,
                )
            return sdk.tick

        sdk.symbol_info_tick = quote
        sdk.order_send.side_effect = lambda request: None
        with patch("scripts.demo_runtime.runner.time.monotonic", side_effect=lambda: self.clock):
            result = runner.cycle(now=sdk.now)
        self.assertEqual(result["status"], "UNKNOWN", result)
        self.assertEqual(sdk.order_send.call_count, 1)
        self.assertEqual(runner.journal.get("active")["status"], "UNKNOWN")

    def test_presend_quote_read_crossing_90_second_window_never_sends(self):
        sdk = SelectedBroker()
        runner = self.runner(sdk, execute=True)
        calls = 0

        def quote(_symbol):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.clock += 90
                return NS(
                    time_msc=int((sdk.now + timedelta(seconds=89.9)).timestamp() * 1000),
                    bid=sdk.tick.bid,
                    ask=sdk.tick.ask,
                )
            return sdk.tick

        sdk.symbol_info_tick = quote
        with patch("scripts.demo_runtime.runner.time.monotonic", side_effect=lambda: self.clock):
            result = runner.cycle(now=sdk.now)
        self.assertEqual(result.get("reason"), "entry_window_expired", result)
        sdk.order_send.assert_not_called()
        self.assertIsNone(runner.journal.get("active"))

    def test_observed_age_over_60_seconds_is_rejected_after_slow_sdk_read(self):
        view, _, _ = self.view(latency=2.0, age=60.001)
        with patch("scripts.demo_runtime.broker.time.monotonic", side_effect=lambda: self.clock):
            with self.assertRaisesRegex(ValueError, "quote_stale"):
                view._quote(NOW)

    def test_genuinely_future_tick_is_rejected_against_post_read_clock(self):
        view, _, _ = self.view(latency=0.25, age=-0.1)
        with patch("scripts.demo_runtime.broker.time.monotonic", side_effect=lambda: self.clock):
            with self.assertRaisesRegex(ValueError, "quote_stale"):
                view._quote(NOW)

    def test_exact_60_second_observed_age_remains_valid(self):
        view, tick, _ = self.view(latency=0.25, age=60.0)
        with patch("scripts.demo_runtime.broker.time.monotonic", side_effect=lambda: self.clock):
            self.assertIs(view._quote(NOW), tick)

    def test_quote_clock_rejects_naive_non_utc_and_backwards_elapsed_time(self):
        for stamp in (NOW.replace(tzinfo=None), NOW.astimezone(timezone(timedelta(hours=7)))):
            with self.subTest(stamp=stamp):
                view, _, _ = self.view(latency=0, age=0)
                with self.assertRaisesRegex(ValueError, "quote_clock_invalid"):
                    view._quote(stamp)
        view, _, _ = self.view(latency=0, age=0)
        with patch("scripts.demo_runtime.broker.time.monotonic", side_effect=[100.0, 99.0]):
            with self.assertRaisesRegex(ValueError, "quote_clock_invalid"):
                view._quote(NOW)

    def test_public_cycle_reports_rejected_tick_age_without_loosening_freshness(self):
        sdk = SelectedBroker()
        sdk.tick.time_msc = int((sdk.now + timedelta(seconds=1)).timestamp() * 1000)
        runner = self.runner(sdk)
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=self.clock):
            result = runner.cycle(now=sdk.now)
        self.assertEqual(result["reason"], "quote_stale", result)
        self.assertEqual(result["quote_rejection"], "future")
        self.assertEqual(result["quote_age_seconds"], -1.0)
        self.assertEqual(result["quote_observed_utc"], sdk.now.isoformat())
        self.assertEqual(result["quote_requested_utc"], sdk.now.isoformat())
        sdk.order_send.assert_not_called()

    def test_active_manager_accepts_fresh_quote_during_read_without_new_entry(self):
        sdk = SelectedBroker()
        runner = self.runner(sdk, execute=True)
        self.assertEqual(runner.cycle(now=sdk.now)["status"], "FILLED")
        self.assertEqual(sdk.order_send.call_count, 1)

        def quote(_symbol):
            self.clock += 0.25
            return NS(
                time_msc=int((sdk.now + timedelta(milliseconds=200)).timestamp() * 1000),
                bid=sdk.tick.bid,
                ask=sdk.tick.ask,
            )

        sdk.symbol_info_tick = quote
        with patch("scripts.demo_runtime.runner.time.monotonic", side_effect=lambda: self.clock):
            result = runner.cycle(now=sdk.now)
        self.assertEqual(result["status"], "MANAGING", result)
        self.assertEqual(sdk.order_send.call_count, 1)
        self.assertIsNotNone(runner.journal.get("active"))


if __name__ == "__main__":
    unittest.main()
