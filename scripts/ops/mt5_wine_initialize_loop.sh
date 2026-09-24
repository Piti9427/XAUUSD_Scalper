#!/usr/bin/env bash
# Host wrapper: load ignored .env, run 64-bit Wine Python initialize loop.
# No credentials printed. No order_send.
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
src = root / "scripts/ops/mt5_wine_initialize_loop.py"
dst = wineprefix / "drive_c/tools/mt5_wine_initialize_loop.py"
py_exe = r"C:\tools\python312\python.exe"
script_win = r"C:\tools\mt5_wine_initialize_loop.py"

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

dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(src, dst)

cmd = [str(wine), py_exe, script_win]
proc = subprocess.run(
    cmd,
    cwd=str(root),
    env=child_env,
    text=True,
    capture_output=True,
)
stdout = proc.stdout or ""
stderr = proc.stderr or ""
# Never leak secrets if a library dumps them.
password = child_env.get("XAUUSD_MT5_PASSWORD") or child_env.get("MT5_PASSWORD") or ""
if password:
    stdout = stdout.replace(password, "<REDACTED>")
    stderr = stderr.replace(password, "<REDACTED>")
sys.stdout.write(stdout)
if stderr.strip():
    # Wine fixme noise is common; keep it off the JSON line.
    noise_path = Path("/tmp/mt5_wine_initialize_loop.stderr.txt")
    noise_path.write_text(stderr, encoding="utf-8")
sys.exit(proc.returncode)
PY
