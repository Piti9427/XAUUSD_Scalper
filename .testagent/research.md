# Pure B1 target refactor research

- Target: `scripts/strategy.py` pure M15 detection, new tick replay caller, then live runner only after replay review.
- Existing reference: `run_b1_breakdown.py` uses prior-30 Donchian, RSI14 EWM span14, EMA50 EWM span50, ATR14 simple rolling mean, strict RSI 30–70.
- Archived +342%: `scripts/research/b1_hybrid_six_month.py` uses `b1_final.reference_bars()` with Wilder RSI buy <=75 / sell >=25 and no EMA50. Preserve its source and outputs.
- Convention: `unittest`; `tests/test_strategy.py` covers legacy strategy, `tests/test_b1_hybrid_six_month.py` covers replay engine.
- Acceptance: deterministic target signals on completed UTC bars, strict thresholds, no lookahead, shared signal caller for replay, preserved old results, risk and cost accounting, no broker/notification side effects.

## 2026-09-29 Pure B1 Shadow implementation

- Scope: read-only broker M15/tick capture, bar/index adapter, one shared Pure B1 decision, daily/exposure gates, append-only Shadow evidence.
- Pre-agreed seam from the approved plan: fake MT5 rates/ticks -> UTC adapter -> `pure_b1_bars` -> `check_fixed_lot_risk` -> JSONL; assert no `order_send` or Telegram.
- Existing helpers: `scripts/smc/broker_rates.py` returns RangeIndex; `scripts/strategy.py` requires UTC DatetimeIndex. `scripts/research/shadow_capture.py` captures bounded ticks with manifest. `scripts/ops/run_b1_d_wine.py` runs read-only scripts under Wine.
- Data contract: `CORE_STRATEGY.md`; archived input/source hashes in `data/b1_pure_target_replay_cost_gated_2026_09_29/contract.json`. Broker costs/fills remain unobserved.

## 2026-10-04 Reward156 paired tuning

# Reward156 paired tuning test research
Bounded sources: breakout_replay.py, new rollover model, new paired research harness.
Existing convention: unittest, synthetic UTC M15 and Bid/Ask arrays; no MT5 calls.
Requirements: identical data/account/costs for independent contracts; preserve trial30 and Reward156 logic; swap affects equity/admission; causal H4; reproducible outputs; unchanged defaults.
Existing tests: test_breakout_logic.py and test_reward156_strategy.py. Archived optional discovery helper exists; no installed generator agent available. Inline workflow.

## Profit/survival v2 (2026-10-04)
Focused extension targets: reward156_search policy/catalog/causal adapter, reward156_campaign checkpoints/rank/finalists, reward156_holdout pre-read lock; existing breakout replay covered by test_breakout_logic/test_reward156_tuning. New tests use deterministic UTC synthetic bars and temporary checkpoint directories. No external orders/notifiers in research imports.

## C22 frequency campaign (2026-10-06)

Bounded new research modules: c22_frequency adapter/policy/store/data/campaign.
Owner-preagreed TDD seams: adapter, qualification, monthly count, cost attribution,
resume. unittest deterministic UTC bar/tick fixtures, isolated temp outputs.
No optional generator agent installed; inline Research/Plan/Implement workflow.
Codegraph source lookup; existing breakout/Reward156 tests provide independent
canonical fill, BE, rollover, daily-state, fixed-lot and risk-cap regressions.
Spec/acceptance checklist: specs/c22-frequency-campaign.md. Existing Demo work
predates this task and stays excluded from its commit.

## SMC challenger implementation (2026-10-08)

# SMC challenger bounded test research

Scope: new signal, adapter and campaign modules only. Existing unittest/pandas/NumPy fixtures; no broker mocks inside economic logic. Public seams approved by owner instruction to implement the reviewed spec: causal frame, replay adapter, campaign CLI.

Acceptance checklist: UTC/coverage and causal session/pivot/CHoCH/FVG/retest timing; mirrored sides and setup expiry/dedup; quote-dependent SELL stop and cost-inclusive10% admission; mandatory modeled swap including calendar boundaries; full-result replay repeat, frozen comparator parity, manifests/resume/drift, output boundaries and descriptive status. Frozen C22/Trial30/pins unchanged. Full suite once at end.

Optional find-untested-sources, test-gap-analysis, assertion-quality tools/commands are unavailable (CLI/tool catalog checked); inline bounded discovery/quality review substitutes. No configured type checker in pyproject or available mypy/pyright command; syntax compilation and Ruff used, not claimed as type checking.

## C22 runtime corrections (2026-10-14)

Request: `$debug-mantra`, following C22 runtime scrutiny findings.

Scope: `Trial30DemoRunner` safety-close reconciliation/accounting and read-only
`scripts/ops/trial30_status.py` readiness reporting. Preserve C22/trial30 entry,
geometry, risk, daily baseline policy, frozen source pins, journal schema, and live
watcher state. Cost attestation is owner-reviewed; do not refresh its timestamp.

Existing conventions: unittest discovery under `tests`; public cycle fixtures in
`test_c22h4_demo.py` and `test_trial30_demo.py`; persistent temporary journals,
aware UTC clocks, broker mocks. No real MetaTrader5 initialization or sends.

Acceptance checklist:
- Confirmed partial safety close recovers only reconciled owned residual volume.
- Pending broker order or incomplete/mismatched ledger prevents resubmission.
- Timeout/placed/no response and legacy pending state never blindly retry.
- Restart retains request evidence; recovery emits no phantom FILLED event.
- Safety halt remains after closure; rejected close can be retried safely.
- Immediate and late safety closures use actual gross/cost/exit ledger values.
- Status separates execute mode from local cost readiness, even without signal.
- Default/explicit cost-policy source and expiry are visible without secrets.
- Existing source pins and C22/trial30 lifecycle/CLI behavior remain verified.

No named test-generation or gap-analysis tools are exposed in this environment;
the Research → Plan → Implement → assertion review workflow runs inline.
