# Measured setting/config continuation

Ten valid campaigns completed1,284 evaluations:1,141 new contracts versus17 preceding valid bidirectional catalogs/current cycles,143 equivalent controls;0 jointly qualified candidates. All7,764 fresh whole-result scenario repeats match frozen initial results. Improvements in individual windows do not meet the owner's original all-window requirement. Demo remains authorized SELL-only trial30; no forced orders, risk-cap removal or runtime promotion.

## Data, gates and reproducibility

Actual45,671,201 archived Bid/Ask ticks and12,100 complete UTCM15 bars; full2026-03-28 through before2026-09-28, halves split2026-06-28. [Hashed index](2026-10-03-setting-tuning-index.json) contains input/tape/source/protocol/verdict/proof hashes, all candidate settings/metrics and scenario hashes. Sources/contracts were frozen before each evaluation; later changes do not replace earlier engines. Dual-frozen verifier loads exact hashed engine and campaign modules before importing research helpers. ATR432 verification completed under its original unchanged engine; subsequent campaigns use dual-frozen verification.

[Original ATR verifier](artifacts/2026-10-03-setting-tuning-atr-verifier.py.txt) retains the exact completed verifier hash; it checked current engine against frozen hash while running. After positional compatibility changes it cannot rerun against current engine without an isolated frozen-source environment. [Dual-frozen verifier](artifacts/2026-10-03-setting-tuning-verifier.py.txt) preserves the subsequent engine/main snapshot-loading method. Do not overwrite original evidence to imply a newer method produced the original proof.

Every full/first_half/second_half base/stress case must strictly exceed trial30 net profit, win rate and realizedRR; DD<=trial30 and<=30%; >=60 full/20 half executed trades, actual BUY+SELL, admitted risk<=10%. Fixed0.01 lot, no recovery/reset; baseline remains D48 SELL-only/SL2.5ATR/TP3ATR/BE1R/daily20%.

Base uses actual archived spread; stress additionally adds0.20USD/oz spread and0.10 slippage. Commission0 assumed and swap omitted, including BUY overnight costs. Reused discovery is not untouched validation, broker execution parity or future profitability. Each half independently starts at$200; full-run admission/equity path differs, so passing a reset half cannot be transplanted into full performance.

[Exporter audit copy](artifacts/2026-10-03-setting-tuning-exporter.py.txt) reproduces published JSON/index via `PYTHONPATH=. .venv/bin/python docs/reviews/artifacts/2026-10-03-setting-tuning-exporter.py.txt`. It verifies source snapshots, proof/artifact hashes, qualification and all143 control results. Controls and60 baseline scenarios match entire parsed results against earlier references except serialized rule metadata. Fresh verification additionally compares whole results including ledger/equity/all-tickDD; same-code reproduction is not an independent implementation oracle. Distinct counts describe parameter contracts, not independent statistical experiments or all historical research.

## Completed loops

| Catalog | Evaluated | New | Controls | Fresh scenarios | Paired passes full/first/second | Jointly qualified |
|---|---:|---:|---:|---:|---|---:|
| ATR stops1.5/2 |432|432|0|2598|0/0/0|0|
| Corrected SELL-parent24/48/96 |192|146|46|1158|6/6/0|0|
| SELL-parent EMAoff/50/200 |288|192|96|1734|8/10/0|0|
| D24/EMA50 symmetric candle/prior-day guards |24|24|0|150|0/0/0|0|
| D96/EMA200 reward1.40/1.45R |48|48|0|294|0/0/6|0|
| D96/EMA200 BUYpause2.5% |12|12|0|78|0/0/2|0|
| D24/D96 stricter risk admission |36|36|0|222|0/0/0|0|
| D96/EMA200 SL1.5/2ATR |72|72|0|438|0/0/0|0|
| D24 early BE/trail protection |144|144|0|870|0/0/0|0|
| D48/EMA50 reward/setup invalidation |36|35|1|222|3/6/0|0|

Paired pass means both base/stress pass every gate for that window. Later loops were separately preregistered after measured earlier results; they remain adaptive discovery. No prefix was declared winner. Ten workers and their verifiers finished; no indefinite worker is claimed.

## Measured progress and remaining failures

New corrected parent-horizon106: RSI BUY7/lower35/EMA50/pause5%, SELL24, SL2.5ATR/target1.35 rounded-stopR/off/daily10%/one losing trade.

| Case | Trial30 net / DD / WR / RR | New106 net / DD / WR / RR | Result |
|---|---|---|---|
| Full base |465.318 /26.01% /52.14% /1.1993|759.437 /23.47% /53.46% /1.2770|Pass|
| Full stress |361.397 /29.44% /50.72% /1.2013|766.849 /23.87% /53.85% /1.2691|Pass|
| First base |346.535 /26.01% /56.25% /1.1859|485.924 /23.47% /56.92% /1.3362|Pass|
| First stress |278.294 /29.44% /54.84% /1.1757|481.997 /23.87% /56.92% /1.3293|Pass|
| Second base |73.916 /32.93% /49.02% /1.2075|84.341 /39.96% /48.05% /1.1966|Fail DD/WR/RR|
| Second stress |12.167 /33.34% /46.00% /1.2040|130.474 /43.28% /50.00% /1.2093|Fail DD|

Full106 executes18BUY/141SELL base and17BUY/139SELL stress; first half has only1BUY in each scenario. Profit improvement is measured but second-half failure rejects it. This example is not a selected winner.

Trend137 (newD96/EMA200, RSI7/lower30/pause10%, target1.35R): fullbase net644.075/DD26.5353, second-halfDD28.9116/26.5561. FullbaseDD slightly exceeds trial3026.0086; second-halfRR1.1670/1.1776 falls below trial301.2075/1.2040. It motivated intermediate rewards, not qualification.

Fine-reward31 (newD96/EMA200, RSI7/lower35/pause5%, target1.45R/daily10%/loss-count disabled) passes both second-half cases: base net110.881/DD27.98%/WR51.61%/RR1.2625, stress74.954/DD28.17%/WR48.39%/RR1.3059; each6BUY/25SELL. Fullbase net350.438/DD40.33%, fullstress-15.214/DD37.31% fail. BUYpause2.5% follow-up yields2 second-half passes but0 joint passes. No calendar-based switching between these configurations is implemented.

Risk36 staticcap5%/drawdown_steps plus cooldown0/1/4 and daily loss-count0/1/2 yields0 paired-window passes. Maximum fullstress net across36 is only13.448USD; some full scenarios admit one trade. Lower fixed-lot admission suppresses exposure and profit without achieving the original joint target.

Owner continuation added72 D96/EMA200 SL1.5/2ATR settings:0paired/joint passes, maxfullstressnet80.736USD withDD43.05%; shortening stops did not improve this combination. D24 BE/trail144 also0paired/joint passes. D48/EMA50 setup-invalidation36 has3full/6first-half paired passes but0second-half; control1 exactly reproduces parent-trend178. New cooldown1/4 variants retain same second-halfDD41.28/34.93. Strict profit/WR/RR/DD still jointly fail.

Trend178 itself is new versus earlier valid catalogs: fullbase864.808/DD19.6391/WR56.93%/RR1.2211, stress789.719/DD19.8149/WR55.97%/RR1.2340;33BUY/104SELL base,30BUY/104SELL stress. First-half paired gates pass, second-halfDD41.2837/34.9287 and baseRR1.1977 fail. Higher fullprofit/lowerDD cannot authorize promotion when independently reset half tests fail.

## Correctness fix and superseded evidence

Review found SELL24 accidentally inheriting D48 upper-anchor warmup while only lower anchor changed. Replay validates both anchors, so natural25-bar public regression reproduced missing SELL24. Fix recomputes both prior high/low with chosen horizon, shifted1. RSI BUY independently overrides both anchors with trigger close. [Correction record](2026-10-03-parent-horizon-review-correction.json) marks initial192 run `SUPERSEDED_IMPLEMENTATION_MISMATCH`, qualification-ineligible; preserves original hashes/artifacts. Corrected192 fully rerun and repeated. Archive metrics happen to remain unchanged, while all1158 complete JSON artifacts differ in rule order/inactive anchor metadata; no fabricated PnL correction claim.

`stop_atr` appended to Rules fields to preserve existing18 positional arguments; regression reproduced initial compatibility failure, then fixed. New stop multipliers1.5/2/default2.5 and rewards1.40/1.45 are research-only; target rounding/risk/protection formulas unchanged. Public replay tests literal two-side prices, fixedlot and cap rejection. Demo SL/target settings remain pinned.

## Current Demo observation

[Read-only runtime snapshot](2026-10-03-setting-tuning-runtime-status.json) shows execute=true, fresh heartbeat, `BLOCKED/quote_stale`, active/halt null and no persisted broker events. Follow-up status at2026-10-03T06:28:46Z confirms same blocker, heartbeat0.18s. Quote guard runs before signal detection; tuning cannot make stale prices executable. [Earlier read-only Wine audit](2026-10-03-trial30-no-order-audit.md) confirmed exact configured Demo, latest returned tickOct2 20:57:59.953Z, zero trial30-magic orders in retrieved history and four historical SELL detections. Prior missed-entry guard history is incomplete; current stale quote does not explain every historical missed entry. Local cost-policy validator rejects the stored policy as invalid_or_stale after expiry2026-10-03T06:09:10Z (13:09ICT), even when validating against its own stored fingerprint; live account binding was not reverified in this check. This is a further admission prerequisite after quote/data/signal checks, not the current persisted quote_stale reason. Renew only after fresh identity/spec/tariff evidence; no timestamp-only renewal. No Wine write/order call or bot restart in this task.

## Validation

Focused70 tests passed. Final `.venv/bin/python -m unittest discover -s tests`:766 tests,764 passed/2 skips,40.765s, exit0. Mypy2 research files, Ruff check/format3 changed code files and whitespace checks pass. No connector changes requiring new MT5 smoke. Existing two platform/dependency skips do not prove broker execution parity.

Exact tests: `test_configured_atr_stop_changes_both_orders_without_resizing_lot`, `test_tighter_atr_config_still_rejects_over_cap_without_lot_clamping`, `test_existing_positional_rules_keep_default_atr_stop_and_target`, `test_parent_sell_24_executes_after_24_natural_bars_before_48`, `test_rsi_buy_with_parent_horizon_uses_prior_lows_and_defers_sell`, `test_parent_sell_trend_filters_countertrend_without_blocking_bearish_entry`, `test_rsi_buy_executes_before_parent_ema200_and_horizon_warmup`, `test_intermediate_reward_uses_rounded_stop_for_both_directions`, `test_tuning_cli_freezes_catalog_budget_and_verifies_resumed_scenarios`. Fixtures are deterministic unit tests; reported performance comes from actual archive, not fixtures.

Agreed review reference develop=a24114097988e4b3669d48d6be19773c502c3924; this task incremental scope starts10aa413. Operator/status changes excluded. Focused reviewers continued both axes for horizon/trend/quality/fine reward/pause/risk/ATR/protection/invalidation. No claim of a new whole-branch audit of unrelated historical commits.

## Standards

Reviewer:0 hard breaches;0 new substantive smells after closing inherited-anchor finding. Fixedlot/cap, causal timestamps, research-only boundary and CORE/spec consistency verified. Existing optional EMA duplication remains deferred. Final shared builder preserves fine48 product order/bounds; source review did not independently rerun archive.

## Spec

Reviewer:0 remaining findings after closing SELL24 warmup issue. Trend filter strict close<EMA/EMA<EMA4barsago, SELL-only application and independent BUY warmup match spec. Ten catalogs/budgets/settings, frozen fine48 identity, gates and unchanged Demo contract verified; campaign26 tests independently passed. Qualification depends on completed measured proofs above.

Standards0 remaining; Spec0 remaining. Superior BUY/SELL outcome remains unmet; no new Demo promotion.
