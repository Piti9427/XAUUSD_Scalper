# Trial30 on MT5 Demo / Wine

This is owner-authorized **research Demo testing**, snapshot `RESEARCH-D48-SELL-BE1R-20261001-T030`. Frozen D30 target and legacy alert/webhook paths are separate. Real accounts are rejected. Research qualification remains failed; running Demo does not establish expected profitability.

Contract: UTC Bid M15 from15 complete M1; prior48 Donchian SELL only; no RSI/EMA; ATR14 SMA; market SELL0.01; SL2.5ATR/TP3ATR; cost-inclusive10% current-equity admission; UTC daily20%; cost-adjusted BE at closed-bar net>=frozen initial1R. No recovery/partial/forced rollover. `config/trial30-demo.json` is pinned and CLI rejects strategy edits.

## Run

Credentials stay in ignored `.env` (`XAUUSD_MT5_LOGIN`, `XAUUSD_MT5_PASSWORD`, `XAUUSD_MT5_SERVER`). Existing Wine prefix and Windows Python are reused; no app/config copies or package upgrades. Mac sandbox may prevent Wine IPC; use authorized host execution when needed. Incomplete/real/netting/wrong-account/permission checks fail closed.

```bash
make guide
make bot-status
make bot-once
make bot-run
make bot-start
make bot-stop
```

`make guide` prints the operator sequence. `bot-once` is the read-only cycle. `bot-run` is the foreground Demo watcher. `bot-start` / `bot-stop` use `data/trial30-demo-watch.pid`. `bot-status` reads the journal and does not contact the broker. Equivalent raw entrypoints:

```bash
# Read-only shadow: no order_send.
.venv/bin/python -m scripts.ops.run_trial30_wine --once

# Owner-authorized actual Demo watcher. Natural signals only.
MT5_ENABLE_DEMO_ORDER_SEND=1 .venv/bin/python -m scripts.ops.run_trial30_wine --watch --execute

# Inspect journal while watcher runs; does not contact broker.
.venv/bin/python scripts/ops/trial30_status.py
```

Ctrl-C stops watcher; broker SL/TP remain. Restart with same journal reconciles broker positions/deals, not a fresh simulated balance. Default persistent journal `data/trial30-demo.sqlite3`; `.lock` SQLite database enforces one local writer per journal. Do not start a second execution host or use alternate journals for this account.

## Costs and baseline

Ignored `data/trial30-demo-cost-policy.json` binds fingerprint and fresh identity artifact hash, timestamp, named tariff, round-trip commission and positive declared slippage allowance. Invalid/missing/stale policy blocks new entries; expiry24h. Refresh only after checking account/spec/tariff again. No automatic timestamp refresh. Standard0 commission comes from [Exness published Standard tariff](https://www.exness.com/standard-accounts/), checked2026-10-01; not an observed Pure B1/trial30 deal rate. Allowance0.10USD/oz on adverse entry/stop-exit fills; not a guaranteed slippage ceiling. Actual broker swap is reconciled in deal PnL; admission does not model overnight swap and no swap-free entitlement is asserted. Cost/spread assumptions cannot prove profitability.

On a flat midnight, reconstruct day-start balance/equity only after full broker cashflow balance and position-volume reconciliation. Trading PnL does not reset baseline. Deposits/withdrawals/credits during current day block new risk. Position carried at midnight needs persisted equity captured in first UTC second; missing mark blocks entries, never BE protection. Daily limit is admission halt, not forced liquidation or guaranteed total daily-loss ceiling.

## Execution and evidence

First historical quote, requested market price and actual fill remain separate. Submission must still be within90s after close with quote age<=60s. Risk reserves both entry/exit allowances; broker margin/profit/check, current identity/exposure and refreshed capital/quote precede submission. Broker prices/slippage can differ; post-fill risk/spec violation triggers owned-ticket safety close and persistent halt.

Write-ahead claim precedes every market order. UNKNOWN/timeout cannot be retried as a fresh entry; reconcile position/deal by magic30261001 and comment. No matching evidence keeps state UNKNOWN and prevents new orders. Safety close targets only matching owned ticket. Broker-confirmed FILLED/BE_MOVED/CLOSED events persist atomically; notifier callback is optional and retries outbox, so delivery is at-least-once. CLI does not enable Telegram or send messages implicitly. Read status events for actual broker outcomes.

SL/TP are server protections; BE requires watcher alive and fresh completed bars/quotes. Stale data, history gaps, unsupported broker specs or denied permissions report BLOCKED. Hard SL gaps or failed safety close can exceed modeled risk; inspect safety_halt/UNKNOWN and broker position before restarting. Never delete journal or reset baseline to bypass guard.

## Validation scope

- Public runner/CLI tests: fixed SELL/stops, closed-bar BE/restart, timeout/unknown/reject, real-account and permission gates, cost/margin/exposure, daily ledger, partial/risk-violating fills, outbox failure and local writer exclusion.
- Saved detector parity:12,100 bars, zero direction/ATR mismatch with research D48 SELL-only source.
- Fresh Wine identity: Demo USD hedging, balance/equity200, no exposure, algo permissions enabled. First actual shadow run WAIT/no_sell_signal.
- Actual broker fill, BE, close and restart evidence must be collected from genuine forward signals. No synthetic signal or forced order is used to claim strategy verification.

Frozen strategy/spec: `docs/specs/2026-10-01-trial30-demo-execution.md`. Original diagnosis artifacts remain evidence of previous mismatch; repro command now uses dedicated trial30 detector and returns PASS.
