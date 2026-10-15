"""Frozen public catalog outputs captured before mechanical separation."""

import hashlib
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts.research.bidirectional_campaign import contracts, main
from tests.research.test_breakout_logic import BROKER, START, END, sample


class CatalogParityTests(unittest.TestCase):
    def test_all_catalogs_preserve_complete_ordered_contracts(self):
        frozen = json.loads(
            (Path(__file__).resolve().parents[1] / "fixtures/research_catalog_hashes.json").read_text()
        )
        for name, expected in frozen.items():
            with self.subTest(catalog=name):
                values = contracts(name)
                self.assertEqual(len(values), expected["count"])
                digest = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
                self.assertEqual(digest, expected["sha256"])

    def test_resume_rejects_changed_extracted_source(self):
        frame, ticks = sample()
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "campaign"
            with (
                patch(
                    "scripts.research.bidirectional_campaign.load_data",
                    return_value=(frame, ticks, BROKER, {"synthetic": True}),
                ),
                patch("scripts.research.bidirectional_campaign.START", START),
                patch(
                    "scripts.research.bidirectional_campaign.TRAIN_END", START + (END - START) / 2
                ),
                patch("scripts.research.bidirectional_campaign.END", END),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                args = ["--output", str(output), "--limit", "1"]
                main(args)
                protocol = json.loads((output / "protocol.json").read_text())
                sources = Path(folder) / "sources"
                for name in protocol["source_hashes"]:
                    target = sources / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(name, target)
                leaf = sources / "scripts/research/catalog_m5.py"
                self.assertTrue(leaf.exists(), "transitive catalog source must be pinned")
                leaf.write_text(leaf.read_text() + "\n# altered frozen source\n")
                try:
                    os.chdir(sources)
                    with self.assertRaisesRegex(
                        ValueError, "resume protocol/source/input mismatch"
                    ):
                        main(args + ["--resume"])
                finally:
                    os.chdir(original_cwd)
