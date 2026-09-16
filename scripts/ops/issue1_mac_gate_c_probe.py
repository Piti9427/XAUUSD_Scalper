#!/usr/bin/env python3
"""One-shot Mac Gate-C probe: MT5 package/path/account completeness + readiness.

Does not invent ok:true. Writes docs/ops/*-exness-smoke-mac-probe.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main() -> int:
    from scripts.smc.mt5_init import (
        initialize_mt5,
        resolve_mt5_account_kwargs,
        resolve_mt5_terminal_path,
    )

    out: dict = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": "mac",
        "git_head": _git_head(),
        "ok": False,
    }
    path = resolve_mt5_terminal_path()
    acct = resolve_mt5_account_kwargs()
    out["path_resolved"] = path
    out["account_kwargs_complete"] = bool(acct)
    if acct:
        out["account_login"] = acct.get("login")
        out["account_server"] = acct.get("server")

    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        out["package"] = f"missing:{exc}"
        out["blocker"] = (
            "MetaTrader5 package missing on this Mac venv; run Gate C on "
            "Windows/Wine Exness Demo host via ./scripts/ops/foundation_live_gate.sh"
        )
        _write(out)
        print(json.dumps(out, indent=2))
        return 2

    out["package"] = "present"
    init = initialize_mt5(mt5, path=path, **acct)
    out["detail"] = init.detail
    out["last_error"] = list(init.last_error) if init.last_error else None
    out["path_used"] = init.path_used
    out["ok"] = bool(init.ok)
    if init.ok:
        try:
            info = mt5.account_info()
            out["attached_login"] = getattr(info, "login", None) if info else None
            out["server"] = getattr(info, "server", None) if info else None
        finally:
            mt5.shutdown()
    else:
        out["blocker"] = (
            f"initialize_failed:{init.detail}; Gate C still requires reachable "
            "Exness Demo terminal (not Mac INCONCLUSIVE_INFRA alone)"
        )
    _write(out)
    print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 2


def _write(payload: dict) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = ROOT / "docs" / "ops" / f"{stamp}-exness-smoke-mac-probe.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
