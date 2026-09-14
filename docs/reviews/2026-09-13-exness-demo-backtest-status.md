# Exness Demo backtest status — 2026-09-13

**BLOCKED: broker-history backtest not executed. Real-money readiness: NO.**

## Verified account/data access

Chrome authenticated at https://my.exness.com/webtrading/ without entering or storing credentials. Selected Demo Pro_test, balance/equity USD 2,254.16, no open positions or pending orders observed. Selected Gold vs US Dollar / XAUUSD, M5. Visible OHLC table read successfully; chart clock states UTC.

Example observed broker bar: 2026-09-11 20:55 UTC, open 4348.472, high 4349.650, low 4347.562, close 4349.341. This is a spot quote observation, not a usable historical dataset or completed backtest. No trade placed.

The inspected chart menus expose table view but no CSV export. Browser content export returned unsupported. The table renders only a short virtualized viewport; no complete M5/H1 history was collected. The web script editor uses Indie, not Pine, and replay was disabled. No native strategy tester was observed in this web workflow.

Local MT5 is installed as a Wine application on this Mac. Native Python cannot import MetaTrader5; the attempted native-app UI connection timed out. These are current access blockers, not proof that Exness has no historical data.

## Corrections completed before trusting results

- Filled volume × contract size × price movement now determines realized cash, including partial exits. Budget percentage no longer fabricates PnL.
- Accounting observes actual orchestrator position evaluation, capturing fill-and-stop on the same bar.
- Exit attribution follows existing rollover-first, then SL-first precedence.
- H1 input requires H1 open time + one hour <= current M5 bar timestamp. This conservatively uses information available at bar open; it does not model tick-level event times.
- Cached fractals mask their final two unconfirmed centers; inputs match recomputing on the observed prefix.

Validation: four legacy counterexamples reproduced before changes. Afterwards `python3 -m unittest discover -s tests`: 67 passed; regression script passed; `git diff --check` passed. Tests cover exact cash, simultaneous SL/TP, same-bar closure, H1/fractal causality, partial plus final exit cash conservation.

## Diagnostic comparison — NOT Exness results

Same local GC=F M15 proxy, March 10–May 18, 2026; initial capital USD 10,000. Existing Python v2 parameters unchanged. These runs do not use the Demo balance or Exness prices.

| Metric | Before accounting/causality fixes | After |
|---|---:|---:|
| Closed trades | 3 | 4 |
| Wins / losses | 2 / 1 | 2 / 2 |
| Net PnL USD | -0.19 | -34.35 |
| Win rate | 66.67% | 50.00% |
| Profit factor | 1.00 rounded | 0.53 |
| Realized-balance drawdown | 0.50% | 0.48% |

Newly recorded March 12 fill-bar SL loses USD 47.55. Volume-based partial cash and subsequent sizing also change the ledger. Earlier performance comparison remains a historical benchmark for the performance-only patch; exact before/after output parity is not expected after these intentional accounting fixes.

Full executed output: `2026-09-13-corrected-proxy-backtest.txt`.

## Remaining financial blockers

Risk percentage and contract settings are not propagated to orchestrator sizing; minimum-lot risk and partial-volume rounding/clamping remain unresolved. Broker specification, historical Bid/Ask spread, commission and slippage not validated. Open exposure at dataset end is not marked to market; reported drawdown measures realized balance only. OHLC cannot establish actual intrabar fill ordering. Historical news and live broker reconciliation remain unverified. Therefore even corrected proxy metrics are diagnostic only.

Python SMC and Pine Master Pro v6 are separate implementations. Running this Python backtester does not certify Pine indicator parity. No strategy rewrite or port to Indie performed.

## Concrete next input

Export XAUUSD M5 and H1 from the connected Demo MT5 desktop: Market Watch context menu > Symbols > Bars > select symbol/timeframe/date range > Request > Export. Official instructions: https://www.metatrader5.com/en/terminal/help/trading/market_watch

Requested history: 2025-08-01 through 2026-09-11 inclusive, with August 2025 for warmup. Evaluate September 2025–May 2026 by month/quarter, June–July 2026 as development comparison, and August 1–September 11, 2026 as locked holdout. Do not tune on holdout. Save exports under `data/exness-demo/`, preserve original files and server timestamps; confirm broker timezone before UTC conversion. Native MT5 GUI exports differ from the Python collector's normalized CSV and must be inspected/normalized before loading.

Also obtain symbol specification (contract size, point, min/step/max volume) and account costs. Use USD 2,254.16 as explicitly labelled snapshot starting balance, not as historical balance. Tick/Bid-Ask data required for a stronger execution-cost check. Required comparison: per-period count, net PnL after costs, PF, drawdown, expected R, long/short, session, and cost sensitivity. No such Exness result exists yet.
