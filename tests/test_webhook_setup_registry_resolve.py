"""Tests for live vs dry-run SetupRegistry path resolution."""

import tempfile
import unittest
from pathlib import Path

from scripts.smc.setup_identity import SetupRegistry
from scripts.webhook.setup_registry_resolve import resolve_setup_registry


class SetupRegistryResolveTests(unittest.TestCase):
    def test_dry_run_defaults_to_memory(self):
        reg = resolve_setup_registry(None, dry_run=True)
        self.assertIsInstance(reg, SetupRegistry)
        self.assertIsNone(reg._persist_path)

    def test_live_defaults_to_persisted_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "setup_registry.json"
            reg = resolve_setup_registry(None, dry_run=False, default_live_path=str(path))
            self.assertEqual(reg._persist_path, path)
            reg.mark_terminal("SMC_LIVE_1", "ttl_expired")
            self.assertTrue(path.is_file())
            reloaded = resolve_setup_registry(str(path), dry_run=True)
            self.assertTrue(reloaded.is_blocked("SMC_LIVE_1"))

    def test_explicit_path_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "explicit.json"
            reg = resolve_setup_registry(str(path), dry_run=True)
            self.assertEqual(reg._persist_path, path)


if __name__ == "__main__":
    unittest.main()
