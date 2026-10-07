# Measured two-sided geometry/timing/exit tuning

Owner invokes implement and requests real measured improvement, never fabricated metrics. Prior agreed replay -> qualification/resume seams and develop review base remain. Starting HEAD7f8e88a. Running trial30 Demo unchanged while research executes. No qualified strategy has been found yet.

Prior288-contract full scenarios failed DD575/576, WR542/576, profit512/576, RR335/576;46 lacked actual fills both sides. Counts overlap; they are failed scenario checks, not distinct failed trials. Hypothesis: quality filters alone do not fix stop/admission geometry, poor entry timing or persistent failed breakouts.

## Frozen tuning loop

One288-contract catalog, all declared before replay;280 new against prior three two-sided catalogs,8 control repeats at trial193..200. Repeats validate source/data/math continuity; not counted as new discoveries. No random mutation, no outcome-conditioned removal of failed contracts.

1. Stop geometry96: BUY breakout/lower_wick; symmetric guard off/body_dominant; stop atr/trigger/boundary; reward distance1.5/2 times immutable rounded stop distance; BE/trail at0.5/1R. BUY prior-day filter, immediate entry, depth0.
2. Entry timing96: confirm/retest; stop atr/trigger/boundary; symmetric guard off/body_dominant; reward1.5/2 actual stop distances; BE/trail1R; BUY filter off/prior-day, upward breakout.
3. False-breakout exits96: entry immediate/confirm; failed_closes0/1/2; stagnant0/4 completed bars (exit only if net<=0); target3/6.25ATR; BE/trail1R; BUY filter off/prior-day, upward breakout. ATR stop.

Existing replay rules reused without changing fill/risk math. ATR stop2.5ATR; trigger stop behind completed execution-trigger candle low/high one tick; boundary stop beyond crossed known setup boundary0.5ATR. Lower-wick BUY boundary prior48low; SELL breakout prior48low; no future candle extrema. Confirm next completed close beyond frozen boundary; retest within4 completed bars touched boundary and close beyond, cancel invalid/expired setup. Earlier protection does not widen stop; TP remains active. Exit clauses cannot force a new entry on same quote.

All single-position fixed0.01, risk<=10%, daily20%, no recovery/reset/martingale; completed15/15 M1 Bid M15 UTC, executable actual Bid/Ask, first entry quote<=90s, margin and cost-inclusive checks. SL changes remain research-only. Actual broker stop/freeze/restart parity required before runtime adoption.

## Comparison and proof

Trial30 baseline replayed same source/ticks/broker/cost/window for all6 scenarios: full/firsthalf/secondhalf, base/stress. Strict net/WR/RR greater than trial30; RR>1; DD<=trial30 and<=30%; >=60 full/20 half trades; at least1 executed BUY and SELL in every scenario; cap<=10%. Existing selection unchanged: lowest worst-window stress DD, then fullstress net, then trial ID. Entire288 must finish before winner freezes. Partial prefix remains DISCOVERY_INCOMPLETE.

Protocol3 stores all contracts, source/input hashes and costs before trials. Scenario files retain full trade ledger/equity and completion hashes. `--resume` verifies protocol/source/input and artifact hashes then replays entire saved scenario, requiring exact equality including all-tickDD. Verdict records verified_scenarios and FRESH_REPLAY_MATCH only when all baseline/evaluated scenarios were actually compared; initial pass reports INITIAL_REPLAY. All288 verification requires1734 scenarios (288*6+6 baseline). No new source edits during replay/verification.

Same reused184-day discovery tape2026-03-28 through before2026-09-28. Base includes actual spread, modeledcommission0/slippage0, no swap. Stress extra_spread0.20USD/oz/adversemarketfill0.10USD/oz. Costs are modeled, not actual account all-in parity; nonzero observed BUY swap is unmodeled. Reproducible discovery improvement is separate from untouched/forward validation. Never tune from sealed holdout; if qualified, freeze and independently validate before runtime substitution. If none qualifies, report unmet objective without fabricating/promoting a rejected row.

```bash
.venv/bin/python -m scripts.research.bidirectional_campaign --catalog tuning --output data/strategy_bidirectional_geometry_tuning_2026_10_01
.venv/bin/python -m scripts.research.bidirectional_campaign --catalog tuning --output data/strategy_bidirectional_geometry_tuning_2026_10_01 --resume
```

Output/protocol version separate from previous catalogs. Starting fixed review base develop=a24114097988e4b3669d48d6be19773c502c3924. Public tests cover literal stop/target math, catalog budget/resume-verification bookkeeping and existing trading/qualification/corruption/partial-winner seams. No Telegram/MT5 order APIs in research loop.
