# Handoff: MT5 Demo order from terminal (2026-09-20)

## Goal and current verdict

User wants the project to submit XAUUSD Demo orders directly from terminal code, without Computer Use. One manual browser Demo order was confirmed; **Python → MT5/Wine remains blocked at `initialize()` with error `-6`**. Do not treat browser execution as a pass for automated execution or strategy profitability.

Read the current evidence first: [`../ops/2026-09-20-demo-order-smoke.md`](../ops/2026-09-20-demo-order-smoke.md). It contains the order receipt and the `debug-mantra` experiment ledger. Keep credentials out of logs and handoffs.

## Resume in order

1. **Protect existing Demo position.** Check broker positions and history before sending any new order. Last verified state had one open XAUUSD247m position with broker-displayed SL/TP; that observation may now be stale. Do not retry a submission merely because a client call times out.
2. **Reproduce connection failure.** Load ignored `.env` into the process without printing it. Run read-only `MetaTrader5.initialize()` from 64-bit Windows Python inside the same Wine prefix; require `account_info()` to match the intended Demo account. The existing short repro and earlier variations are documented in the ops evidence above.
3. **Distinguish terminal authorization from Python IPC.** Inspect the *current* MT5 Wine account status and Journal/terminal log. The inspected `common.ini` and log were old MetaQuotes-Demo records, not proof about the active Exness session. Test one variable at a time; preserve the experiment ledger. Do not change Python auto-trading protection merely to address `initialize()` failure: that protection concerns order submission, a later seam.
4. **Only after `initialize()` succeeds, run identity readiness.** Use [`../../scripts/smoke_broker_identity.py`](../../scripts/smoke_broker_identity.py) and inspect Demo trade mode, exact server/login, account currency, broker symbol metadata, connection/trade permissions, and open positions. Current adapter requires Hedging; the MT5 screenshot showed Netting. Resolve account mode/ownership deliberately; do not bypass [`../../scripts/smc/account_mode.py`](../../scripts/smc/account_mode.py).
5. **Verify terminal submission with bounded risk.** Trace market data → detection → orchestrator risk/admission → [`../../scripts/smc/mt5_adapter/execution.py`](../../scripts/smc/mt5_adapter/execution.py) → broker confirmation → notification. Existing adapter primarily submits pending limit intents; the browser smoke was a manual market order. Check order type and symbol parity before testing. Confirm `order_send()` result *and* broker order/position/deal state; preserve idempotency and SL/TP.
6. **Evaluate the technique separately.** Pine indicator and Python/SMC strategy are not proven equivalent. Source review and backtest limits are in [`2026-09-12-tradingview-master-pro-v6-hardened.md`](2026-09-12-tradingview-master-pro-v6-hardened.md), [`../reviews/2026-09-12-master-pro-v6-logic-review.md`](../reviews/2026-09-12-master-pro-v6-logic-review.md), and [`../specs/2026-09-12-master-pro-v6-net-expectancy.md`](../specs/2026-09-12-master-pro-v6-net-expectancy.md). A separate Python backtest produced zero trades on proxy data, so profitability remains inconclusive.

## Boundaries and source of truth

- [`../../AGENTS.md`](../../AGENTS.md): no over-risk lot rounding, UTC-aware market times, alerts only after broker-approved/executed events. Demo authorization does not authorize real-money trading.
- [`2026-09-16-issue1-foundation-progress.md`](2026-09-16-issue1-foundation-progress.md): software coverage and remaining live gates. Old “no reconciler” notes are superseded by current `scripts/smc/broker_lifecycle.py`.
- [`2026-09-16-open-material-decisions.md`](2026-09-16-open-material-decisions.md): unresolved trading rules; do not silently settle them.
- [`2026-09-17-goal-paused-mac-continue.md`](2026-09-17-goal-paused-mac-continue.md): older pause snapshot. Do not read it as a current claim that no Demo order was ever placed.
- `.env` is ignored and mode 600. Load it locally; never print, copy to docs, or commit it.
- At handoff creation, working tree also had an unrelated untracked `package-lock.json`; preserve it. The new ops evidence file was also untracked.

## Suggested skills

- `$debug-mantra` for continuing the reproducible `initialize()` diagnosis and maintaining the ledger.
- `$diagnosing-bugs` if turning the failure into a regression test and implementing a proven fix.
- `$scrutinize` before claiming Pine strategy parity, edge, or real-money readiness.
