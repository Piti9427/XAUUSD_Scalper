# Python refactor and Exness readiness — 2026-09-13

**Verdict: refactor verified locally; NOT READY for real-money execution or trustworthy profitability certification.**

Use the existing **MT5 desktop on this Mac (Wine)** for the next read-only data check; a separate Windows machine is not established as necessary. The supplied screenshot shows **Demo Pro**, server `Exness-MT5Trial17`; it is not evidence of a funded live account. No supplied password was saved to source, configuration, reports or commands. No broker order, login with supplied credentials, Telegram send or deployment was performed.

## What changed

- [Detector](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/detection.py:206): stop at the nearest matching swing instead of materializing every previous swing price. Same selection semantics; original breakout fix retained. This removes repeated pandas row construction from the measured hot path, without adding NumPy/Numba dependencies or another engine.
- [Live loop](/Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py:80): offload blocking news fetch and chart rendering through `asyncio.to_thread`; propagate cancellation and close SQLite on loop cleanup. Broker calls and SQLite remain on the original thread and are not parallelized. Native MT5 calls can still block the loop; this is a scoped async improvement, not a claim that the entire call path is non-blocking. Cancelling a thread await does not terminate its underlying sync operation; news retains its existing network timeout. See [Python task documentation](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread).
- [CSV loader](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/run_backtest.py:22): accept plain UTC MT5 exports as well as Yahoo multi-header data. Previously the multi-header reader consumed the first broker data row as a header (reproduced 23 rows instead of 24). Runner now labels M15 as diagnostic proxy, without claiming parameter adaptation or M5 equivalence.
- [Read-only probe/exporter](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/mt5_readiness.py:1): inspect the terminal's current account, symbol contract/lot settings, quote and position/order counts; export closed M5/H1 bars with UTC timestamps and SHA-256 metadata. No `order_send`, login switching or Market Watch mutation. `live_ready` is always false: successful data collection alone cannot certify this bot.

## Performance before/after

Baseline is the working tree **after the previous debug fixes**, frozen before this performance refactor at `.scratch/python-readiness/baseline/detection.py`; it is not a different trading strategy. SHA-256: `8504b10e7b35898761055def61ae777a52e69ed694d5363b0e762b1ff1e75c8e`. Current detector: `a9d1b0f364f8724e26406a2300651fb4504454d4145ae1be4111276583d7f4de`.

Same local data, parameters and environment; median of three unprofiled runs per variant. Final measurement was rerun without the concurrent profiler used during exploratory measurements. Python 3.14.6; platform `macOS-26.5.1-arm64-arm-64bit-Mach-O`. Source/data hashes, every timing, detector stream hashes and trade records are in [results JSON](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/2026-09-13-python-refactor-results.json:1).

| Parameter profile | Before | After | Speedup | Behavioral check |
|---|---:|---:|---:|---|
| v1 | 2.814 s | 0.983 s | 2.86x | All 4,417 detector results, trade ledger and summary identical |
| v2 | 5.024 s | 1.208 s | 4.16x | All 4,340 detector results, trade ledger and summary identical |

`cProfile` established the bottleneck before changes: 23.307 s total, 21.025 s detector, 394,340 pandas indexing calls. Exploratory after-profile: 6.553 s total, 4.254 s detector, 83,336 indexing calls. Use the isolated medians above for speedup claims. A 500-M15-bar / 13,608-H1-bar `tracemalloc` sample peaked at 1,566,879 bytes before and 1,565,161 after: essentially unchanged Python heap, not process RSS or proof of lower native memory use.

## Executed backtest — diagnostic only

Input: Yahoo `GC=F`, 4,432 M15 bars from **2026-03-10 04:00 UTC to 2026-05-18 14:15 UTC**; H1 has 13,608 bars from January 2024. No broker XAUUSD M5 data exists locally. M15 bar-count windows cover different clock durations from M5. No fee/slippage model or historical news simulation certifies net results.

| Legacy simulator output | v1 | v2 |
|---|---:|---:|
| Initial balance | $10,000 | $10,000 |
| Trades | 0 | 3 |
| Wins / losses | 0 / 0 | 2 / 1 |
| Reported win rate | No observations | 66.67% |
| Reported P/L | $0.00 | -$0.19 |
| Reported PF | Not meaningful | 1.00 rounded |
| Reported closed-balance drawdown | 0% | 0.50% |
| Reported average R | No observations | 0.00R |

These are **outputs from a simulator with reproduced defects**, not validated economic performance. Identical before/after output verifies a refactor, not correctness of the inherited execution model.

Monthly breakdown of the same v2 ledger, by exit month; not independent walk-forward tests:

| Available interval | Trades | Reported P/L | Coverage |
|---|---:|---:|---|
| March 10–31 | 1 | +$25.00 | Partial month |
| April 1–30 | 1 | +$25.06 | Calendar month span; feed/session completeness not certified |
| May 1–18 | 1 | -$50.25 | Partial month |

Both winners and the loss entered in the London session. This sample provides no separate NY-entry or regime evidence. Three trades cannot establish a robust edge; changing capital or tuning parameters to improve this sample would not fix the measurement defects.

## Blocking differences and reproduced defects

| Area | Current evidence | Required before live execution |
|---|---|---|
| P/L calculation | [Backtester:252](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/backtester.py:252) uses current balance × configured risk, not executed volume. Fixture reports $100 instead of $92.80 from entry/exit × 0.08 lots × 100. | Use actual filled volume, frozen entry risk, contract/currency conversion and costs. |
| SL/TP order | [Backtester:214](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/backtester.py:214) chooses TP first; orchestrator chooses SL first. Same candle hitting both records a win despite stop-first state transition. | One authoritative execution outcome and explicit intrabar ambiguity policy. |
| Fill-bar close | [Backtester:208](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/backtester.py:208) requires a previously open position. Fill then stop in one bar produces zero closed trades and unchanged balance. | Record fill and close events even within one bar. |
| H1 causality | [Backtester:138](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/backtester.py:138) passes current-hour H1 before close. Repro observes H1 01:00 at M5 01:15. Live passes its fetched H1 without closed-H1 selection. | Align closed-bar availability across both paths; replay with causal data only. |
| Actual account risk | [Live account:64](/Users/nopparuj/my-agents/XAUUSD_Scalper/smc_main.py:64) is hardcoded to $10,000; no broker account reconciliation. Risk/lot/contract assumptions are not sourced from Exness. | Read actual equity, symbol constraints, margin and account currency; verify risk rejection against those values. |
| Live/backtest parameters | Live detector defaults sweep→MSS/FVG to 6/3 bars; v2 backtest passes 8/4. Live TTL default 4, backtest orchestrator default 3. Local settings still contain v0 strategy fields and `max_spread=30`, while SMC compares price-distance spread. | One reviewed SMC parameter set with explicit units shared across live/replay. |
| Fills/partial exits | Orchestrator infers fills from OHLC; [partial volume:98](/Users/nopparuj/my-agents/XAUUSD_Scalper/scripts/smc/orchestrator.py:98) rounds to two decimals and clamps remainder to 0.01. | Reconcile broker tickets/fills, lot steps, partial rejection and restart state before emitting execution milestones. |
| Costs/news | Backtest lacks historical spread/slippage/commission/news behavior matching live. | Broker bid/ask or tick data, fee model and timestamped news corpus; baseline and stressed-cost runs. |

Executed [four counterexamples](/Users/nopparuj/my-agents/XAUUSD_Scalper/docs/reviews/reproduce_backtest_readiness.py:1). The broader ledger/account changes above were not silently mixed into a performance refactor because they change financial behavior and require their own reviewed execution contract.

## Local Mac correction

User clarified that MT5 is on this Mac. Read-only filesystem inspection confirmed `/Applications/MetaTrader 5.app`, bundle `net.metaquotes.wine.MetaTrader5`, version `5.0.5834`, and `terminal64.exe` in `~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5`. No `python.exe` or `python3.exe` was found in the inspected Wine drive outside system/history/cache directories. Native macOS Python lacks the MetaTrader5 package.

MetaQuotes documents that its Mac installer runs MT5 inside Wine: [official Mac installation](https://www.metatrader5.com/en/terminal/help/start_advanced/install_mac). This proves local terminal availability, not Python IPC compatibility. A Python environment in the same Wine prefix is a candidate to validate; it was not installed or tested. Windows remains a fallback for Python integration, not a requirement inferred merely from the user's Mac.

The computer-use attempt to inspect MT5 timed out (`timeoutReached`); process listing was denied by the local sandbox. No current account connection or historical export was verified through the GUI. No new runtime was installed and no Wine-prefix configuration changed.

## MT5 desktop vs broker website

| Choice | Fit for this repository | Decision |
|---|---|---|
| MT5 desktop + compatible Python runtime | Existing connector/adapter architecture. MetaQuotes Python package communicates directly with the terminal and exposes account, history and order APIs. | Keep local Mac terminal; validate Wine Python IPC or export data first. Windows is a fallback. |
| Exness browser terminal | Useful for manual account/order inspection. No browser execution adapter exists in this repository. Exness states EAs operate on desktop terminals, not mobile/web; this Python program is not itself an MQL5 EA. | Manual cross-check, not bot backend. |

Sources: [MetaQuotes Python integration](https://www.mql5.com/en/docs/python_metatrader5), [Exness desktop automation support](https://get.exness.help/hc/en-us/articles/360019530859-Using-Expert-Advisors-EA). The screenshot identifies Demo Pro, not a live-account connection. The public broker web URL was inspected without logging in; it does not provide terminal access to this environment.

## Broker data collection and test intervals

The following command is for a compatible **Windows Python environment**, potentially inside the same Wine prefix after compatibility is verified; it does not run directly in native macOS Python. With MT5 already logged into the intended Demo account, run the **read-only** command below from this repository. It uses the current terminal session and does not need a password in the command. Ensure `XAUUSD` is the exact visible symbol. This command has **not** succeeded against the installed Mac/Wine terminal.

```powershell
py scripts/mt5_readiness.py --symbol XAUUSD --start 2025-09-01 --end 2026-09-12 --output-dir data/exness-readonly
```

Use an isolated Python environment with repository requirements installed on Windows. The local Mac has pandas, NumPy and requests but lacks MetaTrader5, PyYAML and python-telegram-bot. Local probe execution returned **exit 2 / METATRADER5_UNAVAILABLE**; no account snapshot or broker history was collected.

The exporter requests 30 extra days for warmup and writes M5/H1 CSVs plus `snapshot.json`. Inspect actual returned coverage: the terminal can limit available history; requested boundaries do not prove completeness, and market closures can leave gaps. See [MetaQuotes history limits and UTC requirements](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py).

Planned coverage, **not executed on Exness data**:

- Historical diagnostics across September 2025–May 2026: month, London/NY, BUY/SELL and volatility groups, after repairing the ledger and causal data handling.
- Preserve the previously agreed June–July 2026 selection / August 1–September 11 holdout for comparisons intended to align with Master. Do not tune on holdout; broker data and model consistency must be established first.
- Compare fixed rules on M5 and M15 separately; TTL and setup windows must have explicit timeframe semantics. H1 is bias input, not an equivalent execution timeframe.
- Freeze code/config, then forward Demo with broker acknowledgements versus notifications, rejected orders, partial fills, restart recovery and realized P/L reconciliation. No numeric readiness threshold or real-money rollout is claimed from the current three-trade proxy sample.

## Validation and handoff

- 62 unit tests passed; async tests first failed for event-loop-thread work and swallowed cancellation, then passed after changes. Broker-export loader test first exposed dropped row, then passed with 24/24 rows and UTC timestamps.
- Repeated before/after full-dataset detector output and trade/summary equivalence passed. Original breakout/cross-level regressions remain covered.
- Read-only collector tests cover no trading/login/symbol-selection calls, shutdown, missing broker-state failure, closed-bar filtering and export/loader round trip.
- Final diff reviewed; no dependency churn. No MT5/Pine/live execution result is asserted.

**Next step: repair the four reproduced accounting/causality defects and unify broker risk/config, while collecting Demo MT5 history read-only. A working Python-to-Mac/Wine terminal connection or broker-exported artifacts is still needed. Real-money execution remains blocked by correctness and missing broker evidence, not by Python speed.**

## Superseding Demo continuation — 2026-09-13

The four legacy accounting/H1 counterexamples above are now fixed and covered by regression checks; cached fractal confirmation also corrected. Suite: 67 passed. Subsequent proxy output changes intentionally: v2 4 closed trades, -USD 34.35, PF 0.53. Previous performance-only parity measurements remain historical, not claims for these accounting changes.

Chrome access verified Demo balance/equity USD 2,254.16 and XAUUSD OHLC. Complete broker history still unavailable; no Exness backtest or orders executed. Risk sizing/partial-volume issues, costs and execution reconciliation still block readiness. Current report: [Exness Demo status](2026-09-13-exness-demo-backtest-status.md).
