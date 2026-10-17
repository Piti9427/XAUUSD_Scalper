# C22H4 host readiness — operational cutover blocked

Owner requested completing replacement of trial30 with frozen C22H4 and explicitly approved read-only process and MT5 broker/history checks outside sandbox. No execution gate enabled, no order sent, no cost-policy timestamp edited.

## Verified this session

- Host process inventory before probe: no `run_trial30_wine`, `mt5_wine_trial30`, `run_c22h4_wine` or `mt5_wine_c22h4` watcher found. This is local host evidence, not exclusion of other execution machines.
- Trial30 journal inspected with SQLite `mode=ro`: active null, safety_halt null, pending outbox0; saved day baseline from2026-10-02. Local state does not prove current broker flatness.
- Existing cost policy reviewed2026-10-02T06:09:10.008282UTC, approximately58 hours old, exceeding24h gate. No refresh without fresh broker/account evidence and owner attestation.
- Approved host `make c22h4-history-probe` reached Python MT5 initialization but reported `BLOCKED initialize_failed`, `order_api_called=false`. No broker rates/parity outputs produced. Log: `runs/c22h4-pr-scrutinize-2026-10-04/history-probe-host.log`.
- During probe, host inventory showed two `terminal64.exe` instances: pre-existing PID65429 and new PID33163. Probe Python PID33160 subsequently exited; host wrapper remained waiting on output stream. Its unified exec session was interrupted with Ctrl-C, observed exit130. No terminal instance intentionally closed.
- Fresh candidate suite: `.venv/bin/python -m unittest discover -s tests -p 'test_c22h4*.py'`,34 tests in23.336s, OK. Log: `runs/c22h4-pr-scrutinize-2026-10-04/candidate-checks.log`.

## Pending

Requested separate permission to restart MT5 terminals because earlier approval covered read-only checks only. Do not launch another client/shadow before terminal connection recovers. Broker account identity, exposure, same-day deal history, deep bootstrap and parity remain unverified. Shadow96 complete M15 bars spanning UTC midnight not started. Entry/exit/risk contract unchanged; real money prohibited.

Next: owner-approved MT5 restart or owner-managed terminal recovery, then exclusive read-only broker/history probe. Only after parity and fresh cost attestation can shadow begin; actual cutover still requires its documented gates and execution-time approval.
