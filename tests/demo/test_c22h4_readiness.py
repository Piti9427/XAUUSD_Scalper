"""Readiness diagnostics never grant order permission or mutate financial state."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.ops.c22h4_readiness import build_report, main


class MarketOpenReadinessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 28, tzinfo=timezone.utc)
        self.since = self.now - timedelta(hours=48)
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(
            "CREATE TABLE kv(key TEXT,value TEXT); CREATE TABLE audit_events(id INTEGER PRIMARY KEY,payload TEXT); CREATE TABLE events(sent INTEGER);"
        )
        self.fingerprint = "1234567890abcdef"
        self.context = dict(
            account_fingerprint=self.fingerprint, release_hash="r" * 64, config_hash="c" * 64
        )
        self.last = dict(
            status="WAIT",
            reason="no_signal",
            execute=False,
            observed_positions=0,
            position_protection="flat",
            captured_utc=self.now.isoformat(),
            macro_ema=4000,
        )
        self.values = dict(
            identity=self.fingerprint,
            strategy_snapshot="RESEARCH-C22-H4EMA200-20261004",
            active=None,
            safety_halt=None,
            last_result=self.last,
        )
        self.spec = dict(
            trade_contract_size=100,
            trade_tick_size=0.001,
            volume_min=0.01,
            volume_max=200,
            volume_step=0.01,
            swap_mode=1,
            swap_long=-490.8,
            swap_short=0,
            swap_rollover3days=3,
        )
        self.broker = dict(
            captured_utc=self.now.isoformat(),
            account_fingerprint=self.fingerprint,
            demo_verified=True,
            hedging_verified=True,
            positions=0,
            orders=0,
            order_send_called=False,
            terminal=dict(connected=True, trade_allowed=True, tradeapi_disabled=False),
            account=dict(trade_allowed=True, trade_expert=True),
            tick=dict(time_msc=int(self.now.timestamp() * 1000)),
            spec=self.spec,
            history_deals=[],
        )
        documents = dict(
            tariff=dict(source="fixture", commission_per_lot=0, unit="USD_per_lot_round_trip"),
            spec=dict(source="fixture", fields=self.spec),
            swap_calendar=dict(
                source="fixture",
                unit="USD_per_lot",
                days={
                    self.now.date().isoformat(): dict(
                        rollover_utc=self.now.replace(hour=21).isoformat(), buy=-49.08, sell=0
                    )
                },
            ),
        )
        self.policy = dict(
            version=2,
            reviewed_utc=self.now.isoformat(),
            account_fingerprint=self.fingerprint,
            account_type="Standard Demo",
            commission_per_lot=0,
            commission_unit="USD_per_lot_round_trip",
            commission_from_symbol_info=False,
            slippage_basis="declared_assumption",
            slippage_allowance_price=0.1,
            source="fixture",
            commission_source="fixture",
            account_evidence_sha256="a" * 64,
            spread_buffer=0,
            evidence={
                k: dict(
                    document=v,
                    sha256=hashlib.sha256(
                        json.dumps(v, sort_keys=True, allow_nan=False).encode()
                    ).hexdigest(),
                )
                for k, v in documents.items()
            },
        )
        for n in range(2881):
            stamp = self.since + timedelta(minutes=n)
            self.event("CYCLE", stamp, result=dict(self.last, captured_utc=stamp.isoformat()))
        for n in range(1, 97):
            bar = self.since + timedelta(minutes=15 * n)
            self.event("SIGNAL", bar, bar=bar.isoformat(), observed=dict(macro_ema=4000))

    def tearDown(self):
        self.conn.close()

    def event(self, kind, utc, **facts):
        event = dict(self.context, kind=kind, utc=utc.isoformat(), **facts)
        self.conn.execute("INSERT INTO audit_events(payload) VALUES (?)", (json.dumps(event),))

    def report(self, **kwargs):
        self.conn.execute("DELETE FROM kv")
        self.conn.executemany(
            "INSERT INTO kv VALUES (?,?)", [(k, json.dumps(v)) for k, v in self.values.items()]
        )
        self.conn.commit()
        return build_report(
            self.conn,
            now=self.now,
            since=self.since,
            broker=self.broker,
            parity=dict(history_gate=True, parity_gate=True, contract_id="1af968e9ac6a26ea"),
            policy=self.policy,
            **kwargs,
        )

    def test_market_closed_does_not_count_historical_or_duplicate_bars(self):
        self.conn.execute("DELETE FROM audit_events WHERE json_extract(payload,'$.kind')='SIGNAL'")
        for _ in range(100):
            self.event(
                "SIGNAL",
                self.now,
                bar=(self.since - timedelta(minutes=15)).isoformat(),
                observed=dict(macro_ema=4000),
            )
        self.last.update(status="BLOCKED", reason="quote_stale")
        self.broker["tick"]["time_msc"] -= 3600 * 1000
        result = self.report()
        self.assertEqual(result["shadow"]["new_complete_m15_bars"], 0)
        self.assertIn("shadow_96_new_complete_m15_missing", result["blockers"])
        self.assertIn("fresh_broker_quote_missing", result["blockers"])
        self.assertFalse(result["execution_authorized"])

    def test_even_all_measured_checks_pass_still_requires_review_and_owner_approval(self):
        self.report()
        self.conn.execute("PRAGMA query_only=ON")
        result = build_report(
            self.conn,
            now=self.now,
            since=self.since,
            broker=self.broker,
            parity=dict(history_gate=True, parity_gate=True, contract_id="1af968e9ac6a26ea"),
            policy=self.policy,
        )
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["status"], "AWAITING_OPERATOR_REVIEW")
        self.assertEqual(result["shadow"]["new_complete_m15_bars"], 96)
        self.assertFalse(result["execution_authorized"])
        self.assertIn("execution_time_owner_approval", result["required_reviews"])

    def test_owner_feed_acceptance_preserves_failed_parity_and_other_gates(self):
        self.report()
        parity = dict(history_gate=True, parity_gate=False, contract_id="1af968e9ac6a26ea")
        review = dict(
            scope="PROSPECTIVE_DEMO_ONLY",
            owner_decision="เตรียม Demo trial บน feed นี้",
            contract_id="1af968e9ac6a26ea",
            account_fingerprint=self.fingerprint,
            release_hash=self.context["release_hash"],
            config_hash=self.context["config_hash"],
            parity_document_sha256=hashlib.sha256(
                json.dumps(parity, sort_keys=True, allow_nan=False).encode()
            ).hexdigest(),
            accepted_utc=self.now.isoformat(),
            same_input_controls_passed=True,
            history_basis="actual_broker_100000_M1_complete_M15",
            diagnosis_report="fixture diagnosed differences",
        )

        def report(feed_review):
            return build_report(
                self.conn,
                now=self.now,
                since=self.since,
                broker=self.broker,
                parity=parity,
                policy=self.policy,
                feed_review=feed_review,
            )

        accepted = report(review)
        self.assertFalse(accepted["feed"]["original_parity_passed"])
        self.assertTrue(accepted["feed"]["prospective_demo_feed_accepted"])
        self.assertFalse(accepted["execution_authorized"])
        self.assertFalse(parity["parity_gate"])
        attended = report(
            review
            | dict(
                operating_mode="ATTENDED_DEMO_TRIAL",
                owner_attended_decision="Demo trial แบบมีคนเฝ้า + backup บน Mac",
            )
        )
        self.assertEqual(attended["operating_mode"], "ATTENDED_DEMO_TRIAL")
        self.assertFalse(attended["unattended_authorized"])
        self.assertIn(
            "attended_operator_console_and_verified_off_VM_snapshot", attended["required_reviews"]
        )
        for key in ("account_fingerprint", "release_hash", "parity_document_sha256", "scope"):
            with self.subTest(key=key):
                self.assertIn(
                    "broker_parity_not_passed", report(review | {key: "changed"})["blockers"]
                )
        self.broker["tick"]["time_msc"] -= 60000
        self.assertIn("fresh_broker_quote_missing", report(review)["blockers"])
        self.assertIn("broker_parity_not_passed", report(None)["blockers"])

    def monday_attended_review(self):
        self.now = datetime(2026, 10, 25, 22, 30, tzinfo=timezone.utc)  # Monday05:30 Bangkok
        self.since = self.now - timedelta(minutes=2)
        self.last["captured_utc"] = self.now.isoformat()
        self.broker["captured_utc"] = self.now.isoformat()
        self.broker["tick"]["time_msc"] = int(self.now.timestamp() * 1000)
        self.policy["reviewed_utc"] = self.now.isoformat()
        calendar = self.policy["evidence"]["swap_calendar"]
        calendar["document"]["days"] = {
            self.now.date().isoformat(): dict(
                rollover_utc=self.now.replace(hour=21).isoformat(), buy=-49.08, sell=0
            )
        }
        calendar["sha256"] = hashlib.sha256(
            json.dumps(calendar["document"], sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        self.conn.execute("DELETE FROM audit_events")
        for n in range(5):
            stamp = self.since + timedelta(seconds=30 * n)
            self.event("CYCLE", stamp, result=dict(self.last, captured_utc=stamp.isoformat()))
        self.event("SIGNAL", self.now, bar=self.now.isoformat(), observed=dict(macro_ema=4000))
        parity = dict(history_gate=True, parity_gate=True, contract_id="1af968e9ac6a26ea")
        return dict(
            scope="PROSPECTIVE_DEMO_ONLY",
            owner_decision="เตรียม Demo trial บน feed นี้",
            contract_id="1af968e9ac6a26ea",
            account_fingerprint=self.fingerprint,
            release_hash=self.context["release_hash"],
            config_hash=self.context["config_hash"],
            parity_document_sha256=hashlib.sha256(
                json.dumps(parity, sort_keys=True, allow_nan=False).encode()
            ).hexdigest(),
            accepted_utc=self.now.isoformat(),
            same_input_controls_passed=True,
            history_basis="actual_broker_100000_M1_complete_M15",
            diagnosis_report="fixture",
            operating_mode="ATTENDED_DEMO_TRIAL",
            owner_attended_decision="Demo trial แบบมีคนเฝ้า + backup บน Mac",
            shadow_time_waiver=dict(
                owner_decision="ยกเว้นเวลา shadow สำหรับ Demo trial มีคนเฝ้า",
                trial_date_local="2026-10-26",
                timezone="Asia/Bangkok",
            ),
        )

    def test_dated_monday_attended_waiver_removes_only_shadow_time_gates(self):
        review = self.monday_attended_review()
        result = self.report(feed_review=review)
        self.assertEqual(result["blockers"], [])
        self.assertTrue(result["shadow"]["time_requirement_waived_for_attended_trial"])
        self.assertEqual(result["shadow"]["new_complete_m15_bars"], 1)
        self.assertFalse(result["execution_authorized"])
        self.broker["tick"]["time_msc"] -= 60000
        self.conn.execute("INSERT INTO events VALUES(0)")
        blocked = self.report(feed_review=review)
        self.assertIn("fresh_broker_quote_missing", blocked["blockers"])
        self.assertIn("pending_outbox", blocked["blockers"])

    def test_waiver_cannot_apply_on_other_day_scope_or_without_complete_bar(self):
        review = self.monday_attended_review()
        for change in (
            dict(trial_date_local="2026-11-02"),
            dict(timezone="UTC"),
            dict(owner_decision="not authorized"),
        ):
            with self.subTest(change=change):
                altered = review | dict(shadow_time_waiver=review["shadow_time_waiver"] | change)
                result = self.report(feed_review=altered)
                self.assertFalse(result["shadow"]["time_requirement_waived_for_attended_trial"])
                self.assertIn("shadow_48h_continuous_observation_missing", result["blockers"])
        foreign = self.report(feed_review=review | dict(account_fingerprint="other"))
        self.assertFalse(foreign["shadow"]["time_requirement_waived_for_attended_trial"])
        self.conn.execute("DELETE FROM audit_events WHERE json_extract(payload,'$.kind')='SIGNAL'")
        self.last["macro_ema"] = float("nan")
        result = self.report(feed_review=review)
        self.assertIn("fresh_closed_m15_not_observed", result["blockers"])
        self.assertIn("current_macro_warmup_not_verified", result["blockers"])

    def test_duplicate_prospective_bar_counts_once(self):
        self.conn.execute("DELETE FROM audit_events WHERE json_extract(payload,'$.kind')='SIGNAL'")
        for _ in range(100):
            self.event("SIGNAL", self.now, bar=self.now.isoformat(), observed=dict(macro_ema=4000))
        result = self.report()
        self.assertEqual(result["shadow"]["new_complete_m15_bars"], 1)
        self.assertIn("shadow_96_new_complete_m15_missing", result["blockers"])

    def test_recent_probe_quote_checked_at_capture_then_fresh_shadow_required(self):
        captured = self.now - timedelta(seconds=120)
        self.broker["captured_utc"] = captured.isoformat()
        self.broker["tick"]["time_msc"] = int(captured.timestamp() * 1000)
        result = self.report()
        self.assertNotIn("fresh_broker_quote_missing", result["blockers"])
        self.assertEqual(result["broker"]["quote_age_at_probe_seconds"], 0)
        self.last.update(status="BLOCKED", reason="quote_stale")
        self.assertIn("current_shadow_admission_blocked", self.report()["blockers"])

    def test_cli_refuses_output_overwriting_financial_journal(self):
        with TemporaryDirectory() as tmp:
            journal = Path(tmp) / "financial.sqlite3"
            journal.write_bytes(b"preserved financial evidence")
            args = [
                "--journal",
                str(journal),
                "--broker",
                str(Path(tmp) / "broker.json"),
                "--parity",
                str(Path(tmp) / "parity.json"),
                "--cost-policy",
                str(Path(tmp) / "cost.json"),
                "--since",
                self.since.isoformat(),
                "--out",
                str(journal),
            ]
            with self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(journal.read_bytes(), b"preserved financial evidence")

    def test_changed_cohort_and_connection_unknown_cannot_pass_soak(self):
        self.context["release_hash"] = "other"
        self.event(
            "CYCLE",
            self.now,
            result=dict(
                self.last,
                status="BLOCKED",
                reason="algo_permissions_required",
                observed_positions=None,
                position_protection="unknown",
            ),
        )
        result = self.report()
        self.assertIn("shadow_release_or_config_changed", result["blockers"])
        self.assertIn("shadow_unexpected_blockers_or_protection_unknown", result["blockers"])

    def test_stale_cost_parity_failure_and_pending_outbox_are_separate_blockers(self):
        self.policy["reviewed_utc"] = (self.now - timedelta(hours=25)).isoformat()
        self.conn.execute("INSERT INTO events VALUES (0)")
        self.conn.commit()
        result = build_report(
            self.conn,
            now=self.now,
            since=self.since,
            broker=self.broker,
            parity=dict(history_gate=True, parity_gate=False, contract_id="1af968e9ac6a26ea"),
            policy=self.policy,
        )
        self.assertIn("cost_cutover_review_older_than_24h", result["blockers"])
        self.assertIn("broker_parity_not_passed", result["blockers"])
        self.assertIn("pending_outbox", result["blockers"])

    def test_signal_requires_finite_macro_and_actual_closed_bar_observation(self):
        self.conn.execute("DELETE FROM audit_events WHERE json_extract(payload,'$.kind')='SIGNAL'")
        self.event(
            "SIGNAL",
            self.now,
            bar=(self.now + timedelta(minutes=15)).isoformat(),
            observed=dict(macro_ema=4000),
        )
        self.event(
            "SIGNAL", self.now, bar=self.now.isoformat(), observed=dict(macro_ema=float("nan"))
        )
        result = self.report()
        self.assertEqual(result["shadow"]["new_complete_m15_bars"], 0)
        self.assertIn("shadow_invalid_bar_evidence", result["blockers"])

    def test_naive_clock_rejected_and_no_financial_mutation(self):
        self.report()
        before = list(self.conn.iterdump())
        self.report()
        after = list(self.conn.iterdump())
        self.assertEqual(before, after)
        with self.assertRaises(ValueError):
            build_report(
                self.conn,
                now=self.now.replace(tzinfo=None),
                since=self.since,
                broker={},
                parity={},
                policy={},
            )

    def test_missing_current_swap_day_blocks_even_when_document_hash_valid(self):
        doc = self.policy["evidence"]["swap_calendar"]["document"]
        row = doc["days"].pop(self.now.date().isoformat())
        other = self.now - timedelta(days=1)
        doc["days"][other.date().isoformat()] = dict(
            row, rollover_utc=other.replace(hour=21).isoformat()
        )
        self.policy["evidence"]["swap_calendar"]["sha256"] = hashlib.sha256(
            json.dumps(doc, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        self.assertIn("cost_deal_or_calendar_unverified", self.report()["blockers"])
