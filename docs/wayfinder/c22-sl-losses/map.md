---
id: c22-sl-losses
title: Why C22 trades lose at SL, and what can be fixed without repeating mistakes
labels: ["wayfinder:map"]
status: open
assignee: null
created: 2026-11-18
---

## Destination
Decide, with evidence, whether any SL loss pattern can be fixed **without** making trend-period profit or DD worse. If nothing passes, keep native 26b8 and let the forward data decide.

## Evidence on 2026-11-18
**Live bot (magic 22261025):** 10 closed trades, all SELL. 7 TP, 1 BE and 2 SL; net **+134.70**.

| Ticket | Entry (ICT) | Stop | Held | Notes |
|---|---|---|---|---|
| 5038591397 | 11-12 22:00 | 35.6 pt (ATR ≈ 14, high volatility) | 10.4 h, overnight through Asia | The 6th SELL in a 225-pt down leg. −35.62 |
| 5067895413 | 11-17 20:45 (signal bar 13:30Z) | 18.0 pt | 45 min | −18.01 |

- Both SLs triggered broker-side at the exact SL price, with no slippage. Protection worked.
- Live fills match the model within $1.40, as found by the earlier availability review.
- **Corrected on 2026-11-18 (scrutinize).**
  - TP is about 1.33R (SELL), so the break-even win rate is about 43%.
  - On the $200 ledger, SELL wins 48% with a mean of +0.14R.
  - Native SELL net by year ($313 base):

    | Year | Net |
    |---|---:|
    | 2020 | −179 |
    | 2021 | −127 |
    | 2022 | +82 |
    | 2023 | +20 |
    | 2024a | −161 |
    | 2024b25 | −87 |
    | 2026 | **+943** |

  - **The whole SELL profit comes from 2026.** Without 2026, SELL is −452.
  - The live 2 SLs out of 10 is a 4% tail under the historical SL rate (P(≤2 SL) = 0.041 at p_SL = 0.52). It reflects the 2026 trend regime, not a better strategy, and it should not be extrapolated.
  - Expect a longest SL streak of 6 (median) to 9 (p90) per 100 SELL trades.

## Hypotheses tested today
History was seen, so each line falsifies at most; none confirms.

| # | Hypothesis | Test | Result |
|---|---|---|---|
| T1 | A US data print at 08:30 ET causes the SL | Bucket SELL by ET time | **Falsified.** ET 08:30–09:29: net −41, 4/7 negative years. The ET 08:30 bucket is +96 |
| T2 | SELL signal bar at 13 UTC | Bucket by UTC hour | n = 96, win 30%, −235, 6/7 negative years. **Weak:** across about 40 hour cells, about 2.5 cells would hit ≥6/7 negative years by chance |
| T3 | Entering after the trend is over-extended | SELL quintiles of h4dist | **Falsified.** Top quintile is +29; Q4 is the best at +484 |
| T4 | Entering after a win streak (exhaustion) | Prior consecutive SELL wins | **Falsified.** Not monotonic: after 3 wins −169, after 4+ wins +142 |

### T2 permutation test (2026-11-18): **consistent with noise**
- Script: `runs/c22-sl-forward-prereg-2026-11-18/perm_hour.py`. Output: `perm_hour_result.json`.
- Settings: 10,000 shuffles, seed 20261118, deterministic on rerun.
- Method: hour labels are shuffled within side × year. 37 cells with n ≥ 10.

| Measure | p |
|---|---:|
| SELL 13, unadjusted (z −1.72) | 0.037 |
| **Family-wise: worst cell at least this bad** | **0.70** |
| Family-wise: some cell with ≥6/7 negative years | 0.98 |
| Family-wise: some cell as bad on both z and negative years | 0.49 |

- **Power check:** an extra −$3 per trade injected into SELL 13 gives a family-wise p of 0.009, and −$6 gives 0.000. So the test can detect a real effect of that size.
- **Conclusion:** the SELL 13 result is about what the worst of 37 cells looks like by chance. Do not build a history-based filter on it.
- The forward pre-registration stays, because it is cheap and frozen, but its prior is low.

## Dead ends (do not retry)
| Family | Where | Verdict |
|---|---|---|
| Entry regime filters (h4slope, h4dist, d1dist, e50slope, er96) | `runs/c22-26b8-regime-fix-2026-11-12` | LOYO FAIL, 1/7 |
| Volatility floor (frozen, relaxed and derived) | `docs/reviews/2026-11-13-c22-losing-trades-volfloor-verdict.md` | FAIL; budget used up |
| Entry timing (pullback limit, skip >1.5 ATR) | `runs/c22-entry-timing-20261113` | Keep the current entry |
| Exits: time stop, trail, lock, TP/BE variants | `runs/c22-26b8-exit-tuning-2026-11-01`, `…exit-oos-2026-11-11` | Walk-forward FAIL |
| Equity pause and DD pause | `runs/c22-pause-2026-11-12`, `…fail-rootcause-2026-11-02` | FAIL against native |
| Cooldown removal | `runs/c22-cooldown-ab-20261112` | Keep the cooldown |

**Root cause (unchanged):** losses come from the breakout edge being near zero or negative in low-volatility range regimes, with costs added on top. There is no repeated *mistake* such as bad fills, missing protection or a broken rule. An SL is the normal cost of a 40%-win, 1.35R system.

## What is open
1. **Forward pre-registration of T2.** Frozen in `runs/c22-sl-forward-prereg-2026-11-18/prereg.json`, sha256 `6eb05d51…c889`.
   - It is evaluated only on forward shadow trades from 2026-11-18 onward.
   - Maturity: ≥10 H13S trades and ≥40 other SELL trades, which is about 6–9 months.
   - The pass rule is fixed and cannot change after any look.
2. **Availability.** 3 of 14 signals were taken in Oct–Nov. G1 and v5/G2 address the cost-gate cause.
   - Correction: it is NOT shown that missed signals cost more than SLs. One known missed signal (11-13) would itself have been an SL of −14.14.
3. **Data mapping for the pre-registration.** This is not a change to the rule.
   - "Signal bar opens" means the M15 bar *before* entry. History used the `bar` column in `native_trades_feats.csv` (`screen.py`: entry − 15 min, floored to M15).
   - For shadow ledgers, take `floor15(entry_utc) − 15 min`. Example: entry 13:30:00 → signal bar 13:15 → H13.
4. **Owner decision, outside this map.** Whether to accept the relaxed volatility-floor trade-off. It is closed under the current rules.

## Owner rules applied
Real money prohibited. 10% cap. No recovery baskets. Swap-inclusive base and stress. Freeze with sha256 before evaluating. Nothing may get worse against native 26b8. One derived iteration per failed mechanism.
