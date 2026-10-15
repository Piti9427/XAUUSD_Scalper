"""Evidence and arithmetic checks for BotTradeGold research screening."""

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.research.evidence_gate import build_gate, evidence_row, verify_source_cache


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.code = self.root / "code"
        self.code.mkdir()
        (self.code / "run.py").write_text("# frozen\n")
        self.baseline = self.root / "baseline"
        (self.baseline / "trades").mkdir(parents=True)
        (self.baseline / "COMPLETE").write_text("complete\n")
        (self.baseline / "data-audit.json").write_text("[]\n")
        source = self.cache / "prices.csv"
        source.write_bytes(b"observed input bytes\n")
        self.manifest = {
            "version": "btg-research-v1",
            "years": [2025, 2026],
            "strategies": [
                {"name": "Donchian20", "family": "donchian", "filters": [], "reconstruction": True}
            ],
            "costs": {
                "units": 1.0,
                "commission_per_unit_roundtrip": 0,
                "slippage": 0,
                "swap_per_unit_night": 0,
            },
            "delay_minutes": 0,
            "source_revision": "fixture",
            "inputs": [
                {
                    "file": source.name,
                    "bytes": source.stat().st_size,
                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "url": "https://example.test/prices.csv",
                }
            ],
            "code_sha256": {
                "run.py": hashlib.sha256((self.code / "run.py").read_bytes()).hexdigest()
            },
        }
        (self.baseline / "manifest.json").write_text(json.dumps(self.manifest))
        annual, summary = [], []
        for mode in ("common", "native"):
            for year, net in ((2025, -2.0), (2026, 5.0)):
                annual.append(
                    {
                        "strategy": "Donchian20",
                        "mode": mode,
                        "year": year,
                        "trades": 1,
                        "net": net,
                        "total_r": net,
                        "pf": "" if net > 0 else 0,
                    }
                )
                self.write_csv(
                    self.baseline / "trades" / f"Donchian20__{mode}__{year}.csv",
                    [
                        {
                            "signal_time": f"{year}-01-01 00:00:00+00:00",
                            "entry_time": f"{year}-01-01 00:01:00+00:00",
                            "exit_time": f"{year}-01-01 00:02:00+00:00",
                            "net": net,
                            "r": net,
                        }
                    ],
                )
            summary.append(
                {
                    "strategy": "Donchian20",
                    "mode": mode,
                    "trades": 2,
                    "net": 3,
                    "total_r": 3,
                    "pf": 2.5,
                    "years": 2,
                    "positive_years": 1,
                    "worst_year_net": -2,
                    "production_ready": False,
                }
            )
        self.write_csv(self.baseline / "annual.csv", annual)
        self.write_csv(self.baseline / "summary.csv", summary)

    @staticmethod
    def write_csv(path, rows):
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_source_bytes_are_verified_and_tampering_fails_closed(self):
        self.assertEqual(verify_source_cache(self.cache, self.manifest)["files_verified"], 1)
        (self.cache / "prices.csv").write_bytes(b"Observed input bytes\n")
        with self.assertRaisesRegex(ValueError, "Source hash mismatch"):
            verify_source_cache(self.cache, self.manifest)

    def test_gate_uses_measured_rows_and_never_promotes(self):
        out = self.root / "out"
        build_gate(self.baseline, self.cache, out, self.code, expected_names=1, expected_years=2)
        with (out / "family-screen.csv").open(newline="") as f:
            row = next(csv.DictReader(f))
        self.assertEqual(float(row["native_net"]), 3)
        self.assertEqual(float(row["extra_cost_to_zero_per_unit_roundtrip"]), 1.5)
        self.assertEqual(float(row["net_excluding_latest_year"]), -2)
        self.assertEqual(float(row["largest_positive_year_share"]), 1)
        self.assertEqual(row["research_status"], "positive_reconstructed_only")
        self.assertEqual(row["production_ready"], "False")
        gate = json.loads((out / "gate-manifest.json").read_text())
        self.assertEqual(gate["source_cache"]["files_verified"], 1)
        self.assertEqual(
            gate["audit_code_sha256"]["evidence_gate.py"],
            hashlib.sha256(Path(build_gate.__code__.co_filename).read_bytes()).hexdigest(),
        )

    def test_negative_native_net_is_rejected_without_fake_cost_budget(self):
        for path in (self.baseline / "summary.csv", self.baseline / "annual.csv"):
            with path.open(newline="") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                if row["mode"] == "native":
                    row["net"] = -abs(float(row["net"]))
            self.write_csv(path, rows)
        # Audit must reject an internally inconsistent edited result.
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            build_gate(
                self.baseline,
                self.cache,
                self.root / "out",
                self.code,
                expected_names=1,
                expected_years=2,
            )

    def test_nonpositive_observation_has_no_cost_headroom(self):
        spec = {"name": "Donchian20", "family": "donchian"}
        summary = {
            ("Donchian20", "native"): {
                "net": -3,
                "total_r": -2,
                "trades": 2,
                "pf": 0.8,
                "positive_years": 1,
            },
            ("Donchian20", "common"): {"net": -5, "total_r": -4},
        }
        annual = {
            ("Donchian20", "native", "2025"): {"net": -4},
            ("Donchian20", "native", "2026"): {"net": 1},
        }
        row = evidence_row("Donchian20", spec, summary, annual, [2025, 2026], 1)
        self.assertEqual(row["research_status"], "nonpositive_reconstructed_native")
        self.assertIsNone(row["extra_cost_to_zero_per_unit_roundtrip"])
        self.assertFalse(row["production_ready"])


if __name__ == "__main__":
    unittest.main()
