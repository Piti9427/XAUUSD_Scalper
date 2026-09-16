# Goal completion audit — fix all open GitHub issues

**Objective:** Implement, verify, and close every open issue on `Piti9427/XAUUSD_Scalper`.  
**Branch:** `feature/smc-v2-hardening` @ `7344201`  
**Last verified:** 2026-09-16 ~15:22 ICT

| Issue | Requirement | In-repo evidence | GitHub closed | Verdict |
| --- | --- | --- | --- | --- |
| **#3** Mechanical S1–S4 spec | Docs + contract tests | specs + contracts | ✅ closed | **Done** |
| **#4** Research handoff | Docs + Gate B/C blockers | specs + contracts | ✅ closed | **Done** |
| **#2** Parent tracker | Close after #3/#4 | Parent closed | ✅ closed | **Done** |
| **#1** Gold Playbook Foundation | Software + **live** Exness/Oracle/Demo | 294+ tests; stories 47–49; SetupDecision API fix; Mac `INCONCLUSIVE_INFRA` | ❌ open | **Live gates still required** |

## Issue #1 live gates (do not close without)

1. Exness Demo smoke on MT5 host → `docs/ops/<date>-exness-smoke.json` with `ok: true` (hedging)
2. Oracle ARM64 soak checklist evidence
3. Forward Demo 12w protocol start artifact

Helper: `./scripts/ops/foundation_live_gate.sh`  
Mac blocker: `docs/ops/2026-09-16-mac-live-gate-blocker.md`  
Fresh Wine IPC re-probe: `docs/ops/2026-09-16-mac-wine-ipc-reprobe.json` (`-10003`)  
Operator host: macOS (confirmed)

## Goal complete when

- [x] #2/#3/#4 closed with evidence  
- [x] Branch pushed with foundation software  
- [ ] #1 live artifacts (not Mac `INCONCLUSIVE_INFRA` only)  
- [ ] #1 closed after live gates  
