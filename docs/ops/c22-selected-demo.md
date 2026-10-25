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
shadow regardless of inherited order-send environment. `--execute`/`--exec`
are rejected before MT5 initialization, and every constructed CLI runner is
forced to shadow until new-candidate readiness is implemented/reviewed.
This block does not assert broker readiness.
Do not route old `make bot-execute` to this candidate as a shortcut.

The config binds all16 named canonical/selected source files and selected
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
Notifications are unset. Terminal AutoTrading remains disabled; no execution unit.

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
