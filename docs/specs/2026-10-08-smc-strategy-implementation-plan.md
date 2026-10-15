# SMC challenger implementation plan — revised 2026-10-08

Status: proposed research design; no implementation, economic result, or Demo authorization.
Implementation follow-up: owner requested implementation after this review. Prototype `smc_m15_v1` / contract `dd80c871955d7422` implemented, tested and evaluated; [implementation/evidence report](../reviews/2026-10-08-smc-challenger-implementation.md). The design record below remains the original reviewed proposal. No strategy selection or Demo authorization follows from implementation.
Supersedes the technical recommendations in the Antigravity plan at
`/Users/nopparuj/.gemini/antigravity-cli/brain/1ae3cc1d-25d1-4117-a5c5-0608b393cccb/smc_strategy_implementation_plan.md`.
Original remains preserved. Review: [findings](../reviews/2026-10-08-smc-and-unified-plans-scrutinize.md).
Companion: [shared infrastructure plan](2026-10-08-unified-core-and-smc-refactor-plan.md).

## Intent and smaller alternative

Test whether a standalone causal SMC challenger improves cost-inclusive return and admitted trade frequency against frozen C22H4 on identical inputs.
Start with one research adapter using existing tick replay, swap calendar and input manifests. Do not couple research to Demo gate changes or create a second sender.
Modes A/B in the original plan become separate future research contracts: combining signals changes arbitration and equity path; filtering C22 changes its signal and exits. Neither modifies frozen C22H4.

## Scope and proposed phase-one contract

The following values are explicit design recommendations, not owner-approved strategy selection. Freeze them in a versioned contract before an economic run. A material change creates a new contract, never edits a completed result.

| Field | Proposed phase-one value |
| --- | --- |
| Strategy | Standalone SMC, research only |
| Signal bars | UTC Bid M15, assembled from all 15 distinct M1 minutes |
| Macro gate | Completed H4 EMA200; reuse canonical calculation and warmup |
| Equity and sizing | USD200 once per scenario; fixed0.01 lot; single position |
| Entry admission | Initial SL risk including modeled adverse entry, exit slippage and commission <=10% current equity; reject, never increase lot |
| Daily circuit |10% UTC equity-loss halt; one losing completed exit per UTC day; no cooldown |
| Pools | Completed Asian00:00–07:00UTC; previous available completed trading day high/low; London deferred |
| Setup | Wick sweep -> protected-swing CHoCH with displacement -> FVG formation -> later closed-bar retest |
| Displacement and gap | Body/range>=0.45; gap>=USD0.30/oz |
| Timing | Sweep-to-CHoCH:1–8 complete M15 bars; FVG third candle:next complete bar after CHoCH; retest:1–4 bars after FVG publication |
| Stop and target | Sweep wick beyond one broker tick; executable-side geometry specified below; fixed2R after grid rounding |
| Management | No break-even, trailing, recovery or pending orders in phase one |
| Views | Base+modeled swap and stress+modeled swap only |

Frequency is a measured output, not a reason to weaken risk controls. Daily equity baseline uses the existing offline replay policy, not C22's process-restart latch; label that difference explicitly. Broker parity is not inferred.

## Causal signal contract

1. Accept ordered unique timezone-aware UTC bar-open timestamps. Reject naive timestamps, conflicting overlaps and invalid OHLC. Never fill a missing minute. Feed detector only bars whose close is <=decision time.
2. H4 is published at its close only from16 valid M15 bars. Missing macro/warmup blocks signal. Retain full indicator prefix at evaluation boundaries.
3. Asian pool is published at07:00UTC only after all28 M15 bars exist. Prior-day pools use last available completed UTC trading day before current day; record that date. Pin an explicit market-session/gap calendar for deciding day completeness before running. Missing coverage makes that pool unavailable, never substitutes another pool. This calendar is a prerequisite, not a profitability assumption inferred from data.
4. Five-bar pivots at index i become available at close of i+2. When calling legacy helpers, pass explicit close timestamps: `pivot_confirmation_time` returns its supplied timestamp without adding bar duration. Ignore unconfirmed pivots; BOS and CHoCH are distinct state transitions. CHoCH must break the protected swing against existing bias, not any recent high/low.
5. BUY sweeps a known low with low<level and close>=level; SELL mirrors high>level and close<=level. Both-side sweep is rejected. Invalidate a pending setup if a later close breaks its sweep wick; latest valid sweep replaces earlier pending setup. Do not retroactively attach a newly published pool to an old sweep.
6. CHoCH candle requires directional body and displacement threshold. FVG uses three consecutive valid M15 bars, CHoCH as middle candle; third candle must close before publication. BUY gap=[first.high,third.low]; SELL gap=[third.high,first.low]. Reject session-gap triples. BOS is recorded diagnostically, not accepted as CHoCH fallback.
7. Entry requires a later completed candle closing inside inclusive gap bounds, without stop-wick invalidation. Macro direction must align at entry. Expired or consumed setup cannot revive. Conflicting directions at one close reject both. Stable setup ID hashes contract, direction, pool publication, sweep, CHoCH and FVG timestamps. One entry attempt per setup; rejection consumes it.
8. Execute at first valid Bid/Ask tick at or after retest close, within90seconds. No qualifying tick => rejected late/no quote. Market entry does not imply100% admission/fills. BUY uses Ask, SELL Bid; apply adverse slippage. No entry at retrospectively known candle close price.

Reuse selected pure helpers in `scripts/smc/structure.py`; write M15-specific orchestration. Do not directly call H1/M5 `evaluate_smc_setup` and inherit hidden H1 EMA/session/spread/TP behavior. Do not rewrite legacy SMC, which remains importable by its tests.

## Replay adapter and accounting

Use `scripts/research/breakout_replay.py:replay` via a new adapter. It already supplies tick Bid/Ask, USD200, fixed-lot admission, circuits, swap-aware equity, ledger and rejection events. `scripts/research/engine.py` is an M1 simulator with different contracts and is excluded.

Adapter produces canonical OHLC, ATR, direction, hh/ll and `stop_low`/`stop_high` with Rules `entry_mode=immediate`, structure stop, target_rr2, protection off, static risk_cap0.1, fixed sizing and phase-one circuits. Assert actual required columns/rule fields against replay before coding; neutralize unrelated breakout/prior-day/depth/reset filters explicitly. Never let a default silently change SMC.

BUY stop anchor uses Bid sweep low. SELL stop must be executable Ask-side: transform Bid sweep high by actual scenario entry spread before passing to canonical structure geometry. Tick rounding must widen protective distance and risk gate must run after rounding. Test this seam explicitly: M15 `prepare_entry` does not automatically add Ask spread to SELL structure anchors. Confirm target stays beyond executable quote and stop is on correct side.

Risk denominator is initial modeled SL loss plus exit slippage and round-trip commission. Spread is already in entry/exit quotes; do not deduct it twice. Future unknown swap is not an invented entry reserve. Accrued swap enters ledger, equity, drawdown and circuits as time advances. Gaps and swap can make realized loss exceed modeled10%; report such cases instead of asserting a guaranteed maximum realized loss.

Require complete broker metadata including swap mode/rates/point/triple weekday, contract/tick size, volume grid and leverage. Reuse `SwapPolicy.from_broker`; missing or unsupported metadata blocks evaluation. Valid explicit short rate0 is permitted; absent rate is not zero. Do not hardcode -567.4/0 as verified historical tariffs. Pin signed rates, units and source. Modeled calendar is UTC midnight labeled by preceding business day, Wednesday triple posted Thursday, weekend rules per `rollover.py`. Retain `COST_INCONCLUSIVE` until historical broker evidence exists.

Base uses recorded Bid/Ask; stress widens total spread byUSD0.20/oz (half each side). Pin slippageUSD0.10/oz and commission in USD/lot/roundtrip only with named assumptions/evidence; no default tariff fallback. Both scenarios require modeled swap.

## Deliverables and stages

1. Audit and freeze input manifests, actual start/end, session calendar, source pins, broker metadata, cost views and contract. Append a research-only contract entry to `CORE_STRATEGY.md` when implementing strategy math; do not alter6.33.
2. Add `scripts/research/smc_challenger_signals.py`, `smc_challenger_adapter.py`, `smc_challenger_campaign.py`, `config/smc-challenger.json` and focused tests. Names are proposed; all paths new. Keep pinned files unchanged.
3. Prove causal signals and accounting with deterministic fixtures before a bounded replay smoke run. Economic smoke runs also include both swap views.
4. Rerun frozen C22 comparator on the same continuous tape, time window, warmup, cost views and USD200. Preserve C22's own exits/circuits. Verify archived full-result parity on exact archived inputs before new-input comparison.
5. Run one frozen SMC configuration first. Tune only in a separate bounded, preregistered catalog with budget and selection policy. Original plans' 35%/38% DD concessions and approximate frequency baselines are not adopted as approved gates.

Planned CLI, available only after implementation:

```bash
.venv/bin/python3 -m scripts.research.smc_challenger_campaign --config config/smc-challenger.json --output runs/smc-challenger-<run-id> --workers 2
```

Use separate USD200 account path per strategy/scenario, no monthly/yearly account reset. Partial current month excluded from full-month mean. Preserve state across storage chunks; resumed output must match uninterrupted output. Requested2024–2026 does not prove full coverage: report actual paired quotes, gaps and warmup exclusions. Previously examined history is discovery, never relabeled holdout. Preregister truly untouched/forward holdout and lock winner before opening it; absent holdout means descriptive research only.

## Validation and acceptance

- Tests: prefix-vs-full causal equality; future-bar mutation; pivot i+2 publication; third-candle FVG timing; session publication/gaps; CHoCH vs BOS; mirrored BUY/SELL; retest/invalidation/TTL; duplicate/conflicting setups; chunks/resume and source drift.
- Replay seams: no quote/stale/late quote, risk boundary/equality and just-over10%, rounded SELL Ask stop, fixed lot incompatibility, margin/busy rejection, midnight held position, complete losing exit counting, all-tick equity DD, swap sign/points/triple/weekend/exact-boundary entry and exit. No broker or notifier API calls permitted from campaign.
- Regression: new tests, all `test_c22h4_*.py`, `test_trial30_demo.py`, relevant SMC structure/detection/liquidity tests, replay and rollover tests; full repository unittest suite before implementation completion. Existing suites passing does not prove new adapter parity.
- Artifacts: `runs/smc-challenger-<run-id>/` contains immutable input/source/config/runtime manifests, bounded catalog if any, signal funnel, rejection ledger, trades, swap debits, equity/DD witnesses, full-month metrics, complete-result repeat checks and resumable checkpoints. Drift/missing swap => BLOCKED; unfinished run => PARTIAL, never COMPLETE.
- Scorecard: net/final equity, tick-equity DD, PF/expectancy/WR/realizedR with undefined values preserved, signal vs admitted trade count, monthly frequency and concentration, costs/swap, risk rejections and terminal risk-only blockage. Ranking cannot hide failed constraints. Hard validity gates precede descriptive ranking.
- Repeat complete results including ledgers/equity/rejections for baseline and any reported finalist. Reconcile cashflows and confirm non-overlap and <=10% initial modeled admission on every trade.

Before selection, owner must define DD ceiling, minimum sample and meaningful gain against baseline. Until then report descriptive comparisons; do not declare a qualified winner. A research result never authorizes Demo cutover or real-money trading.

Verdict: implement isolated research prototype after contract/input prerequisites; retain operational Demo unchanged.
