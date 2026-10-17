# BotTradeGold — Aggressive Research Implementation Guide

Version: `BTG-AGR-GUIDE-1.0` · Prepared: 2026-09-28 · Status: **implementation proposal; research only; Demo/Live NO_GO**

Purpose: investigate clip-inspired short-horizon upside without sacrificing traceability, confusing leverage with edge, or changing B1/D. This document authorizes no account activity. No new backtest, strategy implementation, deployment, or trading occurred while preparing it.

## 1. Outcome and boundaries

Build a separate, bounded RSI/recovery research family. Preserve B1/D as immutable controls. Evaluate recent real XAUUSD data, replay costs and account constraints, diagnose failures, make one justified change, then retest. Freeze before confirmation. A negative or inconclusive result is valid completion; “repeat until green” is not.

The YouTube example motivates questions about return distribution, trade frequency and recovery exposure. It does **not** establish an expected +40% return in eight trading days. No daily profit quota, guaranteed monthly target, or increase in risk to recover missed profits.

Target profile:

- Positive net expectancy and return after explicit costs, with bounded exposure and observable tail losses.
- Report every rolling eight-trading-day return, median, lower/upper quantiles, worst window and proportion reaching +40%. Overlapping windows are correlated; never treat them as independent trials.
- Judge overall results over the full declared window, not the best eight days. Report calendar duration, active sessions and exposure hours separately.
- Seek improvement against B1 and D at comparable capital/risk. Higher raw return from higher exposure alone is not strategy improvement.
- Keep `$100 Standard / XAUUSDm / requested leverage 1:1000` as the historical project target. `$200` is a separately labeled simulation sensitivity matching the clip's initial capital. Neither changes an actual account; no substitution of Cent accounts.

## 2. Evidence, provenance and unresolved authority

Evidence below was read during guide preparation; results were **not rerun**. A report's previous test claims remain report claims.

| Evidence | What it supports | Limitation |
|---|---|---|
| Referenced chat, “ความคืบหน้าแต่ละแชท” | Desired return profile, B1/D comparisons, proposal to separate research and live gates | Chat statements are not independent verification |
| Attached YouTube transcript | Narrator says initial $200, final $279.81; RSI, larger opposite hedge, capped loss $55, leg reaching 0.08 | Self-reported experiment; broker statement, full strategy and exact execution absent |
| `backtest/results/REPORT.md` | B1 OHLC research: 87 trades, WR 27.59%, PF 1.177, expectancy +0.141R at 0.10R cost; primary 2026-06-26 through 2026-09-25 | Ideal fractional sizing; not executable $100 account evidence |
| Same report/handoff | Reported B1 primary return 11.83%, marked DD 10.04%; 0.15R cost gives 6.84% return | OHLC marked DD is not tick DD; cost is generic |
| `XAUUSD_Scalper_loop/config/B1-FINAL-v1.yaml` | Frozen engineering B1, TP 3.5R, 12% HWM entry halt, no Martingale/grid | Tester-only configuration; not live qualification |
| `scripts/research/strategies.py` in that snapshot | `B_Donchian30_RSI` defaults to TP **2.5R**; `D_ATR1.5_RSI_FVG` reconstruction exists | Names alone do not identify comparable B1 variants |
| `docs/research/B1_D_EXNESS_REAL_TICKS_2026-09-26.md` | Historical account replay: B1 zero admitted; D zero signals, September sample | Historical settings and account snapshot; not current broker status |
| `docs/research/FINAL_LOOP_PROGRESS_2026-09-27.md`, through I040 dated September 28 | Saved 31,780,274-tick capture; repeated candidate failures; I040 B1 $100 replay zero trades | Read report, not all raw ticks/ledgers; inspected tape is not unseen OOS |

The chat's attractive Dukascopy B1/D statistics, including B1 287 trades/PF 1.278 and D 85 trades/PF 1.677, remain **chat-reported in this guide**. Do not combine them with local account replays into one performance series. Recover exact source, version, ledger, costs and windows before reproducing those rows.

Clip arithmetic: `(279.81 / 200 - 1) × 100 = 39.905%`. A $55 basket stop is 27.5% of initial $200, or 55% of $100. This is a large loss budget, not a default. “About eight market days” comes from prior discussion; transcript lacks a complete independently verified trading calendar. Do not annualize the result.

### 2.1 Authority conflicts to preserve explicitly

1. Existing `backtest/strategy_loop/gate.json`: PF >=1.30, DD <=15%, at least 30 closed trades. Existing spec prohibits Martingale/grid/DCA.
2. B1-FINAL has its own stricter validation contract: do not replace it with the research gate.
3. Earlier chat proposed PF >1.10 / research DD <=20%. That was a proposal, not an applied change to saved gates.
4. Existing general `CONTEXT.md` describes SMC concepts and execution ownership. Its production-hardening wording does not qualify this new strategy.

This guide defines a **new research protocol**, not a waiver of existing contracts. Approved deviations require a new protocol version before results are viewed. Legacy result verdicts remain unchanged.

## 3. Preserve B1/D; isolate aggressive work

Suggested branch in the actual repository: `research/agr-rsi-capped-recovery`. This workspace is a project mirror, not a Git repository. No branch was created here.

Before coding in the real repository:

1. Inspect local `AGENTS.md`, Git status, current diff, baseline contracts and relevant tests. Preserve unrelated changes.
2. Archive exact baseline source, config, dependency versions and SHA-256 manifest. Record repository commit and dirty patch, if any.
3. Give controls unambiguous IDs: `B1-OHLC-3.5R`, `B1-FINAL-v1`, `B1-REGISTRY-2.5R`, `D-RECON-v1`. Select comparison controls before testing; do not silently switch B1 variants.
4. Freeze D's serialized `Spec`, features, signals, seed/warmup and execution rules. Label it reconstruction until original provenance is established. Current registry: M15 ATR expansion 1.5, RSI/FVG filters, SL default 2 ATR, TP 3R. Source code, not this shorthand, defines exact inequalities.
5. New files under proposed `research/aggressive/`, new config namespace, separate run store. Leave synced files and `sources/` untouched.
6. Never enable aggressive recovery through B1's existing settings. Never share an execution account between B1/D and recovery during qualification.

No baseline signal, stop, size, gate or historical report edits. Shared-engine bug fixes need isolated regression evidence and versioned baseline reruns; preserve original results for comparison.

## 4. Data contract: real, recent, reproducible

Define `as_of_utc` once per study. All scored observations must fall within `[as_of_utc minus 1 calendar year, as_of_utc)`. For September 28, 2026, the earliest permissible scored date is September 28, 2025. Use complete sessions ending before cutoff; disclose actual start/end, missing sessions and lag to last quote. Warmup also stays within that interval for this protocol; shorten scored coverage rather than claiming a full year.

Prefer target-broker observed Bid/Ask ticks, then independently sourced observed Bid/Ask for robustness. Real OHLC can screen signals but cannot confirm an intrabar recovery strategy. Synthetic ticks, interpolated quotes and inferred spread must never be labeled observed. Existing reported capture begins May 7, 2026; requesting January does not create January coverage.

Manifest fields: provider, instrument/suffix, price side, retrieval UTC, UTC timestamp semantics, raw hashes, transformation hashes, coverage, quote count, gaps, session calendar, broker-spec snapshot time and observed-versus-assumed fees. Do not put account credentials in artifacts.

Validate finite positive prices; Ask >= Bid; chronology; stable source order for equal timestamps; exact duplicate handling without deleting distinct same-millisecond quotes; expected quote/session gaps; bar aggregation; incomplete bars; clock shifts/DST. Quarantine invalid partitions. No forward-filling closed bars to invent signals. Higher-timeframe features use completed periods only.

### 4.1 Partition and exposure register

- Chronological discovery, internal validation, then confirmation. Set exact UTC boundaries before any search. Indicative allocation: 60/20/20 of eligible sessions, only if sufficient data exists.
- Register every previously viewed interval, statistic and candidate search. The project's previously inspected recent history is **retrospective confirmation**, not untouched OOS.
- Use genuinely uninspected held-out data only if access history supports that claim; otherwise freeze and collect future data. Do not shift windows repeatedly until an attractive tail appears.
- Indicators may warm up from earlier data. No scored positions cross a selection boundary in the primary flat-start protocol. Continuous carry-state replay is a separately preregistered sensitivity.
- Partition by time, never random trades. Embargo at least maximum basket duration plus entry TTL around boundaries; prevent training outcomes from extending into validation. Log omitted signals.
- With <=1 year available, limited regime coverage is an explicit limitation. Insufficient data means `INCONCLUSIVE`, not relaxed criteria.

## 5. Controlled research loop

`Preregister → replay → reconcile → diagnose → falsify → one change → discovery retest → freeze → confirmation → verdict`

### 5.1 Initial hypotheses and controls

| Arm | Purpose | Exposure |
|---|---|---|
| B1, D frozen | Existing benchmark families | Their original frozen policy |
| AGR-R0 | Does closed-bar RSI entry have edge alone? | One leg, no recovery |
| AGR-R1 | Does an opposite recovery leg help after costs? | Two legs, same total basket budget |
| AGR-R2 | Does capped size escalation add value? | Four cumulative legs maximum, same basket budget |

Start with those three aggressive arms, not a huge optimizer grid. Keep RSI/ATR/session/target and basket risk fixed between them. Recovery and no-recovery comparison must include turnover, margin and DD, not only win rate. Baseline-normalized sizing replays, if added, get separate IDs and do not overwrite original-policy results.

Suggested search budget: at most 12 preregistered configs per study, including controls/ablation choices but excluding deterministic stress reruns; at most three hypothesis revisions on an exposed discovery set. Log all attempts, aborted runs and results. Exhaustion ends the study; a new name does not erase multiple testing.

### 5.2 Failure diagnosis

| Symptom | Investigate first | Smallest justified response |
|---|---|---|
| No trades | Raw signal → admission → fill waterfall; min lot, spread, session, margin | Fix defect if present; otherwise report account infeasibility |
| High WR, negative PnL | Largest baskets, cost turnover, payoff asymmetry | Test removing recovery/escalation |
| Profitable without costs only | Spread relative to stop/target, repeated hedging | Reject hypothesis or test one causally justified entry change |
| Discovery good, confirmation weak | Trial count, regime, sample uncertainty, selection leakage | Reject/freeze failure; do not tune on confirmation |
| USD profit positive, mean R negative | Variable risk weights and admission selection | Report both; inspect risk-normalized cohort |
| Simulator/broker mismatch | Quote side, time, fill, rounding, fees, event ordering | Reproduce minimal defect before strategy changes |
| DD concentrated in a few baskets | Ladder growth, persistent trends, gaps, stop execution | Test no-recovery control; do not widen loss cap |

Every change note: observation, hypothesis, alternative explanation, discriminating test, expected effect, permitted change, reject criterion. Correctness defects need a failing regression fixture, smallest fix and rerun of affected evidence. A filter invented after seeing losing dates is exploratory; validation still required.

### 5.3 Freeze record

Before opening confirmation, seal: candidate/config hash, source/dependency hash, dataset/splits, feature seeds, fees, stress matrix, metric definitions, selection rule, search log, risk contract, confirmation sample/horizon, promotion criteria and random seeds. Store timestamp plus independent read-only copy where available. Hash consistency alone is not external attestation.

Select using discovery/internal validation only. Proposed tie-break: highest worst-cost net basket expectancy in R among qualifying candidates; then lower tick DD; fewer legs; lexical ID. If none qualify, there is no selected candidate. Diagnostic leader must say `DIAGNOSTIC_ONLY`.

Confirmation runs once per frozen candidate/protocol. Failure remains recorded. Any logic/config change creates a new candidate; old confirmation becomes exposed development evidence. A correctness repair also invalidates affected results and cannot make reused data “unseen.”

## 6. Strategy contract: RSI with capped opposite recovery

These are **research defaults**, not extracted YouTube rules or proven profitable parameters. Opposite hedging was described in the transcript; exact conditions were not available. Same-direction averaging is a different family and is excluded here.

### 6.1 Entry and timing

- Signal timeframe M1, RSI14/ATR14, arithmetic seed then Wilder smoothing. Require 100 complete bars; define flat RSI as 50 and positive-gain/zero-loss as 100.
- Long: previous RSI <=30 and current RSI >30. Short: previous RSI >=70 and current RSI <70. Completed Bid bars only; equality rules fixed.
- Enter first executable quote after signal close, within 5 seconds; otherwise expire. Long entry Ask, short entry Bid. No same-bar hindsight fill.
- Research entry session 07:00–17:00 UTC. Latest new basket 16:00 UTC; flatten at 17:00 or basket age 60 minutes, whichever occurs first. These times are hypotheses, not optimized claims.
- No trailing, partial TP, breakeven, trend filter or news filter in first offline arm. Tag news/session exposure where reliable data exists. Before Demo, choose and freeze a tested news policy; unavailable required calendar blocks new entries.

### 6.2 Recovery ladder

R0: `[0.01]`; R1: `[0.01, 0.02]`; R2: `[0.01, 0.02, 0.04, 0.08]` lots. Values are proposed Standard-account simulations subject to broker constraints. R2 maximum gross lots = 0.15; initial long yields sides long/short/long/short and final net short 0.05 lot. Reverse sequence for initial short. Gross costs/margin remain even when net exposure is small.

Each add requires all of:

1. Basket net liquidation PnL negative.
2. A **new completed opposite RSI crossback** after the last confirmed leg fill.
3. Midquote moved against the latest leg by at least frozen initial ATR14 ×1.0 from that leg's fill-midquote reference.
4. At least one complete M1 bar since last fill; fresh quote; no pending/unknown intent; age/session still valid.
5. Next step exists; gross, budget, margin, stop and ownership checks pass after hypothetical fill.

One quote/bar event may cause at most one add. Never jump several levels on a gap. Failed/rejected/unknown orders do not advance the ladder; partial fills are reconciled without automatically topping up. A fourth filled leg exhausts R2 permanently for that basket. No fifth leg, doubling beyond array, stop widening, new basket to bypass cap, or cross-basket loss-recovery multiplier.

### 6.3 Cash risk and liquidation

At basket creation, freeze `B = min(absolute_cap, equity_at_open × basket_risk_fraction, remaining_daily_budget, remaining_HWM_budget)`. If B <=0, reject. Remaining daily room is current liquidation equity minus 90% of UTC day-start equity; remaining HWM room is current liquidation equity minus 85% of persistent HWM. Negative room is zero. Later profits, deposits or larger legs cannot expand B. Risk budget includes entry/exit reserves, commission, swap and already realized basket losses.

Define `P_liq = realized_net_basket + marked_open_PnL_at_liquidation_quotes - unpaid_exit_cost_reserve`. Never subtract costs twice. Stop when `P_liq <= -B`; target when `P_liq >= target_R × B`. Cancel pending adds, persist close intent, close all owned exposure and reconcile. Ladder exhaustion alone does not close; stop/target/time/risk exits do.

Proposed default B cap: 5% of basket-open equity and $10 absolute; target 0.5B. Thus $100 gives at most $5 and $200 at most $10 before remaining-account limits. This intentionally does **not** copy the clip's $55 budget. The ladder may be unaffordable: skip it, report that fact, never round upward or loosen stops.

For each admitted leg require protective broker-side SL at initial ATR ×2 from that leg's entry, unchanged after fill except protective normalization. Sum already realized basket losses, worst-case remaining per-leg protective losses, estimated close costs and adverse-fill reserve; require this conservative non-netted total <=B. Broker `OrderCalcProfit` or a verified equivalent calculates monetary loss; protect against tick-grid rounding increasing risk. A rejected prospective leg leaves existing protected legs under basket management. No fake risk offset from opposite positions.

Basket hard stop is an **exit trigger**, not a guaranteed loss ceiling. Gaps, outages and close rejections can exceed it. Per-leg stops provide outage protection but also cannot guarantee gap prices. Any protective SL fill terminates recovery: cancel adds, flatten remaining owned legs, record overshoot. Admission must also show plausible liquidation before margin stop-out under stress.

Priority on each quote: reconcile broker events → update liquidation equity/HWM → account/day/basket stop → required flatten/cancel → target → expiry → recovery → new entry. Stop dominates conflicting actions. Never add while closing.

Daily loss: 10% of UTC day-start equity including realized and floating PnL; HWM drawdown: 15%; at most two new baskets/day. Remaining daily/HWM loss room constrains B. Breach blocks adds/new baskets and closes owned positions. Daily latch expires only after next UTC day **and** flat/reconciled state; HWM latch survives restart/date change and requires reviewed manual reset. HWM includes floating equity and never resets because a process restarts. External cash flows invalidate the research equity path unless explicitly modeled.

## 7. Config examples — proposed schema, not existing loader inputs

Implement a strict new schema first. Unknown keys, missing pins, placeholders, inconsistent risk limits, nonfinite values and unsupported account modes fail closed. Do not paste these examples into current B1 loaders. Live is disabled regardless of strategy parameters.

```yaml
schema: btg-aggressive-research-v1
candidate_id: AGR-RSI14-R2-v001
mode: offline_research
orders_enabled: false
baseline_refs:
  b1: B1-FINAL-v1@REQUIRED_SHA256
  d: D-RECON-v1@REQUIRED_SHA256
study:
  as_of_utc: '2026-09-28T00:00:00Z'
  maximum_calendar_years: 1
  data_manifest: REQUIRED_IMMUTABLE_MANIFEST
  split_manifest: REQUIRED_EXPOSURE_AUDITED_SPLITS
  gate_version: AGR-GATE-PROPOSED-1
  maximum_configs: 12
  confirmation_label: retrospective_until_proven_unseen
account:
  symbol: XAUUSDm
  type: standard_hedging
  currency: USD
  initial_equity_usd: 100
  broker_spec: REQUIRED_HASHED_SNAPSHOT
signal:
  timeframe: M1
  rsi_period: 14
  rsi_low: 30
  rsi_high: 70
  atr_period: 14
  smoothing: arithmetic_seed_then_wilder
  warmup_bars: 100
  entry_ttl_ms: 5000
  session_utc: ['07:00', '17:00']
  last_new_basket_utc: '16:00'
recovery:
  mode: opposite_confirmed_crossback
  lots: [0.01, 0.02, 0.04, 0.08]
  max_legs: 4
  max_gross_lots: 0.15
  max_active_baskets: 1
  adverse_step_initial_atr: 1.0
  min_complete_bars_since_fill: 1
risk:
  basket_fraction: 0.05
  basket_absolute_cap_usd: 10
  basket_target_r: 0.5
  protective_leg_stop_initial_atr: 2.0
  reserve_all_leg_stop_losses: true
  max_basket_age_minutes: 60
  day_loss_fraction: 0.10
  hwm_halt_fraction: 0.15
  max_new_baskets_per_utc_day: 2
  reset_hwm_automatically: false
  round_volume_up: false
execution:
  require_observed_bid_ask: true
  require_hedging: true
  require_single_account_writer: true
  ambiguous_send: halt_and_reconcile
  stale_quote_max_ms: 2000
  cost_manifest: REQUIRED_COST_AND_STRESS_MANIFEST
promotion:
  demo: false
  live: false
```

Separate immutable ablation overrides:

```yaml
# AGR-RSI14-R0-v001: same entry, target and cash budget; no recovery
recovery:
  mode: disabled
  lots: [0.01]
  max_legs: 1
  max_gross_lots: 0.01
  max_active_baskets: 1
```

R1 changes only recovery mode/ladder limits to two legs and 0.03 gross lots. Material risk changes need their own study; never optimize basket cap alongside entry. `$200` sensitivity changes only hypothetical starting capital, with same fractional/absolute policy and complete rerun of admission.

## 8. Implementation architecture

Reuse existing narrow seams where behavior matches; do not rewrite the trading stack or let a signal module call the broker.

| Proposed component | Responsibility | Existing reference to inspect |
|---|---|---|
| Data adapter / quote tape | Validated UTC quotes, immutable manifests, completed bars | `scripts/research/final_loop/ticks.py`, `b1_d_ticks.py` |
| Pure RSI signal core | Causal features → signal; no I/O | `scripts/research/strategies.py` |
| Basket state machine | Legs, frozen B, pending intent, exits, restart state | New module; do not bolt onto B1 signal state |
| Risk admission | Whole-basket cash loss, lot/price normalization, margin, latches | Existing B1/replay checks; extend via new contract |
| Replay adapter | Same intent/event interface, simulated fills/costs | Existing tick loop; version any execution differences |
| Execution adapter | One account writer, broker responses/reconciliation | Existing adapter/outbox; inspect `scripts/b1_outbox.py` |
| Ledger / persistence | Transactional event journal, state snapshot, durable outbox | Existing lifecycle persistence |
| Evaluator / gate | Recompute metrics and evidence completeness | `final_loop/evidence_audit.py`; keep separate aggressive gate |

Proposed state model:

```text
FLAT → ENTRY_PENDING → OPEN → ADD_PENDING → OPEN
                         ↘ CLOSE_PENDING → COOLDOWN → FLAT
Any unresolved delivery/state/ownership → RECONCILE_REQUIRED
Any persistent risk/integrity breach → HALTED
```

Pending states are not fills. `OrderSend` success does not itself prove execution; inspect return codes and subsequent trade events ([MQL5 OrderSend](https://www.mql5.com/en/docs/trading/ordersend)).

Single-instance protection: exclusive lock plus account/server/symbol ownership, monotonically increasing fencing token where supported, and one sending service. Different magic numbers alone do not prevent duplicate exposure. If broker cannot enforce fencing, use one gateway and block takeover until old sender is proven stopped and reconciliation completes. Cross-host failover cannot depend on a host-local PID lock.

Persist intent before send; deterministic `intent_id = hash(candidate, account_alias, basket_id, leg_index, action_revision)`. Keep broker order/deal/position IDs separately. Timeout after send → query/reconcile; never blindly resend. On restart acquire ownership, replay durable journal, reconcile open orders/positions/deals, recover B/HWM/day latch/ladder index, then consider new entries. Foreign positions or unexpected ownership block new trading; do not close unrelated trades.

Use existing Python adapter path unless repository evidence requires another approved path. No second MQL sender. If later porting to an EA, require event-by-event parity and compile/test evidence; compile success alone proves no strategy parity.

## 9. Costs, broker feasibility and stress

Before executable simulation, obtain min/max/step lot, tick size/value, contract size, stop/freeze distance, supported filling modes, margin/hedged-margin model, stop-out rule, currency conversion, commission/swap and session calendar. These are broker/account-specific; documentation is not a measured snapshot ([MQL5 symbol properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants)). Monetary stop calculations should use broker calculation semantics ([OrderCalcProfit](https://www.mql5.com/en/docs/trading/ordercalcprofit)).

Floor volume to step; below minimum means rejection. Normalize prices conservatively, recalculate risk, then admit. Higher leverage changes margin requirement, not dollar loss at the same lot and stop. Opposite legs incur additional spread and possibly margin; never assume free hedging.

Preregister stress arms:

| Arm | Perturbation |
|---|---|
| Base | Observed Bid/Ask; measured fees when available, otherwise explicitly assumed reserves |
| Cost reserve | Base +0.10B and +0.15B per completed basket, charged once through documented accrual; hypothetical, not same as legacy per-trade 0.15R |
| Spread | Double observed spread around unchanged midquote; rerun admission and outcomes |
| Latency | 250 ms, 500 ms, 1 s, 2 s; first actual quote at/after deadline, no stale fill |
| Adverse fills | $0.10/oz adverse entry and market liquidation, all legs; report USD impact |
| Combined | Doubled spread +2 s +adverse fills +high cost reserve |
| Failure | Missing quotes, failed/partial closes, disconnect through stop, gap trend, margin squeeze |

The new spread convention differs from the legacy runner's fixed-Bid convention. Record it; never compare stress rows as identical. Bid/Ask already embeds spread; do not subtract it again. Every arm reruns signals where quote-derived features change, admission, leg ordering, cash/margin, stops, quotas and equity. Post-hoc subtraction from winning trades is inadequate.

Real-tick testing and explicit execution delay are supported by MT5, but historical replay remains a model ([official tester documentation](https://www.metatrader5.com/en/terminal/help/algotrading/testing)). Reject unreported substitution of generated ticks in scored intervals.

## 10. Metrics and fair comparison

Primary outcome unit: **closed basket**. Leg/deal statistics are secondary. Ten profitable legs plus one disastrous basket cannot be presented as high strategy reliability.

| Metric | Required definition |
|---|---|
| Net return | `(ending liquidation equity / starting equity - 1) ×100`, no cash flows; also realized net PnL |
| Win rate | Positive-net closed baskets / all closed baskets; zero-net baskets remain denominator |
| PF USD | Sum positive net basket PnL / absolute sum negative net basket PnL |
| Expectancy USD | Mean net basket PnL |
| Expectancy R | Mean `net basket PnL / frozen initial B`; keep leg-R separate |
| Drawdown | Maximum `(running equity peak - equity)/peak` on every observed liquidation quote |
| Tail behavior | Worst basket/day/eight-day window, loss streak, 95% expected shortfall with sample size, stop overshoot |
| Exposure | Time in market, max gross/net lots, margin utilization, turnover, recovery-level frequency |
| Executability | Raw signals, each reject reason, accepted intents, fills, completed baskets, forced exits |
| Robustness | Per-month/session/regime/feed, parameter-neighbor sensitivity, cost/latency degradation |

No losses → PF undefined/unbounded with loss count disclosed; not automatic pass. No trades → WR/PF/expectancy unavailable, `INSUFFICIENT_SAMPLE`. At window end report marked open inventory separately; forced liquidation follows preregistered rules and carries `END_LIQUIDATION`, never fake TP. Include tail liquidation PnL in return and disclose impact on closed-basket metrics.

Comparison tables require same UTC scored window, feed, start capital, costs, fill model, account specs and end treatment. Report original-policy B1/D, normalized-risk diagnostic controls and AGR separately. Keep fractional sizing apart from executable minimum-lot accounts. Never add standalone B1 and D results to imply a combined portfolio.

Provide paired block-bootstrap intervals for differences where feasible, using session/week blocks to preserve clustering. Small samples and reused data limit inference. R metrics with different denominators need labels; USD return/DD provide a common but sizing-sensitive view.

### 10.1 Ruin sensitivity

Define three separate events: 15% policy HWM halt, 50% capital impairment, broker stop-out/equity depletion. A policy halt is not insolvency. Estimate probabilities conditional on stated model, never “true ruin probability.”

Run at least 10,000 seeded paths for exploratory sensitivity; use stricter existing baseline requirements when evaluating that baseline. Resample day/week blocks, preserve within-basket leg sequence and costs, rerun path-dependent sizing/admission/latches. Never shuffle individual recovery legs. Where full quote resampling is impractical, label cashflow bootstrap limitations and add deterministic adverse quote scenarios.

Report horizon (e.g. 60 trading sessions), path count, seed, block length, equity percentiles, max-DD distribution, stop-out frequency and confidence intervals. Repeat capital $100/$200, spread multipliers, serial loss clusters, gap overshoot and actual broker margin modes. Do not assume a 20% stop-out just because narrator used it. Zero observed failures in finite simulated paths is not zero risk; missing tail regimes remain missing.

## 11. Logging, ledgers and errors

Each run directory is immutable; write to `.partial`, validate then finalize atomically. Incomplete runs cannot emit PASS. Proposed layout:

```text
runs/AGR-RSI-R2-I001-20260928T120000Z-cfg8-data8/
  hypothesis.md
  config.json                 protocol.json
  code_manifest.json          data_manifest.json
  exposure_register.json      trial_ledger.csv
  frozen_selection.json       event_ledger.jsonl
  signal_ledger.csv           order_ledger.csv
  basket_ledger.csv           equity_ledger.csv
  metrics.json                gate_verdict.json
  review.md                   REPORT.md
```

Naming: `AGR-RSI-R2-I001-20260928T120000Z-cfg8-data8` identifies family, recovery arm, study iteration, UTC run start, config-hash prefix and data-hash prefix. Store full hashes in manifests. Increment candidate version for logic changes, iteration for each preregistered experiment; retries get a new run timestamp plus `retry_of`. Never overwrite or recycle IDs.

Required ledger fields: run/candidate/protocol IDs, source/config hashes, UTC event/decision/quote timestamps, sequence, quote age, Bid/Ask, indicator inputs, signal direction, rejection reason, basket/leg/intent IDs, broker IDs, planned/filled volume and price, partial remainder, B and reserved risk, protective levels, realized/unrealized PnL, each cost component, equity/HWM/day anchor, gross/net lots, margin, latch state, action/response/error and reconciliation version. Preserve planned versus actual values.

Ledger invariants: opening equity + realized net + floating net = liquidation equity; closed-basket sum matches realized ledger; no duplicate intent fill accounting; gross lots equals owned open legs; monotonic leg index <=cap; every send has durable intent; all closed baskets reconcile to deals. Secrets absent; account aliases/redacted identity hashes only.

| Failure | Required behavior |
|---|---|
| Missing/corrupt/stale data | Block entries/adds; continue protective exit handling where connectivity permits; invalidate affected evidence |
| Invalid/missing spec, fees or schema | Fail preflight; no silent defaults for required inputs |
| Insufficient margin/min lot/stop distance | Reject intent with precise reason; never squeeze stop to pass |
| Send timeout / disconnect | `RECONCILE_REQUIRED`; no blind retry or ladder advance |
| Partial fill / rejected protection | Account actual filled exposure; inhibit adds, flatten if protection cannot be established |
| Partial close / market closed | Persist remaining exposure; retry only known unclosed volume with bounded backoff; keep risk latch, alert |
| Lock loss / foreign position | Block sends; transfer only after safe reconciliation; do not liquidate foreign trades |
| Journal write failure | No new intents; use already established protective exit path; mark run invalid and alert |
| Metrics/report failure | Keep raw evidence, verdict `INCOMPLETE`; no promotion |

Distinguish transient retryable reads from ambiguous writes. Alerts are requirements for later implementation, not messages sent by this documentation task.

## 12. Test plan and acceptance evidence

| Layer | Required cases / expected result |
|---|---|
| Causality | Prefix invariance; future bars cannot alter earlier signal; exact RSI equality; incomplete bar ignored |
| Timing | Signal close precedes fill; TTL expiry/gap; equal-timestamp event ordering; UTC/DST/session boundary |
| Ladder | Exactly 1/2/4 legs; no fifth; one add per event; opposite confirmation required; no advance on rejected/unknown send |
| Risk | Budget frozen; realized loss retained; no upward rounding; spread/cost reserve; full-leg protective loss budget; target/stop collision chooses stop |
| Account | Min lot, stops, filling mode, margin, stop-out, hedging vs netting, symbol suffix mismatch |
| Lifecycle | Crash before send, after send before ack, partial fill/close, restart with open hedge, orphan order, stale lock, split-brain attempt |
| Latches | UTC rollover doesn't reset HWM; day latch includes floating loss; restart preserves B/index/HWM; no basket reset bypass |
| Accounting | Independent ledger reconstruction; commission/swap once; spread not doubled; liquidation quote sides correct |
| Replay | Gap overshoot, adverse exit, latency changes sequence, tick path versus OHLC ambiguity; no fake wins at window end |
| Gates | Missing data/stress/ledger cannot PASS; zero trades undefined; retrospective cannot satisfy unseen; research PASS cannot set live true |
| Controls | Baseline source/config hashes unchanged; matching fixture outputs; separate B1 2.5R/3.5R variants |

Use repository-defined checks after inspecting their scope; current snapshot includes `scripts/run_checks.sh` and focused research tests. Do not run broker-connected scripts as a shortcut to unit validation. Later implement deterministic fake-broker fixtures and integration replay; perform mutation/tamper tests on hashes, gate versions, leg caps and DD ledgers. Require independent metric recomputation, not only tests mirroring production formulas.

Execution adapter changes require Demo-only fault drills after authorization. MQL changes, if any, require actual compile and Python↔MQL event parity. Record exact commands, environment and observed results. Existing reported test counts are not new evidence for AGR.

## 13. Promotion policy — separate decisions

All numerical thresholds below are **proposed AGR policy**, not universal statistical guarantees or retroactive B1 gate changes. Freeze accepted policy before testing. Until then use `POLICY_PENDING`; no automatic promotion.

| Stage | Proposed criteria | Meaning |
|---|---|---|
| Research survivor | >=30 closed baskets in discovery/internal validation aggregate; net return >0, PF >1.10, mean net basket R >0; tick DD <=15%; no risk-control violation; declared cost-reserve arm still positive | Worth further evidence collection only |
| Confirmation survivor | Frozen candidate; >=30 closed baskets; positive return/expectancy, PF >1; DD <=15%; no HWM halt; all declared arms completed and reconciled | Historical support; label retrospective/unseen correctly |
| Robustness qualification | Elevated costs/spread and combined arm have positive net expectancy/return and no halt; no unresolved catastrophe scenario; insufficient stressed sample is inconclusive | Risk/cost resilience under tested assumptions |
| Demo candidate | Above plus executable target-account geometry, broker-spec/fee evidence, persistent-state/single-writer tests, complete execution validation; explicit separate Demo authorization | May start bounded Demo trial |
| Live review candidate | Frozen future validation, Demo >=8 weeks and >=50 closed baskets, >=100 genuinely unseen closed baskets overall without double-counting; positive net expectancy/return, PF >1.10, DD <=15%, measured costs inside tested envelope; zero duplicate/unreconciled orders | Ready for owner review; not Live GO |
| Live GO | Owner explicitly approves account, risk, capital, rollout/rollback and production release | Separate irreversible/external decision |

PF >=1.20, expectancy >=0.10 basket-R and DD <=10% are stretch diagnostics, not extra hidden gates. Reject threshold shopping. The clip's +40% is never a promotion requirement. Do not waive engineering safety because a chart looks profitable.

Before confirmation preregister a duration cap (proposed 60 sessions) and assess at the fixed endpoint, not when PnL first turns green. If minimum sample isn't met, record inconclusive. A longer follow-up is separately planned; do not repeatedly peek and stop on success. For confirmation degradation, report discovery→confirmation ratios/intervals; positive absolute floors above decide the proposed gate, avoiding unstable ratios when discovery expectancy is near zero.

Live review also needs preapproved ruin/impairment probability tolerances and evidence they are satisfied. No tolerances are invented as owner-approved here. Missing owner risk tolerance keeps `LIVE_NO_GO`, even with positive performance.

## 14. Demo/live separation and rollback

Offline mode has no broker-write capability. Demo mode checks exact account/server identity, Demo trade mode, symbol and hedging mode before any intent. Live uses separate credentials/config/state/output roots, explicit allowlist and approved release hash. `orders_enabled: true` alone cannot unlock Live.

Promote a frozen evidence bundle, never a mutable working directory. Recovery branch does not inherit B1's release approval. No parallel B1/D/AGR senders on one account. First Demo step is shadow replay/reconciliation, then authorized small bounded execution with proven kill switch.

Rollback: stop new entries/adds, preserve durable state and protective orders, flatten owned exposure under approved risk-exit policy, reconcile to flat, archive evidence. Never switch strategy or reset ladder while basket remains open. Severe state uncertainty, duplicate order, protection failure or unexpected broker identity halts trial immediately. Profit shortfall alone does not justify higher risk.

## 15. Documentation critique — grill-with-docs review

Applied installed `grill-with-docs`: challenged terminology against code/context; resolved questions through source inspection where possible. Remaining owner decisions are labeled proposals instead of blocking document delivery. No independent agent review claimed; no synced glossary edited.

| Challenge | Hardened resolution |
|---|---|
| “Can we configure +40% in eight days?” | Treat as external observation; report distribution, downside and exposure; no guaranteed target |
| “Which B1?” | Explicit 2.5R registry versus 3.5R frozen identity; hash-specific controls |
| “D is already proven?” | Reconstruction labeled; account replay had no signals; old feed results not merged |
| “One instance means one position?” | One account writer / one basket; basket may contain four owned legs |
| “Recovery means averaging?” | First family opposite hedging only; no same-side DCA hidden behind naming |
| “Hard stop guarantees $5 max loss?” | Trigger can overshoot; budget admission, per-leg protection and gap stress required |
| “Can profitable legs fund bigger recovery?” | No; B fixed from basket start, realized losses retained |
| “Higher leverage solves $100 risk?” | Margin differs from stop loss; below-minimum lot rejected |
| “Recent tail is confirmation?” | Only retrospective once viewed; new freeze needs future/uninspected evidence |
| “Research PF threshold can be relaxed?” | New policy only, preregistered; saved baseline gates preserved |
| “Raise win rate?” | Basket expectancy, tail loss and costs govern; leg hit rate secondary |
| “No failures in simulation means safe?” | Conditional probability, confidence bounds, missing-tail limitation |
| “Passing tests means Demo/Live ready?” | Correctness, strategy evidence and release authorization remain distinct |

Owner decisions before enabling Demo: accepted AGR risk budget/ladder, exact authoritative B1/D controls, new protocol thresholds, target account identity, news policy, unseen horizon and loss/ruin tolerances. Implementation can build offline schema, state machine, fixtures and immutable runs first. This guide does not claim those decisions were approved.

## 16. Ordered implementation backlog

1. Pin baseline versions and exposure register; resolve B1 naming; freeze D reconstruction and known evidence gaps.
2. Add strict AGR schema and immutable run scaffold. Default offline; forbid Live capability.
3. Implement RSI-only R0, quote-side accounting and risk admission; verify against hand-calculated fixtures.
4. Add basket state machine and R1/R2 behind independent configs; test gaps, partial fills, restart and caps before profitability runs.
5. Implement independent ledger audit and gate checker. Reconcile all cash/risk metrics.
6. Run preregistered discovery on recent verified ticks; compare all arms against pinned B1/D. Publish failures and rejected signals.
7. Diagnose and test at most the declared changes; freeze a qualifying candidate or stop as no-go/inconclusive.
8. Run untouched/future confirmation; preserve failed verdicts. Complete cost/latency/ruin sensitivity.
9. Prepare concrete Demo evidence bundle for owner approval. No order submission from this documentation task.
10. Forward-test frozen Demo; only then prepare separate live review package.

Definition of implementation completion: reproducible offline engine, bounded strategy contract, complete ledgers, verified safety behavior, preregistered comparison and honest verdict. A profitable candidate is an empirical outcome, not a required software deliverable.

## 17. References and verification status

Local references, paths relative to project root:

- `BotTradeGold_DETAILED_HANDOFF_2026-09-27.md` — historical context; large chronological appendix.
- `backtest/results/REPORT.md`, `backtest/strategy_loop/SPEC.md`, `backtest/strategy_loop/gate.json` — existing research results/contracts.
- `XAUUSD_Scalper_loop/config/B1-FINAL-v1.yaml` — frozen engineering baseline.
- `XAUUSD_Scalper_loop/CONTEXT.md` — domain and execution ownership context.
- `XAUUSD_Scalper_loop/scripts/research/strategies.py`, `b1_d_ticks.py`, `b1_d_comprehensive.py` — version/naming and replay seams.
- `XAUUSD_Scalper_loop/docs/research/B1_D_EXNESS_REAL_TICKS_2026-09-26.md` — historical account feasibility report.
- `XAUUSD_Scalper_loop/docs/research/FINAL_LOOP_PROGRESS_2026-09-27.md` — loop record through I040; no final production pass.
- [Referenced discussion](chatgpt-conversation://6ab9df8a-ebcc-83ec-8e2e-0708cc37048f), plus attached `Nopparuj - บันทึกจาก Youtube-transcript.txt` read through its retrieved local attachment. Transcript claims are not an audited broker statement.
- [grill-with-docs skill](/Users/nopparuj/.codex/skills/grill-with-docs/SKILL.md) — source-aware critique method.

Repeated selection across many configurations creates backtest-overfitting risk; preregistration, trial disclosure and genuinely unseen evaluation address that risk without guaranteeing generalization ([Bailey et al., The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)).

Verification for this artifact: source/document cross-check and internal consistency review only. No strategy backtests or repository tests rerun; no new data capture, broker/account probe, deployment or order. Example schema is proposed, not implemented. Existing baselines and synced references remain unchanged.
