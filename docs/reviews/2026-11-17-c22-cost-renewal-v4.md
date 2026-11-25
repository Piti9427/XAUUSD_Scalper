# C22 cost-policy renewal v4 (2026-11-17)

On 2026-11-17 the cost policy and execution review for the live release `selected-23ab6655adee8443` were renewed for another 168 h. Nothing else changed: no code, unit, strategy, lot, risk, daily-stop or terminal change. Real money remains PROHIBITED.

## Result
| Item | Value |
| --- | --- |
| Previous policy | reviewed 2026-11-12 08:14:35 UTC, swap_long −644.8, expiry 2026-11-19 08:14:35 UTC |
| New policy | reviewed / approved **2026-11-17 11:19:13 UTC**, expiry **2026-11-24 11:19:13 UTC** (18:19 ICT) |
| swap_long | **−644.8 → −474.3** POINTS, as reported by the broker probe and approved by the owner; swap_short 0.0; tolerance band unchanged (adverse 10 / favourable 25) |
| Native positions acknowledged and audited | 9 positions: the 6 from v3 plus 5035244520, 5037305324, 5038591397 |
| Install dir | VM `preparation/selected-review-renewal-v4-20261117T111904Z/` |
| Staging and logs | VM `state/staging-renew-20261117/` |
| Local copy of the tooling | `runs/c22-renewal-v4-2026-11-17/` |
| Post-start state | review VALID, policy_due CURRENT, kv review sha equals the installed review, audit release_hash is 23ab, NRestarts 0 at t+90 s, last_result `armed_trial_new_closed_m15_required` (expected until the next closed M15 bar) |

## Owner approvals (verbatim in `owner-verbatim*.txt`)
- **17:33 ICT, "อนุมัติ เสร็จแล้วสรุป task process":** covered −644.8 only.
- **18:19 ICT, "อนุมัติ −474.3":** used for the successful run.

## Process
1. **Read-only VM check.** Nobody had renewed yet; the account was flat; the sender was on 23ab. `policy_due` was DUE_72H.
2. **Built v4 from the v3 scripts used on 11-12** (`staging-deploy-20261112/v3`, `go-deploy-v3.sh`). Only these changed:
   - the constants: previous cutoff, previous swap −644.8, and the 6 already-audited position ids;
   - a guard requiring the same release cohort;
   - the go script: it renews pointers only and makes no unit change.
3. **Dry-run on the Mac** against the copied 23ab release:
   - the live `ExecutionReview` validator returned VALID;
   - negative controls were refused: swap mismatch, stale broker evidence, unacknowledged native position, and sources older than 24 h.
4. **Fresh source review of official Exness pages** (tariff, About swap, Instrument trading hours) via the in-app browser after the owner signed in. Since 2026-11-17 the help-center pages require sign-in, and automated fetches return 403.
5. **Run attempt 1** was aborted: the probe path still pointed to the old staging dir. The script's automatic restore ran.
6. **Run attempt 2** was aborted: the broker reported swap_long −474.3, which was outside the −644.8 approval. Automatic restore ran.
7. **Run attempt 3** succeeded with the owner's approval of −474.3.

Each of the three runs stopped the sender for about 10–60 s. There was no `order_send` and no position.

## Findings and follow-ups
- **Blocker since 13 Nov.** `cost_policy_invalid_or_stale` was logged twice from 2026-11-13 13:30 UTC. This is likely the broker swap drift −644.8 → −474.3, which is outside the 25-point favourable band. If so, the sender has been blocking entries since then even though the policy had not expired. Verify by checking the blocked signals from 11-13 to 11-17.
- **Process fragility.** Each renewal needs:
  - a hand-derived vN script;
  - the owner's sign-in for the source pages;
  - an exact-value approval.

  Ticket 13 decision 2 (an ops script that prepares the renewal package) is still undone. Generalising v4 into a parameterised renewer would remove the hard-coded paths that caused attempt 1.
- **Forward shadow.** It assumed −490 primary and −567.4 sensitivity, while the broker now reports −474.3. The current results are unaffected because all trades so far are SELL.
- **Next expiry:** 2026-11-24 11:19 UTC (18:19 ICT, Tuesday). No reminder exists yet.
