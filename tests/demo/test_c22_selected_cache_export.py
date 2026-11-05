"""Changed-prefix export avoids repeated CSV work without hiding repair/retry."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import pandas as pd

from scripts.c22_selected.runner import SelectedDemoRunner


class CacheExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "bars.csv"
        self.bars = pd.DataFrame(
            dict(open=[10.0, 11.0], high=[12.0, 13.0], low=[9.0, 10.0], close=[11.0, 12.0]),
            index=pd.date_range("2026-10-01", periods=2, freq="15min", tz="UTC"),
        )
        self.runner = NS(strategy=NS(cache=NS(bars=self.bars)))

    def export(self, path=None, **kwargs):
        SelectedDemoRunner.export_cache(self.runner, path or self.path, **kwargs)

    def test_unchanged_prefix_skips_csv_and_replacement_but_explicit_export_still_writes(self):
        with patch.object(self.bars, "to_csv", wraps=self.bars.to_csv) as write:
            self.export(only_if_changed=True)
            signature = self.path.stat()
            self.export(only_if_changed=True)
            self.assertEqual(write.call_count, 1)
            self.assertEqual(self.path.stat().st_mtime_ns, signature.st_mtime_ns)
            self.export()
            self.assertEqual(write.call_count, 2)

    def test_new_causal_prefix_or_reset_writes_exact_new_data(self):
        self.export(only_if_changed=True)
        grown = pd.concat(
            [
                self.bars,
                self.bars.iloc[[-1]].set_axis([self.bars.index[-1] + pd.Timedelta(minutes=15)]),
            ]
        )
        self.runner.strategy.cache.bars = grown
        self.export(only_if_changed=True)
        self.assertEqual(len(pd.read_csv(self.path)), 3)
        reset = grown.copy()
        reset.iloc[-1, 3] = 99.0
        self.runner.strategy.cache.bars = reset
        self.export(only_if_changed=True)
        self.assertEqual(pd.read_csv(self.path).close.iloc[-1], 99.0)

    def test_missing_changed_or_different_target_is_repaired(self):
        self.export(only_if_changed=True)
        expected = self.path.read_bytes()
        self.path.unlink()
        self.export(only_if_changed=True)
        self.assertEqual(self.path.read_bytes(), expected)
        self.path.write_bytes(b"external invalid data\n")
        self.export(only_if_changed=True)
        self.assertEqual(self.path.read_bytes(), expected)
        alternate = self.path.with_name("alternate.csv")
        self.export(alternate, only_if_changed=True)
        self.assertEqual(alternate.read_bytes(), expected)

    def test_write_failure_does_not_mark_prefix_successful_or_replace_prior_evidence(self):
        self.export(only_if_changed=True)
        expected = self.path.read_bytes()
        fresh = self.bars.copy()
        fresh.iloc[-1, 3] = 88.0
        self.runner.strategy.cache.bars = fresh
        with patch.object(fresh, "to_csv", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.export(only_if_changed=True)
        self.assertEqual(self.path.read_bytes(), expected)
        self.export(only_if_changed=True)
        self.assertEqual(pd.read_csv(self.path).close.iloc[-1], 88.0)
