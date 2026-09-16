# GitHub close-ready notes (blocked by auth)

`gh` keyring invalid + MCP `issue_write` 403 (PAT lacks issues write). Paste when write auth restored.

Retried 2026-09-16: still blocked.

## Issue #3 — S1–S4 mechanical tables

**Status:** Documentation complete in-repo.

Evidence:
- `docs/specs/xauusd-s1-s4-mechanical-v1.md` (decision tables, synthetic BUY/SELL, boundaries, coverage map)
- `tests/test_s1_s4_mechanical_spec_contract.py`
- ADR-0027 references mechanical rule version `s1-s4-mechanical-v1`

Suggested close comment: Mechanical v1 deliverable landed; parent #2 remains open until #4 and foundation gates allow experiment start.

## Issue #4 — Research handoff

**Status:** Documentation complete in-repo; gates intentionally open.

Evidence:
- `docs/specs/xauusd-s1-s4-research-handoff-v1.md`
- Explicit non-actions / unresolved blockers listed in §10
- Specs README marks handoff as “Gates open — not experiment-ready”

Suggested close comment: Handoff published; unresolved Gate B/C items tracked under #1, not silent incompleteness of #4 docs.

## Issue #2 — Parent S1–S4 experiment

**Status:** Parent ready to close only after children #3/#4 closed on tracker AND Gate A freeze acknowledged.

Local children docs done; tracker closure still blocked by auth.

## Issue #1 — still NOT close-ready

Remaining evidence gaps (not software stubs):
1. Live Exness Demo identity smoke (`scripts/smoke_broker_identity.py`)
2. Oracle ARM64 soak evidence (`docs/ops/2026-09-16-oracle-arm64-runtime-checklist.md`)
3. Forward Demo 12-week protocol execution (`docs/ops/2026-09-16-foundation-demo-12w-protocol.md`)
