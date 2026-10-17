# C22H4 commit and execution readiness

Owner requested committing pending work and starting the selected C22H4 Demo strategy. This request supplies execution-time approval conditional on the existing cutover gates; it does not establish their evidence. Default `make bot-*` routes to frozen `RESEARCH-C22-H4EMA200-20261004`, contract `1af968e9ac6a26ea`. Trial30 rollback remains explicit. No execution watcher started, order API called, position closed or cost attestation altered.

## Current broker evidence

Read-only snapshot captured2026-10-05T07:57:03.131970UTC, exit0. Artifact: `runs/c22h4-start-readiness-2026-10-05/broker-snapshot.json`; probe source and host log retained in the same ignored campaign directory. Credentials were loaded from ignored `.env`; account identifiers were not printed.

- Expected Demo account identity matched; USD, hedging margin mode2, terminal connected. Account and terminal trading permissions enabled; API not disabled.
- Account-wide positions3, pending orders0. Balance$200.07, equity$289.75. These are a timestamped broker snapshot, not ownership or lifecycle reconciliation for the open positions. Local trial30 journal has no active lifecycle; do not infer account flatness from it.
- Same-UTC-day deal history count reconciled; no trading deals today, including no trial30-magic30261001 trading deals.
- XAUUSDm exists and is visible. Terminal maximum bars100000. M1 request500 returned500; request100000 returnedNone with MT5 error-2. Required candidate bootstrap therefore remains unavailable. This does not establish the cause of the terminal history limit.
- Symbol swap metadata observed: mode1, long-537.6, short0.0, triple-day3. Current symbol metadata is not historical swap entitlement, realized cost reconciliation or an owner cost attestation.

Before probes, read-only host process inventory found no Demo watcher or MT5/Wine process. `make c22h4-history-probe` reached initialize and passed its Demo identity check, then raised `ValueError: missing M1 bars`; no parity output was produced. The host wrapper remained on its inherited output stream and was interrupted, exit130. Subsequent snapshot used a file output stream and completed normally. Do not repeat another client while an existing client owns the account guard.

## Cutover verdict

**NO-GO for order-enabled bot-run.** Current account is not flat. Broker parity remains absent, as do candidate journal and exported96 completed M15 shadow bars spanning UTC midnight. Existing cost policy was reviewed2026-10-02T06:09:10.008282UTC, approximately74h old; allowed age is24h. Trial30 local journal read-only inspection found no active/safety halt and unsent broker events0, which does not resolve broker exposure.

AGENTS.md requires broker history/parity, midnight-spanning96-bar shadow, fresh cost attestation and flat trial30/account exposure before execution. The owner start request is retained as approval for the intended strategy once gates pass. Resolve account exposure through owner-reviewed management, restore full M1 bootstrap, complete parity and shadow, and obtain fresh evidenced cost attestation before starting execution. No orders were sent to clear these gates.

## Changes and validation

- Default/rollback command routes and operator documentation prepared for commit; frozen entry/exit/risk parameters and source hashes unchanged.
- Removed an uncommitted environment override of the shared account guard directory. Added a regression proving env cannot redirect the guard; reproduced failure before removal, then passed. Concurrent CLI rejection test now uses a temporary test root, retaining shared production guard location and rejection before MT5 initialize/shutdown.
- Executed `make test compile deps lint`:884 tests, OK(skipped2), syntax compilation/dependency integrity/Ruff lint PASS. `git diff --check` PASS; changed test formatting PASS. Frozen C22 source/contract hash validation PASS.
- Whole-repository format check still fails on13 pre-existing files, including source-pinned `scripts/strategy.py`. No broad formatting or source repin performed; aggregate CI readiness is not claimed.

Archived readiness/scrutiny/research proposal notes are included as historical records of the preceding authorized work. Raw runs and credentials remain ignored and uncommitted.
