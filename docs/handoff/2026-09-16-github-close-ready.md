# GitHub close-ready notes (blocked by auth)

`gh` keyring invalid + MCP `issue_write`/`push_files` **403** (token is **read-only** — no issues/contents write).
ConnectScm + `mcp_auth` re-run 2026-09-16: identity `Piti9427` readable; PATCH/POST write still 403.
Git push also blocked (`osxkeychain` err -25293) — local branch **ahead of origin**.

**Operator unblock (local Terminal, interactive):**

```bash
chmod +x scripts/ops_unblock_github.sh
./scripts/ops_unblock_github.sh
```

Or manually:

```bash
security unlock-keychain ~/Library/Keychains/login.keychain-db
gh auth refresh -h github.com -s repo
git push origin feature/smc-v2-hardening
```

Also ensure the GitHub App / PAT used by Cursor MCP has **Issues: Write** and **Contents: Write** (read-only app cannot close trackers).

Retried 2026-09-16 repeatedly: still 403 / invalid keyring / push fail.
MCP `issue_write` close attempt 2026-09-16: **403 Resource not accessible by personal access token** (read-only).

Branch evidence: `feature/smc-v2-hardening` (**ahead 26** of origin — push blocked).
Unit suite: `.venv/bin/python -m unittest discover -s tests` → OK (266).
Live gate helper: `scripts/ops/foundation_live_gate.sh` (MT5 host required).
Pre-close audit: `./scripts/audit_local_issue_gates.sh` · JSON: `python3 scripts/generate_close_evidence.py`
Goal matrix: `docs/handoff/2026-09-16-goal-completion-audit.md`

**Operator:** run in Terminal.app (GUI keychain + browser):

```bash
./scripts/ops_unblock_github.sh
```

Script now: unlock keychain → `gh auth login` if invalid → `gh auth setup-git` → audit → push → close #3→#4→#2.

---

## Issue #3 — S1–S4 mechanical tables

**Close as completed.** Paste comment:

```
Mechanical v1 deliverable landed in-repo.

Evidence:
- docs/specs/xauusd-s1-s4-mechanical-v1.md
- tests/test_s1_s4_mechanical_spec_contract.py (6/6)
- ADR-0027 rule version s1-s4-mechanical-v1

Parent #2 stays open until #4 closes and Gate A freeze is acknowledged.
```

## Issue #4 — Research handoff

**Close as completed.** Paste comment:

```
Research handoff v1 published.

Evidence:
- docs/specs/xauusd-s1-s4-research-handoff-v1.md
- Explicit unresolved Gate B/C blockers listed (not silent incompleteness)
- Specs README: gates open — not experiment-ready

Remaining live/runtime evidence tracked under #1.
```

## Issue #2 — Parent S1–S4 experiment

**Close only after #3 and #4 are closed on the tracker.** Paste comment:

```
Children #3/#4 documentation deliverables are complete in-repo.
Closing parent tracker item; Gate A freeze / experiment start remains a
separate operator decision under the research handoff + foundation gates.
```

## Issue #1 — Gold Playbook Foundation

**Do NOT close yet.** Software/runtime gates advanced on branch; still missing:

1. Live Exness Demo identity smoke (`scripts/smoke_broker_identity.py`) — Mac host currently `mt5_import_missing` (see `docs/ops/2026-09-16-smoke-evidence-log.md`)
2. Oracle ARM64 soak execution evidence
3. Forward Demo 12-week protocol start (prospective)

Progress map: `docs/handoff/2026-09-16-issue1-foundation-progress.md`
