# BUY/SELL challenger against trial30

Owner requests measured improvement over running trial30 while Demo watcher continues. Owner confirms public replay -> qualification/resume and runner cycle/CLI seams; review base develop. Runtime replacement depends on qualified frozen results and independent verification; no order forcing or risk relaxation.

Freeze96 contracts before evaluating: D48 prior-channel/ATR14 SMA, BUY filters off/EMA50 rising4bars/prior completed UTC up-day/body>=half-range/close in upper20%/EMA+prior-day; signed breakout-depth0 or0.15ATR for both sides; TP3 or6.25ATR; BE or cost-covered candle trail; activation1 or1.5 initial cost-inclusiveR. Entry immediate first post-close quote<=90s. EMA warmup50. Prior-day label uses UTC day of bar close and completed prior-day data. SELL never disabled by BUY filters. Filters never guarantee trades: ledger must prove both executed sides in each scenario/window.

All candidates fixed0.01, SL2.5ATR, admission<=10% equity, daily20%, no recovery, resetfalse. Only completed canonical UTC Bid M15. Broker Bid/Ask used for fills/marks, adverse costs reserved. Reuse existing audited replay, unchanged. No runtime edits before winner exists.

Reference trial30 is replayed full, first_half, second_half on identical data and base/stress, including previously missing second_half. Each candidate evaluates all6 scenarios without early screening. Each must have net>0 and strictly greater net/WR/realizedRR than trial30, RR>1, DD<=trial30 and<=30%, >=60 full/20 half trades and at least1 actual BUY plus1 SELL. Sparse side counts reported, not hidden or treated as independent validation. Lowest worst-window stressDD wins; tie highest fullstress net then trial ID.

Loop is finite and resumable:96 hypotheses, progress after each trial, both halves always evaluated. Immutable protocol/source snapshots/input hashes, per-scenario ledger/equity and completion hashes. Resume validates artifact sets/hashes and recomputes selection metrics from artifacts. No tuning from untouched validation; current184-day and existing public discovery tapes already reused. Historical winner alone cannot prove future performance. Freeze qualified contract, cross-check independent discovery, then holdout/forward validation and runner parity before any replacement. Commission0 assumed and swap not modeled; actual tariff/spec/fees remain separately evidenced.

Command:

```bash
.venv/bin/python -m scripts.research.bidirectional_campaign --output data/strategy_bidirectional_trial30_campaign_2026_10_01
# Resume exact source/input protocol only:
.venv/bin/python -m scripts.research.bidirectional_campaign --output data/strategy_bidirectional_trial30_campaign_2026_10_01 --resume
```

If no contract qualifies, preserve running strategy and report failure. Do not call highest-profit rejected row an improvement. Further rounds need distinct stated hypotheses and new frozen catalogs, not unbounded retries against same tape or relaxed gates.

## Round2: alternate BUY setups, same gates

Round1 completed96, zero qualified. New96-contract catalog `--catalog buy_setups` frozen before its evaluation. SELL keeps D48 breakout; BUY replaces upward breakout with either lower-wick sweep (low<prior48low, close>prior48low, high<=prior48high; boundary lower channel), or EMA50 rising4bar pullback (previous candle red, currentclose>previoushigh and>EMA; boundary previoushigh). Only completed bars, SELL precedence on conflicts. BUY filters off/prior-day/body; signed boundary depth0/0.15ATR, TP3/6.25, BE/trail1/1.5R. ATR stops unchanged; no wick/trigger SL substitution. Both-side executed-count and all6 performance gates unchanged.

Output `data/strategy_bidirectional_setups_trial30_campaign_2026_10_01`; separate source/protocol snapshot, no overwritten round1. Protocol2 supports setup catalogs; protocol1 resume requires its original source, never silently migrates source hashes. No holdout consumed by either round.

## Review corrections

Resume now replays each completed scenario from audited ticks and compares entire saved result (including all-tick DD, ledger and compressed equity) against fresh output. This intentionally spends replay time; compressed checkpoints alone cannot reconstruct authoritative all-tick DD. Matching artifact hash/marker metadata is insufficient. Source changes still reject ordinary resume. Already completed runs are independently verified using hashed original source snapshots before their results are published.

`--limit` is an interruption/testing budget, not winner selection. Until all96 complete, verdict stays `DISCOVERY_INCOMPLETE`; qualifying prefix can only expose `provisional_leader`, never `frozen_discovery_winner`. Final winner is eligible only after complete frozen-catalog comparison.
