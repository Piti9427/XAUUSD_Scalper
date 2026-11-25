"""Launch only the dedicated Selected26b8 terminal; never call an order API."""

from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
import re


WINDOWS_TERMINAL = r"C:\tools\mt5-c22-demo\terminal64.exe"
PREFLIGHT_CODES = frozenset({
    "terminal_environment_invalid", "dedicated_terminal_prefix_required",
    "dedicated_wine_binary_required", "dedicated_terminal_missing",
    "attached_ea_blocks_terminal", "saved_chart_inventory_required",
    "terminal_permission_config_invalid",
})


def _failure(reason: str, stage: str, code: str, error: Exception) -> dict:
    """Publish only known codes/types; exception text can contain private inputs."""
    safe_types = (
        json.JSONDecodeError, FileNotFoundError, PermissionError,
        configparser.MissingSectionHeaderError, configparser.ParsingError,
        configparser.DuplicateOptionError, configparser.DuplicateSectionError,
        configparser.Error, OSError, KeyError, ValueError,
    )
    kind = next(cls.__name__ for cls in safe_types if isinstance(error, cls))
    failure = {"code": code, "stage": stage, "exception_type": kind}
    if isinstance(error, OSError) and type(error.errno) is int:
        failure["errno"] = error.errno
    return {"status": "BLOCKED", "reason": reason, "failure": failure}


def launch_options(home: Path, release: Path, inherited: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    """Keep the existing Wine environment and reject another prefix or saved EA."""
    environment = dict(inherited)
    raw = (home / "c22-private/c22-backup.env").read_text()
    if len(raw) > 1024 * 1024:
        raise ValueError("terminal_environment_invalid")
    for line in raw.splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            parsed = json.loads(value)
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or not isinstance(parsed, str):
                raise ValueError("terminal_environment_invalid")
            environment[key] = parsed
    prefix = home / "c22-qemu-demo._g86ow9b"
    if environment.get("WINEPREFIX") != str(prefix):
        raise ValueError("dedicated_terminal_prefix_required")
    wine = Path(environment.get("DEMO_WINE_BIN", ""))
    if not wine.is_absolute() or not wine.is_file():
        raise ValueError("dedicated_wine_binary_required")
    terminal_root = prefix / "drive_c/tools/mt5-c22-demo"
    if not (terminal_root / "terminal64.exe").is_file():
        raise ValueError("dedicated_terminal_missing")
    charts = []
    for folder in (terminal_root / "MQL5/Profiles/Charts", terminal_root / "Profiles/Charts"):
        for path in sorted(folder.rglob("*.chr")) if folder.exists() else []:
            content = path.read_bytes()
            text = content.decode(
                "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8",
                errors="replace",
            ).replace("\x00", "")
            if re.search(r"<\s*expert(?:\s|>)", text, re.I):
                raise ValueError("attached_ea_blocks_terminal")
            charts.append(path)
    if not charts:
        raise ValueError("saved_chart_inventory_required")
    config = release / "deploy/c22-demo/c22-selected-terminal-execution.ini"
    parsed_config = configparser.ConfigParser()
    parsed_config.read_string(config.read_text())
    expected = {"enabled": "1", "allowlivetrading": "1", "allowdllimport": "0", "account": "1", "profile": "1"}
    if parsed_config.sections() != ["Experts"] or dict(parsed_config["Experts"]) != expected:
        raise ValueError("terminal_permission_config_invalid")
    # The native terminal is permitted to trade; only the separate reviewed
    # Python manager receives the explicit order-send environment gate.
    environment["MT5_ENABLE_DEMO_ORDER_SEND"] = "0"
    config_windows = "Z:" + str(config).replace("/", "\\")
    return ["/usr/bin/xvfb-run", "-a", str(wine), WINDOWS_TERMINAL, "/portable", "/config:" + config_windows], environment


def main() -> int:
    release = Path(__file__).resolve().parents[2]
    try:
        arguments, environment = launch_options(Path.home(), release, dict(os.environ))
    except (OSError, ValueError, KeyError, configparser.Error) as error:
        if isinstance(error, configparser.Error):
            code = "terminal_permission_config_parse_failed"
        elif isinstance(error, OSError):
            code = "terminal_preflight_io_failed"
        elif isinstance(error, KeyError):
            code = "terminal_preflight_key_error"
        elif isinstance(error, json.JSONDecodeError):
            code = "terminal_environment_invalid"
        else:
            candidate = error.args[0] if error.args else None
            code = candidate if isinstance(candidate, str) and candidate in PREFLIGHT_CODES else "terminal_preflight_value_error"
        print(json.dumps(_failure(
            "selected_terminal_preflight_failed", "terminal.preflight", code, error
        )), flush=True)
        return 2
    try:
        os.execvpe(arguments[0], arguments, environment)
    except OSError as error:
        print(json.dumps(_failure(
            "selected_terminal_exec_failed", "terminal.exec", "terminal_exec_os_error", error
        )), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
