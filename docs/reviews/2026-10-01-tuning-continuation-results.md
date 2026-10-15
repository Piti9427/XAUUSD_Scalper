# Continued real-quote BUY/SELL tuning

**No qualified improved strategy found.** Implementation and measured tuning completed two additional catalogs:288 geometry/timing/exit evaluations (280 new,8 controls), then96 new admission contracts. Total384 evaluations,376 new versus previous three two-sided catalogs. All full/firsthalf/secondhalf base/stress evaluated. No gate relaxed, no rejected row promoted, running trial30 Demo unchanged.

Performance numbers use audited45,671,201 archived real Bid/Ask ticks and12,100 complete UTC M15 bars,2026-03-28 through before2026-09-28. Synthetic unit-test fixtures only validate calculations, not performance tables. Initial capital200USD, fixed0.01, maxrisk10%, daily20%, no recovery/reset. Replay is historical simulation, not actual Demo deal PnL.

| Family | Evaluations | Full passes | First-half passes | Second-half passes | All-window passes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stop geometry/reward |96 |0 |0 |1 |0 |
| Delayed entry/stop geometry |96 |0 |0 |0 |0 |
| Failed-breakout/stagnant exit |96 |0 |0 |0 |0 |
| Selective BUY/drawdown admission |96 |0 |0 |0 |0 |

Each scenario requires net/WR/RR strictly above trial30, DD<=trial30 and<=30%, risk<=10%, >=60 full/20 half trades, actual BUY and SELL. Same prices/broker/costs/windows for baseline and challenger. Higher full-period profit alone does not satisfy this agreed contract.

## Measured comparisons, rejected examples

| Full scenario | Trial30 net | Trial30 DD | Trial30 WR | Trial30 RR | Exit trial248 net | DD | WR | RR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base |$465.32 |26.01% |52.14% |1.1993 |$490.99 |30.87% |50.00% |1.3189 |
| Stress |$361.40 |29.44% |50.72% |1.2013 |$532.20 |32.19% |50.00% |1.3446 |

Trial248 uses confirm entry, prior-day BUY, ATR stop/TP6.25, trail1R. Second-half net-$64.62/-$30.87, DD45.53%/41.84%: rejected. It is a diagnostic row, not a winner.

Admission trial67 highest fullstress net, **rejected**: base+$712.72/DD33.49%/WR29.50%/RR3.3810,35BUY+104SELL; stress+$792.45/DD33.64%/WR32.86%/RR2.9565,36BUY+104SELL. Secondhalf base-$14.04/DD58.49%,stress+$115.41/DD40.87%. BUYpause10%, static cap, TP6.25, BE1R. Cost scenarios are independent replays: increased costs alter equity/admission and executed trade path; stress is not subtraction from same base trades, so stress net can exceed base. Both still fail DD/WR/half robustness.

Controlled stop comparison within geometry family: same other rules, base trial1 ATR30trades/net-$46.05/DD48.64%/470risk rejects; trial9 trigger200trades/net-$134.43/DD70.76%/261rejects; trial17 boundary324trades/net-$139.83/DD78.76%/118rejects. Narrower stop admits extra trades but worsens this experiment; more signals do not establish performance.

## Reproducibility

First cycle1734 scenarios (288*6 + baseline6) repeated against re-audited inputs and frozen source, exact whole-result equality including ledger/equity/all-tickDD. `FRESH_REPLAY_MATCH`. Control trial193..200 all48 scenario artifacts BYTE_IDENTICAL with earlier runs; repeats not counted as new contracts. [First-cycle metrics/hashes](2026-10-01-geometry-tuning-results.json).

Admission582 scenario repeat verification/export completed **FRESH_REPLAY_MATCH**. [Admission metrics/hashes](2026-10-01-admission-tuning-results.json). Total2316 exact comparisons; repeated verification not extra unique optimization. Original protocols/source snapshots/complete trade/equity artifacts retained in ignored `data/strategy_bidirectional_geometry_tuning_2026_10_01` and `data/strategy_bidirectional_admission_tuning_2026_10_01`. Snapshot/source changes cannot silently resume: protocol checks fail closed. Both exporters validated source snapshots/completion hashes and recomputed gate metadata; admission96 were confirmed distinct from previous four catalogs.

Commands actually executed: `scripts.research.bidirectional_campaign --catalog tuning/admission --output ...`, then same command `--resume`. Geometry export `/tmp/export_geometry_tuning.py` verified source/input/completion hashes, selection metadata and all8 control artifact sets; admission export `/tmp/export_admission_tuning.py` verified its582 comparisons/artifacts and96 new contracts. Logs `logs/bidirectional-geometry-tuning[-verification].log` and `logs/bidirectional-admission-tuning[-verification].log`. Current implementation commits6672551/321b9a1; starting7f8e88a; review base develop. Published JSON preserves metrics/config and original artifact hashes, not fabricated values.

## Standards

Zero documented-standard violations, zero unresolved heuristics. Fixed lot/risk/daily/UTC/no-recovery remain; no MT5/notification APIs introduced. Reviewers ran focused public tests without broker contact/campaign mutation.

## Spec

Zero unresolved findings. Preregistered catalogs and counts280new+8controls/96new confirmed; dynamic full-catalog winner gate, six-scenario comparisons and verification counters match specs. Historical winner would still require independent validation before runtime replacement.

| Requirement | Evidence |
| --- | --- |
| Literal stop/reward math; fixed lot/cap | `test_geometry_targets_use_frozen_stop_distance_with_fixed_lot` |
| Freeze288/96 budgets, partial result, fresh resume12 comparisons | `test_tuning_cli_freezes_catalog_budget_and_verifies_resumed_scenarios` |
| BUY pause retains SELL | `test_buy_pause_blocks_buy_under_peak_and_still_admits_sell` |
| Reduced drawdown cap rejects, never upsizes | `test_drawdown_steps_reject_high_risk_entry_after_two_losses` |
| Gate all costs/both sides; forged artifacts and incomplete winners rejected | Existing `test_both_sides_and_each_cost_scenario_must_improve_trial30` and `test_campaign_resume_rejects_changed_artifact_and_never_opens_broker` |
| Focused campaign/replay/selection suite |54 passed |
| Final full suite |748 tests,746 passed,2 skipped,10.961s |
| Mypy, repository Ruff, scoped format, compile, diff whitespace |Passed |

Global format failures11 pre-existing files remain documented outside this patch. No dependency changes. Replay model assumes commission0, declares stress extra spread0.20/slippage0.10USD/oz, omits overnight swap; fresh broker earlier showed nonzero BUY swap. Reused discovery is not untouched validation. Exact repeat proves reproducibility, not independent algorithm correctness or future profit. No sealed holdout consumed, no synthetic forced Demo order used.

Runtime remains trial30 SELL-only. Requested superior BUY/SELL execution strategy remains unmet because no candidate passes measured gates. These finite catalogs/verification stop after completion; Demo watcher continues independently. A new strategy must supply fresh edge and independent cost/forward evidence before replacing it.

Final runtime evidence2026-10-01T09:14:48Z: execute=true, WAIT/duplicate_bar, heartbeat0.28s, baseline200USD, active=null, safety_halt=null, broker_events empty. No forward broker fill/BE proof claimed.
