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
