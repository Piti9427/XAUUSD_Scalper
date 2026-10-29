"""Passive cache/daily evidence keeps unknown money and raw feed explicit."""

from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import pandas as pd

from tests.demo import test_c22_forward_seal as seal_fixture
from scripts.ops.c22_forward_seal import seal_batch
from scripts.ops.c22_forward_feed import create_coverage, verify_coverage, main

NOW, FINGERPRINT = seal_fixture.NOW, seal_fixture.FINGERPRINT


class ForwardFeedTests(unittest.TestCase):
    def setUp(self):
        fixture = seal_fixture.ForwardSealTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f = fixture
        self.batch = fixture.root / "batch"
        seal_batch(
            fixture.journal,
            fixture.protocol,
            self.batch,
            since=NOW - timedelta(days=1),
            until=NOW,
            now=NOW,
        )
        self.csv = fixture.root / "cache.csv"
        self.meta = fixture.root / "cache.csv.meta.json"
        bars = pd.DataFrame(
            dict(
                open=[100.0, 101.0, 102.0],
                high=[101.0, 102.0, 103.0],
                low=[99.0, 100.0, 101.0],
                close=[100.5, 101.5, 102.5],
            ),
            index=pd.date_range(NOW - timedelta(minutes=60), periods=3, freq="15min"),
        )
        bars.to_csv(self.csv, index_label="bar_open_utc")
        self.metadata = dict(
            version=1,
            aggregation="UTC_BID_M15_FROM_15_COMPLETE_M1_V1",
            account_fingerprint=FINGERPRINT,
            symbol="XAUUSDm",
            contract_id="26b8bcd69e043653",
            config_sha256=fixture.config,
            created_utc=NOW.isoformat(),
            sha256=hashlib.sha256(self.csv.read_bytes()).hexdigest(),
            rows=3,
            first_bar_utc=bars.index[0].isoformat(),
            last_bar_utc=bars.index[-1].isoformat(),
        )
        self.save_meta()

    def save_meta(self):
        self.meta.write_text(json.dumps(self.metadata))

    def build(self, name="coverage", **kwargs):
        return create_coverage(self.batch, self.f.journal, self.f.root / name, now=NOW, **kwargs)

    def test_paired_cache_hash_binding_closed_bars_and_reused_labels(self):
        value = self.build(cache=self.csv, metadata=self.meta)
        feed = value["feed"]
        self.assertEqual(feed["rows"], 3)
        self.assertEqual(feed["csv_sha256"], self.metadata["sha256"])
        self.assertEqual(feed["original_created_utc"], NOW.isoformat())
        self.assertEqual(feed["data_classification"], "REUSED_CACHE_NOT_HOLDOUT")
        self.assertEqual(feed["post_freeze_bar_closes"], 0)
        self.assertEqual(value["raw_m1"], "NOT_CAPTURED")
        self.assertEqual(value["raw_ticks"], "NOT_CAPTURED")
        self.assertFalse(value["execution_authorized"])
        self.assertEqual(verify_coverage(self.f.root / "coverage", journal=self.f.journal), value)

    def test_wrong_identity_hash_or_torn_pair_rejects(self):
        for field, changed in [
            ("account_fingerprint", "f" * 16),
            ("config_sha256", "f" * 64),
            ("sha256", "0" * 64),
            ("rows", 4),
        ]:
            with self.subTest(field=field):
                original = dict(self.metadata)
                self.metadata[field] = changed
                self.save_meta()
                with self.assertRaises(ValueError):
                    self.build(name=field, cache=self.csv, metadata=self.meta)
                self.metadata = original
                self.save_meta()
        with self.assertRaises(ValueError):
            self.build(cache=self.csv)

    def test_open_future_naive_or_duplicate_bars_never_count_complete(self):
        original = self.csv.read_bytes()
        for kind in ("open", "naive", "duplicate"):
            with self.subTest(kind=kind):
                frame = pd.read_csv(self.csv, index_col=0)
                frame.index = pd.to_datetime(frame.index)
                if kind == "open":
                    frame.index += pd.Timedelta(minutes=45)
                elif kind == "naive":
                    frame.index = frame.index.tz_localize(None)
                else:
                    frame.index = [frame.index[0]] * len(frame)
                frame.to_csv(self.csv)
                self.metadata.update(
                    sha256=hashlib.sha256(self.csv.read_bytes()).hexdigest(),
                    first_bar_utc=frame.index[0].isoformat(),
                    last_bar_utc=frame.index[-1].isoformat(),
                )
                self.save_meta()
                with self.assertRaises(ValueError):
                    self.build(name=kind, cache=self.csv, metadata=self.meta)
                self.csv.write_bytes(original)

    def test_change_during_pair_read_is_detected(self):
        original = Path.read_bytes
        calls = 0

        def read(path):
            nonlocal calls
            value = original(path)
            if path == self.csv:
                calls += 1
                if calls == 1:
                    self.csv.write_bytes(value + b"\n")
            return value

        with patch.object(Path, "read_bytes", read), self.assertRaisesRegex(ValueError, "changed"):
            self.build(cache=self.csv, metadata=self.meta)

    def test_daily_partial_windows_all_rows_missing_kinds_and_unknown_money(self):
        self.f.add_event(
            NOW - timedelta(hours=17),
            "CYCLE",
            result={
                "status": "UNKNOWN",
                "position_protection": "unknown",
                "observed_positions": None,
            },
        )
        self.f.add_event(NOW - timedelta(hours=16), "HEALTH", result={})
        with sqlite3.connect(self.f.journal) as connection, connection:
            ident, raw = connection.execute(
                "SELECT id,payload FROM audit_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            event = json.loads(raw)
            event["config_hash"] = "f" * 64
            connection.execute(
                "UPDATE audit_events SET payload=? WHERE id=?", (json.dumps(event), ident)
            )
        batch = self.f.root / "daily-batch"
        seal_batch(
            self.f.journal,
            self.f.protocol,
            batch,
            since=NOW - timedelta(days=1),
            until=NOW,
            now=NOW,
        )
        value = create_coverage(batch, self.f.journal, self.f.root / "daily", now=NOW)
        self.assertEqual(len(value["daily"]), 2)
        self.assertEqual(sum(d["source_window_records"] for d in value["daily"]), 4)
        self.assertEqual(sum(d["excluded_records"] for d in value["daily"]), 1)
        self.assertTrue(all(d["partial_day"] for d in value["daily"]))
        self.assertTrue(all("LIFECYCLE" in d["missing_audit_kinds"] for d in value["daily"]))
        self.assertTrue(all(d["observed_closed_net_usd"] is None for d in value["daily"]))
        self.assertTrue(all(d["cashflow_total_usd"] is None for d in value["daily"]))
        self.assertIsNone(value["feed"])

    def test_cli_and_tampered_attachment_or_report_cannot_pass(self):
        self.build(cache=self.csv, metadata=self.meta)
        with patch("builtins.print"):
            self.assertEqual(
                main(["--verify", str(self.f.root / "coverage"), "--journal", str(self.f.journal)]),
                0,
            )
        target = self.f.root / "coverage" / "coverage.json"
        value = json.loads(target.read_bytes())
        value["daily"][0]["source_window_records"] += 1
        target.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            verify_coverage(self.f.root / "coverage", journal=self.f.journal)

    def test_batch_change_after_parent_verification_cannot_gain_source_bound_status(self):
        from scripts.ops.c22_forward_seal import verify_batch

        def change_after_verify(*args, **kwargs):
            result = verify_batch(*args, **kwargs)
            path = self.batch / "audit.jsonl"
            rows = path.read_text().splitlines()
            row = json.loads(rows[0])
            row["payload"]["kind"] = "HEALTH"
            rows[0] = json.dumps(row)
            path.write_text("\n".join(rows) + "\n")
            return result

        with patch("scripts.ops.c22_forward_feed.verify_batch", side_effect=change_after_verify):
            with self.assertRaisesRegex(ValueError, "changed|hash"):
                self.build()

    def test_scope_aggregation_and_future_metadata_never_attest_a_cache(self):
        for field, changed in [
            ("symbol", "EURUSD"),
            ("contract_id", "old"),
            ("aggregation", "DIRECT_MT5_M15"),
            ("version", True),
            ("created_utc", (NOW + timedelta(seconds=1)).isoformat()),
        ]:
            with self.subTest(field=field):
                original = dict(self.metadata)
                self.metadata[field] = changed
                self.save_meta()
                with self.assertRaises(ValueError):
                    self.build(name=field, cache=self.csv, metadata=self.meta)
                self.metadata = original
                self.save_meta()

    def test_nonfinite_or_impossible_price_geometry_rejected_not_used_for_profit(self):
        original = self.csv.read_bytes()
        for high in (float("nan"), 1.0):
            with self.subTest(high=high):
                frame = pd.read_csv(self.csv, index_col=0)
                frame.iloc[0, frame.columns.get_loc("high")] = high
                frame.to_csv(self.csv)
                self.metadata["sha256"] = hashlib.sha256(self.csv.read_bytes()).hexdigest()
                self.save_meta()
                with self.assertRaisesRegex(ValueError, "ohlc"):
                    self.build(cache=self.csv, metadata=self.meta)
                self.csv.write_bytes(original)

    def test_original_inputs_unchanged_and_copied_cache_tamper_detected(self):
        files = [
            self.f.journal,
            self.csv,
            self.meta,
            self.batch / "audit.jsonl",
            self.batch / "manifest.json",
        ]
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        self.build(cache=self.csv, metadata=self.meta)
        self.assertEqual(
            before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        )
        path = self.f.root / "coverage" / "cache.csv"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "hash"):
            verify_coverage(self.f.root / "coverage", journal=self.f.journal)


if __name__ == "__main__":
    unittest.main()
