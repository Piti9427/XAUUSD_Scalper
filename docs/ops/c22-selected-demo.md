# Selected26b8 shadow and Demo test

Owner selected native Rules `26b8bcd69e043653` on2026-10-25. New snapshot
`RESEARCH-C22-SELECTED-20261025-26B8`,magic22261025, separate journal/cache.
This is a new version of C22 for shadow→Demo qualification. Old frozen
`1af968e9ac6a26ea` and release remain retained rollback evidence.

Exact contract: RSI7cross30 BUY/EMA50; SELL48/EMA50; closed H4EMA200; BUY
SL2.5ATR/TP3R, SELL SL2.5ATR/TP1.35R, both BE1R on completed bars. Fixed0.01,
cost-inclusive10% cap, daily10%/two negative completed exits per final exit UTC
day;30elapsed-minute negative-net cooldown compared with first signal quote.
Swap/commission/fee losses count even if price exit is BE. No lot growth/baskets.

## Local checks and default mode

```bash
PYTHONPATH=. .venv/bin/python -m scripts.c22_selected --verify-sources
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests/demo -p 'test_c22_selected*.py' -v
```

The Wine entrypoint is `scripts/ops/mt5_wine_c22_selected.py`. It defaults to
shadow regardless of inherited order-send environment. `--exec`/`--e`
abbreviations are rejected before MT5 initialization. Exact `--execute` now
requires envgate1, dedicated terminal and `--execution-review <path>` containing
new selected readiness plus explicit operator review. Default remains shadow.
This block does not assert broker readiness.
Do not route old `make bot-execute` to this candidate as a shortcut.

The config binds all17 named canonical/selected source files and selected
research completion/audit proof hashes. The runner adds selected source code to
the release/cohort identity and uses the existing shared broker lifecycle and
account writer guard. Its cooldown hook operates only during admission, never
blocks protection/reconciliation of an active position.

## Oracle shadow release

Build using `deploy/c22-demo/prepare_selected_release.py --out runs/<new-dir>`.
It uses the old explicit58-file allowlist plus new selected files/config,
produces deterministic archive/SHA manifest and a gate0 systemd shadow unit.
No credentials, journal, research runs or historical ticks enter the bundle.
Verify any differences in old runtime files before upload; expected list is empty.

New unit `c22-selected-shadow.service` uses its release directory directly,
`state/c22-selected-shadow.sqlite3` and `state/c22-selected-shadow-bars.csv`.
The old `current` pointer stays unchanged. New release `data` links to old
release `data` solely to share the same account writer lock. Service preconditions
require old shadow/execution units inactive and that exact guard directory.
Notifications are unset. Terminal AutoTrading remains disabled. A separate
execution unit is packaged for review; it is not installed or enabled.

Before handoff: fresh read-only unit/journal inspection → verify no managed
active/UNKNOWN position → consistent SQLite backup/download/restore check →
stop only old shadow → exclusive read-only broker flat/identity probe → new
shadow start. Preserve pending old outbox; do not mark it delivered. Enable
only the chosen gate0 shadow unit for boot, disabling old observer autostart.
Do not stop a financial manager if it has active/UNKNOWN exposure.

After startup verify new snapshot/rules ID,execute=false, release hash, latest
timestamp and journal/no order-intent evidence. Sunday stale quote and missing
cost policy are legitimate BLOCKED results. Bootstrap history is not prospective
qualification; start that evidence on fresh completed market bars.

## Remaining decisions and evidence

Archive parity compares49,729 bars and2,751 recorded entry geometries across6
cost/guard paths; it shares canonical helpers and does not certify independent
algorithm, full lifecycle or broker fill parity. New public cycle tests cover
BUY/SELL BE, cooldown/UTC/restart, daily2 and ambiguous lifecycle separately.

Fresh broker tariff/spec/calendar and account cost review remain required;
do not turn the existing COST_INCONCLUSIVE draft into an attestation. Old
feed exception and Monday waiting waiver do not transfer to26b8. New qualified
shadow observations/feed review and execution-time Demo decision precede sends.
Forward sample/review endpoints must be agreed before economic cohort freeze.
Real money remains prohibited. Historical DD40% is not a guaranteed future cap.


## Owner request for actual Demo execution — 2026-10-25

Owner explicitly requested actual MT5 Demo orders from selected26b8 using the
configured account. This authorizes the Demo execution task. It does not supply
swap entitlement, a qualified feed/prospective interval, or a cost attestation.
No real-money activity is authorized. The account fingerprint supplied by the
owner matches the VM identity; no credential update was necessary.

New CLI uses the same persisted broker lifecycle. Execution approval binds a
measured selected readiness report, exact account/release/config/policy hashes,
explicit owner authorization and reviewed cost/feed/backup/single-sender facts.
First acceptance requires a report/review within5minutes. Exact persisted approval
can resume the same cohort later while cost validity continues to be checked.
Removing/changing the review blocks new admissions. An active/UNKNOWN owned
position bypasses new-entry approval at restart to retain reconciliation/BE/
protection. Never stop its manager merely to repair an entry review.

Generate a new measured report using actual inputs, under ignored runs/:

```bash
PYTHONPATH=. .venv/bin/python -m scripts.ops.c22_selected_readiness \
  --journal <selected-shadow.sqlite3> --broker <fresh-broker.json> \
  --parity <selected-broker-parity.json> --cost-policy <reviewed-policy.json> \
  --since <aware-UTC> --out runs/<campaign>/readiness.json
```

A measured `AWAITING_OPERATOR_REVIEW` report still sets execution_authorized=false.
Operator review must separately verify all required facts. The generated template
in `runs/c22-selected-execution-2026-10-25/` intentionally has null approval time
and false confirmations. Do not turn a BLOCKED report into a permission file.

Staged execution unit uses `c22-selected-execution.service`, gate1, new execution
journal/cache and `state/c22-selected-execution-review.json`. It requires old
execution and both shadow units inactive, shares the account lock, has no boot
installation section and no Conflicts that would kill another financial manager.
Use only after fresh flat/backup/readiness checks and actual terminal permissions.
Old `make bot-execute` still targets old C22; it must not be used for this trial.

Current VM remains shadow/gate0. Quote is stale on closed Sunday; cost policy is
COST_INCONCLUSIVE. Standard new-candidate48h/96fresh-bars/UTC-midnight gates have
not passed; old Monday waiver remains inapplicable. No automatic activation timer
was created, AutoTrading was not enabled, and no broker order was sent.
