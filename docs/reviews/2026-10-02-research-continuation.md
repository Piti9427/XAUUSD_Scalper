# Continued BUY/SELL research against trial30

No candidate qualifies. Seven additional preregistered cycles completed1,160 evaluations:1,144 new versus the five immediately preceding bidirectional catalogs,16 control repeats. All7,002 scenarios repeated exactly, including each baseline and complete ledger/equity/all-tick drawdown. Repetition proves reproducibility of the same implementation, not independent algorithm correctness, untouched validation or future profitability.

Actual input:45,671,201 archived Bid/Ask ticks;12,100 canonical complete UTC M15 bars,2026-03-28 through before2026-09-28. Initial capital200USD, fixed0.01, maxrisk10%, daily20%, no recovery. Synthetic unit fixtures are excluded from performance results. Baseline and candidate use identical prices, broker, windows and cost scenarios. Source snapshots preserve each cycle despite later additions to campaign code.

| Cycle | Evaluations | New | Controls | Exact repeated scenarios | Qualified |
| --- | ---: | ---: | ---: | ---: | ---: |
| Direction horizons / EMA trend |384 |376 |8 |2310 |0 |
| Horizon candle quality |128 |120 |8 |774 |0 |
| Prior-range compression |216 |216 |0 |1302 |0 |
| Rolling RSI price reversal |72 |72 |0 |438 |0 |
| Fixed RSI / D48 direction split |144 |144 |0 |870 |0 |
| RSI BUY drawdown admission |108 |108 |0 |654 |0 |
| Setup invalidation / stagnant exit |108 |108 |0 |654 |0 |

No cycle passes full, first-half or second-half paired gates. Each individual window pair requires profit/WR/realizedRR strictly above trial30, DD<=trial30 and<=30%, both executed sides, risk<=10%, >=60 full or20 half trades. No criterion relaxed. [Index and report hashes](2026-10-02-research-continuation-index.json) links per-cycle contracts, metrics, original source/input/protocol/verdict/proof and scenario hashes. Controls matched all96 full-result artifacts byte-for-byte with earlier outputs. Distinct counts are scoped to preceding five catalogs, not claimed unique across all historical project research.

## Measured promising row, rejected

Admission trial22: rolling RSI7/lower30/EMA50 BUY, unfiltered D48 SELL, BUYpause5%, trail1R, TP3ATR.

| Full scenario | Trial30 net | WR | DD | RR | Challenger net | WR | DD | RR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base |465.318 |52.14% |26.01% |1.1993 |575.878 |55.33% |24.11% |1.1002 |
| Stress |361.397 |50.72% |29.44% |1.2013 |543.836 |55.03% |24.71% |1.0944 |

Full has150/149 trades,11/9 BUY and139/140 SELL. Higher profit/WR and lower full DD are measured, but RR fails. Second half net190.143/162.105 and DD32.81%/35.79%, also fails30% ceiling. It is a rejected diagnostic example; no winner or deployment claim. [Full metrics/config](2026-10-02-hybrid-admission-results.json).

RSI-only trial30 has full net167.077/164.959, WR62.07%, DD18.78%/19.10%, but only29 trades, RR1.0812/1.0716 and second-half loss36.25/37.39 with zero SELL. Better isolated statistics cannot satisfy joint gates.

## Cost-path sensitivity

Horizon trial136 has base net-95.207 with9 trades and stress+1077.404 with248 trades. This is not subtraction of costs from identical trades: quotes, protection, risk admission and equity path are independently replayed. Both fail qualification. On2026-04-17T01:15Z, base admitted risk16.584 against equity166.241; stress equity165.783 admits at most16.5783, below estimated rounded ATR risk16.684 including adverse exit allowance. Stress skips this base losing trade and follows a different sequence. Base1039 versus stress139 risk rejections illustrate sensitivity, not superior robustness. Do not promote maximum stress profit.

Commission0 remains a declared Standard-account tariff assumption; swap is omitted in historical research. Fresh2026-10-02 Demo symbol has BUYswap_long-513.2 in points mode, SELLswap_short0. Historical/current tariff parity and overnight BUY costs require separate validation before any challenger runtime promotion. Reused discovery and all previously inspected halves are not untouched holdout. No sealed holdout prices opened.

## Validation and review

Full suite756 tests,754 passed/2 skipped,11.564s. Focused public campaign/replay43 passed; mypy, repository Ruff, scoped format, compile and diff whitespace passed. Global format issues previously documented are outside this scoped change. No dependencies changed. Concurrent uncommitted operator/status changes belong to another task and were excluded from research commits/review.

| Requirement | Evidence |
| --- | --- |
| “signal ทั้ง buy,sell” | `test_horizon_signals_execute_both_sides_without_future_bars`, `test_rsi_recross_executes_both_sides_after_warmup_without_future_data`, `test_hybrid_rsi_buy_preserves_parent_sell_and_parent_wins_conflict` |
| “ไม่ได้ make ขึ้นมาเอง” | Actual raw-input audit, all7,002 full-result repeat matches and hashed per-cycle reports; synthetic tests excluded from performance |
| “ต้องเทียบวัดผลกันได้จริง” | `test_both_sides_and_each_cost_scenario_must_improve_trial30`; same six baseline/scenario windows, strict measured gates |
| Causal filters and resume | `test_horizon_trend_warmup_and_opposite_trend_block_replay_entries`, `test_compression_uses_prior_range_and_prior_atr_at_exact_boundary`, `test_rsi_expiring_losses_without_price_reversal_cannot_open_trade`, `test_tuning_cli_freezes_catalog_budget_and_verifies_resumed_scenarios` |

### Standards

Zero hard violations or new unresolved findings. One optional possible Duplicated Code: EMA alignment blocks in horizon/oscillator paths. Deferred to avoid unrelated refactoring during frozen campaigns; public behavior tests cover both paths. Earlier stale SELL-D48 docstring corrected. Review scoped incremental research changes fromee345b4; agreed develop basea241140 remains, not a claim that entire historical branch was re-reviewed.

### Spec

Zero unresolved implementation findings. Preregistered catalogs, causality, fixed risk, anchors/conflict precedence, strict gates and frozen-source repetition reviewed. Requested superior strategy outcome remains unmet; this review does not establish performance qualification.

## Demo continuity and remaining work

Actual Demo remains SELL-only `RESEARCH-D48-SELL-BE1R-20261001-T030`. Fresh read-only Wine probe2026-10-02T06:07:58Z verifies target Demo/USD/hedging, equity200.07 and symbol/tick, no order API called. Reviewed [published Standard tariff](https://www.exness.com/standard-accounts/) again; atomically renewed existing cost attestation06:09:10Z after matching identity and fresh symbol. Economic assumptions unchanged, original attestation backed up locally; fresh probe hashed. Standard classification retained from prior evidence, not inferred from symbol_info. Watcher reloads policy; no restart or forced order.06:15:41Z execute=true/WAIT, heartbeat0.21s, active=null/safety_halt=null. This is watcher continuity, not proof of challenger readiness.

Research loops above finished after exact verification; no hidden perpetual optimizer remains. Goal of a superior BUY/SELL strategy is not achieved. Further research must introduce a defensible new hypothesis and eventually cost-complete independent/forward evidence; repeating failed contracts or selecting a profitable subperiod cannot establish the requested improvement.
