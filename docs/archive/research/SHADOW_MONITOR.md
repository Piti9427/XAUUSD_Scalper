# BotTradeGold read-only Shadow monitor

The scripts `scripts.research.shadow_capture` and `scripts.research.shadow_monitor` capture new target-account Demo ticks and audit signals for the three frozen Validation Challengers. They contain no order-placement path. Their output status is always `INCONCLUSIVE`: signal counts are neither trade counts nor profit evidence.

Run the capture command under a Python environment that can import `MetaTrader5` and connect to the target Exness Demo terminal. Set `XAUUSD_MT5_LOGIN`, `XAUUSD_MT5_PASSWORD`, and `XAUUSD_MT5_SERVER` in the environment; set `MT5_TERMINAL_PATH` if terminal discovery needs it. Keep secrets out of command arguments and output files. Confirm the exact gold symbol from the terminal and pass it as `--symbol`. Use a new output directory for each non-overlapping UTC window, at most one day long, strictly after the frozen contract/code timestamp. For example, after replacing the illustrative timestamps and symbol with the approved actual values:

```sh
python3 -m scripts.research.shadow_capture \
  --start 2026-09-24T00:00:00+00:00 \
  --end 2026-09-24T03:00:00+00:00 \
  --freeze-at 2026-09-23T17:00:00+00:00 \
  --symbol XAUUSDm \
  --output /absolute/path/outside-repo/capture-001
```

The CLI rejects non-UTC times, pre-freeze windows, wrong Demo identity, missing symbol specifications, out-of-window ticks, and invalid/crossed quotes. It writes all returned MT5 tick fields, source and code hashes, quote counts, target-account snapshot, and a `COMPLETE` marker only after the capture is written. Keep raw captures immutable and outside Git. A successful capture proves only that the selected window returned tick rows; it does not prove continuous market coverage or true fills.

Audit one or more sealed captures:

```sh
python3 -m scripts.research.shadow_monitor \
  --capture /absolute/path/outside-repo/capture-001 \
  --capture /absolute/path/outside-repo/capture-002 \
  --output /absolute/path/outside-repo/signals-001
```

The audit checks each tick file hash, account/symbol/freeze identity, window overlap, quote validity, ordering, and pinned signal/bar-builder code hashes. It builds observed M1 Bid/Ask bars without forward fill, applies the versioned research signal rules, and writes `signals.csv` plus a manifest. `minute_gaps` and `identical_tick_rows` require review; no market-closure calendar or tick-completeness proof exists yet. A signal at a bar's close is recorded with its availability time, not a simulated trade or broker fill. The current process holds input ticks in memory, so bound capture size to available RAM.

Do not promote any candidate from these files. Qualification still needs complete prospective coverage, target-account sizing, tick-level native exits, measured fill costs with at least 59 independent fills per active order type/session/side stratum, twice-cost replay, account drawdown, adjusted confidence intervals, and portfolio selection per [QUALIFICATION_PROTOCOL.md](QUALIFICATION_PROTOCOL.md). A separate Demo fill calibration experiment requires explicit authorization before it sends any orders.

API reference: [MetaTrader 5 Python `copy_ticks_range`](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py). The source of truth for broker identity, quotes, and fills remains the target terminal and its captured evidence, not this documentation page.
