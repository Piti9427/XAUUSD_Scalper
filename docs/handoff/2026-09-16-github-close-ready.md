# GitHub close-ready notes

**Branch:** `feature/smc-v2-hardening` @ `353771f` (pushed)  
**Unit suite:** `python3 -m unittest discover -s tests` → **353 OK**  
**`gh` CLI:** token **invalid** — run `gh auth refresh -h github.com -s repo`  
**GitHub MCP:** rate-limited / previously read-only for issue write

---

## Issues #2 / #3 / #4

Closed earlier on this branch with local evidence. Re-verify after `gh auth refresh`:

```bash
gh issue view 2 --repo Piti9427/XAUUSD_Scalper
gh issue view 3 --repo Piti9427/XAUUSD_Scalper
gh issue view 4 --repo Piti9427/XAUUSD_Scalper
```

Paste packs (if still open): see historical sections below or `docs/ops/2026-09-16-github-close-evidence.json`.

---

## Issue #1 — Gold Playbook Foundation

**Do NOT close yet.** Gate B software evidence is strong; Gate C/D live artifacts missing.

### Progress comment (paste after `gh auth refresh`)

```
Issue #1 software/Gate B progress on feature/smc-v2-hardening (not closable yet).

Software evidence:
- 353 unit tests OK
- Foundation scenarios 1–23 mapped with in-repo evidence:
  docs/ops/2026-09-16-issue1-scenario-coverage.json
- Progress map: docs/handoff/2026-09-16-issue1-foundation-progress.md
- Recent: freeze_level SL gate, H1 bias cancel + pre-submit block,
  persistent SetupRegistry across restarts, stops geometry, freshness/metadata

Live gates still required (do not invent PASS):
1. Exness Demo hedging identity smoke → docs/ops/<date>-exness-smoke.json ok:true
2. Oracle ARM64 soak completed artifact
3. Demo 12w start artifact after Gates B/C

Mac blocker (current host):
- Wine terminal64 running but MetaTrader5 initialize → -6 Authorization failed
- Bases = MetaQuotes-Demo (not Exness); settings.yaml has no Exness credentials
- Evidence: docs/ops/2026-09-16-mac-wine-reprobe-running.json
- SSH hosts TCP/22 open but Mac ed25519 unauthorized:
  docs/ops/2026-09-16-host-reachability-hunt.json

Readiness: docs/ops/2026-09-16-issue1-live-gate-readiness.json
issue1_closable: false

Operator next:
1. gh auth refresh -h github.com -s repo
2. Authorize Mac pubkey on Windows/Oracle MT5 host OR run foundation_live_gate.sh there
3. Login Exness Demo (hedging) and collect smoke/soak/Demo artifacts
```

### Close comment (ONLY after live artifacts exist)

```
Gold Playbook Foundation acceptance met.

Evidence:
- Software/scenarios: docs/ops/2026-09-16-issue1-scenario-coverage.json
- Exness smoke ok:true: docs/ops/<date>-exness-smoke.json
- Oracle soak: docs/ops/<date>-oracle-soak*.json
- Demo 12w start: docs/ops/<date>-demo-12w-start*.json
- Readiness issue1_closable:true: docs/ops/<date>-issue1-live-gate-readiness.json

Closing #1.
```

---

## Historical #3 / #4 / #2 paste packs

### Issue #3

```
Mechanical v1 deliverable landed in-repo.

Evidence:
- docs/specs/xauusd-s1-s4-mechanical-v1.md
- tests/test_s1_s4_mechanical_spec_contract.py
- ADR-0027 rule version s1-s4-mechanical-v1
```

### Issue #4

```
Research handoff v1 published.

Evidence:
- docs/specs/xauusd-s1-s4-research-handoff-v1.md
- Explicit unresolved Gate B/C blockers listed
```

### Issue #2

```
Children #3/#4 documentation deliverables are complete in-repo.
Closing parent tracker item; Gate A freeze / experiment start remains a
separate operator decision under the research handoff + foundation gates.
```
