# C22 native 26b8: live trades vs model, and the defects they reveal (2026-11-18)

## Data
- **Model:** native replay on the forward window 2026-10-24..11-16 at $360, base view, with public Exness ticks (`runs/c22-candidate-livebal-2026-11-18/fwd_livebal.json`).
- **Live:** bot trades from `logs/trade-journal/trades.csv` (magic 22261025).
- **Reason for each missed trade:** read-only `journalctl` cycles on the VM, from the signal bar close to +150 s.

## Matching
- The model took 23 trades. The live bot took 10: 9 matched, plus 11-17, which falls after the model data ends.
- **The bot missed 13 of the 23 model trades.**

| Model entry (UTC) | Model result | Why live missed it | Class |
|---|---|---|---|
| 10-27 08:15 | SL −15.76 | cost_policy_invalid_or_stale | swap gate |
| 10-28 04:15 | SL −13.29 | cost_policy_invalid_or_stale | swap gate |
| 10-30 07:00 | TP +26.06 | cost_spec_mismatch, swap_long observed −488.0 | swap gate |
| 10-30 12:45 | TP +26.11 | swap −488.0, plus algo_permissions_required (AutoTrading off) | swap gate |
| 10-30 13:45 | TP +33.21 | swap −488.0, plus AutoTrading off | swap gate |
| 10-30 17:15 | SL −27.74 | swap −488.0, plus AutoTrading off | swap gate |
| 11-03 04:45 | TP +24.99 | swap −481.0 | swap gate |
| 11-03 09:00 | SL −17.18 | swap −481.0 | swap gate |
| 11-05 14:45 | SL −25.43 | selected_execution_review_invalid (review expired) | review expiry (fixed D1/D2, v5) |
| 11-06 04:15 | SL −33.59 | selected_execution_review_invalid | review expiry |
| 11-10 16:30 | SL −35.83 | risk_cap (live balance lower than $360) | strategy rule, not a defect |
| 11-12 07:00 | TP +22.66 | day_start_floating_unknown | boundary (fixed D6) |
| 11-13 13:30 | SL −14.14 | swap −475.0 | swap gate |
| 11-16 06:00 | SL −24.75 | swap −471.7 | swap gate |

(The table has 14 rows because 11-16 06:00 is included. It sits right at the model data edge.)

## Defects, ranked by count
1. **The swap gate blocks SELL entries: 10 of 13 misses (77%).**
   - The broker's swap_long drifts (−488 → −481 → −475 → −471.7) away from the pinned value. The pins were −492/−498.9 and then −644.8, outside the adverse 10 / favourable 25 band.
   - A SELL pays swap_short, which is 0.0, yet the whole-spec check blocks it.
   - Mitigations in place: G1 alerts at once (deployed) and G2 does a cross-day check at renewal (v5 uploaded).
   - **Root fix not built:** a direction-aware check (G3) in which SELL admission ignores swap_long drift and swap_short stays exact.
2. **Review expiry: 2 misses, plus about 5 days of downtime.** Fixed by D1/D2 and the renewal process; next renewal is v5, before 11-24.
3. **UTC boundary: 1 miss.** Fixed by D6 (release 23ab).
4. **AutoTrading off on 10-30.** It overlapped the swap gate. The watchdog (D0/D10) covers it.
5. **Feed divergence: 1 matched trade.** Model entry 11-11 18:15 hit TP for +22.87. Live entered at 18:00 with a wider stop (19.04 vs 16.94), so its TP of 3966.721 was never reached. The archive's minimum ask was 3968.73. The live trade ended at BE +0.10. This is the broker Trial7 feed against the public archive, not a bot bug.

## Honest impact
- In this window the 13 missed trades would have netted **−74.68** in the model: 5 TP for +133.03 and 9 SL for −207.71.
- So the defects did not cost money this time. They made the live results differ from the tested strategy, and that difference was luck.
- The reason to fix them is fidelity, so that live equals the tested strategy over time. It is not because they lost money here.
