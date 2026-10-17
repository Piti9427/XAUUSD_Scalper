# B1/D comprehensive backtest and selection — 2026-09-26

**Final selection: no strategy qualifies for deployment.** Highest historical base net is B1 with SL 2.5 ATR, TP 2.5R, risk cap 2%, all sessions; it fails drawdown and cost robustness. Development-only leader is a different B1 contract and fails later periods. These must not be collapsed into one “best” claim.

## Scope completed

Frozen [plan](B1_D_COMPREHENSIVE_PLAN_2026-09-26.md): two reconstructed strategies × 5 ATR stops (1/1.5/2/2.5/3) × 4 targets (1.5/2/2.5/3R) × 4 risk caps (0.5/1/1.5/2%) × 2 session policies (all / London-New York) = **320 policies**. All 320 replayed at 0/0.10/0.20R additional-cost reserve. Four scoring windows = **3,840 account replays**, plus **12** doubled-spread, latency, adverse-fill and combined stress replays on the three development-locked finalists.

Observed broker dataset: **31,780,274 actual Bid/Ask ticks**, 2026-05-07 00:00:00.108 UTC through 2026-09-25 20:57:59.762 UTC. Capture requested January onward; server returned no ticks before May 7. Those absent months are **missing history**, not zero-market-activity evidence. May 7–13 warmup; May 14–June 30 development; July–August validation; September confirmation; May 14–September 25 continuous-account run. Every split starts at the same verified Demo snapshot balance 1,173.46 USD; continuous run carries balance/position lifecycle until final sample liquidation, without monthly account resets. Splits are separate diagnostic accounts, not additive profits.

Build complete M15 Bid bars from tick-derived M1; no fabricated prices or synthetic Ask. Captured source hashes validated daily; tick UTC/day bounds/order/finite prices and Bid<=Ask checked. 139,625 tick-observed M1 minutes, 9,199 complete M15 bars. Tick-level exits and marked drawdown, floor to min/step 0.01 lot, nominal sizing plus cost reserve cannot exceed configured risk. Stops/targets rounded to broker tick grid; risk recomputed. No Martingale or portfolio combination.

## Highest base profit: descriptive only

`B1_sl2.5_rr2.5_risk0.02_all` (unchanged B1 native geometry):

| Cost reserve | Trades | Net USD | PF | Tick equity DD |
|---|---:|---:|---:|---:|
| 0R | 150 | +541.37 | 1.240 | 16.87% |
| 0.10R | 140 | +258.15 | 1.126 | 16.72% |
| 0.20R | 91 | −121.36 | 0.909 | 23.05% |

Highest base profit does not mean strongest validation. DD exceeds frozen 5% threshold and stressed outcome loses. This contract was discovered by full-period comparison, not selected before seeing later returns. **Rejected for deployment.**

Highest 0.20R net across full-period rows is `B1_sl3_rr2_risk0.02_london_ny`: +134.17 USD, PF 1.953, **only 14 trades**, DD 7.36%. Its **zero-extra-cost base loses 21.53 USD** with 32 trades. Additional admission cost changes which minimum-lot setups are affordable, skipping some losers and changing occupancy/compounding; a “better stressed result” is not proof that higher costs improve the same trades. This small retrospective winner also fails eligibility and is not selected.

## Selection fixed before validation

Development screen: >=30 trades, positive net at every cost, PF>=1.1 and DD<=5% at every cost. **Zero policies passed.** Keep three least-bad >=30-trade research finalists by development 0.20R net/DD; do not relax DD threshold or promote them. Development leader: `B1_sl2_rr2_risk0.02_all` (SL2 ATR/2R/2%/all sessions).

| Leader window, 0.20R reserve | Trades | Net USD | PF | Tick equity DD |
|---|---:|---:|---:|---:|
| Development | 49 | +67.32 | 1.122 | 14.31% |
| Validation Jul–Aug | 97 | −52.91 | 0.954 | 22.87% |
| Confirmation September | 38 | −106.20 | 0.777 | 16.07% |
| Continuous May–September | 184 | −180.17 | 0.920 | 34.66% |

Other locked finalists (`B1_sl2_rr1.5_risk0.02_all`, `B1_sl1.5_rr3_risk0.015_all`) also lose in validation and confirmation. Leader loses under doubled spread (−198.38 USD), 2-second latency (−184.23), 0.10 price-distance adverse-fill sensitivity (−181.04) and combined stress (−185.90). Stress already reserves 0.20R; none is calibrated twice-measured-cost validation.

D: at most **3 admitted trades** in any continuous configuration. Best 0.20R D row has 2 trades/+11.42 USD. This is **insufficient**, not demonstrated profitable or demonstrated universally losing. Increasing risk/RR cannot manufacture its missing signals.

## Statistical/market diagnostics

All continuous policies include monthly, long/short, UTC session and causal entry-regime breakdowns (`breakdowns.csv`). Regime labels diagnostic only, not router optimization. Three monthly prior-closed-ledger selections use earlier exit timestamps only; none meets prior screen. Their next-month diagnostic net: July +112.51, August −96.50, September −158.92 USD. Cross-month open trades excluded; this diagnostic does not pretend to be a stitched executable portfolio.

For three locked finalists: 100,000 seeded weekly-block bootstrap draws, quiet weeks retained, 320-policy Bonferroni lower-tail correction. Leader mean closed-trade expectancy −0.053R; unadjusted lower −0.263R; corrected lower −0.449R. No positive lower-bound evidence. The extreme corrected quantile is based on roughly eight tail samples and imprecise; it cannot rescue qualification.

10,000 conditional permutations of observed return fractions: leader 95th-percentile closed-equity DD 39.25%. These permutations do not recreate lot admission, broker execution or intratrade paths; not a forecast or true future ruin probability.

## Limits: “all conditions” is finite

Covered declared risk/stop/target/session matrix, direction/regime/month diagnostics, actual spread, present-spec swap scenario, sample-end positions, minimum-lot rejections, stress latency/spread/slippage, chronology and statistical selection risk. Not established: unavailable January–May6/2025 broker ticks; representative historical commission/slippage/rollover; historical margin/leverage/stop-level changes; news-calendar replay; foreign-position/restart/concurrent-process broker behavior; post-freeze forward fills. Price replay cannot certify those operational paths. Current symbol/account specs verified, but historic broker approval not assumed.

All periods retrospective/exposed. No pristine OOS claim. No live trading config changed and no order API invoked. Existing qualification gates remain in force. Wider stop/risk alternatives do not justify exceeding risk cap or silently raising minimum lots.

## Reproduce and artifacts

```bash
.venv/bin/python -m scripts.research.b1_d_comprehensive \
  --capture data/b1_d_exness_ticks_2026_full_retry \
  --output data/b1_d_comprehensive_2026-09-26

.venv/bin/python -m scripts.research.b1_d_robustness \
  --matrix data/b1_d_comprehensive_2026-09-26 \
  --output data/b1_d_comprehensive_robustness_2026-09-26_verified
```

Existing paths immutable; use fresh output names for rerun. Matrix directory contains hashed manifest, tick tape/coverage audit, locked shortlist timestamp before later scoring, 3,852 reconciled trade ledgers, 3,840 matrix rows, breakdowns, stress and selection JSON, COMPLETE. Robustness directory contains seeded diagnostics, monthly selection, final decision, source/hash manifest and COMPLETE. Every ledger reconciles row count/net on reread; admission budgets and lot-grid assertions executed during writing. Incomplete retries have no COMPLETE and are not evidence.

## Verification

| Requirement | Executed evidence |
|---|---|
| Later results do not change development rank | `test_validation_results_cannot_change_development_ranking` |
| Missing stress rows cannot pass | `test_missing_cost_scenario_cannot_pass_selection` |
| DD failure cannot outrank passing policy | `test_drawdown_failure_cannot_outrank_passing_policy` |
| UTC signal-close session boundaries | `test_session_filter_uses_signal_close_and_excludes_cutoff` |
| Cache preserves fills, sizing and exact tick DD | `test_cache_preserves_account_and_tick_outcomes_across_costs` |
| Latency/adverse fill alters executable quote | `test_latency_and_slippage_change_executable_entry` |
| Mixed timestamp precision / seeded statistics | `test_robustness_accepts_mixed_timestamp_precision_and_repeats_seed` |
| Minimum-lot rejection and explicit risk cap | existing `tests.test_b1_d_ticks` |

Focused combined tests: **13 passed**. Full repository suite executed once before the last statistical timestamp regression was added: **512 passed**. This final additional regression passed in focused suite. MT5 capture observed exact target Demo verification and no order API. Final diff whitespace and compilation checks completed.

## Decision

**Choose none for execution.** Preserve highest-base-profit B1 contract as descriptive reference only; development-picked leader failed its later test. Active shortlist stays unqualified B1/D, with all results retained. A separate new-data experiment is required before any Demo automation decision; do not retune repeatedly on these same months and label that validation.
