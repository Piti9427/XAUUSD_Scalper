"""Host wrapper for trial30: existing Wine prefix, ignored credentials, no copies."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def main(argv=None) -> int:
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    for line in (root / ".env").read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env.setdefault(key.strip(), value.strip().strip("\"'"))
    env["WINEPREFIX"] = str(
        Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5"
    )
    env["WINEDLLOVERRIDES"] = "mscoree,mshtml="
    env["PYTHONPATH"] = "Z:" + str(root).replace("/", "\\")
    args = list(sys.argv[1:] if argv is None else argv)
    command = [
        "/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine",
        r"C:\tools\python312\python.exe",
        "-u",
        "Z:" + str(root / "scripts/ops/mt5_wine_trial30.py").replace("/", "\\"),
        *args,
    ]
    # CLI relative paths resolve to repository; use Z:\ absolute paths for overrides.
    secrets = [
        v
        for k, v in env.items()
        if v and any(s in k.upper() for s in ("PASSWORD", "TOKEN", "SECRET", "LOGIN"))
    ]
    proc = subprocess.Popen(
        command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            for value in secrets:
                line = line.replace(value, "<REDACTED>")
            print(line, end="", flush=True)
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
