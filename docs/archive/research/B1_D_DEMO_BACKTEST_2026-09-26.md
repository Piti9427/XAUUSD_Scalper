# B1 / D reconstructed Exness Demo replay — 2026-09-26

Verdict: **EXPLORATORY_POSITIVE / BROKER_REAL_TICK_VALIDATION_INCOMPLETE**.

Follow-up same day: authenticated target Demo connected and 5,708,205 real ticks captured. Account-sized B1 rejected all 101 September signals by minimum-lot risk; D had no signals. See [real-tick account result](B1_D_EXNESS_REAL_TICKS_2026-09-26.md). Earlier connection blocker below is resolved; proxy results remain unchanged.
User selected B1 and D on 2026-09-26 and explicitly authorized repository reconstruction as a separately versioned baseline. Replaces Donchian20_H4 as the active research shortlist. Neither candidate qualifies for automated Demo deployment or real money from these results.

## Frozen contract

Version: `b1-d-reconstruction-v1.0.0`. Both use complete UTC M15 Bid bars, Wilder ATR14 and repository RSI14 arithmetic seed (first delta is zero). B1: previous 30 highs/lows excluding current bar; strict close breakout; buy RSI <=75 / sell RSI >=25; SL 2.5 ATR / TP 2.5R. D: range >=1.5 ATR and body >=50% seeds expansion; 1–2 opposing candles counted by repository continuation state; close beyond seed extreme within six bars; seed opposite extreme invalidates; same-direction current three-bar FVG >=0.05 ATR and same RSI guard; SL 2 ATR / TP 3R. Exact continuation permits intervening nonopposing candles; no claim of recovering original D.

Both directions, one position per independently simulated candidate; next exact M5 open after signal close; no trailing/BE/scale-out/session filter. **All regimes eligible**: intentionally remove older native simulator's provisional SIDEWAY exclusion because new handoff prohibits unvalidated regime routing. This is not an exact rerun of earlier B/D native research or reported handoff totals.

## Data and execution limitations

Existing broker export: `data/exness-demo/XAUUSDm_M5.csv`, metadata server `Exness-MT5Trial7`, symbol `XAUUSDm`, clock `ok`; 79,999 M5 bars, 2025-08-04 23:00 UTC through 2026-09-21 04:50 UTC. Metadata belongs to prior export, not current account verification. Only complete three-M5 M15 aggregates accepted. Missing next entry bars skipped; incomplete aggregates absent.

No historical Ask/tick path. Ask OHLC is **synthetic Bid + fixed scenario spread**, not exported broker quotes. Long entries Ask/exits Bid; short entries Bid/exits Ask. Adverse stop gaps and stop-first unresolved M5 collisions. M5-close marked drawdown omits intrabar extrema; sample-end liquidation included. Existing research engine runs on M5 observations here; its original M1 execution claims do not apply.

Fixed **1 oz price exposure**, NOT broker-sized lots, account return, margin validation or risk-qualified trades. Commission/swap/slippage remain zero/unmeasured. Constant spread shifts can change both fills and position occupancy; sensitivity need not be monotone and D P/L may stay unchanged while fills and stops shift together. Real fees can materially reduce these results.

## Observed results

| Candidate | Spread price scenario | Trades | Net USD / 1 oz | Total R | PF | M5-close max DD USD / 1 oz |
|---|---:|---:|---:|---:|---:|---:|
| B1 | 0.00 (optimistic diagnostic) | 473 | 2,437.25 | 90.14 | 1.304 | 686.57 |
| B1 | 0.30 | 479 | 2,159.11 | 80.55 | 1.263 | 686.57 |
| B1 | 0.60 | 491 | 1,626.99 | 57.97 | 1.191 | 1,098.65 |
| B1 | 1.00 | 490 | 1,648.90 | 58.85 | 1.194 | 1,098.65 |
| D | 0.00 | 15 | 337.39 | 9.00 | 2.503 | 183.66 |
| D | 0.30 | 15 | 337.39 | 9.00 | 2.503 | 183.66 |
| D | 0.60 | 15 | 337.39 | 9.00 | 2.503 | 183.66 |
| D | 1.00 | 15 | 286.68 | 5.00 | 2.209 | 183.66 |

At spread 0.30, B1 partial 2025: 175 trades, +62.40 USD/+6.66R; partial 2026: 304 trades, +2,096.71 USD/+73.90R. **97.1% of net comes from 2026**. D: 2 trades in 2025, 13 in 2026. D sample far too small for confidence. Both periods were exposed; no untouched OOS/forward evidence.

## Verification and artifacts

Command:

```bash
.venv/bin/python -m scripts.research.b1_d_demo \
  --output data/b1_d_demo_2026-09-26_proxy_verified
```

Output: immutable versioned directory containing manifest with input/code SHA-256, eight trade ledgers, summary and COMPLETE. Writes stage in `.partial`; expected CSV columns/nonempty files validated before final rename. Existing final/staging directories refuse overwrite.

- `.venv/bin/python -m unittest tests.test_research tests.test_research_matrix`: 34 passed.
- `.venv/bin/python -m unittest discover -s tests`: 500 passed.
- Executed deterministic fixture differential: M5 aggregation matches original M1-produced M15 OHLC/ATR/RSI/body/FVG and both B/D signals; prefix signals unchanged by future bars. Passed.
- MT5 read-only probe inside sandbox: Wine `Can't check in server_mach_port`, failed before connection.
- Approved unsandboxed read-only probe: subprocess timeout at 25 seconds. **Current target account unverified; no ticks downloaded; no order API invoked.**

## Remaining work

Restore responsive terminal/Python IPC, verify exact Demo identity and live symbol specs, capture historical Bid/Ask ticks and fees, then implement/replay account-sized risk flooring with 0.5% risk cap, margin/stop constraints and execution reconciliation. Preserve frozen reconstruction and report tick/M5 divergence rather than retune. Walk-forward/OOS and Demo forward remain incomplete. Existing qualification gates stay in force.
