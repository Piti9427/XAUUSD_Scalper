"""Compatibility at legacy imports and public runner/CLI interfaces."""

import importlib
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.c22h4.runner import C22H4DemoRunner
from scripts.demo_runtime.runner import DemoRunner
from scripts.trial30.runner import Trial30DemoRunner
from scripts.trial30.strategy import Trial30Strategy
from tests.demo.test_trial30_demo import Broker, NOW, policy


class DemoRuntimeCompatibilityTests(unittest.TestCase):
    def test_legacy_modules_share_implementation_and_patch_targets(self):
        for old, new in (
            ("scripts.trial30.broker", "scripts.demo_runtime.broker"),
            ("scripts.trial30.journal", "scripts.demo_runtime.journal"),
            ("scripts.trial30.costs", "scripts.demo_runtime.costs"),
            ("scripts.ops.mt5_wine_trial30", "scripts.demo_runtime.cli"),
            ("scripts.ops.run_trial30_wine", "scripts.demo_runtime.host"),
            ("scripts.ops.trial30_status", "scripts.demo_runtime.status"),
        ):
            with self.subTest(module=old):
                self.assertIs(importlib.import_module(old), importlib.import_module(new))
        from scripts.demo_runtime import cli

        with patch("scripts.ops.mt5_wine_trial30.clock_now", return_value=NOW):
            self.assertEqual(cli.clock_now(), NOW)

    def test_runner_adapters_keep_constructor_and_direct_c22_base(self):
        self.assertEqual(C22H4DemoRunner.__bases__, (DemoRunner,))
        signature = inspect.signature(Trial30DemoRunner)
        self.assertEqual(
            list(signature.parameters),
            [
                "mt5",
                "expected_login",
                "expected_server",
                "journal_path",
                "cost_policy",
                "execute",
                "notify",
                "symbol",
                "strategy",
                "account_guard_dir",
            ],
        )
        self.assertIsNone(signature.parameters["strategy"].default)
        self.assertFalse(signature.parameters["execute"].default)
        self.assertEqual(signature.parameters["symbol"].default, "XAUUSDm")

    def test_injected_strategy_matches_rollback_cycle_and_persistence(self):
        # Compare independent brokers/journals through public cycles, including
        # ambiguous send + restart. No terminal or external services involved.
        for mode in ("shadow", "fill", "rejected", "ambiguous", "blocked"):
            observations = []
            for direct in (False, True):
                with self.subTest(mode=mode, direct=direct), TemporaryDirectory() as directory:
                    broker = Broker()
                    if mode == "ambiguous":
                        broker.order_send.side_effect = TimeoutError("synthetic timeout")
                    elif mode == "rejected":
                        broker.order_check.return_value.retcode = 10013
                    elif mode == "blocked":
                        broker.account.trade_mode = 2
                    path = Path(directory) / "journal.sqlite3"
                    options = dict(
                        mt5=broker,
                        expected_login=123,
                        expected_server="Exness-Demo",
                        journal_path=path,
                        cost_policy=policy(),
                        execute=mode != "shadow",
                    )
                    events = []
                    factory = DemoRunner if direct else Trial30DemoRunner
                    strategy = Trial30Strategy()
                    runner = factory(**options, notify=events.append, strategy=strategy)
                    try:
                        self.assertIs(runner.strategy, strategy)
                        results = [runner.cycle(now=NOW)]
                    finally:
                        runner.close()
                    runner = factory(**options, notify=events.append, strategy=strategy)
                    try:
                        results.append(runner.cycle(now=NOW))
                        observations.append(
                            dict(
                                results=results,
                                orders=broker.order_send.call_args_list,
                                checks=broker.order_check.call_args_list,
                                kv=runner.journal.conn.execute(
                                    "SELECT * FROM kv ORDER BY key"
                                ).fetchall(),
                                outbox=runner.journal.conn.execute(
                                    "SELECT * FROM events ORDER BY id"
                                ).fetchall(),
                                events=events,
                            )
                        )
                    finally:
                        runner.close()
            self.assertEqual(observations[0], observations[1], mode)
            expected = {
                "shadow": "SHADOW_ADMIT",
                "fill": "FILLED",
                "rejected": "BLOCKED",
                "ambiguous": "UNKNOWN",
                "blocked": "BLOCKED",
            }
            self.assertEqual(observations[0]["results"][0]["status"], expected[mode])

    def test_legacy_monotonic_patch_reaches_both_collaborators(self):
        from scripts.demo_runtime import admission, runner

        with patch("scripts.trial30.runner.time.monotonic", return_value=123):
            self.assertEqual(admission.time.monotonic(), 123)
            self.assertEqual(runner.time.monotonic(), 123)


if __name__ == "__main__":
    unittest.main()
