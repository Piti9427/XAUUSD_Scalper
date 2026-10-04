---
name: Reward156 paired config tuning
overview: Compare frozen trial30, original Reward156 and three research-only Reward156 candidates on identical archived market/account/cost environments; no Demo cutover.
todos:
  - id: scrutinize-contract
    content: Freeze paired environment, candidates, matrix, costs and decision rules after end-to-end review
    status: completed
  - id: harness-and-tests
    content: Implement config-driven paired harness, causal closed-H4 gate, equity-path swap and admission telemetry with regression tests
    status: completed
  - id: baseline-matrix
    content: Write original Reward156 versus trial30 matrix before evaluating tuning candidates
    status: completed
  - id: tuning-matrix
    content: Evaluate three frozen tuning candidates under identical conditions; verify full-result fresh repeats
    status: completed
  - id: record-verdict
    content: Write paired net/DD/WR/RR/trade/admission results and separate improvement from replacement qualification
    status: completed
  - id: sealed-holdout
    content: Cancelled — no candidate qualified; sealed Jul-Sep2025 remains unopened
    status: cancelled
  - id: review-and-commit
    content: Run repository tests and code-review, fix findings, commit only this work on current branch
    status: completed
isProject: false
---

# Reward156 paired config tuning — frozen implementation contract

## Intent and scope

Owner requests configuration tuning of Reward156 to outperform currently authorized Demo strategy `trial30`. Compare independent strategy/account simulations under identical market/account/cost environments. Strategy-specific entry, exit and protection remain distinct. Results can fail; no profitability guarantee and no result-driven expansion of this catalog.

Smallest complete solution: reuse `breakout_replay.replay`, existing `trial30_bars` / `reward156_bars` detectors and config files. Add one offline paired harness plus opt-in swap and admission telemetry. No replacement execution engine, no Demo runner/config change, no order_send, no notifications, no recovery, no risk-cap removal, no capital/lot substitution.

`main.py` is not current Demo path. Existing Demo is Makefile -> run_trial30_wine -> mt5_wine_trial30 -> trial30.runner -> journal/broker lifecycle. Offline harness terminates at research artifacts; no execution adapter.

## Scrutinize findings resolved in this contract

1. Swap cannot be subtracted only after replay. Existing close/advance/prepare_entry path lacks swap; opt-in accrual must affect quoted-tick equity/DD, settlement, BUY-pause, daily baseline and subsequent risk admission. Legacy default output must remain identical.
2. H4 150 bars cannot support EMA200 min_periods200. Freeze causal bar completeness, availability time and warmup below; future runner feed parity is separate work.
3. Improvement against Reward156 is not qualification against trial30. Freeze both verdicts plus tie-break and holdout rules before execution.
4. M15 rejection totals cannot identify blocked days. Opt-in timestamped admitted/rejected events plus position intervals are required; never claim permanent freeze outside observed sample.
5. Dataset A is ten discovery months, not a full year. `load_discovery` never accesses Jul-Sep2025 even when old scripts requested later ends. Validate manifests/coverage and label windows precisely.

## Frozen environments and matrix

All contracts receive SAME canonical completed UTC Bid M15 bars, SAME archived Bid/Ask tape, SAME broker-spec snapshot, SAME requested [start,end) window and SAME Costs/SwapPolicy within each cell. Each starts independent USD200 account with fixed0.01lot, cost-inclusive10% cap, UTC daily20% admission halt, single position. Never join Dataset A and B across sealed holdout.

- Dataset A: `data/b1_public_exness_2024_09_2025_09`, discovery [2024-09-01,2025-07-01). Continuous full10months; reset halves [Sep1,Feb1) and [Feb1,Jul1), each5months, explicitly not6months.
- Dataset B: `data/b1_public_exness_2025_10_2026_09`, discovery [2025-10-01,2026-10-01). Continuous12months; reset halves [Oct1,Apr1) and [Apr1,Oct1), each6months.
- Base: actual archived spread, slippage0, commission0 assumed.
- Stress: SAME quotes with total spread widened0.20USD/oz (half each side), adverse market-fill slippage0.10USD/oz, commission0 assumed. TP fills at target per existing replay contract.
- Each cell runs BOTH spread/slippage-only and current-spec swap sensitivity, identically for every strategy. Qualification uses swap sensitivity. No-swap path is a separately replayed counterfactual, not post-hoc subtraction.
- Swap sensitivity: points mode from hashed dataset broker metadata; point0.001, contract100, long-567.4points, short0 currently. UTC-midnight research rollover labelled by preceding business day; Wednesday's triple debit posts Thursday00:00UTC, Friday's single posts Saturday00:00, weekend days incur no separate debit. Positions entered exactly at posting time owe no prior-day debit. Accrual included at observed quote timestamps; no invented quotes. Historical broker rates, rollover time, DST, swap-free entitlement unverified; COST_INCONCLUSIVE remains.
- Full window retains account/risk/peak/day state throughout. Reset halves initialize account state anew but use causal indicator prefix from dataset beginning. Every position remaining at end liquidates at last available tick as END_OF_SAMPLE, uniformly; disclose forced exits.
- Validate requested bounds against discovery manifest, tape chronology and nonempty requested window; hash-checked loader verifies input artifacts. No data beyond discovery end may enter indicators or selection.

## Frozen strategy catalog (five contracts)

Config: `config/reward156-tuning.json`; original runtime files remain unchanged.

1. `trial30`: `trial30_bars`, D48SELL-only, ATR14SMA, SL2.5ATR, TP3ATR, BE activation1R; no BUY pause.
2. `reward156_original`: `reward156_bars`, rollingRSI7 crosses35 + positive delta + above/risingEMA50 BUY; D48SELL, conflictSELL precedence; SL2.5ATR, TP1.35 times rounded initial stop; protectionoff; BUYpause5% from equity peak.
3. `reward156_no_pause`: original Reward156, BUYpause0, no macro gate.
4. `reward156_h4_ema100`: no_pause + closed H4EMA100 direction gate.
5. `reward156_h4_ema200`: no_pause + closed H4EMA200 direction gate.

Risk/daily/lot identical for all. Defaults in Rules (daily40%, BE0.5R) MUST be overridden explicitly. Assert config pins against original JSON contracts to catch drift.

## Closed H4 contract

Resample canonical M15 into UTC bins [00,04),[04,08), etc. Eligible H4 requires all16 distinct aligned M15 bars. Incomplete/empty bucket has no usable EMA at that bucket's close. EMA on eligible H4 closes only: adjust=False, first eligible close seed, min_periods=span; missing buckets do not count toward warmup. Seed resets only at dataset start, never at account reset half.

Publish H4 result at bucket close timestamp, map to M15 decision timestamp=bar_open+15min. Availability <= decision timestamp; at04:00 use just-closed00:00H4, never04:00H4. This is closed-bar semantics equivalent to shift-before-mapping, without double shifting.

BUY allowed only M15close > availableEMA; SELL only M15close < availableEMA. Equality, NaN, insufficient history or latest incomplete H4 rejects macro signal. No access to future bars; test unchanged past outputs after appending/modifying future OHLC. Macro unavailable/warmup counts reported. Each strategy's inherent indicator warmup is part of its contract; whole requested calendar remains identical. No claim of MT5H4/live parity; do not implement150bar live feed.

## Metrics and observed blocking

Per cell: net before/after swap on modeled path, independently replayed no-swap net, final equity, quoted-tick maxDD, WR, realizedRR, profit factor, actual BUY/SELL counts, risk/cap maxima, first-reason rejection counts, macro blocked/unavailable counts, forcedEND_OF_SAMPLE exits, ledger and equity checkpoints.

Capture every replay admission/rejection with UTC timestamp, direction and whether position exists. Risk-blocked day means at least1 candidate signal event that day, every event rejected risk_cap, and no ledger position overlaps that UTC day. BUYpause checked before risk_cap; report first reason, never infer other counterfactual blockers.

Report blocked-day count, longest consecutive calendar-day blocked streak, and terminal inactivity interval. Observed terminal risk blockage: no admissions in final30calendar days, at least1 risk-blocked day there, no open position there, and every signal event there rejected risk_cap. No-signal tail is separate, not automatic risk freeze. No assertion of permanent future freeze.

## Frozen verdicts and selection

1. `improves_reward156`: on BOTH continuous datasets, BOTH base/stress with swap, candidate net > original Reward156 net, net >0, maxDD<=35%, admitted risk<=10%, no observed terminal risk blockage. This is research improvement only.
2. `qualifies_vs_trial30`: every full/reset-half base/stress swap cell net > max(0,trial30net), WR > trial30WR, realizedRR > trial30RR AND >1, maxDD<=35%, admitted risk<=10%, actualBUY>=1 AND SELL>=1. Full>=60trades, eachhalf>=10; no observed terminal risk blockage. Retains owner-approved relaxed research gates. Zero/null comparison metric fails closed.
3. Only candidates satisfying BOTH qualify for holdout. Rank by lowest worst continuous swapDD; tie highest minimum continuous swapnet; then catalog order. Never select by combined profits from independently reset accounts.
4. If none qualifies, record measured results and stop catalog. No automatic grid/family/RSI/RR expansion, no holdout opening and no Demo changes.

A/B already reused for selection: in-sample. Jul-Sep2025 stays sealed unless candidate qualifies above. Before opening, persist selected config/source/input hashes and verdict. One selected candidate, original Reward156 and trial30, same heldout data/environment; both base/stress and both cost views. Require same net/WR/RR/DD/risk/BUY+SELL gates vs trial30, >=10trades, positive net and improvement over original in BOTH swap scenarios. Failure stops; no retuning. Holdout historical, not prospective.

## Execution, evidence and acceptance

1. Freeze this plan/config before evaluating candidate outcomes.
2. Implement replay extensions and harness with deterministic seam tests. Defaults preserve legacy behavior/output; test against HEAD source control.
3. Write complete original Reward156/trial30 baseline matrix BEFORE tuning matrix. Same loader/environment objects feed every contract.
4. Evaluate three candidates; save per-cell atomic JSON checkpoints, ledgers/equity, hashes and contract. Fresh repeat compares COMPLETE result objects for every cell. Resume rejects changed contract/source/input hashes.
5. Generate JSON/CSV/Markdown report; verdicts computed by frozen predicates, disclose data/cost/live-parity limitations. Update CORE_STRATEGY.md research contract/results.
6. Conditional holdout only after selected candidate is locked. Future runner/shadow/cutover NOT included; separate owner instruction required.
7. Run narrow tests during development, full `python3 -m unittest discover -s tests` once at end; lint changed Python. No configured typechecker currently found: syntax compilation is reported separately, never called typechecking.
8. Use code-review against starting HEAD, resolve standards/spec findings; commit scoped files only on current branch. Do not include owner's unrelated webhook test or existing scratch/root-cause artifacts.
9. Mark todos completed only after observed artifacts/checks. Conditional holdout gets cancelled with reason if no candidate qualifies; never tick unexecuted work as passed.
