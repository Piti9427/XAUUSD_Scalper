# B1 scrutinize — 2026-09-26

Goal: find minimal, testable changes that improve net expectancy and win rate without increasing risk or confusing paper results with executable results.

Simpler alternative: retain Donchian30/RSI and fix measurement/execution parity first. Do not add another indicator sweep. Eight prior challengers did not improve later-window sized return. No production code or strategy contract changed in this review.

## Blocker — $100 cannot execute this stop geometry on captured XAUUSDm

Trace: `scripts/research/profit_challenger_checks.py:75` → `scripts/research/b1_d_ticks.py:71` quote entry → ATR stop → `:78` risk budget → volume floor → `:87` minimum-lot rejection. Current B1 primary decisions: 378 rejected, zero trades. Minimum stop risk $13.173, median $20.4935, maximum $50.102 at 0.01 lot. Initial budget at 1% of $100 is $1. This is correct risk protection, not missing entry signals.

Change: separate executable-account feasibility from alpha research. For $100, inspect whether an actually available smaller-contract instrument/account can fit this stop within $1; verify broker specifications rather than assume a Cent label solves it. Do not change account or instrument without user decision. At unchanged contract, reducing stop enough to force entry changes the strategy materially; raising risk to 13%+ is not an acceptable implementation fix.

Evidence: `data/b1_scrutinize_2026-09-26/excursions.json`, original broker decision CSVs. Paper fractional sizing cannot prove deployable profit.

## Major — public model and frozen B1 executable reference are different contracts

Public `data/b1_profit_research_2026-09-26/inputs/run.py:24` seeds RSI from nonmissing deltas and gates B1 on H1 EMA readiness (`:38`); frozen `scripts/research/b1_final.py:64` seeds first delta as zero and uses 100-bar readiness (`:72`). Public `run.py:63` enters next observed bar without signal expiry; frozen `config/B1-FINAL-v1.yaml:28` requires immediately next interval. Public `run.py:85` measures HWM at bar closes; broker `scripts/research/b1_d_ticks.py:117` marks each actual tick. These differences are disclosed research assumptions, but they prevent treating public results as B1-FINAL execution parity.

Reproduction: signal June 30 20:45 UTC entered June 30 22:00 UTC, one hour after signal close. A strict-expiry diagnostic removed stale eligibility; portfolio metrics stayed unchanged because the subsequent signal path replaced exposure. Therefore this is a semantic mismatch, **not evidence that fixing expiry increases profit**. Saved original/strict results in `data/b1_scrutinize_2026-09-26/expiry.json`.

Change: version public engine separately, use one canonical detector and entry-expiry contract for final validation, compare signal IDs and actual fills on identical bars/ticks. Preserve old results. Do not silently rewrite baseline.

## Major — higher win rate has already reduced profit

`profit_challengers.py:46` changes TP from 3.5R to 2.5R; `inputs/run.py:90` defines a win as net R > 0. At 0.15R cost in primary: B1 win rate 27.586%, expectancy +0.09138R, return +6.839%; TP2.5 win rate 34.188%, expectancy +0.04594R, return +3.086%. Full-window expectancy also declines, +0.12644R to +0.10510R.

Change: qualify on net expectancy, PF, executable DD and consistency, with win rate secondary. For a pure fixed SL/TP outcome model, breakeven win rate is `(1 + cost_R)/(1 + TP_R)`: 25.56% at TP3.5 versus 32.86% at TP2.5 when cost is 0.15R. Actual gaps/end marks can change this approximation. The observed cushion is small. Primary B1 gross expectancy is 0.24138R; average total costs reaching that value erase its raw fixed-R edge, before sizing effects.

Basis: actual metrics CSV; [CME expectancy explanation](https://www.cmegroup.com/education/courses/trading-psychology/the-mathematics-of-trading-success). Prefer spread/stop-distance cost telemetry and actual Bid/Ask costs over an arbitrary tighter TP.

## Major — profit giveback exists, but automatic breakeven can destroy winners

Frozen contract `config/B1-FINAL-v1.yaml:15` disables partial TP, breakeven and trailing. Public `inputs/run.py:74` checks only fixed stop/target/end mark. Diagnostic excludes the exit candle entirely to avoid asserting its intrabar event order.

Primary: 18/63 eventual losers previously reached +1R; 10/63 reached +2R. Discovery: 26/87 and 12/87 respectively. This justifies investigating exit behavior, not claiming a profitable fix.

Falsification: after a completed trigger bar, later completed bars returned to entry in 7/24 original primary winners after +1R, and 2/24 after +2R. Discovery has 14/35 and 6/35 respectively. These are real winners that a simple entry-price breakeven would interrupt. Moving stop to entry still produces −0.15R after the model's cost, so it does not count as a win. Observed saved-loser counts are not counterfactual strategy PnL: altered exit timing changes subsequent entries, and same-bar paths remain unknown.

Change: first build a counterfactual tick replay for ONE frozen exit hypothesis with unchanged entry/initial risk, cost-aware stop and preserved far TP. Include all displaced winners, subsequent entries, gaps and modification latency. Compare against baseline and plain BE as a negative control. Treat thresholds +1R/+2R as retrospective discovery, not validated optima. Do not deploy BE or partial TP from MFE counts. At minimum lot, partial-close feasibility must also be checked.

Evidence: `data/b1_scrutinize_2026-09-26/excursions.json`, `retrace.json`, reproducible probe scripts in same folder.

## Major — direction filters reverse between regimes; more tuning needs fresh validation

`inputs/run.py:35` allows both directions. Saved `directions.csv` shows primary longs +12.40R and shorts −4.45R; continuous February–September longs −3.85R and shorts +30.15R. Dropping shorts based on the latest period would discard the historically stronger direction in the longer run. The previously tested H1 trend filter (`profit_challengers.py:33`) already loses −8.82% in primary.

Change: do not switch to long-only or reuse that trend filter. If investigating breakout quality, freeze one causal hypothesis such as a retest entry with an expiry, log rejected/missed winners as well as avoided losses, and validate on new regimes. This is a research proposal, not evidence of improvement.

Primary is already exposed (`profit_challengers.py:161`). Current 87 baseline primary trades are also below frozen `config/B1-FINAL-v1.yaml:63` requirement of 100 closed OOS trades. Selection tests prevent code-level leakage, not researcher adaptation after reading results.

## Integration boundary — research is not the running B1 bot

`main.py:34` initializes XAUUSDSniperStrategy, `:84` checks its signals, `:118` sends an insight without a B1 execution adapter or broker-approved B1 order in that path. `mql5/B1FinalValidationEA.mq5:3` explicitly describes a tester-only no-order parity probe. No claim is made about which external process is currently running.

Change: maintain explicit research/alert/execution status. Before any later Demo execution, add the canonical B1 orchestration path, broker admission, persisted risk state, approved/executed-order notification and tester parity. Editing a research candidate does not modify this runtime automatically.

## Validation and decision

Ran 29 focused tests (`tests.test_profit_challengers`, `tests.test_b1_final`, `tests.test_b1_d_ticks`), all passed. Reviewed selector tests: synthetic metrics exercise selection isolation, not profitability; runtime replay tests exercise minlot and risk-state behavior. Ran excursion/retrace and strict-expiry diagnostics against saved ledgers/bars. No fresh profitable candidate backtest claimed; no live orders, new funding, risk increase or production code mutation.

Priority: executable sizing → canonical model/costs → one exit counterfactual → one retest-entry hypothesis only if exit fails → genuinely fresh chronological validation. [MT5 testing documentation](https://www.mql5.com/en/docs/runtime/testing) explains real-tick versus generated-price testing; a public OHLC replay is not tester execution proof.

Verdict: **rework before promotion** — current apparent edge is thin, execution contracts differ, and the $100 account admits zero trades.
