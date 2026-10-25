"""Demo trial cost assumptions bind fresh broker facts without swap entitlement."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from types import SimpleNamespace
import unittest
from typing import Any

from scripts.c22_selected.trial_costs import build_trial_policy
from scripts.demo_runtime.costs import validate_policy


NOW = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)


def broker_fixture() -> dict[str, Any]:
    captured = NOW - timedelta(seconds=1)
    return {
        "captured_utc": captured.isoformat(), "account_fingerprint": "1234567890abcdef",
        "account_type": "Standard Demo", "demo_verified": True, "hedging_verified": True,
        "positions": 0, "orders": 0, "symbol": "XAUUSDm", "order_send_called": False,
        "account": {"currency": "USD", "balance": 204.2, "equity": 204.2},
        "terminal": {"connected": True},
        "spec": {"currency_profit": "USD", "trade_contract_size": 100.0,
                 "trade_tick_size": 0.001, "point": 0.001, "volume_min": 0.01,
                 "volume_max": 200.0, "volume_step": 0.01, "swap_mode": 1,
                 "swap_long": -490.8, "swap_short": 0.0, "swap_rollover3days": 3},
        "history_complete": True, "history_start_utc": "1970-01-01T00:00:00+00:00",
        "history_end_utc": captured.isoformat(), "history_deals_total": 3,
        "history_deals": [
            {"ticket": 1, "type": 2, "time_msc": int((NOW - timedelta(days=2)).timestamp() * 1000),
             "profit": 200.0, "commission": 0.0, "swap": 0.0, "fee": 0.0},
            {"ticket": 2, "type": 1, "time_msc": int((NOW - timedelta(days=1)).timestamp() * 1000),
             "profit": 0.0, "commission": 0.0, "swap": 0.0, "fee": 0.0},
            {"ticket": 3, "type": 0, "time_msc": int((NOW - timedelta(hours=1)).timestamp() * 1000),
             "profit": 4.2, "commission": 0.0, "swap": 0.0, "fee": 0.0},
        ],
    }


def sources_fixture() -> dict[str, Any]:
    return {name: {"source": source, "checked_utc": (NOW - timedelta(hours=1)).isoformat()}
            for name, source in {
                "tariff": "https://www.exness.com/standard-accounts/",
                "swap": "https://get.exness.help/hc/en-us/articles/360014709151-About-swap",
                "calendar": "https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours",
            }.items()}


class TrialCostPolicyTests(unittest.TestCase):
    def test_regular_rates_and_dst_calendar_are_compatible_without_entitlement_claim(self):
        broker, sources = broker_fixture(), sources_fixture()
        original = deepcopy(broker)
        raw = json.dumps(broker, indent=2).encode()
        policy = build_trial_policy(raw, now=NOW, sources=sources)
        self.assertEqual(policy["status"], "CONSERVATIVE_REGULAR_SWAP_DEMO_ASSUMPTIONS")
        self.assertEqual(policy["swap_entitlement"], "UNKNOWN")
        self.assertEqual(policy["research_economic_qualification"], "COST_INCONCLUSIVE")
        self.assertFalse(policy["execution_authorized"])
        self.assertEqual(policy["account_evidence_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(policy["commission_per_lot"], 0)
        self.assertEqual(policy["slippage_allowance_price"], 0.1)
        self.assertEqual(policy["slippage_basis"], "declared_assumption")
        calendar = policy["evidence"]["swap_calendar"]["document"]
        self.assertEqual(len(calendar["days"]), 8)
        self.assertAlmostEqual(calendar["days"]["2026-10-29"]["buy"], -49.08)
        self.assertEqual(calendar["days"]["2026-10-29"]["sell"], 0.0)
        self.assertEqual(calendar["days"]["2026-10-31"]["buy"], 0.0)
        self.assertEqual(calendar["days"]["2026-10-30"]["rollover_utc"], "2026-10-30T21:00:00+00:00")
        self.assertEqual(calendar["days"]["2026-11-01"]["rollover_utc"], "2026-11-01T22:00:00+00:00")
        self.assertAlmostEqual(calendar["days"]["2026-11-04"]["buy"], -147.24)
        self.assertFalse(calendar["broker_holiday_exceptions_verified"])
        valid, reason = validate_policy(policy, fingerprint=broker["account_fingerprint"], now=NOW,
                                        strategy="c22h4", spec=SimpleNamespace(**broker["spec"]))
        self.assertTrue(valid, reason)
        self.assertEqual(broker, original)

    def test_stale_incomplete_or_unreconciled_broker_export_is_rejected(self):
        for failure in ("stale", "future", "naive", "not_demo", "not_hedging", "real_type", "position",
                        "order", "disconnected", "currency", "symbol", "send_called", "history_partial",
                        "history_start", "history_count", "history_empty", "balance", "equity", "duplicate"):
            with self.subTest(failure=failure):
                broker = broker_fixture()
                if failure in ("stale", "future", "naive"):
                    stamp = NOW - timedelta(minutes=6) if failure == "stale" else NOW + timedelta(seconds=1)
                    broker["captured_utc"] = stamp.replace(tzinfo=None).isoformat() if failure == "naive" else stamp.isoformat()
                elif failure == "not_demo":
                    broker["demo_verified"] = False
                elif failure == "not_hedging":
                    broker["hedging_verified"] = False
                elif failure == "real_type":
                    broker["account_type"] = "Standard Real"
                elif failure == "position":
                    broker["positions"] = 1
                elif failure == "order":
                    broker["orders"] = 1
                elif failure == "disconnected":
                    broker["terminal"]["connected"] = False
                elif failure == "currency":
                    broker["account"]["currency"] = "EUR"
                elif failure == "symbol":
                    broker["symbol"] = "XAUUSD247m"
                elif failure == "send_called":
                    broker["order_send_called"] = True
                elif failure == "history_partial":
                    broker["history_complete"] = False
                elif failure == "history_start":
                    broker["history_start_utc"] = (NOW - timedelta(days=2)).isoformat()
                elif failure == "history_count":
                    broker["history_deals_total"] = 2
                elif failure == "history_empty":
                    broker["history_deals"], broker["history_deals_total"] = [], 0
                elif failure == "balance":
                    broker["account"]["balance"] = broker["account"]["equity"] = 205
                elif failure == "equity":
                    broker["account"]["equity"] = 205
                else:
                    broker["history_deals"][-1]["ticket"] = 2
                with self.assertRaises(ValueError):
                    build_trial_policy(json.dumps(broker).encode(), now=NOW, sources=sources_fixture())

    def test_missing_or_unsupported_swap_metadata_never_becomes_zero(self):
        for field, value in (("swap_long", None), ("swap_short", None), ("swap_long", float("nan")),
                             ("swap_short", True), ("point", 0), ("trade_contract_size", 0),
                             ("swap_mode", 0), ("swap_rollover3days", 5), ("currency_profit", "EUR")):
            with self.subTest(field=field, value=value):
                broker = broker_fixture()
                broker["spec"][field] = value
                with self.assertRaises(ValueError):
                    build_trial_policy(json.dumps(broker).encode(), now=NOW, sources=sources_fixture())

    def test_charged_standard_deal_contradicts_zero_commission_assumption(self):
        for field in ("commission", "fee"):
            with self.subTest(field=field):
                broker = broker_fixture()
                broker["history_deals"][-1][field] = -0.1
                broker["account"]["balance"] = broker["account"]["equity"] = 204.1
                with self.assertRaisesRegex(ValueError, "actual_charges_contradict"):
                    build_trial_policy(json.dumps(broker).encode(), now=NOW, sources=sources_fixture())

    def test_sources_require_fresh_dated_official_urls(self):
        for kind in ("tariff", "swap", "calendar"):
            for failure in ("stale", "future", "naive", "third_party", "url_credentials"):
                with self.subTest(kind=kind, failure=failure):
                    sources = sources_fixture()
                    if failure == "stale":
                        sources[kind]["checked_utc"] = (NOW - timedelta(hours=25)).isoformat()
                    elif failure == "future":
                        sources[kind]["checked_utc"] = (NOW + timedelta(seconds=1)).isoformat()
                    elif failure == "naive":
                        sources[kind]["checked_utc"] = NOW.replace(tzinfo=None).isoformat()
                    elif failure == "third_party":
                        sources[kind]["source"] = "https://example.com/exness"
                    else:
                        sources[kind]["source"] = "https://username@www.exness.com/standard-accounts/"
                    with self.assertRaises(ValueError):
                        build_trial_policy(json.dumps(broker_fixture()).encode(), now=NOW, sources=sources)

    def test_missing_input_metadata_is_a_rejection_not_a_zero_fallback(self):
        broker = broker_fixture()
        del broker["spec"]["swap_short"]
        with self.assertRaisesRegex(ValueError, "trial_cost_evidence_missing_or_malformed"):
            build_trial_policy(json.dumps(broker).encode(), now=NOW, sources=sources_fixture())

    def test_malformed_deal_type_or_outside_declared_history_window_is_rejected(self):
        for failure in ("string_type", "bool_type", "future", "outside_end"):
            with self.subTest(failure=failure):
                broker = broker_fixture()
                if failure in ("string_type", "bool_type"):
                    broker["history_deals"][-1]["type"] = "0" if failure == "string_type" else False
                elif failure == "future":
                    broker["history_deals"][-1]["time_msc"] = int((NOW + timedelta(seconds=1)).timestamp() * 1000)
                else:
                    broker["history_end_utc"] = (NOW - timedelta(minutes=2)).isoformat()
                    broker["history_deals"][-1]["time_msc"] = int((NOW - timedelta(minutes=1)).timestamp() * 1000)
                with self.assertRaises(ValueError):
                    build_trial_policy(json.dumps(broker).encode(), now=NOW, sources=sources_fixture())
