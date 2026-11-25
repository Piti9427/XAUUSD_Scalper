# Selected26b8 live availability — root cause (2026-11-12)

Plan: `/Users/nopparuj/.claude/plans/cuddly-percolating-snail.md`, Track A step 1. All evidence is read-only:
- VM `audit_events` (sqlite `mode=ro`);
- `journalctl -u c22-selected-execution`;
- the MT5 terminal logs of the selected Wine prefix (`c22-qemu-demo…/mt5-c22-demo/logs`);
- installed cost-policy JSONs.

No VM file was written. Problem: the sender took **3 of 14** model signals from 2026-10-24 to 11-10.

## Root causes

| # | Mechanism | Evidence | Misses |
| --- | --- | --- | --- |
| R1 | **Exact swap match in cost evidence.** `validate_evidence` (`scripts/demo_runtime/costs.py`) requires live `swap_long` == the stored value. Exness changes it every few days: −490.8 (10-25), −490.0 (10-28), −492.0 (10-29), −498.9 (11-10). Each change blocks admission (`cost_policy_invalid_or_stale`) until a manual renewal. The v1 24 h expiry before the 10-28 v2 install had the same effect | policy JSONs; blockers only at signal bars | 8 |
| R2 | **Terminal reconnect loop.** At a round time (00:00/12:00) the MT5 terminal rescans access points and "auto connects to a better access point with 99% (previous 99%)". It loses the connection, re-authorizes, and repeats every ~16 s until the terminal restarts. During the loop `terminal_connected=False` / `account_trade_allowed=False`, which surfaces as `algo_permissions_required`. **AutoTrading was not switched off** | terminal logs: lost/day 10-27 2184, 10-28 2571, 10-30 1301, 11-01 985, 11-02 958; zero after the restarts on 10-29 and 11-02 | 3 (overlapping R1) |
| R3 | **Cost-policy expiry → review invalid.** `ExecutionReview.check` requires v2 costs within 168 h. The 10-29 install expired about 11-05 09:20, and every admission then failed `selected_execution_review_invalid` | blockers 11-05 09:20–21:50 | 1 |
| R4 | **Crash loop after a journal lock.** At 21:50 UTC (the daily journal backup) `journal.put` raised `OperationalError`, crashing the sender (also on 11-04). On restart with no open position, `install_execution_review` calls `review.check()`, which raised (R3). The process exited, so systemd restarted it **13,805 times** until the 11-10 05:28 renewal. There were no cycles 11-06..11-09 | journalctl exit traces (`journal.py:64`, `execution.py:178`) | 1 + 4 days down |
| R5 | **Account-size risk cap**: SL 35.7 → $35.7 > 10% of ≈ $313 | blocker 11-10 16:30 | 1 (by design) |
| R6 | **Non-bot use of the account**: manual positions (`foreign_exposure` 11-02 08:34–11:54), a −$1,612.81 withdrawal on 11-01, and logins from other IPs (49.229.x, 58.97.x, 124.12x.x) | terminal log, audit | indirect |

Also observed: `OPERATIONAL_FAILURE evidence_packet_context_mismatch` on every cycle since the 11-10 release
(`scripts/c22_selected/evidence.py:139`). It is not yet analysed and does not block admission.

## Proposed fixes

| Fix | Type | Decision needed |
| --- | --- | --- |
| F1 Journal writes tolerate a backup lock (busy timeout + bounded retry; the backup must not hold a write lock) | code + tests | none (reliability) |
| F2 Startup with an invalid review stays alive: manager only, entries blocked, alert. No exit/crash loop | code + tests | none (matches the existing "manager continues" contract) |
| F3 Cost-evidence swap drift: either (a) a tolerance band or (b) attended renewal with an alert before expiry/drift. The current owner rule says any swap difference blocks and forbids automatic renewal | policy | **owner** |
| F4 Terminal reconnect loop: detect churn (> N losses/hour) → alert, plus an attended or automatic terminal restart; check whether the MT5 access-point auto-switch can be disabled | ops | **owner** (auto-restart of the terminal) |
| F5 Alerts for every operational blocker lasting more than one signal (reuse the batch-A alerter) | ops code | none |
| F6 Bot-only account (Q3): no manual trades, logins or cash moves during measurement | owner action | owner |
