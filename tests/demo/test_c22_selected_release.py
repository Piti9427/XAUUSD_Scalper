"""Deterministic selected release never bundles financial state or credentials."""

import importlib.util
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("selected_release", ROOT / "deploy/c22-demo/prepare_selected_release.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SelectedReleaseTests(unittest.TestCase):
    def test_archive_is_deterministic_shadow_only_and_exclusive(self):
        with TemporaryDirectory(dir=ROOT / "runs") as folder:
            root = Path(folder)
            old_files = {
                "scripts/demo_runtime/cli.py": b'"""Frozen runtime fixture."""\n',
                "config/c22h4-demo.json": b'{}\n',
            }
            selected_files = {
                "scripts/c22_selected/__init__.py": b'"""Selected fixture."""\n',
                "scripts/ops/mt5_wine_c22_selected.py": b'"""Shadow entry fixture."""\n',
            }
            config = {
                "contract_id": "26b8bcd69e043653", "volume": 0.01,
                "real_money": "PROHIBITED", "default_mode": "shadow",
                "source_hashes": {name: hashlib.sha256(data).hexdigest()
                                  for name, data in selected_files.items()},
            }
            files = old_files | selected_files | {
                "config/c22-selected-demo.json": json.dumps(config).encode(),
                "runs/c22-oracle-compat-2026-10-24/phase2-evidence/release-manifest.json":
                    json.dumps({"files": {name: hashlib.sha256(data).hexdigest()
                                           for name, data in old_files.items()}}).encode(),
                "config/private.env": b"SECRET_MUST_NOT_BE_BUNDLED=fixture\n",
                "data/private.sqlite3": b"financial state fixture",
            }
            for name, data in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            first = MODULE.build_release(root, root / "runs/first")
            second = MODULE.build_release(root, root / "runs/second")
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])
            self.assertEqual(first["changed_from_old_release"], [])
            with tarfile.open(first["archive"], "r:gz") as archive:
                names = archive.getnames()
                self.assertTrue(all(not name.startswith(("data/", "runs/")) and not name.endswith((".env", ".sqlite3")) for name in names))
                stream = archive.extractfile("c22-selected-shadow.service")
                self.assertIsNotNone(stream)
                unit = stream.read().decode()
                self.assertIn("MT5_ENABLE_DEMO_ORDER_SEND=0", unit)
                self.assertNotIn("--execute", unit)
                self.assertNotIn("Conflicts=", unit)
                self.assertIn("c22-selected-shadow.sqlite3", unit)
            with self.assertRaises(ValueError):
                MODULE.build_release(root, root / "runs/first")
