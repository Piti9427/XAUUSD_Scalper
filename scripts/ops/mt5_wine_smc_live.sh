#!/usr/bin/env bash
# Host wrapper: GOLD_V2 Demo live loop inside Wine Python. Credentials from .env.
set -euo pipefail
set +x
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

python3 - <<'PY'
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
env_path = root / ".env"
wineprefix = Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5"
wine = Path("/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine")
src = root / "scripts/ops/mt5_wine_smc_live.py"
dst = wineprefix / "drive_c/tools/mt5_wine_smc_live.py"
py_exe = r"C:\tools\python312\python.exe"
script_win = r"C:\tools\mt5_wine_smc_live.py"
repo_win = "Z:" + str(root).replace("/", "\\")

if not env_path.is_file():
    print('{"ok": false, "stage": "env_missing"}')
    raise SystemExit(2)
if not wine.is_file():
    print('{"ok": false, "stage": "wine_missing"}')
    raise SystemExit(2)

child_env = os.environ.copy()
for line in env_path.read_text(encoding="utf-8").splitlines():
    raw = line.strip()
    if not raw or raw.startswith("#") or "=" not in raw:
        continue
    key, value = raw.split("=", 1)
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    child_env[key] = value

child_env["WINEPREFIX"] = str(wineprefix)
child_env.setdefault(
    "MT5_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5\terminal64.exe"
)
child_env.setdefault("WINEDLLOVERRIDES", "mscoree,mshtml=")
child_env["XAUUSD_REPO_ROOT"] = repo_win
child_env["PYTHONPATH"] = repo_win

dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(src, dst)

proc = subprocess.run(
    [str(wine), py_exe, script_win],
    cwd=str(root),
    env=child_env,
    text=True,
    capture_output=False,
)
sys.exit(proc.returncode)
PY
