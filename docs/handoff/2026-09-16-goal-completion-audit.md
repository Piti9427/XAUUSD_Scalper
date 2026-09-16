# Goal completion audit — fix all open GitHub issues

**Objective:** Implement, verify, and close every open issue on `Piti9427/XAUUSD_Scalper`.  
**Branch:** `feature/smc-v2-hardening` @ `ee8222c` (+ local Gate-C probe WIP)  
**Last verified:** 2026-09-16 ~16:57 ICT

| Issue | Requirement | In-repo evidence | GitHub closed | Verdict |
| --- | --- | --- | --- | --- |
| **#3** Mechanical S1–S4 spec | Docs + contract tests | specs + contracts | ✅ CLOSED (prior) | **Done** |
| **#4** Research handoff | Docs + Gate B/C blockers | specs + contracts | ✅ CLOSED (prior) | **Done** |
| **#2** Parent tracker | Close after #3/#4 | Parent closed | ✅ CLOSED (prior) | **Done** |
| **#1** Gold Playbook Foundation | Software + **live** Exness/Oracle/Demo | 359 tests; scenarios 1–23 software OK; Mac Gate C still fail-closed | ❌ OPEN (gh token invalid this session) | **Live gates still required** |

## Issue #1 gate audit (authoritative)

| Gate | Required evidence | Current state | Status |
| --- | --- | --- | --- |
| A — freeze / open decisions | ADR-0027/0028 + open-material registry | Present; open rows stay open | Software OK |
| B — scenarios 1–23 | `docs/ops/2026-09-16-issue1-scenario-coverage.json` | `software_evidence_complete: true` | Software OK |
| C — Exness Demo smoke `ok:true` | `docs/ops/*-exness-smoke*.json` | Latest Mac probe `ok:false` (no MetaTrader5 package); Wine `-6`; SSH pubkey denied | **BLOCKED** |
| C — Oracle soak complete | `docs/ops/*-oracle-soak*.json` | Checklist only | **BLOCKED** |
| D — Demo 12w start | `docs/ops/*-demo-12w-start*.json` | Protocol only | **BLOCKED** |
| Closable? | smoke + soak + Demo start | `issue1_closable: false` | **Not closable** |

## Host reachability (do not invent SSH success)

- Reprobe `docs/ops/2026-09-16-host-ssh-reprobe.json`: TCP/22 open on OCI `158.178.243.98` + LAN `192.168.7.{8,19,21,22}`; BatchMode auth **Permission denied (publickey)** for `nopparuj/ubuntu/opc/root`.
- Mac venv: `MetaTrader5` package **missing** (`issue1_mac_gate_c_probe.py`).
- Only Mac pubkey: `~/.ssh/id_ed25519.pub` (printed by `issue1_operator_unblock.sh`).

## Operator unblock

```bash
./scripts/ops/issue1_operator_unblock.sh
python3 scripts/ops/issue1_mac_gate_c_probe.py   # expect ok:false on Mac
```

1. Authorize Mac `~/.ssh/id_ed25519.pub` on MT5 host **or** run `./scripts/ops/foundation_live_gate.sh` there with Exness Demo (hedging).  
2. Refresh `gh auth refresh -h github.com` (token currently invalid for issue verify/comments).  
3. After `ok:true` smoke + soak + Demo start → readiness `issue1_closable:true` → close #1.

## Goal complete when

- [x] #2/#3/#4 closed with evidence  
- [x] Foundation software + Gate B coverage on branch  
- [ ] `gh` can re-verify issue states (token invalid now)  
- [ ] #1 live artifacts (not Mac fail-closed only)  
- [ ] #1 closed after live gates  
