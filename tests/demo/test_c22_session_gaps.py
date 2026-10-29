"""Session classification from explicit evidence; no broker or candle mutation."""

import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone

from scripts.ops.c22_session_gaps import classify_gaps


ACCOUNT = "0123456789abcdef"
NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


def packet(intervals, *, start="2026-10-26T00:00:00Z", end="2026-11-04T00:00:00Z"):
    document = dict(
        schema_version=1,
        account_fingerprint=ACCOUNT,
        symbol="XAUUSDm",
        timezone="UTC",
        coverage=dict(from_utc=start, until_utc=end),
        intervals=intervals,
    )
    raw = json.dumps(document, sort_keys=True).encode()
    return dict(
        source_kind="BROKER_ACCOUNT_SYMBOL_DATED",
        captured_utc="2026-11-03T23:00:00Z",
        source_sha256=hashlib.sha256(raw).hexdigest(),
        document=document,
    ), raw


def interval(start, end, state, reason="regular"):
    return dict(from_utc=start, until_utc=end, state=state, reason=reason)


def capture_fixture(root):
    bars = b"bar_open_utc,open,high,low,close\n2026-10-26T20:30:00Z,100,101,99,100\n2026-10-26T22:00:00Z,100,101,99,100\n"
    (root / "vm-bars.csv").write_bytes(bars)
    snapshot = dict(
        captured_utc="2026-10-27T00:00:00Z",
        cache_sha256=hashlib.sha256(bars).hexdigest(),
        config=dict(symbol="XAUUSDm"),
        journal=dict(identity=ACCOUNT),
    )
    (root / "vm-snapshot.json").write_text(json.dumps(snapshot))
    missing = [
        f"2026-10-26T{hour}:{minute}:00Z"
        for hour, minute in (("20", "45"), ("21", "00"), ("21", "15"), ("21", "30"), ("21", "45"))
    ]
    (root / "additional-evidence.json").write_text(json.dumps(dict(missing_bar_open_utc=missing)))
    return bars


class SessionGapTests(unittest.TestCase):
    def classify(self, gaps, schedule=None, raw=None):
        return classify_gaps(
            gaps,
            schedule=schedule,
            source_bytes=raw,
            account_fingerprint=ACCOUNT,
            symbol="XAUUSDm",
            now=NOW,
        )

    def test_missing_dated_schedule_keeps_actual_gap_unknown(self):
        gaps = [dict(kind="M15", from_utc="2026-10-26T21:00:00Z", until_utc="2026-10-26T21:15:00Z")]
        original = json.dumps(gaps, sort_keys=True)
        result = self.classify(gaps)
        self.assertEqual(result["gaps"][0]["classification"], "UNKNOWN")
        self.assertEqual(result["gaps"][0]["reason"], "dated_account_schedule_missing")
        self.assertEqual(json.dumps(gaps, sort_keys=True), original)
        self.assertFalse(result["native_rules_changed"])

    def test_rollover_closed_minutes_and_open_market_missing_minutes_are_distinct(self):
        schedule, raw = packet(
            [
                interval("2026-10-26T20:45:00Z", "2026-10-26T20:58:00Z", "OPEN"),
                interval("2026-10-26T20:58:00Z", "2026-10-26T22:00:00Z", "CLOSED", "rollover"),
                interval("2026-10-26T22:00:00Z", "2026-10-26T23:00:00Z", "OPEN"),
            ]
        )
        gaps = [
            dict(kind="M1", from_utc="2026-10-26T20:58:00Z", until_utc="2026-10-26T20:59:00Z"),
            dict(kind="M15", from_utc="2026-10-26T21:00:00Z", until_utc="2026-10-26T21:15:00Z"),
            dict(kind="M1", from_utc="2026-10-26T22:00:00Z", until_utc="2026-10-26T22:01:00Z"),
        ]
        result = self.classify(gaps, schedule, raw)
        self.assertEqual(
            [row["classification"] for row in result["gaps"]],
            [
                "EXPECTED_SESSION_CLOSURE",
                "EXPECTED_SESSION_CLOSURE",
                "UNEXPECTED_GAP_DURING_DECLARED_OPEN",
            ],
        )
        self.assertEqual(result["gaps"][0]["schedule_reasons"], ["rollover"])

    def test_partial_m15_session_overlap_stays_unknown_without_raw_minute_membership(self):
        schedule, raw = packet(
            [
                interval("2026-10-26T20:45:00Z", "2026-10-26T20:58:00Z", "OPEN"),
                interval("2026-10-26T20:58:00Z", "2026-10-26T21:00:00Z", "CLOSED", "rollover"),
            ]
        )
        result = self.classify(
            [dict(kind="M15", from_utc="2026-10-26T20:45:00Z", until_utc="2026-10-26T21:00:00Z")],
            schedule,
            raw,
        )
        self.assertEqual(result["gaps"][0]["classification"], "UNKNOWN")
        self.assertEqual(result["gaps"][0]["reason"], "partial_open_closed_interval")

    def test_dated_dst_shift_and_explicit_holiday_are_not_weekly_guesses(self):
        schedule, raw = packet(
            [
                interval(
                    "2026-10-30T21:00:00Z", "2026-10-30T21:15:00Z", "CLOSED", "rollover_summer"
                ),
                interval("2026-11-02T21:00:00Z", "2026-11-02T21:15:00Z", "OPEN", "winter_session"),
                interval(
                    "2026-11-02T22:00:00Z", "2026-11-02T22:15:00Z", "CLOSED", "rollover_winter"
                ),
                interval(
                    "2026-11-03T00:00:00Z", "2026-11-04T00:00:00Z", "CLOSED", "synthetic_holiday"
                ),
            ]
        )
        gaps = [
            dict(kind="M15", from_utc=start, until_utc=end)
            for start, end in (
                ("2026-10-30T21:00:00Z", "2026-10-30T21:15:00Z"),
                ("2026-11-02T21:00:00Z", "2026-11-02T21:15:00Z"),
                ("2026-11-02T22:00:00Z", "2026-11-02T22:15:00Z"),
                ("2026-11-03T12:00:00Z", "2026-11-03T12:15:00Z"),
            )
        ]
        result = self.classify(gaps, schedule, raw)
        self.assertEqual(
            [x["classification"] for x in result["gaps"]],
            [
                "EXPECTED_SESSION_CLOSURE",
                "UNEXPECTED_GAP_DURING_DECLARED_OPEN",
                "EXPECTED_SESSION_CLOSURE",
                "EXPECTED_SESSION_CLOSURE",
            ],
        )
        self.assertEqual(result["gaps"][3]["schedule_reasons"], ["synthetic_holiday"])

    def test_missing_date_inside_coverage_and_gap_after_coverage_remain_unknown(self):
        schedule, raw = packet(
            [
                interval("2026-10-26T21:00:00Z", "2026-10-26T21:05:00Z", "CLOSED", "rollover"),
                interval("2026-10-26T21:10:00Z", "2026-10-26T21:15:00Z", "CLOSED", "rollover"),
            ],
            end="2026-10-27T00:00:00Z",
        )
        gaps = [
            dict(kind="M15", from_utc="2026-10-26T21:00:00Z", until_utc="2026-10-26T21:15:00Z"),
            dict(kind="M15", from_utc="2026-10-28T21:00:00Z", until_utc="2026-10-28T21:15:00Z"),
        ]
        result = self.classify(gaps, schedule, raw)
        self.assertEqual([x["classification"] for x in result["gaps"]], ["UNKNOWN", "UNKNOWN"])
        self.assertEqual(
            [x["reason"] for x in result["gaps"]],
            ["schedule_dated_coverage_missing", "schedule_dated_coverage_missing"],
        )

    def test_generic_hours_wrong_account_symbol_or_tampered_bytes_cannot_attest(self):
        schedule, raw = packet([interval("2026-10-26T21:00:00Z", "2026-10-26T22:00:00Z", "CLOSED")])
        gap = [dict(kind="M15", from_utc="2026-10-26T21:00:00Z", until_utc="2026-10-26T21:15:00Z")]
        cases = []
        cases.append(
            (
                dict(schedule, source_kind="OFFICIAL_GENERIC_HOURS"),
                raw,
                "schedule_source_scope_unverified",
            )
        )
        cases.append((schedule, raw + b" ", "schedule_source_hash_mismatch"))
        cases.append((schedule, None, "schedule_source_bytes_missing"))
        for key, value in (
            ("account_fingerprint", "fedcba9876543210"),
            ("symbol", "EURUSD"),
            ("timezone", "Europe/Athens"),
        ):
            doc = dict(schedule["document"], **{key: value})
            data = json.dumps(doc).encode()
            changed = dict(schedule, document=doc, source_sha256=hashlib.sha256(data).hexdigest())
            reason = (
                "schedule_timezone_unverified"
                if key == "timezone"
                else "schedule_account_symbol_mismatch"
            )
            cases.append((changed, data, reason))
        for changed, data, expected in cases:
            with self.subTest(expected=expected):
                row = self.classify(gap, changed, data)["gaps"][0]
                self.assertEqual(row["classification"], "UNKNOWN")
                self.assertEqual(row["reason"], expected)

    def test_ambiguous_overlap_naive_dates_and_missing_fields_stay_unknown(self):
        gap = [dict(kind="M15", from_utc="2026-10-26T21:00:00Z", until_utc="2026-10-26T21:15:00Z")]
        for intervals in (
            [
                interval("2026-10-26T21:00:00Z", "2026-10-26T22:00:00Z", "CLOSED"),
                interval("2026-10-26T21:05:00Z", "2026-10-26T21:10:00Z", "OPEN"),
            ],
            [interval("2026-10-26T21:00:00", "2026-10-26T22:00:00", "CLOSED")],
            [dict(state="CLOSED")],
        ):
            schedule, raw = packet(intervals)
            with self.subTest(intervals=intervals):
                self.assertEqual(
                    self.classify(gap, schedule, raw)["gaps"][0]["classification"], "UNKNOWN"
                )

    def test_source_document_mismatch_duplicate_json_and_future_capture_are_unknown(self):
        gap = [dict(kind="M15", from_utc="2026-10-26T21:00:00Z", until_utc="2026-10-26T21:15:00Z")]
        schedule, raw = packet([interval("2026-10-26T21:00:00Z", "2026-10-26T22:00:00Z", "CLOSED")])
        wrong_document = dict(
            schedule, document=dict(schedule["document"], timezone="Europe/Athens")
        )
        future = dict(schedule, captured_utc="2026-11-05T00:00:00Z")
        duplicate = b'{"schema_version":1,"schema_version":1}'
        dupe_packet = dict(schedule, source_sha256=hashlib.sha256(duplicate).hexdigest())
        for changed, data, reason in (
            (wrong_document, raw, "schedule_source_document_mismatch"),
            (future, raw, "schedule_capture_in_future"),
            (dupe_packet, duplicate, "schedule_document_invalid"),
        ):
            with self.subTest(reason=reason):
                result = self.classify(gap, changed, data)
                self.assertEqual(result["gaps"][0]["classification"], "UNKNOWN")
                self.assertEqual(result["gaps"][0]["reason"], reason)

    def test_adjacent_same_closed_intervals_cover_boundary_without_false_overlap(self):
        schedule, raw = packet(
            [
                interval("2026-10-26T21:00:00Z", "2026-10-26T21:05:00Z", "CLOSED", "rollover"),
                interval(
                    "2026-10-26T21:05:00Z", "2026-10-26T21:15:00Z", "CLOSED", "broker_exception"
                ),
            ]
        )
        result = self.classify(
            [dict(kind="M15", from_utc="2026-10-26T21:00:00Z", until_utc="2026-10-26T21:15:00Z")],
            schedule,
            raw,
        )
        self.assertEqual(result["gaps"][0]["classification"], "EXPECTED_SESSION_CLOSURE")
        self.assertEqual(result["gaps"][0]["schedule_reasons"], ["broker_exception", "rollover"])

    def test_bad_gap_or_duplicate_observation_is_rejected_without_creating_candles(self):
        good = dict(kind="M15", from_utc="2026-10-26T21:00:00Z", until_utc="2026-10-26T21:15:00Z")
        for gaps in (
            [good, good],
            [dict(good, from_utc="2026-10-26T21:00:00")],
            [dict(good, until_utc="2026-10-26T21:30:00Z")],
            [dict(good, kind="H4")],
        ):
            with self.subTest(gaps=gaps), self.assertRaises(ValueError):
                self.classify(gaps)

    def test_actual_capture_reader_checks_cache_hash_identity_and_missing_bar_proof(self):
        from scripts.ops.c22_session_gaps import capture_report

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bars = capture_fixture(root)
            report = capture_report(root, account_fingerprint=ACCOUNT, symbol="XAUUSDm", now=NOW)
            self.assertEqual(len(report["gaps"]), 5)
            self.assertEqual(report["classification_counts"], {"UNKNOWN": 5})
            self.assertEqual(report["raw_m1_membership"], "NOT_CAPTURED")
            self.assertEqual(report["capture_observed_utc"], "2026-10-27T00:00:00+00:00")
            self.assertEqual((root / "vm-bars.csv").read_bytes(), bars)
            (root / "vm-bars.csv").write_bytes(bars + b"\n")
            with self.assertRaisesRegex(ValueError, "capture_cache_hash_mismatch"):
                capture_report(root, account_fingerprint=ACCOUNT, symbol="XAUUSDm", now=NOW)

    def test_cli_missing_or_invalid_optional_schedule_preserves_unknown_report(self):
        from scripts.ops.c22_session_gaps import main

        runs = Path(__file__).resolve().parents[2] / "runs/c22-session-gaps-2026-10-29"
        runs.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runs) as temp:
            root = Path(temp)
            capture_fixture(root)
            schedule, raw = packet(
                [interval("2026-10-26T21:00:00Z", "2026-10-26T22:00:00Z", "CLOSED")]
            )
            (root / "schedule.json").write_text(json.dumps(schedule))
            (root / "raw.json").write_bytes(raw)
            (root / "malformed.json").write_text("{broken")
            for index, (schedule_path, source_path, reason) in enumerate(
                (
                    (root / "missing.json", root / "raw.json", "schedule_packet_unreadable"),
                    (root / "malformed.json", root / "raw.json", "schedule_packet_invalid_json"),
                    (
                        root / "schedule.json",
                        root / "missing.json",
                        "schedule_source_bytes_missing",
                    ),
                )
            ):
                output = root / f"out-{index}"
                with self.subTest(reason=reason), redirect_stdout(io.StringIO()):
                    main(
                        [
                            "--capture-dir",
                            str(root),
                            "--account-fingerprint",
                            ACCOUNT,
                            "--schedule",
                            str(schedule_path),
                            "--schedule-source",
                            str(source_path),
                            "--out",
                            str(output),
                        ]
                    )
                    result = json.loads((output / "report.json").read_text())
                    self.assertEqual(result["classification_counts"], {"UNKNOWN": 5})
                    self.assertEqual(result["schedule_evidence"]["reason"], reason)

    def test_capture_wrong_identity_present_bar_claim_or_future_observation_is_rejected(self):
        from scripts.ops.c22_session_gaps import capture_report

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            capture_fixture(root)
            snapshot_path = root / "vm-snapshot.json"
            original = snapshot_path.read_bytes()
            snapshot = json.loads(original)
            snapshot["journal"]["identity"] = "fedcba9876543210"
            snapshot_path.write_text(json.dumps(snapshot))
            with self.assertRaisesRegex(ValueError, "capture_account_symbol_mismatch"):
                capture_report(root, account_fingerprint=ACCOUNT, symbol="XAUUSDm", now=NOW)
            snapshot = json.loads(original)
            snapshot["captured_utc"] = "2026-11-05T00:00:00Z"
            snapshot_path.write_text(json.dumps(snapshot))
            with self.assertRaisesRegex(ValueError, "capture_observation_in_future"):
                capture_report(root, account_fingerprint=ACCOUNT, symbol="XAUUSDm", now=NOW)
            snapshot_path.write_bytes(original)
            (root / "additional-evidence.json").write_text(
                json.dumps(dict(missing_bar_open_utc=["2026-10-26T20:30:00Z"]))
            )
            with self.assertRaises(ValueError):
                capture_report(root, account_fingerprint=ACCOUNT, symbol="XAUUSDm", now=NOW)


if __name__ == "__main__":
    unittest.main()
