# B1/D reconstructed real-tick account replay — 2026-09-26

**Verdict: B1 NOT_EXECUTABLE_AT_CURRENT_RISK; D NO_SIGNALS_IN_WINDOW. Profitability INCONCLUSIVE.**

Authenticated MT5 using ignored repository `.env`. Exact login and server equality checked in process; account trade mode Demo, hedging, USD. Credentials/login not copied to artifacts. Fresh snapshot: Exness-MT5Trial7, XAUUSDm, balance/equity 1,173.46 USD, leverage 1:1000. Contract 100 oz/lot, volume minimum/step 0.01 lot, tick grid 0.001. No order API called; this is historical simulation using actual account specifications, not executed forward trades.

## Observed account result

Frozen `b1-d-reconstruction-v1.0.0`; same B1/D rules as [prior contract](B1_D_DEMO_BACKTEST_2026-09-26.md). All regimes, candidates independently simulated. Current balance is hypothetical historical starting capital; historical balance not inferred.

Risk cap 0.5% per setup = **5.8673 USD**. Lot always floored, rejected below minimum; no rounding up, no account-risk increase.

| Candidate | Signals, 1–25 September | Admitted trades | Rejected by minimum lot | Final balance | Profitability |
|---|---:|---:|---:|---:|---|
| B1 | 101 | 0 | 101 | 1,173.46 USD | Cannot estimate |
| D | 0 | 0 | 0 | 1,173.46 USD | Cannot estimate |

B1 nominal stop risk at minimum 0.01 lot: **14.24–48.11 USD**, median **20.59 USD**. Every signal exceeds 5.87 USD risk budget before fees. Cheapest observed setup would require approximately 2,847.94 USD capital at unchanged 0.5% cap before extra costs; this is a derived affordability threshold, not a recommendation to add funds. Account balance, risk, strategy stops and lot floor were not modified.

Additional 0.10R per-trade cost reserve gives same zero-trade account result. Zero trades means PF, win rate and expectancy unavailable; unchanged balance does not establish profitable or safe alpha.

## Data verification

Read-only broker capture contains **5,708,205 actual Bid/Ask ticks**, 2026-09-01 00:00:00.128 UTC through 2026-09-25 20:57:59.762 UTC. Daily source files include observed empty Saturdays. M1 history starts August for indicator warmup. Median/p99 tick spread 0.260 USD price distance in this sample.

Matched broker M1 minutes in scored window: **25,904/25,904**, zero broker minutes lacking ticks, zero tick minutes lacking broker M1. Seventeen M1 bars have OHLC difference exceeding one tick, max absolute difference 0.353. Reconstructed Bid M1 from ticks substituted into the feature calculation: **zero B1/D signal divergences**. Both audits saved. This proves minute coverage and signal agreement for this tape, not unobserved historical execution behavior.

Replay evaluates confirmed M15 bars, enters first real executable-side tick within 60 seconds after close, rejects missing entry quotes, and processes real tick barrier ordering. Long entry Ask/exit Bid; short entry Bid/exit Ask. Stops fill adverse actual tick; target conservative target price. Stop/target normalized to measured tick grid, risk recomputed before lot flooring. Tick equity marks include modeled swap and extra fee reserve.

## Costs and evidence limits

Actual spread included. Commission/fill slippage unmeasured. Present swap mode is points; sensitivity uses present symbol swap values, with explicitly assumed UTC-midnight/triple-day schedule. This is not verified historical broker rollover or realized fee evidence. Historical margin/leverage/stops changes and broker approval not simulated; no claim of execution qualification. With zero admitted trades these assumptions do not affect observed zero-account-trade result.

Period is historical/exposed, not prospective OOS. D's sparse behavior requires longer frozen observation; no parameter retuning done. No B1/D live runner deployed and no Demo order submitted. Cannot claim backtest-vs-executed reconciliation.

## Reproduce and inspect

Read-only connection:

```bash
python3 scripts/ops/run_b1_d_wine.py
```

Capture (new output path required):

```bash
python3 scripts/ops/run_b1_d_wine.py \
  --script scripts/ops/b1_d_capture_ticks.py \
  --output data/b1_d_exness_ticks_2026-09-26
```

Replay:

```bash
.venv/bin/python -m scripts.research.b1_d_ticks \
  --capture data/b1_d_exness_ticks_2026-09-26 \
  --output data/b1_d_exness_tick_replay_2026-09-26_verified
```

Existing capture/replay directories immutable. Finalized replay uses staged `.partial` output, CSV schema validation and directory rename before final completion is accepted. Captured files/checksums, account/symbol snapshot, replay code hashes, versioned specs and ledgers preserved under `data/`.

Validation: `python3 scripts/ops/run_b1_d_wine.py` observed `initialized=true`, `target_demo_verified=true`, `last_error=[1,"Success"]`. Four focused replay tests cover minimum-lot rejection, long Ask entry/TP gap handling, short Ask stop and extra cost reservation/UTC. Combined replay/research/shadow tests: 36 passed. Previous full repo suite: 500 passed; not rerun for this capture-only iteration.

## Connection blocker resolved

Previous 25-second probe timeout did not prove MT5 permanently unavailable. Current Wine Python startup succeeded; authenticated file-based probe with full 60-second API initialization allowance succeeded in under one second. `.env` values used only in child process environment. Exact cause of earlier timeout not isolated; do not attribute it solely to credentials or timeout duration.

## Next decision

Under existing account/risk settings, B1 cannot submit valid lots in observed period; D has no setups. Current result is sufficient to reject immediate B1 execution on this balance at this risk. Keep account risk unchanged. Any change to capital, risk percentage or stop contract is a separate user decision/new experiment. Longer historical replay or post-freeze shadow monitoring can collect additional evidence; neither can certify a strategy without admitted trades and execution-cost evidence.
