# Goal paused — Mac-only continue (2026-09-17)

## Decision

Operator paused the “close all GitHub issues / Gate C–D live” goal.

- **#1 stays OPEN** on GitHub until real Exness smoke + Oracle soak + Demo 12w start exist.
- **Do not invent** `issue1_closable: true` or close #1 from Mac Wine / web terminal.
- **MacBook-only path** for later resume: UTM Windows VM + Exness MT5 (see `docs/ops/2026-09-17-macbook-only-gate-c-path.json`).

## What is done on Mac (software)

- Branch `feature/smc-v2-hardening` pushed through `bfa090f`.
- Gate B scenarios 1–23 software evidence complete.
- Webhook/clock modularization + risk-halt clock flatten + unit tests (413 OK at pause).

## What is deferred

| Item | Why |
| --- | --- |
| Gate C Exness smoke `ok:true` | No Windows IPC host; Wine = MetaQuotes-Demo + initialize -6 |
| Gate C Oracle soak | Needs completed soak artifact |
| Gate D Demo 12w start | Needs start artifact after B/C |
| GitHub close of #1 | Blocked on above |

## Resume checklist

1. Create UTM Windows VM (or other MT5 host).
2. `./scripts/ops/foundation_live_gate.sh` → smoke `ok:true`.
3. Fill soak + Demo start templates with real values.
4. `python3 scripts/ops/issue1_live_gate_readiness.py` → `issue1_closable: true`.
5. Then close #1 with evidence links.

## Active track now

Mac-only software/tests/docs that do **not** claim live-gate PASS.
