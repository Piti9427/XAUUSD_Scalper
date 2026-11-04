# Attended maintenance C v2 notification handoff proposal

Status: OWNER APPROVED LOCAL SOURCE/TESTS; IMPLEMENTED LOCALLY. This addendum
refines the selected C typed-plan family. Existing execution-time
approvals and their zero-outbox predicates remain unchanged. Nothing here
authorizes VM execution,external delivery,renewal,financial changes or publication.

## Verified conflict

All three saved cost/AP/reboot guards count `events WHERE sent=0` and require
zero. That table is a notification outbox. `Journal.flush(None)` preserves pending
rows while delivery is OFF; a confirmed exit adds an event rather than removing
its earlier FILLED notification. A flat state alone cannot make that queue empty.

The source-backed offline reproduction includes a successful ordinary selected
entry with a pre-existing pending notification. Thus notification backlog itself
does not block normal reviewed Admission. Current optional renewal code also
does not contain this predicate; the coupling is in the saved attended wrappers.
No activation or current broker result is inferred from that source finding.

Existing reboot proof protects audit prefix and selected KV bindings and reports
queue counts. It still passes after a disposable fixture changes only
`events.payload`. It therefore cannot certify full notification continuity for
a future nonempty handoff. Its original zero-outbox scope is not relaxed.

Evidence: `runs/c22-notification-handoff-2026-10-30/` includes exact source
hashes,real Journal fixtures,three actual saved guards,public selected-cycle
disproof and an independent repeat. No real SDK,journal,VM or notification was
used by these experiments.

## Proposed policy modes

The typed plan identifies its exact mode. Preparation cannot grant authority.
Every actual operation still needs execution-time approval binding its source,
account,configuration,cost/review generation and permitted recovery.

- STRICT_ZERO remains the existing contract and the compatibility default.
  Legacy approvals cannot be interpreted as permission for another mode.
- OFF_NOTIFICATION_HANDOFF is proposed only for separately approved plans with
  proven sender notification delivery OFF and no in-flight/uncertain delivery
  work. It preserves all queued rows. No transport is enabled and no delivery
  receipt is fabricated. Notification data never becomes an order command.

For the proposed handoff mode,the approved private plan must bind pending count,
event identities,payload hashes,sent markers,known notification schema/kinds and
the applicable delivery state. Unknown schema/kinds or unproven delivery state
defer the operation. CRITICAL alerts are not assumed to be confirmed trade
events: any associated unresolved condition or unreviewed critical item requires
operator review. Existing financial/exposure/incident gates cannot be overridden.

## Required safety invariants

1. Keep fresh broker flat/noorders and Journal noactive/noUNKNOWN/nohalt checks.
   Prove quiescence and actual sender inactivity before exclusive broker reads.
2. Preserve the current owned manager when exposure or uncertainty is present.
   Do not force close,clear a halt or remove cooldown/risk gates for maintenance.
3. Explicitly classify pending notifications and separately inspect their
   unresolved conditions. A count alone cannot prove what the queue contains.
4. Capture every existing outbox row and its full accepted schema,including raw
   payload bytes,identity and sent state. Retain delivery state where applicable;
   missing evidence means deferred. Do not discard unrecognized fields.
5. The maintenance module accesses the financial Journal read-only. It must not
   delete,drain,requeue,mark sent,renumber,reset or restore notification rows.
6. Independent before/after verification compares each original row exactly,
   including presence and payload,not only aggregate count. Legitimate new
   runtime notifications may append after manager restoration; they do not
   justify altering prior rows. Attribute permitted later changes explicitly.
7. Retain source/cohort/event lineage and the existing audit prefix. A private
   review may inspect payloads; public summaries contain sanitized counts and
   hashes,not account data or raw message contents.
8. OFF mode must not acquire a notification transport or call a broker sender.
   Once-only financial intent/reconciliation rules stay unchanged.
9. After restoration,a live owned manager survives a failed handoff proof.
   Report STATE_REVIEW_REQUIRED with evidence; do not rewind financial state
   or stop management to force equality.
10. Preserve the bounded pause,recovery reserves,durable handles and uncertain
    reboot no-redispatch rules in the base typed-plan contract.

## Proposed local implementation and tests

Implement the reviewed C module and three action adapters with this explicitly
selected handoff mode only after owner confirmation. Keep STRICT_ZERO available
for existing scopes. No actual SSH/SDK/systemd calls occur in this local phase.
Use recording adapters and real temporary SQLite/files for deterministic tests.

Required tests cross prepare/run/read-only-inspect and independently query
SQLite. Cover empty strict mode; queued FILLED/BE/CLOSED with delivery OFF;
queue retention across restart; changed payload with unchanged count; deleted or
renumbered event; altered sent flag; unknown event kind/schema; unreviewed or
unresolved CRITICAL alert; uncertain/in-flight delivery; source/cohort drift;
missing mode approval; active/UNKNOWN/open broker exposure; legitimate append;
and handoff proof failure after owned management resumes.

Existing source/economics/risk/position protections remain unchanged. No new
backtest or profitability claim follows from notification continuity tests.
Local implementation now exists under `scripts/ops/attended_maintenance/` with
39passing focused tests. Host effects are exercised only through a recording
adapter; no actual SSH/SDK/systemd/production adapter was introduced. Standard
full-suite status and independent-review limits are explicit in
`docs/reviews/2026-10-30-c22-attended-maintenance-local.md`.

## Decision requested

The owner confirmed C-v2 and local implementation under the reviewed OFF
notification handoff contract. Choosing handoff
does not authorize external alerts or a VM rollout. Each later VM operation
still requires its own fresh proof and explicit execution-time approval that
includes the selected mode. The original23issue goal remains incomplete.

## Concrete local interface

`Maintenance(financial_journal)` derives one canonical private operation store
for that approved financial journal. One account must retain its existing one
canonical journal; a duplicate financial database is not an alternative account
or execution identity. No financial schema is migrated.

- `prepare(plan,host)` returns a frozen `Handle`; it only reads host observations
  and the financial journal and writes a private operational receipt.
- `run(handle,approval,host)` starts or continues the same operation. Closed
  AP/cost/reboot adapters own their different recovery rules. There are no
  caller-authored shell steps or arbitrary callbacks in a plan.
- `inspect(handle)` only reads the stored receipt; it never contacts a host or
  changes permission. The approval binds exact prepared evidence and recovery
  permissions. It is a caller-supplied record of owner authority,not a signature
  or an authority manufactured by preparation.

The first handoff implementation conservatively freezes every existing outbox
row and accepted schema at preparation. Any changed or extra pre-quiescence row
requires new preparation/review. After restoration,new notifications are allowed
only with matching cohort and original audit lineage; original rows remain byte
equivalent in id/payload/sent. Unknown legacy kinds/schema/cohorts defer rather
than being silently classified. CRITICAL review binds its exact row/payload and
requires no unresolved condition. Existing historical approvals never acquire
handoff authority automatically.

Host observations/effect receipts remain a true external seam. A future host
adapter must supply actual source,exclusive-reader,backup,process identity,
conditional review/pointer recovery and outside-clock evidence. The local tests
do not establish any of those live facts. The library has no production CLI,
transport or default host adapter; it cannot operate the VM by itself.
