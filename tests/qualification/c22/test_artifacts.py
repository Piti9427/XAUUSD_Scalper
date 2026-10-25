"""Public artifact integrity behavior."""

import tempfile
import unittest
from pathlib import Path

from scripts.qualification.c22.artifacts import read_json


class ArtifactTests(unittest.TestCase):
    def test_nonfinite_and_duplicate_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "evidence.json"
            for content in ('{"profit":NaN}', '{"status":"PASS","status":"FAIL"}'):
                path.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    read_json(path)
