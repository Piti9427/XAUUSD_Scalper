"""Focused source-data validation for public monthly ZIP import."""

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.research.public_exness_archive import import_month
from scripts.research.tune_breakout_logic import sha256


class PublicArchiveTests(unittest.TestCase):
    def make_archive(self, root, stamps):
        name = "Exness_XAUUSDm_2024_09.zip"
        rows = ["Exness,Symbol,Timestamp,Bid,Ask"]
        rows += [f"exness,XAUUSDm,{stamp},2500.0,2500.2" for stamp in stamps]
        with zipfile.ZipFile(root / name, "w") as archive:
            archive.writestr(name[:-4] + ".csv", "\n".join(rows) + "\n")
        (root / "discovery").mkdir()
        return dict(month="2024-09", file=name, sha256=sha256(root / name))

    def test_import_excludes_incomplete_m15_without_filling_missing_minute(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stamps = [f"2024-09-02T00:{minute:02d}:00.000Z" for minute in range(29)]
            item = self.make_archive(root, stamps)
            audit, bars = import_month(root, item)
            self.assertEqual(audit["ticks"], 29)
            self.assertEqual(len(bars), 1)
            self.assertEqual(str(bars.index[0]), "2024-09-02 00:00:00+00:00")

    def test_import_rejects_reversed_source_ticks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = self.make_archive(root, ["2024-09-02T00:01:00.000Z", "2024-09-02T00:00:00.000Z"])
            with self.assertRaisesRegex(ValueError, "unsorted ticks"):
                import_month(root, item)
            self.assertFalse((root / "discovery" / "2024-09.npz").exists())
