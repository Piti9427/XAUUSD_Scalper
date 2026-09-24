# Demo order smoke test — 2026-09-20

## Verified execution

- Account: [REDACTED_ID], Exness-MT5Trial7, Standard_Demo. Personal Area identified this account as Demo with balance USD 1,100.
- Route: authenticated Exness Terminal browser session; no Python execution adapter used.
- Instrument: XAUUSD247m (UI: XAU/USD247), Buy 0.01 lot.
- Ticket displayed in open-position row: [REDACTED_ID].
- Open time displayed with chart timezone UTC: 2026-09-20T13:07:44+00:00.
- Entry: 4371.338; stop loss: 4366.338; take profit: 4376.338.
- Order form showed SL -5.00 USD (-0.45% equity), below configured 0.5% risk budget of USD 5.50. Slippage can change actual realized loss.
- Verified one open position, floating P/L -2.90 USD, equity 1097.10 USD, margin 21.86 USD, balance 1100.00 USD.
- Position remains open with SL/TP as of the final observation at 13:08:51 UTC. No close was requested or executed.
- Automatic permission review timed out on the first submit attempt. Checked unchanged order form and no open position before retrying once; only one confirmed position was observed.
- Declined optional automatic TP/SL preference prompt after execution.

## Connection diagnosis still unresolved

`diagnosing-bugs` feedback loop: Windows Python inside existing Wine prefix calls MetaTrader5.initialize with credentials loaded from .env, checks account_info for the requested login and ACCOUNT_TRADE_MODE_DEMO, and exits nonzero unless both match. No credentials printed.

Observed three runs: keyword path, positional path, then positional path with portable=True. Each returned initialize=False, error_code=-6, target_demo_verified=False, exit 1. Thus neither positional path nor portable mode resolved the failure.

The inspected on-disk common.ini still named MetaQuotes-Demo, and the inspected terminal log contained earlier MetaQuotes-Demo invalid-account failures. These older disk records do not establish whether the latest Exness credentials were rejected by the broker. Native MT5 UI access timed out. Exness Personal Area's MT5 WebTerminal link redirected to a 404 page. No terminal configuration or application code was changed.

## Limits

This verifies one browser-submitted simulated order with broker-displayed SL/TP. It does not verify Python/Wine connectivity, an automated strategy execution path, Pine signal correctness, backtest profitability, or real-money readiness. XAUUSD247m is not the same feed/instrument as the FOREX.com XAUUSD chart used for the Pine indicator.

## Follow-up debugging ledger (debug-mantra)

Repro command: run 64-bit Windows Python 3.12.8 inside the existing Wine prefix and call `MetaTrader5.initialize()` with the installed terminal executable, then require `account_info()` to match login [REDACTED_ID] and Demo mode. The authenticated run returned `initialize=False`, `last_error()[0]=-6`, `target_demo=False`, exit 1. No order API was called. This was the same result as the prior three variants documented above.

Fail path: `.env` → `resolve_mt5_account_kwargs()` / `initialize_mt5()` → MetaTrader5 Python extension → running `terminal64.exe`. The failure occurs inside `initialize()`, before `account_info()`, broker identity validation, or `order_send()`. Native debugger attachment to the proprietary Wine terminal was not available; source trace and read-only process/config inspection were used.

| Probe | Change | Observation | What it rules out |
| --- | --- | --- | --- |
| Prior three variants | keyword path; positional path; positional path + portable | all error -6 | Python argument spelling or portable flag alone |
| Current authenticated repro | exact Exness Demo credentials from `.env` | error -6 | confirms current failure, not credential validity |
| Current unauthenticated repro | omit login/password/server | error -6, account absent | wrong supplied password alone cannot explain every failure; saved terminal state may still be involved |
| Process inspection | running terminal PID 67026 | launched from `C:\Program Files\MetaTrader 5\terminal64.exe` with `/portable` | missing terminal process |
| Open file inspection | `lsof` on terminal PID | same installation's `logs/20260920.log` open | wholly different terminal executable/log path |
| Config/log inspection | read-only | `common.ini` mtime 19:21 local names MetaQuotes-Demo; log mtime 19:48 local has older invalid-account messages, no latest repro records | old disk data cannot establish current broker authorization |
| Runtime inspection | read-only | Wine Python 3.12.8 x64, MetaTrader5 module 5.0.6180; one established TCP 443 socket on terminal PID | missing module, wrong process bitness, or total absence of a network socket |

Ranked open hypotheses: (1) terminal's active account authorization is invalid or stale; (2) Wine terminal/Python authorization handshake is failing independent of broker credentials; (3) Python extension build 6180 and terminal build 6204 are incompatible in this environment; (4) terminal uses a different in-memory account state than the old `common.ini`. The read-only probes do not distinguish these yet. `-6` is documented by MetaQuotes as authorization failure. MT5's separate Python auto-trading protection controls sending trades, and has a different documented error code (`-8`); changing that protection before `initialize()` succeeds is not supported by current evidence.

## 2026-09-20 evening resume (`diagnosing-bugs` Phase 1–2)

Durable loop: `scripts/ops/mt5_wine_initialize_loop.sh` → Wine Python `C:\tools\python312\python.exe` + `scripts/ops/mt5_wine_initialize_loop.py`. Loads ignored `.env` in-process. Asserts `initialize` + `account_info()` login `[REDACTED_ID]` + Demo. Exit 0 only if `target_demo_verified`. No `order_send`. No secrets in stdout.

| Probe | Change | Observation | What it rules out |
| --- | --- | --- | --- |
| Loop run 1 authenticated | keyword `path`+login+server | `initialize=false` `error_code=-6` `target_demo_verified=false` exit 1 in 2.9s; module 5.0.6180 | loop not red-capable; import/bitness missing |
| Loop run 2 authenticated | same command | identical JSON; journal `20260920.log` size 4638 mtime unchanged | flake; this initialize call writing Network journal |
| Minimise omit creds | `MT5_OMIT_CREDENTIALS=1` → kwargs `path` only | still `-6`; still one `terminal64` PID 67026 `/portable`; journal still frozen | supplied Exness password as necessary cause of `-6` |
| Minimise drop `path` | `mt5.initialize()` no path | `-10003` `IPC initialize failed, MetaTrader 5 x64 not found` | `-6` without explicit `path`; path is load-bearing for this symptom |
| Extra log hunt | read-only | AppData `D0E8209F…/temp/logs/20260920.log` mtime 19:46:56, not updated by loop | initialize writing a second known journal instead of portable `logs/` |
| Disk account | read-only `common.ini` | `Login=[REDACTED_ID]` `Server=MetaQuotes-Demo`; `[Experts] Enabled=0 Api=0` | on-disk account already being Exness; (Api=0 not flipped this session) |

Re-ranked hypotheses for Phase 3: (1) Wine Python↔terminal IPC handshake fails locally and reports generic `-6` without a broker Network attempt; (2) invalid MetaQuotes-Demo session makes the terminal refuse Python attach locally, still without a new journal line; (3) MetaTrader5 5.0.6180 vs terminal build 6204 incompatibility; (4) `[Experts] Api=0` reported as `-6` not `-8`; (5) leftover: in-memory account differs from `common.ini` — weaker now that journal/PID/path are stable and disk still says MetaQuotes-Demo.

Demo position: Wine terminal is MetaQuotes-Demo `[REDACTED_ID]`, not Exness `[REDACTED_ID]`. Python cannot read Exness positions while `initialize()` fails. No order API called. Playwright had no Exness session (`about:blank` only). Browser-open XAUUSD247m ticket `[REDACTED_ID]` not re-verified this resume.

| Probe | Change | Observation | What it rules out |
| --- | --- | --- | --- |
| lsof during 8× `initialize(path=)` | instrumentation only | 0 shared pipe/unix NODE ids between Wine Python PID and terminal PID 67026; Python TCP=0; terminal one ESTABLISHED `*:443` to `36.255.76.33` | Python package opening its own broker TCP. Does **not** rule out IPC via `wineserver` (Wine processes often have no direct Mac pipe) |
| H3 version probe | `pip index versions MetaTrader5` in Wine Python | installed=latest=`5.0.6180`; no wheel for terminal build `6204` | cannot falsify version mismatch by upgrading the Python package |
| GUI Exness login | operator logged Wine UI to `[REDACTED_ID]` / `Exness-MT5Trial7` (title also `Netting`) | loop still `initialize=false` `error_code=-6`; portable `common.ini` still MetaQuotes-Demo `[REDACTED_ID]`; portable journal frozen at 19:48; `Bases/Default/trades/[REDACTED_ID]` exists; `[Experts] Enabled=0 Api=0` | “GUI still on invalid MetaQuotes-Demo” as the sole cause of this `-6`. Does not yet falsify `Api=0` |
| Experts Options + OK | Allow algorithmic trading on; Disable Python API left off | `common.ini` `Login=[REDACTED_ID]` `Enabled=1` `Api=0` but `Server=MetaQuotes-Demo`; authenticated initialize and omit-creds both `-10005 IPC timeout` (~63s); journal `automated trading is disabled because the account has been changed`; `'[REDACTED_ID]': authorization on MetaQuotes-Demo failed` | `-6` as the only failure; Python never reaching this terminal. Does not prove Exness server attach |
| Navigator Exness-MT5Trial7 | operator selected `[REDACTED_ID]` under `Exness-MT5Trial7`; also `Account=0 Profile=0` | still `-10005 IPC timeout`; journal file mtime unchanged during this run | selecting the account in Navigator as sufficient for Python IPC |
| GUI Network success | title `Demo Account - Hedge`; Journal authorized on `Exness-MT5Trial7`, hedging, 0 positions | `initialize=true` `error_code=1 Success` `attached_login=[REDACTED_ID]` `attached_server=Exness-MT5Trial7` `trade_mode=0` `target_demo_verified=true` exit 0 in ~2.3s; `common.ini` now `Server=Exness-MT5Trial7`; no `order_send` | Wine Python IPC permanently broken on this prefix |
| Execution Path Probe | synthetic BUY_LIMIT `XAUUSDm` via Orchestrator then `order_send` | identity/hedging/geometry passed; lot 0.02; `order_send` retcode **10018 Market closed**; no ticket; no fill | weekend gold session; path reached broker reject, not a fill |
| Execution Path Probe (market open) | same command Monday | `stage=probe_ok` `place_retcode=10009` ticket `[REDACTED_ID]` then `cancel_retcode=10009` `cancel_ok=true` `leftover_orders=[]` | weekend-only close; Demo Execution Path for pending limit+cancel on `XAUUSDm` |
| Test order retry | same probe, still auto-cancel | ticket `[REDACTED_ID]` place+cancel `10009` leftover none | fluke first fill; leftover pending |
| History-tab miss | read-only `history_orders_get` on same login `[REDACTED_ID]` balance `1173.46` | tickets `[REDACTED_ID]` / `[REDACTED_ID]` exist as `XAUUSDm` BUY_LIMIT `state=2` canceled, `deals=[]`; History Deals symbols only `XAUUSD247m`; open orders/positions empty | probe never hit this account; History Positions view showing fills; `XAUUSDm` vs `XAUUSD247m` same instrument |
