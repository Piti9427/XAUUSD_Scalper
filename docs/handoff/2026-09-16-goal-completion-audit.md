# Goal completion audit — fix all open GitHub issues

**Objective:** Implement, verify, and close every open issue on `Piti9427/XAUUSD_Scalper`.  
**Branch:** `feature/smc-v2-hardening` @ `adb89da`  
**Last verified:** 2026-09-16 ~16:45 ICT

| Issue | Requirement | In-repo evidence | GitHub closed | Verdict |
| --- | --- | --- | --- | --- |
| **#3** Mechanical S1–S4 spec | Docs + contract tests | specs + contracts | ✅ CLOSED | **Done** |
| **#4** Research handoff | Docs + Gate B/C blockers | specs + contracts | ✅ CLOSED | **Done** |
| **#2** Parent tracker | Close after #3/#4 | Parent closed | ✅ CLOSED | **Done** |
| **#1** Gold Playbook Foundation | Software + **live** Exness/Oracle/Demo | 355 tests; scenarios 1–23 software OK; Mac `INCONCLUSIVE_INFRA` | ❌ OPEN | **Live gates still required** |

## Issue #1 gate audit (authoritative)

| Gate | Required evidence | Current state | Status |
| --- | --- | --- | --- |
| A — freeze / open decisions | ADR-0027/0028 + open-material registry | Present; open rows stay open (no silent invent) | Software OK |
| B — scenarios 1–23 | `docs/ops/2026-09-16-issue1-scenario-coverage.json` | `software_evidence_complete: true` | Software OK |
| C — Exness Demo smoke `ok:true` | `docs/ops/*-exness-smoke.json` | Latest attempt `exness-smoke-mac-retry` **ok:false**; Wine `-6`; **0 Exness** in Wine prefix | **BLOCKED** |
| C — Oracle soak complete | `docs/ops/*-oracle-soak*.json` | Checklist only; no completed artifact | **BLOCKED** |
| D — Demo 12w start | `docs/ops/*-demo-12w-start*.json` | Protocol only | **BLOCKED** |
| Closable? | All of C smoke + C soak + D start | `issue1_closable: false` | **Not closable** |

## Host reachability (do not invent SSH success)

- Default BatchMode SSH as `nopparuj@` known hosts → **Permission denied (publickey)** on all probed LAN/OCI endpoints.
- Wine MT5 running; IPC initialize still `-6 Authorization failed`.
- Wine prefix Exness filename/ini search → **0 matches** (`docs/ops/2026-09-16-mac-wine-exness-prefix-hunt.json`).

## Operator unblock

```bash
./scripts/ops/issue1_operator_unblock.sh
```

1. Authorize Mac `~/.ssh/id_ed25519.pub` on MT5 host **or** run `./scripts/ops/foundation_live_gate.sh` there with Exness Demo (hedging).  
2. Logging Exness into Mac Wine GUI alone is **insufficient** while IPC stays `-6` and no Exness base exists.  
3. After `ok:true` smoke + soak + Demo start → refresh readiness → close #1.

## Goal complete when

- [x] #2/#3/#4 closed with evidence  
- [x] Branch pushed with foundation software  
- [x] `gh` can re-verify issue states  
- [ ] #1 live artifacts (not Mac `INCONCLUSIVE_INFRA` only)  
- [ ] #1 closed after live gates  
