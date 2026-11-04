# Selected26b8: native BE/close observed; ledger audit and runtime faults remain open

Latest continuation supersedes the pending-export/patch sections below: the
owner-approved one-shot export completed and restored the prior request. The
final retained-evidence audit now passes #25's observed lifecycle acceptance;
see `2026-10-31-c22-native-lifecycle-final-audit.md`. Owner-approved public closure
completed at 05:57:46 UTC; exact comment bytes and closed/completed state were
read back. Original scope is now 20 CLOSED / 3 OPEN: #13, #14, #34.
The approved standalone diagnostics patch002c is applied
locally; focused tests pass and the corrected-fixture full suite passes
1,630tests with two skips and stable source/test pins.
See `2026-10-31-c22-runtime-diagnostic-implementation.md`. No VM diagnostic
rollout, live SQLite repair, AP repair, new cost acceptance or external delivery
is inferred. The earlier acquisition/decision narrative below is preserved as
history, not the latest action status. The continuation entry point is
`docs/ops/c22-claude-handoff-2026-10-31.md`.

The original GitHub scope remains19 of 23 closed. This 31 October read-only follow-up
observes the first retained native SELL through BE and close, but does not yet
independently reconcile its deal-level ledger. It also records continuing sender
restarts and the exact historical conditions refusing later signals. No strategy,
cost policy, permission, service or financial journal was changed.

## Authorized collection and verified coverage

The owner approved bounded read-only SSH outside the sandbox, then identified
the existing key directory. Only directory names/permissions were inspected;
OpenSSH used the existing 0600 key without displaying its content. Strict host-key
checking remained enabled. Identity preflight succeeded at 31 October 01:30:50 UTC
(08:30 Thai): expected hostname and UID1001. No additional broker SDK reader,
request file, order or remote application write was introduced.

The frozen V2 reader SHA256 is
`4d932d337d520391bd76b97e8b4b13b96bc428648d5c366de6ae4cc63771be1c`.
Fifteen successful pages contain all 48,900 numeric audit IDs 154942–203841 under
one fixed upper. Root rechecked gzip/payload hashes, row/UTF8byte limits and
continuity; independent lifecycle/AP reviewers checked their respective evidence
and recovered tail. The initial state snapshot is bound to 203841. Later service
and filesystem observations have separate capture times.

An initial last-page SSH timeout and a subsequent generic collection failure
were preserved. A third call to the unchanged V2function recovered the 122-row
tail. The second failure's SQLite/root cause remains UNKNOWN; successful retry
does not establish BUSY, FULL or I/O as its cause. Original partial manifests
remain acquisition history. Current complete verification is:
`runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31/complete-capture-verification.json`,
SHA256 `b21f3b8acde1c71b11a74ba2619f159b760afc662cab037182b5992346d33e4f`.

## Native lifecycle: observed outcome and remaining proof

The original native SELL was filled 29 October 16:15:20.530 UTC. Prior retained
signal/request/response/fill and 22 persisted cycles in its 90-second admission
window remain linked to the same position, native rules and account/source/config
cohort. The new capture contains no additional market-entry request.

At 30 October 06:15:08.331286 UTC (13:15 Thai), BE_MOVED audit 169435 confirms observed
SL 4015.254 and unchanged TP, following matched SLTP request 169432 and successful
response 169433. The persisted protection activation uses the unchanged predicate;
the underlying SDK profit-calculation return was not separately retained.

At 06:47:20.531424 UTC (13:47 Thai), CLOSED 169977 transitions that owned position to
None. The sender reports profit 33.84, commission 0, swap 0, fee 0 and net 33.84.
Independent Decimal summation confirms the reported components add to 33.84.
This is one sender-reconciled trade outcome, not an independently audited account
return or a claim that forward trading matches research profitability.

The raw opening/closing deals are still required to independently validate
unique tickets, ownership, signed volume, completeness and component totals.
All 69 journal BROKER_EVIDENCE receipts refer to the old 29 October 12:47 packet.
Source tracing showed raw packet publication precedes journal bookkeeping, so
stale receipts alone were insufficient to conclude no newer artifact existed.
The actual existing export directory was therefore inspected read-only: exactly
two regular broker packets exist, captured 29 October 09:21 and 12:47 UTC, each containing 43 deals,
both before the native fill and neither containing its position. No fresh orphan
packet was found in that bounded directory inventory. Receipt:
`capture-2026-10-31/existing-export-artifact-check.json`, SHA256
`ce8afd0d49884d69e8d4de59d1233033b4005c1d589f0445b2fde29c48ad204c`.

#25 stays OPEN for that specific ledger requirement. An existing-sender export
request can be prepared separately; it writes an observational request/packet
and exports full epoch account history because the installed schema has no date
filter or TTL. Read-only SSH permission does not authorize that request. No new
request has been posted.

## Later signals: actual failed predicates

Thirteen new true FULL SELL signals have all their persisted 90-second windows
retained: 470 cycles comprise 312 algo-permission refusals, 154 cost refusals and
four first-quote refusals. No counterfactual fill or missed profit is assumed.

All 9,224 captured `algo_permissions_required` cycles have
`terminal.connected=False` and `account.trade_allowed=False`, while terminal
trade permission, account expert permission and the API-enabled flag remain
permissive. The interval is 30 October 12:00:20–18:00:03 UTC (19:00–01:00 Thai).
These are the exact failed predicates, not evidence that the owner disabled
AutoTrading. Nine FULL windows contain these refusals and also contain cost
refusals; neither cause is claimed to be the sole execution blocker.

All 154 cost refusals report `cost.spec` field `swap_long`, expected −492.0 versus
observed −488.0 POINTS, from 30 October 07:00:12 through 19:46:27 UTC (14:00 through
02:46 Thai). These are historical sender SDK observations, not a fresh cost
attestation, Swap-Free entitlement or permission to accept a new rate. The
unchanged exact-cost policy correctly continues to require review of drift.

## Runtime and AP remain separate unresolved problems

Five persisted `broker_evidence_export_failed` events originated in
`Journal.put` after optional exporter return. The label does not prove raw-file
publication failed. A separately captured existing service log reports another
OperationalError at `Journal.put:64`, propagated through `cli.cycle` at
31 October 01:35:08 UTC, followed by service failure and restart counter 74. That
fault predates the collector's 01:36:57 start. The deployed diagnostics omit the
native SQLite numeric code for these runtime faults; their root cause remains
UNKNOWN.

At 03:23:21 UTC (10:23 Thai), execution service is active/running but reports
NRestarts 95. The active sender cwd matches retained release selected-1c0453.
Known deployed source hashes were read, including shared runner SHA256
`ea904a373dbcbc7afd3832d93aeac7dff2aaf18cf90dcc0a8b636fe9a540fd19`, so its
traceback lines can be mapped without substituting the newer local source.

A point-in-time FD/lock snapshot shows one shared READ lock for the journal
under a QEMU process in the terminal service, plus the execution service's
Python process holding the journal open. This does not identify the guest
process payload, prove historical lock contention, establish causality or
authorize killing a process. No terminal/runtime/lock change was made.

Native 30 October log metadata contains 1,301 handoffs and 1,301 lost messages. Guest
wall-clock alignment and transport-flow causality remain UNKNOWN. A 31 October
scan-only file is not proof of repair or stability. #13 remains PARTIAL;
#14 still lacks a confirmed one-factor repair, matched 1-hour repeat and total
24 hours covering rollover. #34 remains OWNER_DEFERRED/OFF.

## Current decision boundary

Source/financial behavior is unchanged. The earlier constructor/cleanup Journal
patch remains a separate unapplied local proposal; it must not be presented as
a verified repair for the live runtime faults. Any new diagnostic or fix must
name its actual runtime path and validation scope. No permission bypass, cost
acceptance, policy renewal, service restart, external notification, GitHub write
or commit follows from these findings.

Two concrete actions are now prepared, with separate owner questions pending:

- One existing-sender exporter request, script SHA256
  `935ca5728c438414ee00560b571a459fc3257c7a3074282c19d8f2519ca21910`,
  passes eight synthetic controls, root repetition and independent review. It
  creates a private full-history packet on the VM but transfers only the target
  deals, allowlisted metadata and aggregates. One durable approval claim prevents
  another ID under that operation; polling is bounded to 90 seconds, and the
  prior request is conditionally restored. A single request writer is required;
  late publication or an uncatchable process interruption cannot be ruled out.
  No request has been posted.
- The isolated runtime diagnostic patch SHA256
  `002c3132369dd7c80ad8de522602e0ebac2fc5a7398c8c1f413edec2affaa3b4`
  targets only `diagnostics.py`. Fourteen focused tests and three additional
  independent controls pass. It adds validated SQLite code/name fields to
  runtime/fallback errors, leaving SQL, transactions, exception behavior and
  financial callers unchanged. It is not applied, is not a root-cause repair,
  and grants no VM deployment. It and the older constructor patch use different
  baseline-specific alternatives; do not stack them without a rebuilt review.

Private detailed audits and receipts are under
`runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31/`:
`lifecycle-review/independent-lifecycle-review.md`,
`lifecycle-review/complete-lifecycle-coverage-addendum.json`,
`ap-review/AP13-AP14-acceptance-review.md`,
`runtime-metadata-0322.json`, and`process-role-and-source.json`.
