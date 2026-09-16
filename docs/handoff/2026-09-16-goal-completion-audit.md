# Goal completion audit — fix all open GitHub issues

**Objective:** Implement, verify, and close every open issue on `Piti9427/XAUUSD_Scalper`.  
**Branch:** `feature/smc-v2-hardening` @ `1f20ced` (pushed).  
**Last verified:** 2026-09-16 ~14:17 ICT — push OK · closed #3/#4/#2 via `gh`

| Issue | Requirement | In-repo evidence | GitHub closed | Verdict |
| --- | --- | --- | --- | --- |
| **#3** Mechanical S1–S4 spec | Docs + contract tests | `docs/specs/xauusd-s1-s4-mechanical-v1.md`, contract 6/6 | ✅ closed | **Done** |
| **#4** Research handoff | Docs + Gate B/C blockers | `docs/specs/xauusd-s1-s4-research-handoff-v1.md`, contract 6/6 | ✅ closed | **Done** |
| **#2** Parent tracker | Close after #3/#4 | Parent closed on tracker | ✅ closed | **Done** |
| **#1** Gold Playbook Foundation | Software + **live** Exness/Oracle/Demo gates | Progress map + 268 tests; Mac smoke = `INCONCLUSIVE_INFRA` | ❌ open | **Live gates still required** |

## Auth / push (resolved 2026-09-16)

| Action | Evidence |
| --- | --- |
| Push | `gh auth setup-git` + `git push` → `b1548cc..1f20ced` |
| Close #3→#4→#2 | `gh issue close` completed with evidence comments |
| #1 | **Do not close** until live smoke + Oracle soak + Demo 12w |

## Issue #1 live gates (do not close #1 without)

1. `scripts/smoke_broker_identity.py --out docs/ops/<date>-exness-smoke.json` on MT5 + Exness Demo  
2. Oracle ARM64 soak per `docs/ops/2026-09-16-oracle-arm64-runtime-checklist.md`  
3. Forward Demo 12w per `docs/ops/2026-09-16-foundation-demo-12w-protocol.md`  

Helper: `./scripts/ops/foundation_live_gate.sh`

## Goal complete when

- [x] Issues #2/#3/#4 **closed** on GitHub with evidence  
- [x] Branch pushed (`1f20ced`)  
- [ ] #1 live artifacts under `docs/ops/` (not `INCONCLUSIVE_INFRA` only)  
- [ ] Issue #1 closed after live gates
