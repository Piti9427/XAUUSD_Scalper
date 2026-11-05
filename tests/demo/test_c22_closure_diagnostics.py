"""Canonical entry refusals survive public cycles without weakening admission."""

import ast
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.demo_runtime.diagnostics import RESUME, public_reason
from tests.demo import test_c22_identity_diagnostics as fixtures
from tests.demo.test_c22_selected_runner import SelectedBroker


class CanonicalRefusalDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.helper = fixtures.IdentityDiagnosticsTests()
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)

    def cycle(self, broker, name):
        runner = self.helper.runner(broker, name)
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            result = runner.cycle(now=broker.now)
        return runner, result

    def assert_refusal(self, broker, name, reason, origin_path):
        runner, result = self.cycle(broker, name)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], reason)
        self.assertEqual(result["failure"]["code"], reason)
        self.assertEqual(result["failure"]["classification"], "GATE_BLOCK")
        self.assertIn(
            origin_path,
            {
                frame["path"]
                for cause in result["failure"]["cause_chain"]
                for frame in cause["frames"]
            },
        )
        item = result["entry_availability"]["known_blockers"][0]
        self.assertEqual(item["code"], reason)
        self.assertEqual(item["resume_condition"], RESUME[reason][1])
        self.assertNotEqual(item["resume_condition"], "inspect_recorded_runtime_failure")
        self.assertEqual(result["entry_availability"]["downstream_admission"], "NOT_PROVEN")
        self.assertEqual(runner.journal.get("last_result")["failure"], result["failure"])
        self.assertIsNone(runner.journal.get("active"))
        self.assertIsNone(runner.journal.get("selected_last_loss_ms"))
        broker.order_check.assert_not_called()
        broker.order_send.assert_not_called()
        return runner, result

    def test_real_native_geometry_refusals_keep_exact_cause_and_never_send(self):
        for name in ("risk_cap", "margin", "invalid_stop"):
            with self.subTest(name=name):
                broker = SelectedBroker()
                if name == "risk_cap":
                    broker.info.trade_contract_size = 1000
                elif name == "margin":
                    broker.account.leverage = 0.01
                else:
                    broker.tick.ask = broker.tick.bid + 100
                self.assert_refusal(broker, name, name, "scripts/c22_selected/strategy.py")

    def test_real_m1_refusals_keep_exact_cause_and_never_send(self):
        for name, reason in (
            ("empty", "missing M1 bars"),
            ("one_minute", "no complete M15 bars from M1"),
            ("invalid_ohlc", "invalid_closed_M1_OHLC"),
        ):
            with self.subTest(name=name):
                broker = SelectedBroker()
                if name == "empty":
                    broker.rates = []
                elif name == "one_minute":
                    broker.rates = broker.rates[-1:]
                else:
                    broker.rates[-1]["high"] = 0
                path = (
                    "scripts/pure_b1/broker_data.py"
                    if name == "one_minute"
                    else "scripts/demo_runtime/market_data.py"
                )
                self.assert_refusal(broker, name, reason, path)

    def test_real_native_risk_refusal_recovers_only_when_original_geometry_passes(self):
        broker = SelectedBroker()
        broker.info.trade_contract_size = 1000
        runner, _ = self.assert_refusal(
            broker, "risk-recovery", "risk_cap", "scripts/c22_selected/strategy.py"
        )
        broker.info.trade_contract_size = 100
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            admitted = runner.cycle(now=broker.now)
            managing = runner.cycle(now=broker.now)
        self.assertEqual(admitted["status"], "FILLED")
        self.assertEqual(managing["status"], "MANAGING")
        self.assertEqual(broker.order_send.call_count, 1)
        self.assertEqual(runner.journal.get("active")["request"]["volume"], 0.01)

    def test_fixed_transitive_helper_codes_have_resume_while_untrusted_errors_stay_private(self):
        root = Path(__file__).resolve().parents[2]
        targets = {
            "scripts/demo_runtime/market_data.py": {"completed_m15_from_m1"},
            "scripts/pure_b1/broker_data.py": {"completed_m15_from_m1", "_closed_m1"},
            "scripts/research/breakout_entry.py": {"prepare_entry"},
        }
        codes = set()
        for relative, names in targets.items():
            tree = ast.parse((root / relative).read_text())
            functions = [
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name in names
            ]
            for node in (node for function in functions for node in ast.walk(function)):
                if (
                    isinstance(node, ast.Raise)
                    and isinstance(node.exc, ast.Call)
                    and isinstance(node.exc.func, ast.Name)
                    and node.exc.func.id == "ValueError"
                    and node.exc.args
                    and isinstance(node.exc.args[0], ast.Constant)
                    and isinstance(node.exc.args[0].value, str)
                ):
                    codes.add(node.exc.args[0].value)
                elif (
                    isinstance(node, ast.Return)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    codes.add(node.value.value)
        self.assertTrue({"risk_cap", "margin", "invalid_stop"}.issubset(codes))
        for code in sorted(codes):
            with self.subTest(code=code):
                self.assertIn(code, RESUME)
                self.assertEqual(public_reason(ValueError(code)), code)
                self.assertTrue(RESUME[code][1])
        self.assertEqual(public_reason(ValueError("password=PRIVATE-SDK-secret")), "ValueError")
        broker = SelectedBroker()
        broker.copy_rates_from_pos = lambda *args: (_ for _ in ()).throw(
            ValueError("password=PRIVATE-SDK-secret")
        )
        runner, result = self.cycle(broker, "private-sdk")
        self.assertEqual(result["reason"], "ValueError")
        self.assertEqual(result["failure"]["classification"], "FAULT")
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertIsNone(runner.journal.get("active"))
        broker.order_send.assert_not_called()

    def test_native_unknown_fill_keeps_specific_reason_and_never_resends(self):
        broker = SelectedBroker()
        original_send = broker.send

        def fill_without_deal(request):
            response = original_send(request)
            broker.deals[:] = [deal for deal in broker.deals if deal.type not in (0, 1)]
            return response

        broker.order_send.side_effect = fill_without_deal
        runner, result = self.cycle(broker, "missing-opening-deal")
        self.assertEqual(result["status"], "UNKNOWN", result)
        self.assertEqual(result["reason"], "awaiting_fill_deal_costs")
        blockers = {item["code"]: item for item in result["entry_availability"]["known_blockers"]}
        self.assertIn("awaiting_fill_deal_costs", blockers)
        self.assertIn("no_resend", blockers["awaiting_fill_deal_costs"]["resume_condition"])
        with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
            again = runner.cycle(now=broker.now)
        self.assertEqual(again["reason"], "awaiting_fill_deal_costs")
        self.assertIsNotNone(runner.journal.get("active"))
        self.assertEqual(broker.order_send.call_count, 1)

    def test_all_fixed_lifecycle_return_reasons_have_specific_resume(self):
        root = Path(__file__).resolve().parents[2]
        tree = ast.parse((root / "scripts/demo_runtime/lifecycle.py").read_text())
        reasons = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "reason"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                    ):
                        reasons.add(value.value)
        self.assertIn("awaiting_fill_deal_costs", reasons)
        self.assertIn("safety_close_position_changed", reasons)
        self.assertEqual(reasons - RESUME.keys(), set())


if __name__ == "__main__":
    unittest.main()
