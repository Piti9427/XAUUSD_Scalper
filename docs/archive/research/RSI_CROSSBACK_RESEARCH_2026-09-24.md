# RSI cross-back research — 2026-09-24

Follow-up: [the complete selection rerun](BACKTEST_SELECTION_2026-09-24.md) now includes a fresh 120-spec baseline using the current engine, RSI, all three top-down policies, and the five declared handoff variants. It resolves the older-engine comparison limitation described below; RSI remains rejected.

## Decision

Reject `RSI14_CrossBack_30_70_M15` as a BotTradeGold challenger. Do not connect it to Demo or real-money execution. No existing strategy has passed the independent Demo qualification protocol; this research does not promote another strategy.

## Declared contract

This is a new research assumption, **not** a reproduction of the video's unpublished code. On consecutive complete M15 Bid bars, RSI14 crossing from `<=30` to `>30` signals long; crossing from `>=70` to `<70` signals short. Enter at the next exact M1 open, paying Ask for buys and receiving Bid for sells. One position at a time. No averaging, grid, martingale, or lot schedule. Both modes use the existing 2 ATR stop and 2R target; native mode also excludes sideway entries as in the BotTradeGold engine. No thresholds or exits were tuned after seeing the result.

The signal implementation is isolated in `scripts/research/rsi_reversal.py`; the frozen 120-spec registry and live order path are unchanged. The video's summary does not provide enough detail to claim parity with its RSI/grid strategy.

## Evidence

- Pinned Dukascopy-derived Bid/Ask M1 OHLC, source revision `922f83a60cc574e7395fb27397077288055a1ef6`. This is not real ticks or target-broker execution. `acquire` verifies local CSV hashes. Outputs record input hashes, code hashes, yearly data audits, and reconciled trade logs.
- Exact comparison: 2025 plus partial 2026 (source through 2026-08-20), same source bytes, code, years, zero added commission/slippage/swap, and execution engine as the completed 120-spec baseline. `matrix.audited_run` checks all 480 baseline trade logs before writing the combined 121-spec comparison. Historical Bid/Ask spread is included.
- Candidate common: 989 trades, net `-2668.82 USD/1 oz`, PF `0.774`; native: 883 trades, net `-2626.95 USD/1 oz`, PF `0.752`. Ranked 121 of 121 by net in each mode for that comparison. Two-year `INSUFFICIENT` labels are mechanical sample-length labels, not evidence of viability.
- Separate 2010–2025 run: common 9,112 trades, net `-4257.21 USD/1 oz`, PF `0.855`; native 8,116 trades, net `-3701.77 USD/1 oz`, PF `0.856`. Both have 0 positive years of 16 and classify `REJECT_RESEARCH`. The 2025 rows match the exact-comparison run. This longer run is candidate-only because the historical 120-spec baseline was produced by an older engine revision; do not present its ranking as an exact same-code comparison.

These are fixed 1 oz-equivalent price P/L figures, **not** account returns. Extra Exness commission, fill slippage, swap, broker-valid lot sizing, margin/stop-out, continuous account drawdown, and prospective performance remain unmeasured. Adding nonnegative costs cannot rescue this negative historical net, but historical rejection does not prove every possible RSI rule fails.

## Reproduce

Run `python -m scripts.research.rsi_reversal --help`. Completed local artifacts:

- `data/research_results/rsi-crossback-2025-2026-20260924/` — `comparison.csv`, candidate annual/summary/trades, manifest, data audit, and `COMPLETE`.
- `data/research_results/rsi-crossback-2010-2025-20260924/` — candidate annual/summary/trades, manifest, data audit, and `COMPLETE`.

The generated result directory is ignored by Git; retain its manifest and trade logs together when sharing or archiving. Source CSVs live in the existing verified Dukascopy cache outside this repository. The unrelated `data/research_cache/` user files were not touched.

## Next gate

Keep the three frozen Validation Challengers only as hypotheses for post-freeze Exness Demo real-tick validation. Follow `QUALIFICATION_PROTOCOL.md` for target-account specs, measured costs/fills, 0.5% risk sizing, account drawdown, twice-cost replay, and statistical/portfolio gates. Current verdict: **no Demo strategy bot candidate and no real-money strategy approval**.
