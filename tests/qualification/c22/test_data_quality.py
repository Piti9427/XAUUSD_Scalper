"""Behavior of bounded, read-only C22 data qualification reports."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.qualification.c22.data_quality import audit_data


class DataQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({
            "ticks": 300,
            "bars": 20,
            "first_quote_utc": "2026-10-01T00:00:00Z",
            "last_quote_utc": "2026-10-01T02:00:00Z",
            "artifacts": {},
        }))

    def csv_file(self, name, headers, rows):
        path = self.root / name
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
        return path

    def test_manifest_counts_do_not_certify_provider_completeness(self):
        result = audit_data(self.manifest)
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["data"]["source_completeness"], "NOT_CERTIFIED")
        self.assertEqual(result["data"]["bounded_checks_status"], "NOT_RUN")

    def test_bounded_scan_reports_truncation_without_inspecting_later_rows(self):
        path = self.csv_file("bars.csv", ["bar_open_utc", "open", "high", "low", "close"], [
            ["2026-10-01T00:00:00Z", 10, 12, 9, 11],
            ["2026-10-01T00:15:00Z", 11, 13, 10, 12],
            ["NOT_A_TIMESTAMP", "NaN", 1, 0, 1],
        ])
        result = audit_data(self.manifest, bars_path=path, max_rows=2)
        scan = result["data"]["checks"]["bars"]
        self.assertEqual(scan["rows_examined"], 2)
        self.assertTrue(scan["truncated"])
        self.assertEqual(result["data"]["bounded_checks_status"], "PASS")
        self.assertEqual(result["data"]["source_completeness"], "NOT_CERTIFIED")

    def test_bar_defects_report_rows_and_never_repair_input(self):
        path = self.csv_file("bad-bars.csv", ["bar_open_utc", "open", "high", "low", "close"], [
            ["2026-10-01T00:00:00Z", 10, 12, 9, 11],
            ["2026-10-01T00:15:00Z", 10, 9, 11, 10],
            ["2026-10-01T00:30:00Z", "NaN", 12, 9, 11],
            ["2026-10-01T00:45:00", 10, 12, 9, 11],
        ])
        original = path.read_bytes()
        result = audit_data(self.manifest, bars_path=path)
        self.assertEqual(result["status"], "DATA_QUALITY_ISSUES")
        counts = result["data"]["issue_counts"]
        self.assertEqual(counts["INVALID_OHLC"], 1)
        self.assertEqual(counts["NONFINITE_PRICE"], 1)
        self.assertEqual(counts["INVALID_TIMESTAMP"], 1)
        self.assertEqual({item["row"] for item in result["data"]["issues"]}, {3, 4, 5})
        self.assertEqual(path.read_bytes(), original)

    def test_duplicate_order_and_missing_intervals_keep_witnesses(self):
        path = self.csv_file("bars.csv", ["bar_open_utc", "open", "high", "low", "close"], [
            [time, 10, 12, 9, 11] for time in [
                "2026-10-01T00:00:00Z", "2026-10-01T00:15:00Z",
                "2026-10-01T00:15:00Z", "2026-10-01T00:00:00Z",
                "2026-10-01T01:00:00Z",
            ]
        ])
        result = audit_data(self.manifest, bars_path=path)
        self.assertEqual(result["data"]["issue_counts"]["DUPLICATE_TIMESTAMP"], 2)
        self.assertEqual(result["data"]["issue_counts"]["OUT_OF_ORDER"], 1)
        gap = next(item for item in result["data"]["issues"] if item["code"] == "MISSING_INTERVAL")
        self.assertEqual(gap["missing_intervals"], 3)
        self.assertEqual(gap["classification"], "UNEXPLAINED_GAP")

    def test_weekend_gap_is_not_automatically_accepted_as_market_closure(self):
        path = self.csv_file("bars.csv", ["bar_open_utc", "open", "high", "low", "close"], [
            ["2026-10-02T20:45:00Z", 10, 12, 9, 11],
            ["2026-10-04T22:15:00Z", 10, 12, 9, 11],
        ])
        result = audit_data(self.manifest, bars_path=path)
        gap = next(item for item in result["data"]["issues"] if item["code"] == "MISSING_INTERVAL")
        self.assertEqual(gap["classification"], "WEEKEND_OVERLAP_UNVERIFIED")
        self.assertEqual(result["status"], "DATA_QUALITY_ISSUES")

    def test_missing_m1_minute_marks_m15_bucket_incomplete(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["bar_timeframe_minutes"] = 1
        self.manifest.write_text(json.dumps(manifest))
        path = self.csv_file("m1.csv", ["bar_open_utc", "open", "high", "low", "close"], [
            [f"2026-10-01T00:{minute:02d}:00Z", 10, 12, 9, 11]
            for minute in range(15) if minute != 7
        ])
        result = audit_data(self.manifest, bars_path=path)
        assembly = result["data"]["checks"]["bars"]["m15_from_m1"]
        self.assertEqual(assembly["complete_buckets"], 0)
        self.assertEqual(assembly["incomplete_buckets"], 1)
        self.assertEqual(assembly["incomplete_examples"][0]["missing_minutes"], [7])
        self.assertEqual(result["data"]["issue_counts"]["INCOMPLETE_M15_FROM_M1"], 1)

    def test_truncated_last_m1_bucket_is_sampling_boundary_not_missing_data(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["bar_timeframe_minutes"] = 1
        self.manifest.write_text(json.dumps(manifest))
        path = self.csv_file("m1.csv", ["bar_open_utc", "open", "high", "low", "close"], [
            [f"2026-10-01T00:{minute:02d}:00Z", 10, 12, 9, 11] for minute in range(30)
        ])
        result = audit_data(self.manifest, bars_path=path, max_rows=20)
        assembly = result["data"]["checks"]["bars"]["m15_from_m1"]
        self.assertEqual(assembly["complete_buckets"], 1)
        self.assertEqual(assembly["incomplete_buckets"], 0)
        self.assertEqual(assembly["sample_boundary_partial_buckets"], 1)

    def test_tick_spread_and_exact_duplicate_checks_allow_distinct_same_time_quotes(self):
        path = self.csv_file("ticks.csv", ["Timestamp", "Bid", "Ask"], [
            ["2026-10-01T00:00:00Z", 10, 10.1],
            ["2026-10-01T00:00:00Z", 10, 10.2],
            ["2026-10-01T00:00:00Z", 10, 10.2],
            ["2026-10-01T00:00:01Z", 10.3, 10.2],
            ["2026-10-01T00:00:02Z", 10.3, "NaN"],
        ])
        result = audit_data(self.manifest, ticks_path=path)
        self.assertEqual(result["data"]["issue_counts"]["NEGATIVE_SPREAD"], 1)
        self.assertEqual(result["data"]["issue_counts"]["DUPLICATE_QUOTE"], 1)
        self.assertEqual(result["data"]["issue_counts"]["NONFINITE_PRICE"], 1)
        self.assertNotIn("DUPLICATE_TIMESTAMP", result["data"]["issue_counts"])

    def test_rejects_ambiguous_csv_headers_and_unbounded_requests(self):
        path = self.csv_file("ambiguous.csv", ["bar_open_utc", "open", "OPEN", "high", "low", "close"], [
            ["2026-10-01T00:00:00Z", 10, 10, 12, 9, 11],
        ])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audit_data(self.manifest, bars_path=path)
        for value in [0, -1, True, 1_000_001]:
            with self.subTest(max_rows=value):
                with self.assertRaises(ValueError):
                    audit_data(self.manifest, max_rows=value)

    def test_invalid_manifest_interval_is_a_defect_not_a_valid_coverage_claim(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["first_quote_utc"] = "2026-10-02T00:00:00Z"
        manifest["last_quote_utc"] = "2026-10-01T00:00:00Z"
        manifest["ticks"] = -1
        self.manifest.write_text(json.dumps(manifest))
        result = audit_data(self.manifest)
        self.assertEqual(result["data"]["issue_counts"]["INVALID_MANIFEST_INTERVAL"], 1)
        self.assertEqual(result["data"]["issue_counts"]["INVALID_MANIFEST_COUNT"], 1)
        self.assertEqual(result["status"], "DATA_QUALITY_ISSUES")

    def test_empty_input_is_not_a_clean_data_sample(self):
        path = self.csv_file("empty.csv", ["bar_open_utc", "open", "high", "low", "close"], [])
        result = audit_data(self.manifest, bars_path=path)
        self.assertEqual(result["data"]["issue_counts"]["EMPTY_INPUT"], 1)

    def test_timeframe_metadata_does_not_silently_coerce_values(self):
        for value in [True, 1.0, "1", 5]:
            with self.subTest(timeframe=value):
                manifest = json.loads(self.manifest.read_text())
                manifest["bar_timeframe_minutes"] = value
                self.manifest.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    audit_data(self.manifest)

    def test_reports_keep_actual_scanned_csv_provenance_for_each_input(self):
        headers = ["bar_open_utc", "open", "high", "low", "close"]
        first = self.csv_file("first.csv", headers, [["2026-10-01T00:00:00Z", 10, 12, 9, 11]])
        second = self.csv_file("second.csv", headers, [["2026-10-01T00:00:00Z", 20, 22, 19, 21]])
        ticks = self.csv_file("ticks.csv", ["time_utc", "bid", "ask"], [
            ["2026-10-01T00:00:00Z", 10, 10.2],
        ])
        manifest = json.loads(self.manifest.read_text())
        manifest["artifacts"] = {"first.csv": "a" * 64, "second.csv": "b" * 64, "ticks.csv": "c" * 64}
        self.manifest.write_text(json.dumps(manifest))
        for bars, expected_declared in ((first, "a" * 64), (second, "b" * 64)):
            with self.subTest(bars=bars.name):
                report = audit_data(self.manifest, bars_path=bars, ticks_path=ticks)
                sources = {item["path"]: item for item in report["sources"]}
                self.assertEqual(set(sources), {
                    str(self.manifest.resolve()), str(bars.resolve()), str(ticks.resolve()),
                })
                self.assertEqual(sources[str(bars.resolve())]["declared_sha256"], expected_declared)
                for path in (bars, ticks):
                    reference = sources[str(path.resolve())]
                    self.assertEqual(reference["scan_scope"], "BOUNDED_CSV_ROWS")
                    self.assertFalse(reference["declared_hash_verified"])
                    self.assertIsNone(reference["sha256"])


if __name__ == "__main__":
    unittest.main()
