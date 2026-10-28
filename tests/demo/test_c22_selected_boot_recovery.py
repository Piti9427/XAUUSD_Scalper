"""Boot packaging resumes the selected journal without a second sender."""

from datetime import datetime, timedelta, timezone
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load("boot_release_builder", "deploy/c22-demo/prepare_selected_release.py")
LAUNCHER = load("boot_terminal_launcher", "deploy/c22-demo/launch_selected_terminal.py")
BOOT = load("selected_boot_registration", "deploy/c22-demo/enable_selected_boot.py")


class SelectedBootRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(dir=ROOT / "runs")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def build_fixture(self):
        paths = {"scripts/demo_runtime/cli.py": b"# original runtime fixture\n",
                 "scripts/c22_selected/__init__.py": b"# selected fixture\n",
                 "scripts/ops/mt5_wine_c22_selected.py": b"# selected entry fixture\n",
                 "scripts/ops/c22_selected_watchdog.py": b"# read-only watchdog fixture\n",
                 "scripts/demo_runtime/diagnostics.py": b"# safe diagnostics fixture\n",
                 "scripts/demo_runtime/boundary.py": b"# midnight observer fixture\n"}
        for name in ("deploy/c22-demo/launch_selected_terminal.py", "deploy/c22-demo/enable_selected_boot.py",
                     "deploy/c22-demo/c22-selected-terminal-execution.ini"):
            paths[name] = (ROOT / name).read_bytes()
        paths["config/c22-selected-demo.json"] = json.dumps({
            "contract_id": "26b8bcd69e043653", "volume": 0.01, "real_money": "PROHIBITED",
            "default_mode": "shadow", "source_hashes": {},
        }).encode()
        paths["runs/c22-oracle-compat-2026-10-24/phase2-evidence/release-manifest.json"] = json.dumps({
            "files": {"scripts/demo_runtime/cli.py": hashlib.sha256(paths["scripts/demo_runtime/cli.py"]).hexdigest()}
        }).encode()
        for name, content in paths.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return BUILDER.build_release(self.root, self.root / "runs/boot-build")

    def terminal_fixture(self):
        home = self.root / "home"
        terminal = home / "c22-qemu-demo._g86ow9b/drive_c/tools/mt5-c22-demo"
        charts = terminal / "MQL5/Profiles/Charts/Default"
        charts.mkdir(parents=True)
        (charts / "chart01.chr").write_text("<chart>\n</chart>\n")
        (terminal / "terminal64.exe").write_bytes(b"fixture native terminal")
        wine = home / "bin/wine"
        wine.parent.mkdir()
        wine.write_text("# fixture binary\n")
        private = home / "c22-private/c22-backup.env"
        private.parent.mkdir()
        private.write_text("\n".join(key + "=" + json.dumps(value) for key, value in {
            "WINEPREFIX": str(home / "c22-qemu-demo._g86ow9b"), "DEMO_WINE_BIN": str(wine),
            "WINEDEBUG": "-all", "MT5_ENABLE_DEMO_ORDER_SEND": "1",
        }.items()))
        release = self.root / "release"
        config = release / "deploy/c22-demo/c22-selected-terminal-execution.ini"
        config.parent.mkdir(parents=True)
        config.write_bytes((ROOT / "deploy/c22-demo/c22-selected-terminal-execution.ini").read_bytes())
        return home, release, charts, config

    def boot_fixture(self):
        release = self.root / "reviewed-release"
        units = self.root / "systemd"
        release.mkdir()
        units.mkdir()
        files = {}
        for name in BOOT.UNITS:
            content = "[Service]\nWorkingDirectory=" + str(release) + "\n"
            (release / name).write_text(content)
            (units / name).write_text(content)
            files[name] = hashlib.sha256(content.encode()).hexdigest()
        (release / "release-manifest.json").write_text(json.dumps({"files": files, "remote_release": str(release)}))
        review = self.root / "review.json"
        review.write_text(json.dumps({"scope": "SELECTED_DEMO_ARMED_TRIAL", "owner_authorized": True,
                                     "readiness": {"account_fingerprint": "fixture-demo", "snapshot": BOOT.SNAPSHOT}}))
        now = datetime(2026, 10, 26, 0, 1, tzinfo=timezone.utc)
        state = {"identity": "fixture-demo", "active": None,
                 "selected_execution_review_sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
                 "last_result": {"captured_utc": now.isoformat(), "execute": True,
                                 "snapshot": BOOT.SNAPSHOT, "observed_positions": 0, "position_protection": "flat"}}
        journal = self.root / "execution.sqlite3"
        with closing(sqlite3.connect(journal)) as connection, connection:
            connection.execute("CREATE TABLE kv (key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            connection.executemany("INSERT INTO kv VALUES (?,?)", [(key, json.dumps(value)) for key, value in state.items()])
        def systemctl(command, **kwargs):
            if command[-1] == "--value":
                return SimpleNamespace(stdout="not-found\n" if "c22-demo-execution.service" in command else "loaded\n")
            return SimpleNamespace(stdout="ActiveState=active\nWorkingDirectory=" + str(release) + "\n")
        return release, units, journal, review, now, Mock(side_effect=systemctl)

    def test_persistent_pair_uses_same_journal_and_does_not_bind_terminal_failure(self):
        result = self.build_fixture()
        with tarfile.open(result["archive"]) as archive:
            execution = archive.extractfile("c22-selected-execution.service").read().decode()
            terminal = archive.extractfile("c22-selected-terminal.service").read().decode()
            watchdog = archive.extractfile("c22-selected-watchdog.service").read().decode()
            timer = archive.extractfile("c22-selected-watchdog.timer").read().decode()
            self.assertIn("After=network-online.target c22-selected-terminal.service", execution)
            self.assertIn("Wants=network-online.target c22-selected-terminal.service", execution)
            self.assertNotIn("Requires=", execution)
            self.assertNotIn("BindsTo=", execution)
            self.assertIn("WantedBy=multi-user.target", execution)
            self.assertIn("StartLimitIntervalSec=0", execution)
            self.assertIn("--journal Z:/home/ubuntu/c22-demo/state/c22-selected-execution.sqlite3", execution)
            self.assertIn("--execution-review Z:/home/ubuntu/c22-demo/state/c22-selected-execution-review.json", execution)
            self.assertIn("WantedBy=multi-user.target", terminal)
            self.assertIn("Restart=always", terminal)
            self.assertIn("! systemctl is-active --quiet c22-selected-terminal-armed.service", terminal)
            self.assertNotIn("--execute", terminal)
            self.assertNotIn("--notify", watchdog)
            self.assertIn("--state /home/ubuntu/c22-demo/state/c22-selected-watchdog.sqlite3", watchdog)
            self.assertIn("ReadOnlyPaths=-/home/ubuntu/c22-demo/state/c22-selected-execution.sqlite3", watchdog)
            self.assertIn("OnUnitActiveSec=60s", timer)
            for name in ("scripts/ops/c22_selected_watchdog.py", "scripts/demo_runtime/boundary.py",
                         "deploy/c22-demo/launch_selected_terminal.py"):
                self.assertIn(name, result["files"])

    def test_terminal_launch_keeps_dedicated_environment_and_never_has_python_send_gate(self):
        home, release, _, _ = self.terminal_fixture()
        command, environment = LAUNCHER.launch_options(home, release, {"MT5_ENABLE_DEMO_ORDER_SEND": "1"})
        self.assertEqual(command[:2], ["/usr/bin/xvfb-run", "-a"])
        self.assertEqual(command[3], LAUNCHER.WINDOWS_TERMINAL)
        self.assertEqual(environment["MT5_ENABLE_DEMO_ORDER_SEND"], "0")
        self.assertEqual(environment["WINEDEBUG"], "-all")
        self.assertTrue(command[-1].endswith("c22-selected-terminal-execution.ini"))
        self.assertNotIn("--execute", command)

    def test_build_rejects_terminal_permission_symlink_without_bundling_private_bytes(self):
        self.build_fixture()
        config = self.root / "deploy/c22-demo/c22-selected-terminal-execution.ini"
        private = self.root / "private.env"
        private.write_text("PRIVATE_MUST_NOT_ENTER_RELEASE=fixture\n")
        config.unlink()
        config.symlink_to(private)
        output = self.root / "runs/rejected-build"
        with self.assertRaisesRegex(ValueError, "Release path not permitted"):
            BUILDER.build_release(self.root, output)
        self.assertFalse(output.exists())
        self.assertEqual(private.read_text(), "PRIVATE_MUST_NOT_ENTER_RELEASE=fixture\n")

    def test_terminal_rejects_wrong_prefix_ea_inventory_and_permission_drift(self):
        home, release, charts, config = self.terminal_fixture()
        (charts / "chart01.chr").write_text("<expert>unreviewed</expert>", encoding="utf-16")
        with self.assertRaisesRegex(ValueError, "attached_ea"):
            LAUNCHER.launch_options(home, release, {})
        (charts / "chart01.chr").write_text("<chart></chart>")
        config.write_text("[Experts]\nEnabled=0\n")
        with self.assertRaisesRegex(ValueError, "permission_config"):
            LAUNCHER.launch_options(home, release, {})
        (home / "c22-private/c22-backup.env").write_text('WINEPREFIX="/another-prefix"\n')
        with self.assertRaisesRegex(ValueError, "dedicated_terminal_prefix"):
            LAUNCHER.launch_options(home, release, {})

    def test_boot_registration_never_stops_or_starts_manager_and_skips_missing_old_unit(self):
        release, units, journal, review, now, run = self.boot_fixture()
        before = journal.read_bytes()
        plan = BOOT.boot_plan(release, journal, review, fingerprint="fixture-demo", unit_directory=units, now=now, run=run)
        self.assertFalse(plan["starts_or_stops_manager"])
        self.assertEqual(plan["commands"], [
            ["systemctl", "disable", "c22-selected-shadow.service", "c22-demo-shadow.service"],
            ["systemctl", "enable", "c22-selected-terminal.service", "c22-selected-execution.service"],
        ])
        apply = Mock()
        BOOT.apply_plan(plan, run=apply)
        self.assertEqual(apply.call_count, 2)
        self.assertEqual(journal.read_bytes(), before)
        for call in apply.call_args_list:
            self.assertIn(call.args[0][1], ("enable", "disable"))
            self.assertNotIn("--now", call.args[0])

    def test_boot_preflight_rejects_active_unknown_stale_or_changed_permission(self):
        release, units, journal, review, now, run = self.boot_fixture()
        for mutation in ("unknown", "stale", "review"):
            with self.subTest(mutation=mutation):
                with closing(sqlite3.connect(journal)) as connection, connection:
                    connection.execute("INSERT OR REPLACE INTO kv VALUES ('active',?)", (json.dumps({"status": "UNKNOWN"}) if mutation == "unknown" else "null",))
                stamp = now + timedelta(seconds=20) if mutation == "stale" else now
                if mutation == "review":
                    review.write_text(review.read_text() + "\n")
                with self.assertRaisesRegex(ValueError, "fresh_flat_reviewed_manager_required"):
                    BOOT.boot_plan(release, journal, review, fingerprint="fixture-demo", unit_directory=units, now=stamp, run=run)
        self.assertTrue(all(call.args[0][1] == "show" for call in run.call_args_list))

    def test_boot_apply_rejects_start_stop_and_foreign_unit_injection(self):
        run = Mock()
        for command in (["systemctl", "restart", "c22-selected-execution.service"],
                        ["systemctl", "enable", "--now", "c22-selected-execution.service"],
                        ["systemctl", "enable", "foreign.service"]):
            with self.subTest(command=command), self.assertRaises(ValueError):
                BOOT.apply_plan({"commands": [command]}, run=run)
        run.assert_not_called()

    def test_boot_preflight_rejects_installed_unit_and_release_integrity_drift(self):
        release, units, journal, review, now, run = self.boot_fixture()
        name = BOOT.UNITS[0]
        original = (units / name).read_bytes()
        (units / name).write_bytes(original + b"# unexpected unit edit\n")
        with self.assertRaisesRegex(ValueError, "installed_selected_unit_mismatch"):
            BOOT.boot_plan(release, journal, review, fingerprint="fixture-demo", unit_directory=units, now=now, run=run)
        (units / name).write_bytes(original)
        (release / name).write_bytes(original + b"# unexpected source edit\n")
        with self.assertRaisesRegex(ValueError, "release_integrity_required"):
            BOOT.boot_plan(release, journal, review, fingerprint="fixture-demo", unit_directory=units, now=now, run=run)
        run.assert_not_called()
