# Goal completion audit — fix all open GitHub issues

**Objective:** Implement, verify, and close every open issue on `Piti9427/XAUUSD_Scalper`.  
**Branch:** `feature/smc-v2-hardening` (local ahead of origin; push blocked).  
**Last verified:** 2026-09-16 ~14:09 ICT — `./scripts/audit_local_issue_gates.sh` OK · `docs/ops/2026-09-16-github-close-evidence.json` · HEAD `09b32f8` · **ahead 27**

| Issue | Requirement | In-repo evidence | GitHub closed | Verdict |
| --- | --- | --- | --- | --- |
| **#3** Mechanical S1–S4 spec | Docs + contract tests | `docs/specs/xauusd-s1-s4-mechanical-v1.md`, `tests/test_s1_s4_mechanical_spec_contract.py` (6/6) | ❌ open (MCP PATCH **403** read-only PAT) | **Software done; tracker open** |
| **#4** Research handoff | Docs + explicit Gate B/C blockers | `docs/specs/xauusd-s1-s4-research-handoff-v1.md`, `tests/test_s1_s4_research_handoff_contract.py` (6/6) | ❌ open | **Software done; tracker open** |
| **#2** Parent tracker | Close after #3/#4 | `tests/test_issue2_parent_tracker_contract.py`, local acceptance audit | ❌ open | **Blocked on #3/#4 close** |
| **#1** Gold Playbook Foundation | Software + **live** Exness/Oracle/Demo gates | Progress map + unit suite OK; Mac smoke = `INCONCLUSIVE_INFRA` | ❌ open | **Live gates + tracker open** |

## Auth blockers (operator) — rechecked 2026-09-16 14:09

| Action | Evidence |
| --- | --- |
| Push 27 commits | `gh` token **invalid**; HTTPS keychain `-25293`; SSH `Permission denied (publickey)` |
| Close #3→#4→#2 | MCP `issue_write` **403** Resource not accessible by personal access token |
| MCP read | `issue_read` works (issues still `open`) |
| Offline push handoff | `/tmp/smc-v2-hardening-ahead.bundle` (requires base `b1548cc`) |

## Issue #1 live gates (do not close #1 without)

1. `scripts/smoke_broker_identity.py --out docs/ops/<date>-exness-smoke.json` on MT5 + Exness Demo  
2. Oracle ARM64 soak per `docs/ops/2026-09-16-oracle-arm64-runtime-checklist.md`  
3. Forward Demo 12w per `docs/ops/2026-09-16-foundation-demo-12w-protocol.md`  

## Goal complete when

- [ ] All four issues **closed** on GitHub with evidence comments  
- [ ] Branch pushed; close comments reference commit SHA from `generate_close_evidence.py`  
- [ ] #1 live artifacts recorded under `docs/ops/` (not `INCONCLUSIVE_INFRA` only)
