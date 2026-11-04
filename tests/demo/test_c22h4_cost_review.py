"""Operator cost review cannot be replaced by timestamp renewal or input drift."""

from copy import deepcopy
from datetime import timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import tests.demo.test_c22h4_readiness as fixtures

MODULE = Path(__file__).resolve().parents[2] / "deploy/c22-demo/review_cost_policy.py"
SPEC = importlib.util.spec_from_file_location("c22_cost_review", MODULE)
reviewer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reviewer)


class CostReviewTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.MarketOpenReadinessTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        self.now = fixture.now
        self.draft = deepcopy(fixture.policy)
        self.draft.update(status="DRAFT_NOT_ATTESTED", reviewed_utc=None)
        self.broker = deepcopy(fixture.broker)
        self.broker["account"]["currency"] = "USD"
        self.broker["spec"].update(point=0.001, currency_profit="USD")
        self.draft["evidence"]["spec"]["document"]["fields"]["point"] = 0.001
        self.broker.update(
            symbol="XAUUSDm", history_deals=[dict(type=2, entry=0, commission=0, fee=0)]
        )
        days = self.draft["evidence"]["swap_calendar"]["document"]["days"]
        for offset in range(8):
            date = self.now + timedelta(days=offset)
            days[date.date().isoformat()] = dict(
                rollover_utc=date.replace(hour=21).isoformat(), buy=-49.08, sell=0
            )
        self.rehash()
        self.review = dict(
            reviewed_utc=self.now.isoformat(),
            sources_checked_utc=self.now.isoformat(),
            reviewed_by="operator fixture",
            review_note="Fixture review of tariff applicability, swap and dated notices",
            confirmations=dict.fromkeys(reviewer.CONFIRMATIONS, True),
        )

    def rehash(self):
        for item in self.draft["evidence"].values():
            item["sha256"] = hashlib.sha256(
                json.dumps(item["document"], sort_keys=True, allow_nan=False).encode()
            ).hexdigest()

    def run_review(self, *, rebind=True):
        draft, broker = json.dumps(self.draft).encode(), json.dumps(self.broker).encode()
        if rebind:
            self.review.update(
                draft_sha256=hashlib.sha256(draft).hexdigest(),
                broker_sha256=hashlib.sha256(broker).hexdigest(),
            )
        return reviewer.review_policy(draft, broker, self.review, now=self.now)

    def test_explicit_review_binds_fresh_evidence_without_enabling_execution(self):
        before = deepcopy(self.draft)
        result = self.run_review()
        self.assertEqual(result["status"], "REVIEWED_DEMO_ASSUMPTIONS")
        self.assertEqual(result["operator_review"], self.review)
        self.assertEqual(result["account_evidence_sha256"], self.review["broker_sha256"])
        self.assertEqual(self.draft, before)
        self.assertNotIn("execution_authorized", result)

    def test_missing_confirmation_and_changed_input_cannot_renew_policy(self):
        self.run_review()
        self.broker["account"]["balance"] = 100
        with self.assertRaisesRegex(ValueError, "exact evidence"):
            self.run_review(rebind=False)
        self.review["confirmations"][reviewer.CONFIRMATIONS[0]] = False
        with self.assertRaisesRegex(ValueError, "confirmation"):
            self.run_review()

    def test_stale_future_and_naive_review_rejected(self):
        for stamp in (
            self.now - timedelta(hours=1),
            self.now + timedelta(seconds=1),
            self.now.replace(tzinfo=None),
        ):
            with self.subTest(stamp=stamp):
                self.review["reviewed_utc"] = stamp.isoformat()
                with self.assertRaises(ValueError):
                    self.run_review()

    def test_spec_drift_missing_calendar_and_charged_deal_fail_closed(self):
        self.broker["spec"]["swap_long"] -= 1
        with self.assertRaisesRegex(ValueError, "spec changed"):
            self.run_review()
        self.broker["spec"]["swap_long"] += 1
        self.broker["history_deals"].append(dict(type=0, commission=-0.1, fee=0))
        with self.assertRaisesRegex(ValueError, "charges contradict"):
            self.run_review()
        self.broker["history_deals"].pop()
        self.draft["evidence"]["swap_calendar"]["document"]["days"].pop(
            (self.now + timedelta(days=7)).date().isoformat()
        )
        self.rehash()
        with self.assertRaisesRegex(ValueError, "168 hours"):
            self.run_review()

    def test_attested_policy_and_corrupt_document_are_not_renewable(self):
        self.draft["reviewed_utc"] = self.now.isoformat()
        with self.assertRaisesRegex(ValueError, "renewal prohibited"):
            self.run_review()
        self.draft["reviewed_utc"] = None
        self.draft["evidence"]["tariff"]["document"]["commission_per_lot"] = 99
        with self.assertRaisesRegex(ValueError, "unapproved v2 draft"):
            self.run_review()

    def test_point_conversion_and_currency_must_match_cost_evidence(self):
        self.broker["spec"]["point"] = 0.01
        with self.assertRaisesRegex(ValueError, "spec changed"):
            self.run_review()
        self.broker["spec"]["point"] = 0.001
        self.broker["spec"]["currency_profit"] = "EUR"
        with self.assertRaisesRegex(ValueError, "Demo evidence required"):
            self.run_review()

    def test_cli_publishes_private_complete_file_and_never_overwrites_inputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_review()
            for key, value in (
                ("draft", self.draft),
                ("broker", self.broker),
                ("review", self.review),
            ):
                (root / key).write_text(json.dumps(value))
            argv = sum((["--" + key, str(root / key)] for key in ("draft", "broker", "review")), [])
            with patch.object(reviewer, "datetime") as clock:
                clock.now.return_value = self.now
                clock.fromisoformat.side_effect = fixtures.datetime.fromisoformat
                self.assertEqual(reviewer.main(argv + ["--out", str(root / "approved")]), 0)
            self.assertEqual((root / "approved").stat().st_mode & 0o777, 0o600)
            original = (root / "approved").read_bytes()
            for path in (root / "draft", root / "approved"):
                with self.assertRaises(SystemExit):
                    reviewer.main(argv + ["--out", str(path)])
            self.assertEqual((root / "approved").read_bytes(), original)
