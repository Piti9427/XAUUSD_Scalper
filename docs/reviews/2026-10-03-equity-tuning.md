# USD200 equity-sizing and causal M5 research

Implementation and measured research completed; requested superior strategy remains
UNMET. Research initialUSD200 per independent window, current-equity compounding,
owner-approved cap ceiling20%. Trial30 Demo contract unchanged fixed0.01/cap10%.

Qualification `profit_dd_v2`: every annualfull/half base/stress net>max(0,trial30),
DD<=trial30/30%, >=60full/20halves trades, actualBUY+SELL and risk<=20%. WR/RR
reported, not superiority gates. Legacy `strict_v1` preserved. No fabricated fees,
forced fills, top-ups or calendar-specific tuning. Cost validation INCONCLUSIVE:
commission0 assumed and swap omitted. No holdout access or Demo promotion.

| Stage | Evaluations | Exact fresh scenarios | Joint qualifiers |
| --- | ---: | ---: | ---: |
| Sizing/admission |60|366|0|
| Short BUY ATR |32|198|0|
| Corrected M5 intraday |64|390|0|
| Corrected M5 bounded24 |64|390|0|
| M5 BUY/M15 SELL hybrid |64|390|0|
| Hybrid SELL quality/risk |48|294|0|
| Directional BUY sizing |48|294|0|
| M5 SELL ATR reward |64|390|0|

444 parameter evaluations,2,712 exact fresh whole-result repeats (not444 independent hypotheses); initial128 M5 evaluations
are preserved SUPERSEDED after review correction and excluded above. Actual annual
archive104,133,248Bid/Ask ticks/23,230completeM15 and70,460completeM5. Dataset
SHA20882811cf0f2300ee38ccb4012995d65c3a894f52d4ae97dc91e0f2ae7883e2.

Why changes were needed: fixed0.01 trial30 loses7 first-half trades then admission
rejects further wide stops. Raising cap increases participation but excessive DD;
compounding raises net without reliable drawdown. Shorter BUY stops create more
entries but frequent RSI variants lose. M5 retests improve first-half participation,
but common SELL R-target loses second-half edge. Hybrid preserves M15 SELL geometry,
yet second-halfprofit/DD still misses. Lower shared risk caps suppress profitable
second-half SELL admission. Directional sizing/SELLATR reward also fail joint gates.

Concrete hybrid14: fullbase431.24/DD29.52%, fullstress460.86/DD30.90%; first-half
87.82/44.88 USD and DD28.89/29.82%; second-half504.03/400.04 USD and DD26.85/26.92%.
Trial30 second-half507.245/452.366USD, DD25.99/26.07%. Hybrid is NOT qualified.
No annual weighted score or merged reset equity hides half-year failures.

Implementation: lot floor/minimum/cost-inclusive risk/margin, per-position fee/PnL/BE,
optional directional overrides; causal M15availability/M5retouchTTL2/4; strict wrong-side
invalidation; SELL Bid->Ask stop geometry; M15only protection; actual-quoteintraday
20:30cutoff/20:45flatten and24hdeadline. M5 rejection events support monthlyside/reason
executionfunnel. Complete bar cache pins dataset/source/output SHA, missingM1 excludesM5.

Review against develop, Spec/Standards axes: two verified bugs fixed RED->GREEN
(boundaryequality cancellation andM5prior-day midnight lookahead), glossarypolicy
clarified; finalreview0openfindings. Publiccatalog smoke catches all444contract
constructors/rules/replay contracts; CLI initialization typo fixed before any inputs.
[Post-mortem](../post-mortem/2026-10-03-m5-retest-debug.md).

Validation finalsource: unittest792/790pass2skip19.864s; Rufffivefilespass;
scopedstrictmypy3filespass (`--check-untyped-defs --follow-imports skip`, imported
modules excluded). Defaultmypyalso passed earlier; broader importchecking exposes
pre-existingrun_strategy_campaign errors, notclaimedcleanrepositorytypecheck.
18legacy whole-result matches normalize only documented defaultRules metadata.
Actualboundedasync correctedM5freshrepeat twochildexit0/0,780exactscenarios.

[Hashed results and monthly funnel](2026-10-03-equity-tuning-results.json),
[Spec](../specs/2026-10-03-equity-sizing.md),
[legacy parity](2026-10-03-equity-sizing-legacy-parity.json),
[async proof](2026-10-03-equity-m5-supervision.json).
Versioned result audit records protocol/verdict/source hashes, per-scenario failure
reasons and actual monthly hybrid14 execution funnel. Next hypothesis must address
second-half SELL edge and cost-valid boundedholding without sacrificing first-half
participation; independent holdout remains sealed until a complete discovery winner.
