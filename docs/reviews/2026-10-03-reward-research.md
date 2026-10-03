# Measured BUY/SELL reward continuation

All five catalogs completed1,350 evaluations,1,344 distinct versus12 preceding bidirectional catalogs/current cycles plus6 equivalent controls;0qualified. All8,130 fresh whole-result scenario repeats match. Larger full-period profits are not sufficient: original strict six comparisons remain unchanged. Actual45,671,201 Bid/Ask ticks and12,100 complete UTCM15 bars,2026-03-28 through before2026-09-28. No synthetic performance data, sealed holdout or runtime promotion.

Each candidate repeats the same full/first_half/second_half base/stress as trial30,200USD initial capital, fixed0.01, cap<=10%, no recovery. Some registered admission states reduce cap/daily limits; geometry states use existing non-ATR stops. Trial30 baseline and actual SELL-only Demo contract unchanged.

| Catalog | Evaluations | Fresh exact scenarios | Qualified |
| --- | ---: | ---: | ---: |
| Rounded-stop reward |594 |3570 |0 |
| Fixed UTC entry session |108 |654 |0 |
| Loss-cluster admission |324 |1950 |0 |
| Symmetric candle quality |108 |654 |0 |
| RSI/D48 stop geometry |216 |1302 |0 |

[Hashed index](2026-10-03-reward-research-index.json) links complete contracts, metrics, source/input/protocol/verdict/fresh-proof and scenario hashes. Frozen-source verification compares whole result including ledger/equity/all-tickDD; this is same-implementation reproduction, not independent algorithm correctness. Distinct accounting normalizes inactive protection activation when protectionoff; admission has6 equivalent controls. Controls match complete result excluding serialized rule metadata, not a claim of byte-identical JSON when inactive metadata differs. Counts are scoped to12 preceding bidirectional catalogs and current cycles, not all historical experiments.

## Diagnostic row: reward156, rejected

RSI BUY7/lower35/EMA50 + D48SELL, BUYpause5%, rounded-stop target1.35R, protectionoff. This row improves profit/WR/realizedRR in all six scenarios. Four DD comparisons fail, so no winner. It motivates admission/quality/geometry hypotheses, not selection by number of passing metrics.

| Window / cost | Net USD | WR | RR | DD | BUY / SELL |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full base |883.770 |54.61% |1.2726 |22.50% |23 /129 |
| Full stress |742.033 |53.42% |1.2641 |33.97% |17 /129 |
| First half base |476.661 |56.72% |1.2708 |22.50% |5 /62 |
| First half stress |398.600 |55.22% |1.2462 |33.97% |5 /62 |
| Second half base |370.605 |55.71% |1.2129 |34.45% |13 /57 |
| Second half stress |335.645 |54.29% |1.2338 |34.72% |13 /57 |

Trial30 fullbase net465.318/WR52.14%/RR1.1993/DD26.01%; stress361.397/WR50.72%/RR1.2013/DD29.44%. First-half DD baseline26.01/29.44%; second-half candidate must<=30% even though baseline32.93/33.34%. Thus reward156 cannot qualify despite substantial measured profit improvement. [Complete candidate/baseline metrics](2026-10-03-hybrid-reward-results.json).

## Admission progress, still rejected

Admission has12 paired full-window passes and12 paired first-half passes;6 contracts pass both windows, zero second-half passes. Trial219 (RSI7/lower35/EMA50BUY, D48SELL, BUYpause5%, target1.35R/off, staticcap10%, daily10%, one daily loss, all sessions) fullbase net866.671/WR56.83%/RR1.2140/DD22.47%; stress791.464/WR55.88%/RR1.2266/DD23.68%. It passes all original full and first-half comparisons including actual both-side trades. Second-half DD41.2837% base/34.9287% stress rejects it. This is measured partial progress, not superior-strategy qualification. [Complete metrics](2026-10-03-hybrid-reward-admission-results.json). All30 baseline scenario artifacts across five cycles also byte-identical to previously pinned trial30 baseline.

## Validation and review

Research CLI tests observedRED for missing admission/quality/geometry catalog, thenGREEN after implementation; literal rounded-stop1.25/1.35 BUY/SELL targets, UTC21entry rejection/next-daySELL and held-position21:01TP already covered. Public daily loss-count replay proves both-side blocking and UTCday reset. Existing cooldown/drawdown-step/geometry seams reused; no new runtime math.

Final full suite759tests passed757/skip2 in12.839seconds, after latest geometry catalog addition. Prior repeat also passed757/skip2. First run759 had1failure in existing webhook duplicate/restart test; payload timestamps regenerated from wall clock can differ across seconds. Isolated repeat passed, full repeat passed; no unrelated webhook code/test edited. This is a suspected timing-sensitive fixture issue, not a confirmed root cause or hidden clean first run. Focused63passed, mypy2research files/Ruff/scopedformat/whitespace passed.

| Requirement | Evidence |
| --- | --- |
| Actual measured comparison | Hashed raw-tick audit; six identical baseline/window/cost definitions; complete frozen-source fresh repeats |
| Actual BUY/SELL fills | Ledger-derived side counts; qualification rejects missing side in any case |
| Preserve risk | Fixed0.01, admission cap<=10%, stricter states never resize or clamp lots; public risk/daily/cooldown tests |
| Honest winner | No incomplete-prefix selection; original strict gates; rejected row not promoted |
| No-order diagnosis | [Read-only Wine history/quote audit](2026-10-03-trial30-no-order-audit.md) |

### Standards

Earlier594 review had zero hard findings. Separate reviewer continuations for new session work failed due usage limit; root performed fallback review of final scoped diff. No documented-standard breach found; existing catalog construction and source freeze maintained. Optional duplicated catalog field construction/EMA blocks deferred; no speculative abstraction or unrelated refactor. Independent Standards review unavailable for latest additions. Concurrent .gitignore/Makefile/status/operator changes excluded. Agreed review base develop=a24114097988e4b3669d48d6be19773c502c3924; incremental task start=e31a8e1, not a whole historical branch review claim.

### Spec

Earlier594 review had zero implementation findings; latest independent Spec continuation also failed usage limit. Root fallback checked registered contracts, actual replay math/UTC/risk/side gates, session exits, snapshot/source checks and metadata-normalized controls. No unresolved scoped implementation mismatch found. Requested superior BUY/SELL strategy outcome remains unmet; no profitability qualification or execution readiness inferred.

## Runtime and limits

Demo watcher still originalSELL-only trial30. [Current no-order audit](2026-10-03-trial30-no-order-audit.md): quote stale before signal evaluation; historical SELLs exist; two latest nominal risks exceed observed cap; no trial30-magic/prefix orders in retrieved window. Past guard history missing, so not all missed entries diagnosed. No forced order, freshness/risk gate bypass, policy timestamp refresh or bot restart.

Research assumes commission0, stress extraSpread0.20/slippage0.10, omits swap. Archived BUYswap_long-567.4points; freshOct2probe-513.2points, not swap-free. Reused discovery/halves are not untouched validation. Exact replay proves reproducibility only. No new Demo strategy can be implemented as superior before complete gates and separate independent/cost/forward evidence.

All five finite research and exact-verification processes completed; no hidden indefinite optimizer remains. Superior BUY/SELL strategy objective remains unachieved. Failed hypotheses and current runtime blocker recorded; no performance gates relaxed to manufacture success.
