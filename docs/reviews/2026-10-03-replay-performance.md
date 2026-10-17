# Measured annual replay performance

Profile-guided optimization speeds actual annual replay while preserving full frozen results. CPU replay remains synchronous; async supervision waits for isolated worker/verifier processes, bounds concurrency to two, propagates errors and reaps children on timeout/cancellation. No MT5, order, strategy selection, risk cap or fee formula migration.

## Actual inputs and measured evidence

Same audited2025-10-01–2026-10-01 public XAUUSDm dataset:104,133,248 actual Bid/Ask ticks,23,230 completed UTCM15 bars. [Before profile](2026-10-03-replay-profile-before.json), [after profile](2026-10-03-replay-profile-after.json) use cProfile/tracemalloc and assert entire saved results, including ledger/equity/DD/rejections. Original profiling ran alongside ongoing research workers; use [alternating paired benchmark](2026-10-03-replay-paired-benchmark.json) for comparative timing: five timed repetitions per engine per case, alternating old/new order after both warmups.

| Actual full-year case | Old median seconds | Optimized median seconds | Paired speedup | Old traced allocation peak MiB | Optimized peak MiB |
|---|---:|---:|---:|---:|---:|
| Trial30 baseline, base |1.1123|0.1808|6.15x|2,486.14|9.35|
| Directional circuit22, base |0.8386|0.5846|1.43x|2,486.14|10.13|
| Directional circuit22, stress |1.5761|0.6787|2.32x|2,486.14|1,599.16|

Single host, warm pages; no universal speed guarantee. Timings include complete-result comparison, exclude archive acquisition/auditing and output serialization. Tracemalloc captures allocations, excludes file-backed mapped input resident pages; these are not total process RAM claims. Stress still creates adjusted Bid/Ask arrays, so its allocation remains high. Base no longer copies both104Mtick quote arrays. No cache skips input audits or validation.

## Mechanism and regression

cProfile identified full-window array-copy/validation costs plus23,230 scalar quote searches. Replay now reuses floating input views when extra spread is zero; non-floating and stressed inputs retain original arithmetic. Quote validation uses100k chunks with one timestamp overlap, rejecting cross-chunk chronology corruption, NaN and crossed quotes. Completed UTCbar epoch-ms stamps enter one vectorized search; duplicate timestamp priority, first available quote and end-exclusive window preserved. Held-position100k chunks and checkpoint/extrema compression unchanged, so ledger/equity and all-tickDD remain byte-value comparable.

Public `test_zero_spread_replay_bounds_allocation_and_checks_chunk_boundaries`: original peak25,045,773bytes for1Mticks fails allocation guard; optimized passes below6MiB and rejects corruption at chunk boundary. Initial4MiB probe was too low for existing held-position100k arrays (optimized4,376,103bytes); final6MiB budget accommodates unchanged held buffers, while original25MB still fails. This is implementation memory behavior, not simulated financial performance.

[Optimized frozen-control comparison](2026-10-03-optimized-replay-parity.json): all150 complete scenarios for baseline+24 original annual_directional_fine settings match optimized engine exactly, across full/two independently reset halves and base/stress. New control adds0strategy settings. Its frozen fresh verifier independently repeats150 cases. Reviewer also compared36 synthetic dtype/side/cost/entry-mode scenarios with old engine, excluding no fields since performance patch changes none.

## Async lifecycle and readiness fix

[Original supervisor](artifacts/2026-10-03-annual-async-supervisor.py.txt) successfully completed originalfine24, two child exits0. Review then found real next-run race: `protocol.json` published before source snapshots, while verifier immediately hashes those snapshots. Actual verifier reproduced FileNotFoundError with present protocol and absent snapshot. Original executed source/proofs preserved.

[Corrected supervisor v2](artifacts/2026-10-03-annual-async-supervisor-v2.py.txt) waits for every frozen source hash to match, using `asyncio.to_thread` for file checks and nonblocking0.1s waits with120s startup deadline. Each worker has7200s timeout; finally terminates/waits then kills/reaps after5s if necessary. Sibling tasks cancelled/awaited after errors. Self-tests verify timeout/error propagation and missing/partial snapshot blocking. Actual optimized24 pipeline completed two child exits0 in74.10s; source/protocol/proof hashes preserved in parity report. This duration is observed pipeline timing, not controlled attribution of speedup to async.

Public research rules remain fixed0.01/max10% risk, no recovery and UTC. Profitability qualification remains separate from Python throughput improvement; no research strategy deployed to Demo by this change.
