"""Deterministic selected release never bundles financial state or credentials."""

import importlib.util
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "selected_release", ROOT / "deploy/c22-demo/prepare_selected_release.py"
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SelectedReleaseTests(unittest.TestCase):
    def test_archive_defaults_shadow_and_stages_exclusive_reviewed_execution(self):
        with TemporaryDirectory(dir=ROOT / "runs") as folder:
            root = Path(folder)
            old_files = {
                "scripts/demo_runtime/cli.py": b'"""Frozen runtime fixture."""\n',
                "config/c22h4-demo.json": b"{}\n",
            }
            selected_files = {
                "scripts/c22_selected/__init__.py": b'"""Selected fixture."""\n',
                "scripts/ops/mt5_wine_c22_selected.py": b'"""Shadow entry fixture."""\n',
                "scripts/ops/c22h4_readiness.py": b'"""Shared readiness fixture."""\n',
                "scripts/ops/c22_selected_readiness.py": b'"""Selected readiness fixture."""\n',
                "scripts/ops/c22_selected_watchdog.py": b'"""Read-only health fixture."""\n',
                "scripts/demo_runtime/boundary.py": b'"""Boundary observer fixture."""\n',
                "scripts/demo_runtime/diagnostics.py": b'"""Safe diagnostic contract fixture."""\n',
                "deploy/c22-demo/launch_selected_terminal.py": b'"""Terminal launcher fixture."""\n',
                "deploy/c22-demo/enable_selected_boot.py": b'"""Boot registration fixture."""\n',
            }
            config = {
                "contract_id": "26b8bcd69e043653",
                "volume": 0.01,
                "real_money": "PROHIBITED",
                "default_mode": "shadow",
                "source_hashes": {
                    name: hashlib.sha256(data).hexdigest() for name, data in selected_files.items()
                },
            }
            files = (
                old_files
                | selected_files
                | {
                    "config/c22-selected-demo.json": json.dumps(config).encode(),
                    "runs/c22-oracle-compat-2026-10-24/phase2-evidence/release-manifest.json": json.dumps(
                        {
                            "files": {
                                name: hashlib.sha256(data).hexdigest()
                                for name, data in old_files.items()
                            }
                        }
                    ).encode(),
                    "config/private.env": b"SECRET_MUST_NOT_BE_BUNDLED=fixture\n",
                    "data/private.sqlite3": b"financial state fixture",
                    "deploy/c22-demo/c22-selected-terminal-execution.ini": b"[Experts]\nEnabled=1\nAllowLiveTrading=1\nAllowDllImport=0\nAccount=1\nProfile=1\n",
                }
            )
            for name, data in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            first = MODULE.build_release(root, root / "runs/first")
            second = MODULE.build_release(root, root / "runs/second")
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])
            self.assertEqual(first["changed_from_old_release"], [])
            self.assertFalse(first["execution_authorized"])
            self.assertEqual(first["mode"], "shadow-default-execution-staged")
            self.assertRegex(first["builder_sha256"], r"\A[0-9a-f]{64}\Z")
            revised_source = (
                Path(MODULE.__file__)
                .read_text()
                .replace(
                    "Description=Selected C22 26b8 Demo execution (review required)",
                    "Description=Selected C22 26b8 Demo execution (revised review required)",
                )
            )
            self.assertNotEqual(revised_source, Path(MODULE.__file__).read_text())
            revised_path = root / "revised_builder.py"
            revised_path.write_text(revised_source)
            revised_spec = importlib.util.spec_from_file_location(
                "revised_selected_release", revised_path
            )
            assert revised_spec is not None and revised_spec.loader is not None
            revised_module = importlib.util.module_from_spec(revised_spec)
            revised_spec.loader.exec_module(revised_module)
            revised = revised_module.build_release(root, root / "runs/revised")
            self.assertNotEqual(first["release_id"], revised["release_id"])
            self.assertNotEqual(first["builder_sha256"], revised["builder_sha256"])
            with tarfile.open(first["archive"], "r:gz") as archive:
                names = archive.getnames()
                self.assertTrue(
                    all(
                        not name.startswith(("data/", "runs/"))
                        and not name.endswith((".env", ".sqlite3"))
                        for name in names
                    )
                )
                self.assertIn("scripts/ops/c22h4_readiness.py", names)
                self.assertIn("scripts/ops/c22_selected_readiness.py", names)
                self.assertIn("scripts/demo_runtime/diagnostics.py", names)
                stream = archive.extractfile("c22-selected-shadow.service")
                self.assertIsNotNone(stream)
                unit = stream.read().decode()
                self.assertIn("MT5_ENABLE_DEMO_ORDER_SEND=0", unit)
                self.assertNotIn("--execute", unit)
                self.assertNotIn("Conflicts=", unit)
                self.assertIn("c22-selected-shadow.sqlite3", unit)
                stream = archive.extractfile("c22-selected-execution.service")
                self.assertIsNotNone(stream)
                execution = stream.read().decode()
                manifest_stream = archive.extractfile("release-manifest.json")
                self.assertIsNotNone(manifest_stream)
                self.assertEqual(
                    json.load(manifest_stream)["builder_sha256"], first["builder_sha256"]
                )
                self.assertIn("WorkingDirectory=" + first["remote_release"], execution)
                self.assertIn("MT5_ENABLE_DEMO_ORDER_SEND=1", execution)
                self.assertIn(" --execute ", execution)
                self.assertIn(
                    "--execution-review Z:/home/ubuntu/c22-demo/state/c22-selected-execution-review.json",
                    execution,
                )
                self.assertIn("c22-selected-execution.sqlite3", execution)
                self.assertIn("c22-selected-execution-bars.csv", execution)
                for service in (
                    "c22-demo-shadow.service",
                    "c22-selected-shadow.service",
                    "c22-demo-execution.service",
                ):
                    self.assertIn("! systemctl is-active --quiet " + service, execution)
                self.assertIn(
                    'test "$(readlink -f data)" = /home/ubuntu/c22-demo/releases/d091bc6b810e792c/data',
                    execution,
                )
                self.assertIn(
                    "UnsetEnvironment=DEMO_TELEGRAM_TOKEN DEMO_TELEGRAM_CHAT_ID DEMO_HEALTHCHECK_URL",
                    execution,
                )
                self.assertIn("NoNewPrivileges=true", execution)
                self.assertIn("Restart=on-failure", execution)
                self.assertIn("[Install]\nWantedBy=multi-user.target", execution)
                self.assertIn(
                    "After=network-online.target c22-selected-terminal.service", execution
                )
                self.assertIn(
                    "Wants=network-online.target c22-selected-terminal.service", execution
                )
                self.assertIn("StartLimitIntervalSec=0", execution)
                self.assertIn("c22-selected-terminal.service", names)
                self.assertIn("c22-selected-watchdog.service", names)
                self.assertIn("c22-selected-watchdog.timer", names)
                self.assertNotIn("Conflicts=", execution)
                self.assertEqual(
                    (root / "runs/first/c22-selected-execution.service").read_text(), execution
                )
            with self.assertRaises(ValueError):
                MODULE.build_release(root, root / "runs/first")
