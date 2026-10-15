# Demo replacement scrutiny — 2026-10-04

Intent: identify a Reward156 research candidate worth testing on Demo as an alternative to current trial30, distinguishing discovery performance from executable broker lifecycle.

Recommendation: first candidate `variant_1af968e9ac6a26ea` (circuit22 + closedH4EMA200), according to frozen profit/survival ranking. If owner prioritizes DD<=35%, alternative `variant_a970d2864f1fade4` (fine6 + closedH4EMA200) has lower worst DD at lower worst discovery profit. Neither is a drop-in Demo replacement today.

Smaller path: retain authorized trial30, add candidate read-only Shadow parity first; reuse verified trial30 lifecycle safeguards through an explicit bidirectional adapter rather than deploying incomplete Reward156 runner. Trial30 contains SELL-specific assumptions, so copying or switching its detector alone is insufficient. Demo research testing can be authorized separately without declaring a candidate research-qualified; failure of profit/trade-count thresholds does not itself prove Demo trial should be prohibited.

## Measured candidate comparison

Continuous independent USD200 accounts, A Sep2024–Jun2025 and B Oct2025–Sep2026; same archived quotes, lot0.01, cap10%, base/stress, no-swap/current-spec swap.

| Candidate | Worst net across8 cells | Worst quoted-tick DD | A base/stress net with swap | B base/stress net with swap |
|---|---:|---:|---:|---:|
| circuit22 +H4EMA200 (`variant_1af968e9ac6a26ea`) | +29.74 | 35.60% | +37.06 /+29.74 | +186.93 /+292.53 |
| fine6 +H4EMA200 (`variant_a970d2864f1fade4`) | +16.59 | 29.39% | +23.92 /+16.59 | +310.53 /+233.35 |

Both are positive and beat trial30/original Reward156 in all8 discovery cells. Neither passes full v2 qualification: A32trades<60 and A profit<50; candidates have not received reset-half/additional-swap or sealed holdout validation. This table ranks discovery evidence, not future-profit guarantees. Source: `reward156-profit-survival-2026-10-04/results.json`, `one-factor-catalog.json`, `summary.md:21`, `summary.md:55`.

Original Reward156, H4EMA100/200 alone, circuit22/fine6 without H4 do not supply a stronger worst-case candidate under this paired campaign. Full original controls lose money in these continuous account paths; do not substitute favorable reset-half results or previous archive summaries.

## Blocker1 — Reward156 execute path calls nonexistent Journal methods

Path: `Reward156DemoRunner.cycle` -> `_cycle` -> broker identity/history/bars/signal -> cost/risk/margin/order_check -> `self.journal.claim_active(active)` -> AttributeError.

Evidence: `scripts/reward156/runner.py:272`, then `runner.py:281` calls `record_event`; imported `scripts/trial30/journal.py:30` exposes get/put/transition/event/flush/close, neither called method. Fake broker with valid policy and actual completed-bar SELL signal reaches order_check once, then BLOCKED/AttributeError; order_send count0. This is a current failure, not speculative deployment risk.

Suggested change: integrate existing durable Journal API with explicit write-ahead active/last-bar transaction and proven bidirectional execution tests; do not fix only method names and call runner ready, because blocker2 remains.

## Blocker2 — uncertain submission is incorrectly declared closed

`scripts/reward156/runner.py:297` accepts a position solely by ticket OR comment, without symbol/magic/direction/volume/fill-risk checks. With no matching positions, line304 clears active and returns CLOSED without using deals. A persisted SENDING claim plus empty positions/deals reproduces CLOSED and activeNone. Delayed broker evidence can lose unresolved intent and permit subsequent admission; current blocker1 prevents natural execute from reaching this latent path.

No corresponding filled risk validation, safety close, net/commission/swap close event or BE management exists in this reconciliation function. Candidate requires SELL BE1R, so the current function cannot preserve candidate strategy behavior either.

Contrast verified lifecycle: `scripts/trial30/runner.py:260` matches symbol/magic/comment; absence remains UNKNOWN unless completed deal ledger reconciles volume and costs; lines348–362 recalculate fill risk; lines407 onward manage closed-bar BE; journal.transition binds state and broker-confirmed event. SELL assumptions must be generalized explicitly for BUY.

Suggested change: retain uncertain active state, reconcile opening/closing deals by owned position identifier, enforce fill/volume/SL/TP/risk and safety-close invariants, then notify only broker-confirmed lifecycle events. [MetaQuotes return-code reference](https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes) distinguishes PLACED10008, DONE10009, DONE_PARTIAL10010 and TIMEOUT10012; submission status alone is not a reconciled position/close ledger.

## Major3 — winning research config is absent from executable Demo path

Current entrypoint is Makefile -> `scripts/ops/run_trial30_wine.py:28` -> `scripts/ops/mt5_wine_trial30.py:43` pinned trial30 config -> line100 Trial30DemoRunner. Passing current Reward156 config reproduces `snapshot_config_mismatch`, exit2 before MT5 initialize. No Reward156 Wine CLI appears in current scripts inventory.

`scripts/reward156/runner.py:92` invokes frozen RSI7/D48 detector; line155 invokes sharedSL2.5ATR/TP1.35R; lines127–148 apply BUYpause5%/daily20%. It has no candidate config parameter. Winning research path is `scripts/research/reward156_search.py:154` -> archived RSI14cross25/D96/SELL EMA50 -> closedH4EMA200 -> side-specific BUYSL1.5ATR/TP2R and SELLSL2.5ATR/TP3ATR/BE1R -> daily10%/one loss. Changing `config/reward156-demo.json` cannot transfer that behavior to either runner.

History seam also differs: Reward156 runner requests5000M1 (`runner.py:90`), at most20 completeH4. Research `closed_h4_ema` requires200 completeH4 (`reward156_tuning.py:60`), at least48,000 alignedM1 before additional prefix/continuity concerns. Actual333-M15 fixture yields zero non-null EMA200 values. Increasing count alone does not prove EMA seeding parity; use identical causal historical prefix/persisted indicator state, rejecting incomplete H4.

Suggested change: freeze candidate identity separately, share pure candidate detector/levels/circuits with offline replay, validate broker-M1/M15/H4 and EMA-prefix parity, then add opt-in CLI. Do not repurpose trial30 snapshot or silently bypass its config pins.

## Major4 — existing test/document readiness claim masks failure

`tests/test_reward156_demo.py:137` claims BUY-pause coverage but asserts only statusBLOCKED at line151. Its BrokerMock lacks terminal_info, so cycle stops in identity with AttributeError before signal/pause. Reproduced actual reason AttributeError. The other test only checks initialization/login/server. `CORE_STRATEGY.md:453`–454 says Demo Runner Ready; current trace/refutations do not support that claim. Research detector parity is separate from execution readiness.

Suggested change: correct readiness claim; strengthen tests to assert expected reason and actual BUY signal, and cover public-cycle SELL/BUY fill, rejected/partial/timeout, restart/UNKNOWN, post-fill risk safety close, BE, broker close net/swap, persisted one-loss daily circuit and outbox delivery. Require end-to-end real paths, not mocks that omit broker methods and pass because cycle blocks early.

## Checks executed

`.venv/bin/python -m unittest tests.test_reward156_demo tests.test_reward156_strategy tests.test_reward156_search tests.test_trial30_demo`:49tests/0.766s/OK, exit0. Passing existing tests does not falsify blockers above; explicit inline reproductions do expose them.

Read-only fake-broker probes observed:

```text
Reward156 valid broker/policy actual cycle: BLOCKED / AttributeError
order_check_count 1; order_send_count 0
Journal claim_active False; record_event False
SENDING + no positions/deals: CLOSED; active cleared
Existing BUY-pause fixture: BLOCKED / AttributeError
Reward156 config through trial30 CLI: snapshot_config_mismatch; exit2; initialize0
H4EMA200 on333 completed M15 bars:0 non-null values
```

No production code, active Demo process/config/journal, broker account or orders changed. No new backtest/holdout run. Raw campaign results remain frozen.

**Verdict: fix-then-ship to opt-in research Demo; candidate circuit22+H4EMA200 first. Biggest blocker: executable lifecycle neither runs successfully nor preserves broker-confirmed state and candidate logic. Keep existing authorized trial30 until those execution/parity gaps are resolved.**
