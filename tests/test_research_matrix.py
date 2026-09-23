"""Falsification tests for the offline BotTradeGold matrix audit."""

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.research.matrix import audited_run, build_matrix, check_trade_log


class MatrixAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.baseline = self.root / "baseline"
        self.baseline.mkdir()
        self.code = self.root / "code"
        self.code.mkdir()
        (self.code / "run.py").write_text("# pinned run\n")
        self.names = ("Donchian20", "Donchian20__rsi", "A_TrendStructure")
        self.nets = {
            "Donchian20": (10.0, -4.0),
            "Donchian20__rsi": (5.0, -2.0),
            "A_TrendStructure": (-1.0, -1.0),
        }
        manifest = {
            "version": "btg-research-v1", "years": [2010, 2011],
            "strategies": [
                {"name": n, "family": "donchian", "filters": ["rsi"] if n.endswith("__rsi") else []}
                for n in self.names
            ],
            "costs": {"commission_per_unit_roundtrip": 0, "slippage": 0, "swap_per_unit_night": 0},
            "delay_minutes": 0, "source_revision": "test-pinned",
            "inputs": [{"file": "test.csv", "sha256": "test-sha", "url": "https://example.test/test.csv"}],
            "code_sha256": {"run.py": hashlib.sha256((self.code / "run.py").read_bytes()).hexdigest()},
        }
        (self.baseline / "manifest.json").write_text(json.dumps(manifest))
        (self.baseline / "data-audit.json").write_text("[]")
        (self.baseline / "COMPLETE").write_text("complete")
        (self.baseline / "trades").mkdir()
        annual, summary = [], []
        for n in self.names:
            for mode in ("common", "native"):
                vals = self.nets[n]
                for year, value in zip((2010, 2011), vals):
                    annual.append({"strategy": n, "mode": mode, "year": year,
                                   "trades": 1, "net": value, "total_r": value,
                                   "pf": "" if value >= 0 else 0})
                    self.write_trade(n, mode, year, value)
                gains = sum(max(0, v) for v in vals)
                losses = -sum(min(0, v) for v in vals)
                summary.append({"strategy": n, "mode": mode, "trades": 2,
                                "net": sum(vals), "total_r": sum(vals),
                                "pf": gains / losses if losses else "",
                                "years": 2, "positive_years": sum(v > 0 for v in vals),
                                "worst_year_net": min(vals), "production_ready": "False"})
        self.write_rows(self.baseline / "annual.csv", annual)
        self.write_rows(self.baseline / "summary.csv", summary)

    @staticmethod
    def write_rows(path, rows):
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def write_trade(self, name, mode, year, net):
        path = self.baseline / "trades" / f"{name}__{mode}__{year}.csv"
        self.write_rows(path, [{"signal_time": f"{year}-01-01 00:00:00+00:00",
                                "entry_time": f"{year}-01-01 00:01:00+00:00",
                                "exit_time": f"{year}-01-01 00:02:00+00:00",
                                "net": net, "r": net}])

    def test_family_matrix_preserves_observed_metrics_and_no_promotion(self):
        result = build_matrix(self.baseline, self.root / "out", self.code, expected_names=3, expected_years=2)
        self.assertEqual(result["counts"]["families"], 1)
        self.assertEqual(result["counts"]["trade_logs_verified"], 12)
        with (self.root / "out" / "family-matrix.csv").open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(float(rows[0]["net"]), 6)
        self.assertEqual(float(rows[0]["pf"]), 2.5)
        self.assertEqual(rows[0]["contract_status"], "reconstructed")
        self.assertEqual(rows[0]["production_ready"], "False")

    def test_ablation_uses_matched_year_delta(self):
        build_matrix(self.baseline, self.root / "out", self.code, expected_names=3, expected_years=2)
        with (self.root / "out" / "ablation-matrix.csv").open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(float(rows[0]["delta_net"]), -3)
        self.assertEqual(int(rows[0]["years_variant_net_higher"]), 1)
        self.assertEqual(int(rows[0]["years_base_net_higher"]), 1)

    def test_missing_complete_fails_closed(self):
        (self.baseline / "COMPLETE").unlink()
        with self.assertRaisesRegex(ValueError, "COMPLETE marker missing"):
            audited_run(self.baseline, self.code, expected_names=3, expected_years=2)

    def test_code_hash_mismatch_fails_closed(self):
        (self.code / "run.py").write_text("# edited after backtest\n")
        with self.assertRaisesRegex(ValueError, "code hash mismatch"):
            audited_run(self.baseline, self.code, expected_names=3, expected_years=2)

    def test_trade_reconciliation_fails_closed(self):
        self.write_trade("Donchian20", "native", 2010, 11.0)
        with self.assertRaisesRegex(ValueError, "Trade/annual reconciliation failed"):
            audited_run(self.baseline, self.code, expected_names=3, expected_years=2)

    def test_noncausal_trade_fails_closed(self):
        path = self.baseline / "trades" / "Donchian20__native__2010.csv"
        self.write_rows(path, [{"signal_time": "2010-01-01 00:02:00+00:00",
                                "entry_time": "2010-01-01 00:01:00+00:00",
                                "exit_time": "2010-01-01 00:03:00+00:00",
                                "net": 10, "r": 10}])
        with self.assertRaisesRegex(ValueError, "Noncausal"):
            check_trade_log(path, {"trades": 1, "net": 10, "total_r": 10, "pf": ""})

    def test_naive_and_non_utc_trade_timestamps_fail_closed(self):
        path = self.baseline / "trades" / "Donchian20__native__2010.csv"
        for suffix in ("", "+02:00"):
            with self.subTest(suffix=suffix):
                self.write_rows(path, [{"signal_time": f"2010-01-01 00:00:00{suffix}",
                                        "entry_time": f"2010-01-01 00:01:00{suffix}",
                                        "exit_time": f"2010-01-01 00:02:00{suffix}",
                                        "net": 10, "r": 10}])
                with self.assertRaisesRegex(ValueError, "Non-UTC trade timestamp"):
                    check_trade_log(path, {"trades": 1, "net": 10,
                                           "total_r": 10, "pf": ""})

    def test_reconstructed_contracts_never_promote(self):
        summary_path = self.baseline / "summary.csv"
        with summary_path.open() as f:
            rows = list(csv.DictReader(f))
        rows[0]["production_ready"] = "True"
        self.write_rows(summary_path, rows)
        with self.assertRaisesRegex(ValueError, "Unexpected production promotion"):
            audited_run(self.baseline, self.code, expected_names=3, expected_years=2)


if __name__ == "__main__":
    unittest.main()
