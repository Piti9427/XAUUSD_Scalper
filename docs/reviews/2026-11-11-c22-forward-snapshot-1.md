# Forward snapshot 1 — native vs B2+maxloss_1 on unseen ticks (2026-11-11)

Early snapshot, not a gate decision. The plan's gates need ≥3 months and ≥60 trades.
- Protocol: `runs/c22-forward-2026-11/protocol.json` (sha256 `eb737074…dea6`), frozen before data contact.
- Data: Exness archive Aug–Nov 2026, sha-pinned. Aug 1 – Oct 24 is warm-up only. Overlap bars match the
  discovery tape (5,353 bars).
- Forward window: 2026-10-24 → 2026-11-10 23:59 UTC.

## Result

| Cell | native net / trades / DD | candidate |
| --- | --- | --- |
| base $313 | +48.01 / 14 / 23.98% | identical |
| stress $313 | +47.13 / 14 / 24.09% | identical (native skipped one trade by risk cap) |
| stress $1,845 | +9.11 / 15 / 7.13% | **+47.13** / 14 / 5.19% (maxloss_1 blocked the 11-05 23:00 SELL, −38.02) |

All 14 trades were SELL; no BUY signal occurred, so B2 had no effect. maxloss_1 only mattered once.
**Too early to judge the candidate.**

## Model vs live Demo (does the backtest match reality?)

The 3 trades the live bot made are reproduced by the model:

| Trade | Live entry / TP / exit / net | Model entry / TP / exit / net |
| --- | --- | --- |
| 10-29 23:15 SELL | 4015.354 / 3982.396 / 10-30 13:47:16 / +33.84 | 4015.359 / 3982.556 / 13:47:16 / +32.80 |
| 11-10 16:15 SELL | 4096.178 / 4071.721 / 18:06:04 / +24.46 | 4095.784 / 4071.459 / 18:06:04 / +24.33 |
| 11-10 20:45 SELL | 4057.858 / 4028.297 / 23:21:12 / +29.56 | 4056.465 / 4027.411 / 23:21:12 / +29.05 |

Prices are within $1.40, exit times are identical, and net differs by ≤ $1.04. Live was slightly better.
The tick model is realistic for trades that happen.

## Real-world gap found

**The model took 14 trades. The live bot took 3.** These 11 signals were not traded live:

| Date (ICT) | Missed trades | Net |
| --- | --- | --- |
| 10-27 | 1 | −15.76 |
| 10-28 | 1 | −13.29 |
| 10-30 | 3 | +26.06, +26.11, +33.21 |
| 10-31 | 1 | −27.74 |
| 11-03 | 2 | +24.99, −17.18 |
| 11-05 | 1 | −25.43 |
| 11-06 | 1 | −33.59 |
| 11-10 23:30 | 1 | still open |

The closed missed trades sum to ≈ −$22.6. Execution availability is a bigger live-vs-backtest gap than
any tuning knob.

Root cause is not established. Candidates seen in the record:
- manual positions on the same account (foreign exposure blocks admission; for example the 11-02 manual BUY);
- cost-assumption expiry (2026-11-01 13:25 UTC per CORE_STRATEGY 6.54);
- the 11-01 account equity change;
- quote freshness or entry-window misses.

Resolving it needs a read-only pull of the VM execution journal's rejection reason for each missed bar.

## Root cause of the 11 missed signals (read-only VM journal pull, 2026-11-11)

Source: `audit_events` in `/home/ubuntu/c22-demo/state/c22-selected-execution.sqlite3`, opened `mode=ro`
over SSH. No VM file was written.

| Signal close (UTC) | Model trade | Live blocker at admission |
| --- | --- | --- |
| 10-27 08:15 | SELL −15.76 | `cost_policy_invalid_or_stale`, then `entry_window_expired` |
| 10-28 04:15 | SELL −13.29 | `cost_policy_invalid_or_stale` |
| 10-30 07:00 | SELL +26.06 | `cost_policy_invalid_or_stale` |
| 10-30 12:45 | SELL +26.11 | `algo_permissions_required` (terminal AutoTrading off) + cost policy |
| 10-30 13:45 | SELL +33.21 | same |
| 10-30 17:15 | SELL −27.74 | same |
| 11-03 04:45 | SELL +24.99 | `cost_policy_invalid_or_stale` |
| 11-03 09:00 | SELL −17.18 | `cost_policy_invalid_or_stale` |
| 11-05 14:45 | SELL −25.43 | `selected_execution_review_invalid` (09:20–21:50 UTC) |
| 11-06 04:15 | SELL −33.59 | **no CYCLE events at all 11-06..11-09**: sender not running or not logging for about 4 days |
| 11-10 16:30 | SELL (open) | `risk_cap`: live equity ≈ $313 and SL distance 35.7 → $35.7 > 10% cap; the model account had +$48 more equity |

Summary:
- 8 of 11 hit the cost-policy gate. That release recorded no sub-code; `costs.py` checks freshness
  (24 h for v1), account binding and evidence.
- 3 of those 8 were also blocked by AutoTrading being off.
- 1 was blocked by an invalid execution review, 1 fell in the sender outage, and 1 was the account-size cap.
- Over the whole window, `algo_permissions_required` covered most of 10-25..10-28 and 10-30..11-02.

**The live Demo is not running the strategy that was backtested.** Operational availability
(cost-policy renewal, AutoTrading state, review validity, sender uptime) loses more trades than any
tuning knob gains. Fixing availability is the prerequisite for any forward comparison and for the B2/maxloss_1 rollout.
