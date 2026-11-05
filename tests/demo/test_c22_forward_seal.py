"""Passive audit batches preserve provenance; reused history is not holdout."""

from datetime import datetime, timedelta, timezone
from contextlib import closing
import hashlib
import io
import json
import tarfile
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from scripts.ops.c22_forward_seal import freeze_protocol, seal_batch, verify_batch

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 28, 15, tzinfo=timezone.utc)
FINGERPRINT = "a" * 16


class ForwardSealTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(dir=ROOT / "runs")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.journal = self.root / "source.sqlite3"
        self.manifest = self.root / "source-manifest.json"
        payload = {
            name: ("# deterministic fixture " + name + "\n").encode()
            for name in (
                "scripts/c22_selected/runner.py",
                "scripts/c22_selected/strategy.py",
                "scripts/c22_selected/execution.py",
                "scripts/demo_runtime/runner.py",
                *(f"scripts/demo_runtime/helper_{index:02}.py" for index in range(17)),
            )
        }
        config = dict(
            contract_id="26b8bcd69e043653",
            volume=0.01,
            source_hashes={name: hashlib.sha256(raw).hexdigest() for name, raw in payload.items()},
        )
        payload["config/c22-selected-demo.json"] = json.dumps(config, sort_keys=True).encode()
        self.config = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        base = b"".join(
            payload[name] for name in sorted(payload) if name.startswith("scripts/demo_runtime/")
        )
        digest = hashlib.sha256(hashlib.sha256(base).hexdigest().encode())
        for name in sorted(payload):
            if name.startswith("scripts/c22_selected/"):
                digest.update(Path(name).name.encode())
                digest.update(payload[name])
        self.release = digest.hexdigest()
        self.manifest.write_text(
            json.dumps(
                {"files": {name: hashlib.sha256(raw).hexdigest() for name, raw in payload.items()}}
            )
        )
        with tarfile.open(self.root / "release.tar.gz", "w:gz") as archive:
            for name, raw in payload.items():
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                archive.addfile(info, io.BytesIO(raw))
        with closing(sqlite3.connect(self.journal)) as connection, connection:
            connection.execute(
                "CREATE TABLE audit_events(id INTEGER PRIMARY KEY,payload TEXT NOT NULL)"
            )
            connection.execute("CREATE TABLE kv(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            connection.execute("INSERT INTO kv VALUES (?,?)", ("identity", json.dumps(FINGERPRINT)))
        self.add_event(NOW - timedelta(minutes=2), "SIGNAL", direction=-1, bar="prior")
        self.add_event(
            NOW - timedelta(minutes=1),
            "CYCLE",
            result={"status": "BLOCKED", "reason": "cost_spec_mismatch"},
        )
        self.protocol = self.root / "protocol"
        self.freeze = NOW + timedelta(seconds=1)
        freeze_protocol(
            self.journal,
            self.manifest,
            self.protocol,
            release_hash=self.release,
            config_hash=self.config,
            account_fingerprint=FINGERPRINT,
            freeze_utc=self.freeze,
            exposed_through_utc=NOW,
            now=NOW,
        )

    def add_event(self, stamp, kind, **fields):
        with closing(sqlite3.connect(self.journal)) as connection, connection:
            ident = connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] + 1
            event = dict(
                event_id=f"event-{ident}",
                utc=stamp.isoformat(),
                kind=kind,
                release_hash=self.release,
                config_hash=self.config,
                account_fingerprint=FINGERPRINT,
                **fields,
            )
            connection.execute("INSERT INTO audit_events VALUES (?,?)", (ident, json.dumps(event)))

    def test_reused_history_seals_every_kind_without_claiming_fills_or_prospective_profit(self):
        target = self.root / "history"
        result = seal_batch(
            self.journal,
            self.protocol,
            target,
            since=NOW - timedelta(minutes=3),
            until=NOW,
            now=NOW,
        )
        self.assertEqual(result["data_classification"], "REUSED_HISTORY")
        self.assertEqual(result["records"], 2)
        self.assertEqual(result["prospective_observations"], 0)
        self.assertEqual(result["report"]["distinct_signal_bars"], 1)
        self.assertEqual(result["report"]["cycle_count"], 1)
        self.assertEqual(result["report"]["blocked_cycles"], {"cost_spec_mismatch": 1})
        self.assertIsNone(result["report"]["broker_fill_count"])
        self.assertIsNone(result["report"]["cashflow_total_usd"])
        self.assertEqual(result["report"]["cashflows"], "NOT_CAPTURED_IN_AUDIT")
        self.assertEqual(result["report"]["profitability"], "INCONCLUSIVE")
        self.assertFalse(result["execution_authorized"])
        verified = verify_batch(target)
        self.assertEqual(verified["records"], 2)
        self.assertEqual(verify_batch(target, journal=self.journal)["records"], 2)
        with self.assertRaises(ValueError):
            seal_batch(
                self.journal,
                self.protocol,
                target,
                since=NOW - timedelta(minutes=3),
                until=NOW,
                now=NOW,
            )

    def test_future_passive_rows_are_prospective_only_after_real_freeze_and_all_original_records_retained(
        self,
    ):
        self.add_event(self.freeze + timedelta(seconds=1), "SIGNAL", direction=1, bar="new")
        self.add_event(
            self.freeze + timedelta(seconds=2),
            "CYCLE",
            result={"status": "UNKNOWN", "position_protection": "unknown"},
        )
        self.add_event(self.freeze + timedelta(seconds=3), "REQUEST", request={"volume": 0.01})
        self.add_event(self.freeze + timedelta(seconds=4), "RESPONSE", response=None)
        self.add_event(
            self.freeze + timedelta(seconds=5),
            "LIFECYCLE",
            event={"kind": "CLOSED", "net": -1.25, "position_id": 7},
        )
        result = seal_batch(
            self.journal,
            self.protocol,
            self.root / "future",
            since=self.freeze,
            until=self.freeze + timedelta(seconds=6),
            now=self.freeze + timedelta(seconds=7),
        )
        self.assertEqual(result["data_classification"], "PROSPECTIVE_COLLECTION_ONLY")
        self.assertEqual(result["prospective_observations"], 5)
        self.assertEqual(result["report"]["unknown_cycles"], 1)
        self.assertEqual(result["report"]["request_count"], 1)
        self.assertEqual(result["report"]["response_count"], 1)
        self.assertEqual(result["report"]["closed_position_events"], 1)
        self.assertEqual(result["report"]["observed_closed_net_usd"], -1.25)
        self.assertEqual(result["report"]["profitability"], "INCONCLUSIVE")
        self.assertEqual(result["report"]["costs"], "COST_INCONCLUSIVE")

    def test_tamper_truncation_wrong_cohort_or_reused_event_id_fails_integrity(self):
        for kind in ("tamper", "truncate", "cohort", "event_id"):
            with self.subTest(kind=kind):
                target = self.root / kind
                seal_batch(
                    self.journal,
                    self.protocol,
                    target,
                    since=NOW - timedelta(minutes=3),
                    until=NOW,
                    now=NOW,
                )
                events = target / "audit.jsonl"
                rows = events.read_text().splitlines()
                if kind == "truncate":
                    events.write_text(rows[0] + "\n")
                else:
                    row = json.loads(rows[-1])
                    if kind == "tamper":
                        row["payload"]["result"]["reason"] = "changed"
                    elif kind == "cohort":
                        row["payload"]["release_hash"] = "f" * 64
                    else:
                        row["payload"]["event_id"] = "event-1"
                    rows[-1] = json.dumps(row)
                    events.write_text("\n".join(rows) + "\n")
                with self.assertRaises(ValueError):
                    verify_batch(target)

    def test_backdated_protocol_future_window_and_unopened_claim_without_new_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "freeze"):
            freeze_protocol(
                self.journal,
                self.manifest,
                self.root / "backdated",
                release_hash=self.release,
                config_hash=self.config,
                account_fingerprint=FINGERPRINT,
                freeze_utc=NOW - timedelta(seconds=1),
                exposed_through_utc=NOW - timedelta(seconds=2),
                now=NOW,
            )
        with self.assertRaisesRegex(ValueError, "window"):
            seal_batch(
                self.journal,
                self.protocol,
                self.root / "future-invalid",
                since=self.freeze,
                until=self.freeze + timedelta(hours=1),
                now=NOW,
            )
        missing = seal_batch(
            self.journal,
            self.protocol,
            self.root / "missing",
            since=self.freeze,
            until=self.freeze + timedelta(seconds=5),
            now=self.freeze + timedelta(seconds=6),
        )
        self.assertEqual(missing["records"], 0)
        self.assertEqual(missing["report"]["coverage"], "NO_MATCHING_RECORDS")
        self.assertEqual(missing["prospective_observations"], 0)
        self.assertEqual(missing["report"]["profitability"], "INCONCLUSIVE")

    def test_empty_manifest_foreign_account_and_rewound_bootstrap_rejected(self):
        self.manifest.write_text("{}")
        with self.assertRaisesRegex(ValueError, "manifest"):
            freeze_protocol(
                self.journal,
                self.manifest,
                self.root / "bad-manifest",
                release_hash=self.release,
                config_hash=self.config,
                account_fingerprint=FINGERPRINT,
                freeze_utc=self.freeze,
                exposed_through_utc=NOW,
                now=NOW,
            )
        with closing(sqlite3.connect(self.journal)) as connection, connection:
            connection.execute(
                "UPDATE kv SET value=? WHERE key='identity'", (json.dumps("f" * 16),)
            )
        with self.assertRaisesRegex(ValueError, "account"):
            seal_batch(
                self.journal,
                self.protocol,
                self.root / "wrong-account",
                since=self.freeze,
                until=self.freeze + timedelta(seconds=5),
                now=self.freeze + timedelta(seconds=6),
            )
        with closing(sqlite3.connect(self.journal)) as connection, connection:
            connection.execute(
                "UPDATE kv SET value=? WHERE key='identity'", (json.dumps(FINGERPRINT),)
            )
            connection.execute("DELETE FROM audit_events WHERE id=1")
        with self.assertRaisesRegex(ValueError, "lineage"):
            seal_batch(
                self.journal,
                self.protocol,
                self.root / "rewound",
                since=self.freeze,
                until=self.freeze + timedelta(seconds=5),
                now=self.freeze + timedelta(seconds=6),
            )

    def test_all_window_cohorts_and_foreign_account_rows_retained_with_denominators(self):
        self.add_event(self.freeze + timedelta(seconds=1), "SIGNAL", direction=1, bar="new")
        self.add_event(self.freeze + timedelta(seconds=2), "CYCLE", result={"status": "WAIT"})
        self.add_event(self.freeze + timedelta(seconds=3), "CYCLE", result={"status": "UNKNOWN"})
        with closing(sqlite3.connect(self.journal)) as connection, connection:
            connection.execute(
                "UPDATE audit_events SET payload=json_set(payload,'$.release_hash',?) WHERE id=4",
                ("f" * 64,),
            )
            connection.execute(
                "UPDATE audit_events SET payload=json_set(payload,'$.account_fingerprint',?) WHERE id=5",
                ("f" * 16,),
            )
        result = seal_batch(
            self.journal,
            self.protocol,
            self.root / "excluded",
            since=self.freeze,
            until=self.freeze + timedelta(seconds=4),
            now=self.freeze + timedelta(seconds=5),
        )
        self.assertEqual(result["records"], 3)
        self.assertEqual(result["matched_records"], 1)
        self.assertEqual(
            result["report"]["excluded_by_reason"],
            {"different_or_missing_cohort": 1, "account_mismatch": 1},
        )
        self.assertEqual(result["data_classification"], "REUSED_HISTORY")
        self.assertEqual(verify_batch(self.root / "excluded")["records"], 3)

    def test_actual_signed_cashflow_attachment_reconciles_or_rejects_wrong_proof(self):
        stamp = self.freeze + timedelta(seconds=1)
        self.add_event(stamp, "CYCLE", result={"status": "WAIT"})
        until = self.freeze + timedelta(seconds=2)
        packet = dict(
            source="existing_sender_reads",
            account_fingerprint=FINGERPRINT,
            release_hash=self.release,
            config_hash=self.config,
            captured_utc=until.isoformat(),
            read_observed_utc=until.isoformat(),
            execution_authorized=False,
            demo_verified=True,
            hedging_verified=True,
            symbol="XAUUSDm",
            positions=0,
            orders=0,
            terminal={"connected": True},
            account={"currency": "USD", "balance": 75},
            history_complete=True,
            history_start_utc="1970-01-01T00:00:00+00:00",
            history_end_utc=until.isoformat(),
            history_deals_total=2,
            history_deals=[
                dict(
                    ticket=1,
                    type=2,
                    time_msc=int((NOW - timedelta(days=1)).timestamp() * 1000),
                    profit=100,
                    commission=0,
                    swap=0,
                    fee=0,
                ),
                dict(
                    ticket=2,
                    type=2,
                    time_msc=int(stamp.timestamp() * 1000),
                    profit=-25,
                    commission=0,
                    swap=0,
                    fee=0,
                ),
            ],
        )
        result = seal_batch(
            self.journal,
            self.protocol,
            self.root / "ledger",
            since=self.freeze,
            until=until,
            now=until,
            broker_bytes=json.dumps(packet).encode(),
        )
        self.assertEqual(result["report"]["cashflow_total_usd"], -25)
        self.assertEqual(result["broker_attachment"]["epoch_cash_total_usd"], 75)
        self.assertEqual(
            verify_batch(self.root / "ledger")["report"]["cashflows"],
            "OBSERVED_RECONCILED_SAME_SENDER_LEDGER",
        )
        for field, value in [
            ("positions", 1),
            ("account_fingerprint", "f" * 16),
            ("history_deals_total", 1),
        ]:
            bad = dict(packet, **{field: value})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "binding"):
                seal_batch(
                    self.journal,
                    self.protocol,
                    self.root / ("bad-" + field),
                    since=self.freeze,
                    until=until,
                    now=until,
                    broker_bytes=json.dumps(bad).encode(),
                )
        bad = dict(packet, account={"currency": "USD", "balance": 100})
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            seal_batch(
                self.journal,
                self.protocol,
                self.root / "bad-cash",
                since=self.freeze,
                until=until,
                now=until,
                broker_bytes=json.dumps(bad).encode(),
            )

    def test_manifest_cannot_relabel_reused_history_or_unknown_net_as_profit(self):
        target = self.root / "relabel"
        seal_batch(
            self.journal,
            self.protocol,
            target,
            since=NOW - timedelta(minutes=3),
            until=NOW,
            now=NOW,
        )
        manifest = target / "manifest.json"
        value = json.loads(manifest.read_bytes())
        value["data_classification"] = "PROSPECTIVE_COLLECTION_ONLY"
        value["prospective_observations"] = value["records"]
        manifest.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "classification"):
            verify_batch(target)
        self.add_event(
            self.freeze + timedelta(seconds=1),
            "LIFECYCLE",
            event={"kind": "CLOSED", "position_id": 7},
        )
        result = seal_batch(
            self.journal,
            self.protocol,
            self.root / "unknown-net",
            since=self.freeze,
            until=self.freeze + timedelta(seconds=2),
            now=self.freeze + timedelta(seconds=3),
        )
        self.assertIsNone(result["report"]["observed_closed_net_usd"])
        self.assertEqual(result["report"]["closed_net_missing_events"], 1)

    def test_independent_source_verification_rejects_another_backup(self):
        target = self.root / "independent"
        seal_batch(
            self.journal,
            self.protocol,
            target,
            since=NOW - timedelta(minutes=3),
            until=NOW,
            now=NOW,
        )
        self.add_event(NOW, "CYCLE", result={"status": "WAIT"})
        with self.assertRaisesRegex(ValueError, "source_mismatch"):
            verify_batch(target, journal=self.journal)


if __name__ == "__main__":
    unittest.main()
