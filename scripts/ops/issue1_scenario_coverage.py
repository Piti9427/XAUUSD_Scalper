#!/usr/bin/env python3
"""Issue #1 required-scenario software coverage matrix (Gate B evidence).

Does NOT claim live Gate C/D PASS. Scenario 24 live infra stays operator-owned.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Foundation § Required scenarios → in-repo evidence paths (files must exist).
# status: software_covered | open_material | live_ops_required
SCENARIOS: list[dict] = [
    {
        "id": 1,
        "title": "H1 bias ok but M5 BOS/no CHoCH blocks entry",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/detection.py",
            "scripts/smc/structure.py",
            "tests/test_smc_detection.py",
            "tests/test_smc_structure_choch.py",
        ],
    },
    {
        "id": 2,
        "title": "Protected swing vs internal; wick-only fails body confirmation",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/structure.py",
            "tests/test_smc_structure_choch.py",
        ],
        "note": "HH/HL construction details remain open material (story 48)",
    },
    {
        "id": 3,
        "title": "UNKNOWN/RANGE and unconfirmed swings match structure contract",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/structure.py",
            "tests/test_smc_structure_choch.py",
        ],
    },
    {
        "id": 4,
        "title": "Replay-prefix / future-append invariance",
        "status": "software_covered",
        "evidence": [
            "tests/test_smc_structure_choch.py",
        ],
    },
    {
        "id": 5,
        "title": "Sweep→MSS 8 / MSS→FVG 4 / no fill before confirmation",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/detection.py",
            "tests/test_smc_detection.py",
        ],
    },
    {
        "id": 6,
        "title": "Displacement/body-ratio/FVG orientation boundaries",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/structure.py",
            "tests/test_smc_detection.py",
        ],
    },
    {
        "id": 7,
        "title": "Pool availability / consumed / nearest R / tick rounding",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/liquidity.py",
            "tests/test_smc_liquidity.py",
            "tests/test_smc_liquidity_tp.py",
            "tests/test_smc_pool_tp.py",
        ],
    },
    {
        "id": 8,
        "title": "Setup identity: TTL / H1 invalidate / SL-before-fill / fill / no revive",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/setup_identity.py",
            "scripts/smc/orchestrator.py",
            "scripts/smc/quotes.py",
            "scripts/smc/mt5_adapter/broker.py",
            "scripts/webhook_bridge.py",
            "scripts/webhook/h1_bias.py",
            "smc_main.py",
            "tests/test_smc_setup_identity.py",
            "tests/test_smc_live_h1_bias.py",
            "tests/test_smc_orchestrator.py",
            "tests/test_smc_quotes.py",
            "tests/test_webhook_bridge.py",
            "tests/test_webhook_h1_bias.py",
        ],
    },
    {
        "id": 9,
        "title": "Fib/OTE research log without admission filter",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/fibonacci.py",
            "tests/test_smc_fibonacci.py",
            "tests/test_smc_detection.py",
        ],
    },
    {
        "id": 10,
        "title": "Min lot over budget / volume floor / stops+freeze metadata",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/risk.py",
            "scripts/smc/stops_geometry.py",
            "scripts/smc/broker_metadata.py",
            "tests/test_smc_risk.py",
            "tests/test_smc_stops_geometry.py",
            "tests/test_smc_broker_metadata.py",
            "tests/test_webhook_bridge.py",
        ],
    },
    {
        "id": 11,
        "title": "Manual vs bot PnL; incomplete history blocks parity/reset",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/account_pnl_sync.py",
            "scripts/smc/risk_halt.py",
            "tests/test_smc_account_pnl.py",
            "tests/test_smc_risk_halt.py",
            "tests/test_smc_replay_report.py",
        ],
    },
    {
        "id": 12,
        "title": "Account-mode / bot-owned cancel-close isolation",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/account_mode.py",
            "scripts/smc/mt5_adapter/models.py",
            "scripts/smc/mt5_adapter/execution.py",
            "tests/test_smc_account_mode.py",
            "tests/test_smc_ownership.py",
        ],
    },
    {
        "id": 13,
        "title": "Accept/reject/UNKNOWN / duplicate / restart claim races",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/mt5_adapter/journal.py",
            "scripts/smc/mt5_adapter/adapter.py",
            "tests/test_smc_mt5_adapter.py",
            "tests/test_webhook_bridge.py",
        ],
    },
    {
        "id": 14,
        "title": "Fill-during-cancel / partial residual reconcile",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/reconcile.py",
            "scripts/smc/broker_lifecycle.py",
            "tests/test_smc_reconcile.py",
            "tests/test_smc_broker_lifecycle.py",
        ],
    },
    {
        "id": 15,
        "title": "Spread blowout after pending does not invent no-fill",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/orchestrator.py",
            "tests/test_smc_orchestrator.py",
        ],
    },
    {
        "id": 16,
        "title": "SL/TP same bar / tick order / TIME_EXIT P/L/flat",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/quotes.py",
            "scripts/smc/orchestrator.py",
            "tests/test_smc_quotes.py",
            "tests/test_smc_orchestrator.py",
            "tests/test_smc_backtester.py",
        ],
    },
    {
        "id": 17,
        "title": "Daily losses / equity halt / 5% DD persistence",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/risk_halt.py",
            "tests/test_smc_risk_halt.py",
            "tests/test_webhook_bridge.py",
        ],
    },
    {
        "id": 18,
        "title": "News blackout: cancel pending; no pre-news BE/force exit",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/news.py",
            "tests/test_smc_news.py",
            "tests/test_webhook_bridge.py",
        ],
    },
    {
        "id": 19,
        "title": "Wall-clock TIME_EXIT; no close notify without broker evidence",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/clock_exit.py",
            "scripts/smc/notification_policy.py",
            "tests/test_smc_clock_exit.py",
            "tests/test_smc_notification_policy.py",
        ],
    },
    {
        "id": 20,
        "title": "Accepted vs fill notifications; no phantom TRADE_CLOSED",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/notification_policy.py",
            "tests/test_smc_notification_policy.py",
            "tests/test_webhook_bridge.py",
        ],
    },
    {
        "id": 21,
        "title": "Cost layers; frozen R; operating cost not hidden",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/cost_accounting.py",
            "tests/test_smc_cost_accounting.py",
            "tests/test_smc_backtester.py",
        ],
    },
    {
        "id": 22,
        "title": "Provenance gap/proxy → DATA_INSUFFICIENT; few trades INCONCLUSIVE",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/provenance.py",
            "scripts/smc/stats_protocol.py",
            "tests/test_smc_provenance.py",
            "tests/test_smc_stats_protocol.py",
            "tests/test_smc_backtester.py",
        ],
    },
    {
        "id": 23,
        "title": "Frozen Wilson/sample protocol fixtures",
        "status": "software_covered",
        "evidence": [
            "scripts/smc/stats_protocol.py",
            "scripts/smc/eval_windows.py",
            "tests/test_smc_stats_protocol.py",
            "tests/test_smc_eval_windows.py",
        ],
    },
    {
        "id": 24,
        "title": "Oracle/Mac-off infra ≠ strategy PnL; live Exness identity",
        "status": "live_ops_required",
        "evidence": [
            "scripts/smc/infra_verdict.py",
            "scripts/smoke_broker_identity.py",
            "docs/ops/2026-09-16-mac-live-gate-blocker.md",
            "docs/ops/2026-09-16-issue1-live-gate-readiness.json",
        ],
        "note": "Software labels infra failures; live smoke/soak/Demo start still required",
    },
]


def _git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _check_scenario(row: dict) -> dict:
    missing = [rel for rel in row["evidence"] if not (ROOT / rel).is_file()]
    ok = len(missing) == 0
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "evidence_ok": ok,
        "missing_evidence": missing,
        "note": row.get("note"),
    }


def build_report() -> dict:
    checked = [_check_scenario(s) for s in SCENARIOS]
    software = [c for c in checked if c["status"] == "software_covered"]
    live = [c for c in checked if c["status"] == "live_ops_required"]
    software_ok = all(c["evidence_ok"] for c in software)
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "source": "docs/specs/gold-playbook-foundation.md § Required scenarios",
        "scenarios": checked,
        "summary": {
            "total": len(checked),
            "software_covered": len(software),
            "software_evidence_complete": software_ok,
            "live_ops_required": len(live),
            "issue1_closable_from_software_alone": False,
            "note": (
                "Scenarios 1–23 software evidence is Gate B support only. "
                "Scenario 24 + Exness/Oracle/Demo artifacts still required to close #1."
            ),
        },
    }


def main() -> int:
    report = build_report()
    out = ROOT / "docs" / "ops" / "2026-09-16-issue1-scenario-coverage.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    if not report["summary"]["software_evidence_complete"]:
        missing = [
            f"s{c['id']}:{m}"
            for c in report["scenarios"]
            for m in c["missing_evidence"]
        ]
        print("MISSING:", ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
