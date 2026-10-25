# Selected26b8 actual Demo execution: prepared, activation blocked

Owner explicitly requested actual MT5 Demo orders from selected26b8 on2026-10-25.
The supplied account identity matches the existing VM env fingerprint
`c4020d69b754dfb5`; no credential update was necessary. Credentials are omitted
from every artifact. The current observer's broker journal recorded equity
$1,812.21 at2026-10-25T12:41:09Z. This is the actual Demo account equity, distinct
from the $200 historical research baseline. Fixed0.01 and equity-based admission
cap10% remain unchanged; retained profit does not increase lot size.

## Implemented and verified

Selected CLI now supports exact `--execute` only with the existing explicit env
send gate, dedicated terminal and a selected execution review. Default remains
shadow; abbreviated execution switches cannot bypass review. Broker sends,
SL/TP/BE, persisted UNKNOWN reconciliation, cost/risk checks and same-account
writer lock remain the existing shared lifecycle. All28 native Rules are intact.

Review binds selected identity, actual account/release/config, canonical measured
readiness report, policy hash and explicit owner/operator confirmations. First
acceptance requires fresh evidence within5minutes. Persisted exact review bytes
permit same-cohort restart while policy stays valid. Every new admission reloads
permission; missing/revoked/changed review or invalid/changed cost policy blocks
new entries. Active/UNKNOWN positions still reconcile/protect after restart even
if an entry review is missing; no blind resend. Policy renewals require actual
review; no automatic cost renewal is implemented.

Readiness shares measured C22 rules through explicit identity parameters with
old defaults preserved. New selected report binds current completed heartbeat,
single source cohort and broker/parity/policy hashes. Old feed/time-waiver records
cannot qualify it. The report is always execution_authorized=false and requires
separate review; no tool synthesizes a passed shadow interval or cost attestation.

Tests:34selected tests PASS;full1,130tests PASS(skipped2),139.005s. Scoped Ruff
and new-code Pyright PASS. Existing optional-value type diagnostics in the old
readiness file remain outside this change; no repository-wide typecheck is
claimed. Independent Standards/operational and Spec reviews found no unresolved
material code finding. Real archive detector/entry agreement was repeated:
49,729bars/2,751entry geometries across6cost/guard paths,0mismatches. It shares
canonical helpers; no new economic backtest or broker fill qualification.
All101 frozen research source hashes remain unchanged. Selected config now
binds17 runtime sources, including the admission permission module.

## Oracle state and artifact evidence

New release staged at
`/home/ubuntu/c22-demo/releases/selected-6f9d1a75e34073a9`.
Archive SHA256:
`36108678fc9e937135628bc678b4a7d5fb4d73c7b6e692d223335418c85d501d`.
70file bindings verified; original58 runtime files unchanged. Builder source hash
participates in release identity so a changed unit template cannot reuse a
previous immutable directory name.

Both shadow and execution unit templates are packaged. Execution uses explicit
gate1/review, separate journal/cache, shared account guard, other units inactive,
notifications unset and restart-on-failure. It has no Conflicts that kill a
financial manager and no boot-install section. It is NOT installed or started.
The running `c22-selected-shadow.service` and old source release were not replaced
in this task; gate0/AutoTrading-off remain. No actual order API was called.

A new consistent VM journal backup was downloaded to Mac and verified with
SHA256/SQLite integrity/table counts. Read-only snapshot-time readiness is
BLOCKED:0fresh prospective M15 bars, stale quote, unsupported old broker/parity
inputs, unreviewed costs and original duration criteria not passed. Stale retained
broker export is explicitly labelled; it is not described as fresh verification.

Machine artifacts: ignored `runs/c22-selected-execution-2026-10-25/` contains
RED/GREEN logs, archive agreement, VM snapshot/restore, actual BLOCKED report,
review template with null time/false confirmations, deterministic release and
staging proof. No review template was published as runtime permission.

## Actual remaining decisions and evidence

Account login/server are verified, but they do not establish swap applicability.
Current XAUUSDm BUY swap entitlement needs account-specific evidence. Retained
XAUUSDm history consists of SELL positions; charged BUY swaps from XAUUSD247m
are a different instrument and do not qualify XAUUSDm BUY.
Exness says current status is viewed in Personal Area → Trading conditions →
Swap-Free: [official status documentation](https://get.exness.help/hc/en-us/articles/4402341895570-Swap-free-status).
The actual status was requested; the provided account credentials are not a
swap-status answer. Do not assume zero.

Fresh tariff/spec/full dated calendar/deal review, selected broker feed/history,
prospective observations and operational backup/monitor remain required before
activation. The owner was separately asked whether this new candidate should
retain48h/96bars/UTC-midnight or have a newly explicit Demo-only duration waiver.
No answer or inherited old Monday waiver is assumed. A waiver would not waive
cost/identity/feed/risk/fresh-data requirements or create economic qualification.

No automatic activation was scheduled. No approval review rejection occurred in
this task; activation was deliberately not attempted with missing evidence.
Real-money permission remains prohibited. Demo fills/profit are not claimed.
