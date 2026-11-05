"""Cost rejection attribution must not change existing admission economics."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from scripts.demo_runtime import costs
from scripts.c22_selected.runner import SelectedDemoRunner
from tests.demo.test_c22_selected_runner import SelectedBroker, selected_config
from tests.demo.test_trial30_demo import policy


NOW = datetime(2026, 10, 27, 8, 30, tzinfo=timezone.utc)
FIELDS = dict(
    trade_contract_size=100.0,
    trade_tick_size=0.001,
    point=0.001,
    volume_min=0.01,
    volume_max=100.0,
    volume_step=0.01,
    swap_mode=1,
    swap_long=-490.8,
    swap_short=0.0,
    swap_rollover3days=3,
)


def rebind(raw, name):
    item = raw["evidence"][name]
    item["sha256"] = hashlib.sha256(
        json.dumps(item["document"], sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def v2_policy(now=NOW, fields=None):
    raw = policy() | dict(version=2, reviewed_utc=now.isoformat())
    fields = deepcopy(FIELDS if fields is None else fields)
    documents = dict(
        tariff=dict(source="fixture", commission_per_lot=0.0, unit="USD_per_lot_round_trip"),
        spec=dict(source="fixture", fields=fields),
        swap_calendar=dict(
            source="fixture",
            unit="USD_per_lot",
            days={
                now.date().isoformat(): dict(
                    rollover_utc=now.replace(hour=21).isoformat(), buy=-49.08, sell=0.0
                ),
            },
        ),
    )
    raw["evidence"] = {name: dict(document=doc) for name, doc in documents.items()}
    for name in documents:
        rebind(raw, name)
    return raw


class CostDiagnosticsTests(unittest.TestCase):
    def validate(self, raw=None, *, now=NOW, spec=None, **overrides):
        raw = v2_policy() if raw is None else raw
        diagnostic = {"prior_failure": "must_not_survive"}
        result = costs.validate_policy(
            raw,
            fingerprint=policy()["account_fingerprint"],
            now=now,
            strategy="c22h4",
            spec=spec,
            diagnostics=diagnostic,
            **overrides,
        )
        return result, diagnostic

    def test_exact_spec_field_failure_preserves_legacy_refusal_and_safe_numeric_facts(self):
        for key, expected in FIELDS.items():
            with self.subTest(field=key):
                fields = dict(FIELDS, **{key: expected + 1})
                (cost, status), detail = self.validate(spec=NS(**fields))
                self.assertEqual((cost, status), ({}, "invalid_or_stale"))
                self.assertEqual(
                    detail,
                    dict(
                        stage="cost.spec",
                        code="cost_spec_mismatch",
                        field=key,
                        expected=expected,
                        observed=expected + 1,
                    ),
                )
                self.assertNotIn("prior_failure", detail)

    def test_equal_spec_and_optional_no_spec_preserve_original_valid_result(self):
        raw = v2_policy()
        before = deepcopy(raw)
        for spec in (None, NS(**FIELDS)):
            with self.subTest(spec_provided=spec is not None):
                (result, status), detail = self.validate(raw, spec=spec)
                self.assertEqual(status, "attested_demo_assumptions")
                self.assertEqual(result, raw)
                self.assertEqual(detail, {})
        self.assertEqual(raw, before)
        legacy, legacy_status = costs.validate_policy(
            raw,
            fingerprint=raw["account_fingerprint"],
            now=NOW,
            strategy="c22h4",
            spec=NS(**FIELDS),
        )
        self.assertEqual(legacy, raw)
        self.assertEqual(legacy_status, "attested_demo_assumptions")

    def test_policy_expiry_future_and_timezone_boundaries_remain_exact(self):
        for now, accepted, code in (
            (NOW, True, None),
            (NOW + timedelta(hours=168), True, None),
            (NOW + timedelta(hours=168, microseconds=1), False, "cost_policy_expired"),
            (NOW - timedelta(microseconds=1), False, "cost_policy_review_future"),
        ):
            with self.subTest(now=now):
                (result, status), detail = self.validate(now=now, spec=NS(**FIELDS))
                self.assertEqual(bool(result), accepted)
                self.assertEqual(
                    status, "attested_demo_assumptions" if accepted else "invalid_or_stale"
                )
                self.assertEqual(detail.get("code"), code)
        raw = v2_policy()
        raw["reviewed_utc"] = NOW.replace(tzinfo=None).isoformat()
        (result, status), detail = self.validate(raw)
        self.assertEqual((result, status), ({}, "invalid_or_stale"))
        self.assertEqual(detail["code"], "cost_policy_review_timezone_invalid")

    def test_base_policy_failures_identify_guard_without_private_values(self):
        cases = (
            ("version", 99, "cost_policy_version_unsupported"),
            ("account_fingerprint", "private-fixture-fingerprint", "cost_policy_account_mismatch"),
            ("account_type", "private-fixture-account", "cost_policy_account_type_invalid"),
            ("commission_unit", "private-fixture-unit", "cost_policy_commission_unit_invalid"),
            ("commission_from_symbol_info", True, "cost_policy_commission_basis_invalid"),
            ("slippage_basis", "private-fixture-basis", "cost_policy_slippage_basis_invalid"),
            ("source", "", "cost_policy_source_missing"),
            ("commission_source", "", "cost_policy_commission_source_missing"),
            (
                "account_evidence_sha256",
                "private-fixture-hash",
                "cost_policy_account_evidence_invalid",
            ),
            ("commission_per_lot", -0.1, "cost_policy_commission_invalid"),
            ("commission_per_lot", float("nan"), "cost_policy_commission_invalid"),
            ("slippage_allowance_price", 0, "cost_policy_slippage_invalid"),
            ("slippage_allowance_price", float("inf"), "cost_policy_slippage_invalid"),
            ("spread_buffer", 0.01, "cost_policy_spread_buffer_invalid"),
            ("reviewed_utc", "private-fixture-timestamp", "cost_policy_input_invalid"),
        )
        for key, value, code in cases:
            with self.subTest(key=key, value_type=type(value).__name__):
                raw = v2_policy()
                raw[key] = value
                before = deepcopy(raw)
                (result, status), detail = self.validate(raw)
                self.assertEqual((result, status), ({}, "invalid_or_stale"))
                self.assertEqual(detail["code"], code)
                self.assertNotIn("private-fixture", json.dumps(detail, allow_nan=False))
                # Use serialization for NaN fixture equality, not NaN != NaN.
                self.assertEqual(
                    json.dumps(raw, sort_keys=True), json.dumps(before, sort_keys=True)
                )
        detail = {}
        self.assertEqual(
            costs.validate_policy(None, fingerprint="private-fixture", now=NOW, diagnostics=detail),
            ({}, "missing"),
        )
        self.assertEqual(detail, {"stage": "cost.policy", "code": "cost_policy_missing"})

    def test_invalid_evidence_reports_stage_without_private_document_payload(self):
        cases = (
            ("hash", "cost_evidence_hash_mismatch"),
            ("source", "cost_evidence_source_missing"),
            ("required_field", "cost_spec_required_fields_missing"),
            ("calendar_timezone", "cost_calendar_rollover_invalid"),
            ("calendar_unit", "cost_calendar_contract_invalid"),
        )
        for mode, code in cases:
            with self.subTest(mode=mode):
                raw = v2_policy()
                raw["evidence"]["spec"]["document"]["source"] = "secret-fixture-source"
                rebind(raw, "spec")
                if mode == "hash":
                    raw["evidence"]["spec"]["sha256"] = "0" * 64
                elif mode == "source":
                    raw["evidence"]["spec"]["document"]["source"] = ""
                    rebind(raw, "spec")
                elif mode == "required_field":
                    del raw["evidence"]["spec"]["document"]["fields"]["volume_step"]
                    rebind(raw, "spec")
                elif mode == "calendar_timezone":
                    raw["evidence"]["swap_calendar"]["document"]["days"][NOW.date().isoformat()][
                        "rollover_utc"
                    ] = "2026-10-27T21:00:00"
                    rebind(raw, "swap_calendar")
                else:
                    raw["evidence"]["swap_calendar"]["document"]["unit"] = "private-fixture-unit"
                    rebind(raw, "swap_calendar")
                (result, status), detail = self.validate(raw, spec=NS(**FIELDS))
                self.assertEqual((result, status), ({}, "invalid_or_stale"))
                self.assertEqual(detail["code"], code)
                encoded = json.dumps(detail, allow_nan=False)
                self.assertNotIn("secret-fixture-source", encoded)
                self.assertNotIn("private-fixture-unit", encoded)
                self.assertNotIn(raw["account_fingerprint"], encoded)

    def test_missing_nonfinite_and_unsafe_spec_values_never_leak_payload(self):
        for value, expected in (
            (None, {"state": "MISSING"}),
            (float("nan"), {"state": "NONFINITE"}),
            ("secret-fixture-live-spec", {"state": "INVALID"}),
        ):
            with self.subTest(value_type=type(value).__name__):
                spec = NS(**(FIELDS | {"swap_long": value}))
                (result, status), detail = self.validate(spec=spec)
                self.assertEqual((result, status), ({}, "invalid_or_stale"))
                self.assertEqual(detail["field"], "swap_long")
                self.assertEqual(detail["observed"], expected)
                self.assertNotIn("secret-fixture", json.dumps(detail, allow_nan=False))

    def test_spec_getter_failure_preserves_original_exception_and_safe_origin(self):
        class GetterFailure(NS):
            @property
            def swap_long(self):
                raise RuntimeError("secret-fixture-getter")

        spec = GetterFailure(**{k: v for k, v in FIELDS.items() if k != "swap_long"})
        detail = {}
        with self.assertRaisesRegex(RuntimeError, "secret-fixture-getter") as caught:
            costs.validate_policy(
                v2_policy(),
                fingerprint=policy()["account_fingerprint"],
                now=NOW,
                strategy="c22h4",
                spec=spec,
                diagnostics=detail,
            )
        self.assertEqual(
            detail,
            dict(
                stage="cost.spec",
                code="cost_spec_read_failed",
                field="swap_long",
                exception_class="RuntimeError",
            ),
        )
        self.assertEqual(caught.exception.diagnostics, detail)
        self.assertNotIn("secret-fixture", json.dumps(detail, allow_nan=False))

    def test_first_spec_failure_keeps_short_circuit_without_second_attribute_read(self):
        class ShortCircuit(NS):
            @property
            def swap_long(self):
                raise RuntimeError("must-not-read-later-field")

        spec = ShortCircuit(**{k: v for k, v in FIELDS.items() if k != "swap_long"})
        spec.trade_contract_size = 99
        (result, status), detail = self.validate(spec=spec)
        self.assertEqual((result, status), ({}, "invalid_or_stale"))
        self.assertEqual(detail["field"], "trade_contract_size")

    def test_previously_caught_spec_getter_errors_keep_refusal_and_operation_detail(self):
        for error_type in (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            with self.subTest(error_type=error_type.__name__):

                class GetterFailure(NS):
                    @property
                    def swap_long(self):
                        raise error_type("private-fixture-getter")

                spec = GetterFailure(**{k: v for k, v in FIELDS.items() if k != "swap_long"})
                (result, status), detail = self.validate(spec=spec)
                self.assertEqual((result, status), ({}, "invalid_or_stale"))
                if error_type is AttributeError:
                    # getattr(spec, key, None) intentionally treats this as missing.
                    expected = dict(
                        stage="cost.spec",
                        code="cost_spec_mismatch",
                        field="swap_long",
                        expected=-490.8,
                        observed={"state": "MISSING"},
                    )
                else:
                    expected = dict(
                        stage="cost.spec",
                        code="cost_spec_read_failed",
                        field="swap_long",
                        exception_class=error_type.__name__,
                    )
                self.assertEqual(detail, expected)
                self.assertNotIn("private-fixture", json.dumps(detail))

    def test_unknown_stored_spec_key_rejects_without_logging_key_or_value(self):
        raw = v2_policy(fields=FIELDS | {"secret-fixture-key": 7.0})
        (result, status), detail = self.validate(raw, spec=NS(**FIELDS))
        self.assertEqual((result, status), ({}, "invalid_or_stale"))
        self.assertEqual(
            detail,
            dict(stage="cost.spec", code="cost_spec_mismatch", field="UNRECOGNIZED_SPEC_FIELD"),
        )
        self.assertNotIn("secret-fixture", json.dumps(detail))

    def test_public_admission_keeps_raw_reason_and_carries_same_read_spec_detail(self):
        with TemporaryDirectory() as tmp:
            sdk = SelectedBroker()
            for key, value in FIELDS.items():
                setattr(sdk.info, key, value)
            raw = v2_policy(sdk.now)
            sdk.info.swap_long = -500.0
            sdk.symbol_info = Mock(wraps=sdk.symbol_info)
            runner = SelectedDemoRunner(
                mt5=sdk,
                expected_login=123,
                expected_server="Exness-Demo",
                journal_path=Path(tmp) / "journal.sqlite3",
                config=selected_config(),
                cost_policy=raw,
                execute=True,
            )
            try:
                runner._started = 100
                with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
                    with self.assertRaises(ValueError) as caught:
                        runner._cycle(sdk.now)
                self.assertEqual(str(caught.exception), "cost_policy_invalid_or_stale")
                self.assertEqual(
                    caught.exception.diagnostics,
                    dict(
                        stage="cost.spec",
                        code="cost_spec_mismatch",
                        field="swap_long",
                        expected=-490.8,
                        observed=-500.0,
                    ),
                )
                self.assertEqual(sdk.symbol_info.call_count, 1)
                sdk.order_check.assert_not_called()
                sdk.order_send.assert_not_called()
                self.assertIsNone(runner.journal.get("active"))
                self.assertIsNone(runner.journal.get("last_bar"))
                self.assertIsNotNone(runner.journal.get("last_signal_bar"))
                sdk.symbol_info.reset_mock()
                with patch("scripts.demo_runtime.runner.time.monotonic", return_value=100):
                    result = runner.cycle(now=sdk.now)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["reason"], "cost_policy_invalid_or_stale")
                failure = result["failure"]
                self.assertEqual(failure["code"], "cost_spec_mismatch")
                self.assertEqual(failure["stage"], "cost.spec")
                self.assertEqual(failure["details"], caught.exception.diagnostics)
                self.assertTrue(failure["correlation_id"])
                self.assertEqual(runner.journal.get("last_result")["failure"], failure)
                self.assertEqual(sdk.symbol_info.call_count, 1)
                sdk.order_check.assert_not_called()
                sdk.order_send.assert_not_called()
                self.assertIsNone(runner.journal.get("active"))
            finally:
                runner.close()


if __name__ == "__main__":
    unittest.main()
