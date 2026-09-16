#!/usr/bin/env python3
"""Smoke-check Exness Demo identity without placing orders."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.smc.broker_identity import verify_broker_identity
from scripts.smc.infra_verdict import classify_infra_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--server-substring", default="Exness")
    parser.add_argument("--allow-live", action="store_true", help="Permit non-demo trade_mode")
    parser.add_argument(
        "--out",
        type=Path,
        help="Write evidence JSON for Issue #1 ops (timestamp + optional git sha)",
    )
    args = parser.parse_args(argv)

    def _git_head() -> str | None:
        try:
            out = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            return out.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def _emit(payload: dict) -> None:
        body = {
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_head": _git_head(),
            **payload,
        }
        print(json.dumps(body, indent=2))
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")

    try:
        import MetaTrader5 as mt5
    except ImportError:
        infra = classify_infra_evidence(
            mt5_available=False,
            identity_ok=False,
            soak_completed=False,
        )
        _emit(
            {
                "ok": False,
                "reasons": ["mt5_import_missing"],
                "infra_verdict": infra.verdict,
                "infra_detail": infra.detail,
            }
        )
        return 2

    if not mt5.initialize():
        infra = classify_infra_evidence(
            mt5_available=False,
            identity_ok=False,
            soak_completed=False,
        )
        _emit(
            {
                "ok": False,
                "reasons": ["mt5_initialize_failed"],
                "infra_verdict": infra.verdict,
                "infra_detail": infra.detail,
            }
        )
        return 2
    try:
        report = verify_broker_identity(
            expected_server_substring=args.server_substring,
            expected_symbol=args.symbol,
            allow_demo_only=not args.allow_live,
            account_info=mt5.account_info(),
            symbol_info=mt5.symbol_info(args.symbol),
        )
    finally:
        mt5.shutdown()

    infra = classify_infra_evidence(
        mt5_available=True,
        identity_ok=report.ok,
        soak_completed=False,
    )

    payload = {
        "ok": report.ok,
        "broker_server": report.broker_server,
        "account_login": report.account_login,
        "currency": report.currency,
        "trade_mode": report.trade_mode,
        "symbol": report.symbol,
        "reasons": list(report.reasons),
        "infra_verdict": infra.verdict,
        "infra_detail": infra.detail,
    }
    _emit(payload)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
