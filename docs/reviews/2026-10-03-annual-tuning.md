# Actual annual BUY/SELL research verdict

648 parameter evaluations across14 completed annual catalogs, **0 jointly qualified strategies**. All3,972 frozen fresh whole-result scenarios match original measured outputs. Additional optimized control repeats150 cases and matches the150 original outputs exactly; adds0 strategy settings. These are actual archived Bid/Ask replays. Python speed improvement is verified; superior strategy under all approved gates remains unmet.

## Actual data and frozen comparison

2025-10-01 inclusive through2026-10-01 exclusive:365calendar days,12audited nonempty public Exness XAUUSDm months,104,133,248ticks and23,230complete UTCBidM15 assembled from all15M1. No forward-filled or manufactured prices. Sealed Jul–Sep2025 validation files untouched. Annual2026 overlaps reused discovery; adaptive tuning is not independent validation or target-Demo parity. Broker specifications remain research assumptions, fixed0.01/leverage1000. Commission0 assumed, swap omitted. Base uses actual archived spread; stress adds0.20spread/0.10adverse market-fill slippage.

Full window begins$200. First halfOct1–Apr1 and secondApr1–Oct1 each independently begin$200. Baseline trial30: D48SELL/SL2.5ATR/TP3ATR/BE1R/daily20%/fixed0.01/10%cap. Each full/half base/stress case requires positive net strictly higher than same-window baseline, WR/realizedRR strictly higher than baseline; candidateRR>1; DD<=baseline and<=30%; admittedrisk<=10%; actualBUY+SELL; >=60full/20half trades. Owner explicitly approved all-loss baselineRRreference0 only when actual negative-net ledger count equalspositive trade count, WR0/netnegative. Measured baselineRR remainsNone. Empty/mixed/flat/undocumented-loss baselines reject. Other gates unchanged.

| Window/cost | Baseline net USD | DD% | WR% | Measured RR | Trades |
|---|---:|---:|---:|---|---:|
| Full base |-90.710|47.7851|0|undefined, approvedreference0|7SELL losses|
| Full stress |-91.817|48.2398|0|undefined, approvedreference0|7SELL losses|
| First base |-90.710|47.7851|0|undefined, approvedreference0|7SELL losses|
| First stress |-91.817|48.2398|0|undefined, approvedreference0|7SELL losses|
| Second base |507.245|25.9878|53.0612|1.17015|147SELL|
| Second stress |452.366|26.0663|52.3810|1.16444|147SELL|

Full baseline loses early, then591detections rejected by cost-risk cap; reset second-half capital follows a different admission path. Never combine independently reset halves into full-year capital, or compare annual candidate profit only with old six-month dollars.

## Completed catalogs and actual partial passes

| Annual catalog | Evaluations | Exact fresh scenarios | Full paired passes | First paired passes | Second paired passes | Joint qualifiers |
|---|---:|---:|---:|---:|---:|---:|
| Parent invalidation |36|222|0|0|3|0|
| Parent reward fine |48|294|0|0|0|0|
| Parent ATR |72|438|0|0|0|0|
| Corrected symmetric breakout |36|222|0|0|0|0|
| Risk admission |36|222|0|4|0|0|
| Confirm/retest |48|294|0|0|0|0|
| Hybrid without BUY pause |96|582|1|14|0|0|
| Fixed UTC entry windows |36|222|0|0|0|0|
| Separate BUY exits/parent SELL |48|294|0|0|1|0|
| Separate exits/SELL trend/risk |48|294|0|0|0|0|
| Separate exits/daily circuit |24|150|3|0|0|0|
| Separate exits/BUY admission fine |24|150|3|0|1|0|
| Faster breakout/candle quality |72|438|0|0|0|0|
| Short SELL stop/larger SELL reward |24|150|0|0|0|0|

Initial192 counts use [separate actual-ledger approved requalification](2026-10-03-annual-approved-requalification.json), including3second-half paired passes for parentinvalidation, while retaining0joint qualifiers. These evaluations include reused contracts and equivalent controls; not648 novel or statistically independent strategies. Catalogs frozen before replay; incomplete prefixes never winners. All finite annual workers/verifiers complete.

[Final measured results](2026-10-03-annual-final-results.json) publish every setting, full/half/base/stress metric, protocol/source/dataset/verdict/scenario hashes and completed proof hashes. [Original192 publication](2026-10-03-annual-results.json) and [intermediate552 publication](2026-10-03-annual-approved-results.json) remain historical evidence. [Final exporter](artifacts/2026-10-03-annual-final-exporter.py.txt) verifies completed proofs/source snapshots, baseline entire-result parity and approved qualification against measured outputs. Raw quotes and complete ledgers remain under listed local`data/strategy_annual_*` roots; large archives/raw directories intentionally excluded from commit. [Frozen versions](artifacts/annual-snapshots/index.json) preserve every source contract used.

| Actual selected partial result | Full base net / DD / WR / RR | Full stress net / DD / WR / RR | Remaining fail |
|---|---|---|---|
| Hybrid unpaused28 |124.452 /22.6045% /50% /1.21127|104.875 /21.4179% /51.2195% /1.15404|Full and first paired pass; second profits102.966/103.635 and WR51.02/50% below baseline. |
| Directional circuit22; fine4 equivalent |533.916 /24.4878% /54.955% /1.22426|512.056 /24.7161% /53.636% /1.27751|Full paired pass; first only12trades below20 and net-12.561/-13.083; second stress429.542 below452.366baseline. |
| Directional fine6 |237.663 /37.4419% /51.685% /1.21388|161.320 /33.1820% /50% /1.21472|Second paired pass521.573/457.046profits andDD22.67/23.15%; fullDD>30, first12trades and net-15.268/-16.063. |

Circuit22 settings: BUY RSI14/lower25/EMA50, BUY SL1.5ATR/target2R/off; SELL prior-low96/EMA50/SL2.5ATR/TP3ATR/BE1R; fixed0.01/static10/daily10%/oneUTC loss/noBUYpause. Fine6: sameBUY butSL1ATR, SELL96/EMA200, otherwise samecircuit. Unpaused28: BUY RSI7/lower35/EMA50 + SELL24/EMA200, commonSL1.5ATR/target1.35R/off/drawdown_stepsmax10/daily10/oneUTC loss. They are different fixed strategies, never stitched by calendar to manufacture a winner.

Highest initial fullbase profit symmetric17 net1,057.245/DD46.50%, stress51.309/DD65.63%, fails. New fast-quality lowest fullbaseDD41.17%; short-SELL lowest36.70%; both fail30%. Profits, lower DD or one passing window alone do not establish requested superiority.

## Diagnosis and implementation fixes

One-year CLI coverage gate fixes prior184-day archive gap: verifies duration, ordered/nonempty actual monthly tick/bar counts and freezes annual requirement for resume. Public CLI regression rejects short/missing/count mismatch before scenarios.

RealBE config defect: newly documented1R inherited0.5R default. Explicit1.0 fixed, public regression RED→GREEN. Initial10results preserved [superseded](2026-10-03-annual-be-correction.json), excluded from648count; corrected36 rerun/repeated. New short-SELL BE0.5R explicitly intentional, distinct contract.

Owner-approved RR definition implemented with actual ledger loss count; synthetic fixture probes are comparator tests only. Original192 ledgers/proofs untouched. New optional BUY exits append to`Rules` and defaultinherit, retain SELL/default behavior and shared quote/cost/rounded-stop risk math. Fixed0.01 over-cap orders reject, never resize. BUY-only1ATR extension is research-scoped and regression verifies fee-inclusive rejection.

[Python performance evidence](2026-10-03-replay-performance.md): cProfile/tracemalloc first, then no zero-spread quote copies,100k overlapping validation chunks, vectorized UTC completed-bar quote indices. Five alternating paired repetitions on actual full-year cases show1.43–6.15x replay speedup, exact ledger/equity/DD match. Base allocation peak2,486MiB→9–10MiB; stress retains adjusted arrays and peak1,599MiB. Allocation is not entire resident RAM. [150case optimized-control parity](2026-10-03-optimized-replay-parity.json) verifies all24fine settings+baseline exactly, no extra strategycount.

Async supervises two isolated CPU processes, preserves fully synchronous replay. Review reproduced protocol-before-snapshot readiness race in actual verifier. Original executed supervisor/proofs preserved; v2 waits all frozen source hashes before verifier launch,120sstartup/7200schild bounds, cancellation/failure cleanup. Missing/partial snapshot, timeout and failure self-tests pass; actual optimized pipeline child exits0/0. No async MT5/runtime migration.

[Independent raw-quote arithmetic proofs](2026-10-03-annual-independent-arithmetic.json) check90scenario evaluations across baseline/selected controls: final balance, all-tickDD and selected cost-inclusive risk/admission caps match. Checks share same input feed/spec assumptions, are not independent signal/broker validation. See original/publication proofs and actual `ledger-oracle.json` in parent-invalidation, corrected-symmetric, risk, directional, hybrid-unpaused and directional-fine roots.

[Experiment ledger](2026-10-03-annual-experiment-ledger.json), [post-mortem](../post-mortem/2026-10-03-annual-research-debug.md) and immutable executed artifacts cross-reference repro, debugger path, hypotheses, supersession, real-data runs, arithmetic disproof, performance measurements and remaining red goal.

## Requirement and validation evidence

| Owner requirement | Executed evidence / status |
|---|---|
| “backtest ย้อนหลัง 1 ปี” |365days/12realmonths/104,133,248ticks; annualguard/resume tests pass. Synthetic fixtures validate contract only, never used for performance. |
| “ปรับแก้ไขแล้ว loop หาให้เจอ” |Coverage/BE/RRdefinition/supervisor race fixed;648actualevaluations,3,972originalfresh repeats+150optimized repeats complete. Search goal still unmet. |
| “ต้องได้ประสิทธิ์ที่ดีกว่าผผลลัพเดิม” |0jointly qualified; passing full or half results published with specific remainingfail, no fabricated winner or relaxed other gates. |
| `$python-performance-optimization $async-python-patterns` |Actual profiles, alternating paired benchmark, boundedprocess async, readiness/cancellation/error checks and150exactresult parity. |

Final fullsuite776tests:774pass/2skips,14.667s exit0. Ruffcheck/format four changedcode/testfiles, whitespacecheck and regular mypy two researchfiles with`--ignore-missing-imports` pass. Plain mypy previously reported missing external pandas/pandas_ta stubs; this is not strict whole-project typing. No connector/credential/timeframe changes; no new MT5 smoke or order sent.

## Standards

0remaining hard breaches;0actionable smells. BE default and snapshot readiness defects reproduced/fixed. Source/default/Sell/risk/causalUTC compatibility reviewed. Reviewers independently executed focused tests; checked originaldirectional48 freeze equality,36synthetic performance-parity cases and150actual parity artifact hashes. No independent certification of future financial performance.

## Spec

0remaining implementation defects. Annual requirements, approved RR policy, explicit grids and performance semantics match code. Superior-strategy requirement remains unmet. Reviewbase develop=a24114097988e4b3669d48d6be19773c502c3924, incremental scope starts0068121; concurrentoperator Makefile/.gitignore/status/ops changes excluded.

Demo strategy selection unchanged: authorized SELL-onlytrial30. No annual BUY/SELL strategy promoted, no recovery, forced order, removedcap or current live broker parity claim. Research checkpoint complete; requested superior strategy not yet found.
