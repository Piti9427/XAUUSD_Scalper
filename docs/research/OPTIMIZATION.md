# BotTradeGold retrospective variant selection

`scripts.research.optimize` compares the completed 17-base/120-spec Bid/Ask backtest without rerunning its price simulation. It first calls `matrix.audited_run`, which checks the baseline `COMPLETE` marker, source/code manifest, all annual/summary rows, and every trade log. The optimizer requires the repository code that produced that baseline; changing the backtester requires a new baseline.

```sh
.venv/bin/python -m scripts.research.optimize \
  --baseline /absolute/path/to/verified-baseline \
  --output /absolute/path/to/new-output
```

The default experiment uses `native` mode, 2010–2017 as the first training window, and annual one-year tests for 2018–2025. At each fold, only earlier years enter selection. The fixed objective ranks candidates by median annual training net, then total training net, positive training years, training trades, and name. No post-result profitability gate or per-year retuning is applied. A selected strategy may have negative training net; that failure is visible in `selected-folds.csv` and must not be hidden by altering the objective after seeing test results.

Each of the 17 base configurations competes with its five single-filter variants. The global comparison considers all distinct contracts among the 120 specs; identical aliases are removed from that pool and recorded in `manifest.json`. The output contains every candidate/fold, the selected candidate for each base/fold and global/fold, a cross-fold summary, and a manifest with input/output hashes. `COMPLETE` is written last. Outputs are immutable and research-only. A positive cross-fold total is **not** a live trading signal.

All historical years, including these test years, were previously exposed during BotTradeGold research. The strategy rules are mostly reconstructions. Thus these folds test chronology of the selector but are not untouched out-of-sample validation. Native mode uses a provisional regime filter and historical Bid/Ask M1 OHLC; non-spread broker costs, real ticks, and actual Exness fills are absent. Results are USD price P&L for 1 oz-equivalent exposure, not account profit. Reserve genuinely new data after freezing rules and verify original-code parity, broker costs/ticks, parameter stability, and demo forward behavior before any live decision.

## Declared parameter experiments

`scripts.research.param_sweep` runs additional, explicitly declared risk/lookback/filter combinations through the same Bid/Ask M1 signal and execution engine. Input parameters live in `handoff-parameter-candidates.json`, which cites their handoff line references and states every known rule mismatch. These five candidates are *not* exact reproductions of the historical chat results. The script verifies SHA-256 metadata for all cached source CSVs before running; it writes annual metrics, complete trade logs, source/code/config hashes, and a final `COMPLETE` marker.

```sh
.venv/bin/python -m scripts.research.param_sweep \
  --spec-file docs/research/handoff-parameter-candidates.json \
  --cache /absolute/path/to/verified-price-cache \
  --output /absolute/path/to/new-output
```

The default experiment uses complete years 2010–2025, native mode, historical Bid/Ask spread, and zero *unmeasured* non-spread costs. It also applies the same fixed walk-forward objective to these five declared configurations for 2018–2025 and retains each year's intratrade equity drawdown in the pooled summary as `max_annual_equity_dd`. The output audit requires every candidate/year pair and reconciles all trade logs before writing `COMPLETE`. It cannot model original one-opposing-candle State10, original ORB noon cutoff, original GSS impulse/body thresholds, or standalone FVG CE50 without further verified rule definitions and code. Results remain exploratory even when net positive.
