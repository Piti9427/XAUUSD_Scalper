# Local acceptance audit — issues #3 / #4 (2026-09-16)

Tracker write still blocked (MCP/gh 403). This file is local evidence that
documentation deliverables satisfy acceptance; it is **not** a GitHub close.

## Issue #3 — Mechanical specification

| Acceptance theme | Local evidence |
| --- | --- |
| Confirmed choices recorded (H1/M5, CHoCH, midpoint, full OB, 2R, Legacy separate) | `docs/specs/xauusd-s1-s4-mechanical-v1.md` |
| Confirmed vs defaults vs unresolved separated | Mechanical § decisions / unresolved gates |
| IF/THEN/INVALID tables | Mechanical rule sections + boundary tables |
| FVG/OB/overlap inclusivity | Mechanical zone sections |
| SL/TP/R/TTL/session/identity/time-exit | Mechanical lifecycle sections |
| BUY/SELL worked examples per candidate | Mechanical §5 |
| Negative/boundary examples | Mechanical §6 |
| Prefix/AMBIGUOUS/restart | Mechanical §6 + ADR-0027 |
| Replay seam named | Mechanical testing section; contract tests |
| Parent scenario map | Mechanical + research handoff §1 |
| No production trading-code claim | Docs-only; contract tests assert docs exist |

Contract: `tests/test_s1_s4_mechanical_spec_contract.py` → **6/6 OK** (ran 2026-09-16).

## Issue #4 — Research handoff

| Acceptance theme | Local evidence |
| --- | --- |
| Parent scenarios routed | `docs/specs/xauusd-s1-s4-research-handoff-v1.md` §1 |
| Datasets vs proxies separated | Handoff §2 |
| Evidence-to-readiness table | Handoff readiness/gates sections |
| Run-manifest / pre-run registration | Handoff templates + Gate B/C blockers |
| Shared controls / Legacy isolation | Handoff |
| Stats protocol fields labeled proposal vs frozen | Handoff + `stats_protocol.py` (foundation) |
| Verdict: docs complete ≠ experiment-ready | Handoff explicit Gate B/C unresolved |
| No auto close of parent / no trading enable | Handoff status banner |

## Issue #2 parent

Close on tracker **only after** #3 and #4 are closed on GitHub. Local docs ready; remote close blocked by auth.

## Issue #1

Software advanced on `feature/smc-v2-hardening`; live Exness/Oracle/Demo gates still open. Do not close.
