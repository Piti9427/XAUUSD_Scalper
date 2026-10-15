# bot-run default mode and M1 bootstrap diagnosis

Owner invoked debug-mantra to make `bot-run` usable and explicitly selected shadow as its default. Debug session separates the command-mode problem from broker history availability. No strategy, sizing, stops, indicators or frozen source pins changed; no orders sent or broker positions closed.

## Reproduction and traced failure

`make bot-run` without parent-shell `MT5_ENABLE_DEMO_ORDER_SEND=1` reproduced the old Make guard, exit2, before Wine or `.env` loading. Existing C22 shadow journal repeatedly showed `BLOCKED/missing M1 bars` with execute=false. Shadow was stopped to obtain exclusive diagnostic access.

Source path: Make -> Wine host wrapper -> frozen C22 CLI -> Demo identity/exposure/full ledger/spec/quote ->5000-M1 tail ->100000-M1 bootstrap -> complete-M15 assembler -> `_closed_m1`. Live Python `pdb` breakpoint at `scripts/pure_b1/broker_data.py:42` confirmed `rates is None`, empty frame and the exact `ValueError`. A first5000-M1 debugger run instead succeeded with328 M15 bars, disproving a permanent5000/symbol/API failure. Earlier cold history failures are therefore transient or a separate cause; they are not all attributed to the capacity boundary.

## Differential and falsification

At MT5 package5.0.6180, terminal build6230, terminal Max bars100000:

- Same XAUUSDm/M1/start0 query returned500,1000,2000,4999,5000,10000,50000 and99999 rows successfully.
- Query100000 returnedNone, error-2 (`Terminal: Invalid params`). Alternating99999/100000 repeated three times: success3/3 below boundary, failure3/3 at boundary.
- Exact `common.ini` `[Charts] MaxBars=100000` matched terminal_info. These results falsify broken symbol/timeframe/API and explain the reproducible bootstrap failure site. A capacity-only intervention remains necessary to establish causality and operational recovery.
- Official API documents that available bar history is bounded by terminal chart capacity, and that None indicates an error requiring last_error inspection: [copy_rates_from_pos](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrompos_py), [last_error](https://www.mql5.com/en/docs/python_metatrader5/mt5lasterror_py). The exact observed boundary behavior is local evidence, not an assertion that every MT5 build has this boundary.

Do not reduce bootstrap to99999 or seed cached/archive bars: that changes the causal prefix of the frozen contract. Proposed intervention retains100000-M1 bootstrap and increases terminal history capacity to200000.

## Code fix and reviewable host change

`make bot-run` and `make bot-start` now default to shadow and print selected mode. Only invoking-shell env1 adds `--execute`; Make does not read the execution gate from `.env` or enable it implicitly. C22 exports its exact causal cache; trial30 rollback receives no unsupported cache option. Shared account lock, Demo identity, cost/risk and cutover contracts remain intact. Candidate PID is ignored as runtime state. README, runbooks and CORE_STRATEGY updated.

Eight actual subprocess Make smoke checks replaced broker command with echo: candidate/rollback crossed with unset,0,1,typo env. All passed; only1 supplied execution flag. These are command-interface regressions, not economic backtests.

Executed `make test compile deps lint`:884 tests in52.414s, OK(skipped2); compile, pip check and Ruff lint PASS. Frozen contract/source-hash validation and working-tree whitespace check PASS. Whole-repository formatting has13 previously recorded failures; no source-pinned files reformatted.

Actual `make bot-run` launched in background with explicit env0 to exclude inherited execution settings; Make PID5326, host runner5329, Wine client5331. Printed `Starting c22h4 Demo watcher: shadow`; fresh journal heartbeat2026-10-05T08:44:33.496955UTC confirms selected C22 snapshot, execute=false, `BLOCKED/missing M1 bars`. This verifies the Make startup fix, not bootstrap recovery. Only one candidate watcher/client was observed; trial30 was absent. Existing broker positions were not managed or closed by this shadow.

Prepared host intervention and rollback under ignored `runs/bot-run-debug-2026-10-05/`: backup/proposed UTF16 common.ini, sanitized plan and exact change script. Change only `[Charts] MaxBars=100000 ->200000`; preserve remaining bytes/encoding, require no Demo client, verify terminal executable before reload, and never send orders. Automatic approval review rejected mutation/restart because three Demo positions remain open and preceding escalation approval was read-only. No config change or terminal restart performed. Explicit owner permission requested; pending.

## Evidence and readiness

Machine ledger, live debugger transcripts, count-query results, Make smoke results and validation logs reside in `runs/bot-run-debug-2026-10-05/`. Original broker snapshot shows expected Demo identity, positions3, orders0; position ownership and lifecycle are not inferred from these counts. Fresh cost attestation, parity,96 completed-M15 shadow bars spanning UTC midnight and account flatness remain independent gates before execution. Default shadow command usability is not execution readiness or a profitability claim.
