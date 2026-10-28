# Selected26b8 — forward, boundary, UNKNOWN and deferred-scope frontier

Status: LOCAL_EVIDENCE_REVIEW; source/report date28October2026 (Asia/Bangkok).
This document audits publishedT10/T12/T13/T16/T22/T23 acceptance criteria. It does
not clear a halt, change a financial baseline, enable notifications, resume lot
research, call the SDK or close GitHub issues. Latest runtime/cost deployment
facts belong to the separately dated sender/cost-install reports, not this local
review.

## T10 / #21 — optional alert decision preparation

**Decision recorded: OWNER_DEFERRED; external delivery remains OFF.** The owner
selected “เตรียม monitor ไว้ก่อน ยังไม่ส่งภายนอก”. Publishing or implementing
local diagnostics does not replace that decision.

Three separate facts must remain separate:

1. Local incident/audit/outbox: proves a sender/observer recorded an event. A
   pending queue or log line does not prove receipt by the owner.
2. Delivered receipt: requires an explicitly approved destination, bounded
   sanitized payload, durable stableeventID, transport response and retry result.
3. Off-VM observer coverage: requires an observer outside the Oracle VM. A local
   watchdog cannot observe or deliver its own total-machine outage.

Reviewable options use existing code seams rather than a new sender:

| Option | Payload and recipient | Credential entry and verification |
|---|---|---|
| ExistingTelegramDelivery for incidents | Owner-chosen chat; code/stage/status/observedUTC/correlation only. No login, password, raw broker object or account balance by default. | Owner enters DEMO_TELEGRAM_TOKEN and DEMO_TELEGRAM_CHAT_ID in private VM environment, never chat/repo/issue. After explicit outbound-test authorization, test one known incident, lostack/retry/dedupe and ownerreceipt. |
| ExistingHealthDelivery plus external missing-heartbeat observer | Owner-chosen external endpoint/operator; heartbeat time and sanitized health only. Separate incident delivery receipt. | Owner enters DEMO_HEALTHCHECK_URL privately; explicitly authorize outage scenario and credentials. Test external missingheartbeat whileVM unreachable, delivery/recovery receipts and observerindependence. |
| Continue localonly | No recipient, no outbound credentials or test. | Current decision. Local diagnostics/collector/attendedmaintenance continue independently. |

Implementation references: `scripts/demo_runtime/delivery.py` TelegramDelivery,
HealthDelivery; `scripts/ops/c22_selected_watchdog.py`; current release service
explicitly unsets DEMO_* delivery variables. No channel was enabled in this task.
T10 decision-preparation criteria are satisfied by this recorded deferred choice
and plan. T23 actualdelivery criteria remain blocked by the owner's opt-in.

## T12 / #23 — held-midnight equity proof

**LOCAL_INVARIANTS_VERIFIED; robust-observation limitation remains OPEN.**
Existing source captures actual verified account equity only when both SDK read
start and observed response are in UTCmidnight's firstsecond. It persists the
first accountbound mark, never overwrites it with later equity and never creates
midnight floating equity from current equity after restart.

- `scripts/demo_runtime/boundary.py:_inside_window`, `capture`, `read_mark`.
- `scripts/demo_runtime/broker.py:_baseline`: flatmidnight reconstruction uses
  reconciled complete cashhistory. Heldmidnight requires the genuine mark;
  otherwise `day_start_floating_unknown` blocks admission. Active management can
  continue and a complete close can be recorded without using an invented budget.
- `tests/demo/test_c22_boundary_capture.py` covers before/exact/afterresponsewindow,
  slowSDK, crossedread, persistedrestart, wrongaccount, malformed/nonfinite mark,
  firstproofimmutability, olddayproof and active/provenclose continuity.
- `tests/demo/test_c22_selected_lifecycle_recovery.py` verifies heldmidnight close
  labels an old/unproved baseline invalid without changing its value.

The physical cause of missed proof remains: a response taking beyond firstsecond
cannot prove what equity was at midnight under this accepted contract. Moving
window limits, interpolating equity or resetting to today's firstpoll would alter
financialbaseline semantics. No such policy change is made here. A robust
broker-timestamped equity/floating/cash event source or a separately reviewed
baseline policy is still missing. Therefore do not closeT12 as “always captures”.
The existing deterministic no-proof path is deliberate failclosed behavior, not
proof that its operational availability drawback is solved.

## T13 / #24 — UNKNOWN and reviewed halt resolution

**AUTOMATIC_RECONCILIATION_VERIFIED; MANUAL_RESOLUTION_INTERFACE_OPEN.**

Currentpublic lifecycle preserves persistedrequest/positionidentity, waits for
completeopening/exitcashvolume evidence, reconciles a provedclosedposition after
restart and never blindresends. `safety_halt` remains latched even after automatic
brokerreconciliation establishes closure. That distinction is correct.

Concrete regression references:

- `test_unknown_intent_resolves_complete_exit_after_restart_without_resending`
- `test_incomplete_history_never_clears_active_or_sends_again`
- `test_unknown_exposure_never_infers_flat_from_complete_exit_history`
- `test_missing_owned_opening_never_infers_close_from_an_empty_account`
- `test_read_only_reconciliation_never_weakens_mutation_or_demo_identity_gates`
- `test_resolved_unknown_latched_halt_still_blocks_fresh_entry_after_restart`

Missing work is an incidentbound operatorreview module and reviewed application
step, with account/source/incident/request/proof hashes, actualcompletebrokerproof,
no foreign exposure, bounded freshness, explicit outcome/reason and an appendonly
resolution record. Wrongincident/staleproof/foreignexposure/restart negative tests
must precede activation. A generic instruction to continue does not prove an
individual incident's broker outcome or authorize timestamp-based clearing.
No manual `journal.put('safety_halt', None)` workaround is approved by this review.
T13 stays open until that concrete seam and its approval evidence exist.

## T16 / #27 — passive collection and bounded sealed batches

A new standalone localcollector, `scripts/ops/c22_forward_seal.py`, reads only a
consistent localSQLitebackup from the existing sender. It never opens an SDK
session or changes the financialjournal. It freezes a source-manifest/cohort and
realcreation time, then seals every matchingauditkind in a halfopenUTCwindow,
includingrejections/UNKNOWN/losses, with auditIDs,eventIDs,originalpayloadbytes,
payloadSHA/hashchain and a recheckeddenominator report. Eachoutput is new under
ignoredruns; no historicalsource is overwritten.

Publicfunctions:

```python
freeze_protocol(journal, source_manifest, output,
                release_hash=..., config_hash=...,
                freeze_utc=..., exposed_through_utc=..., now=...)
seal_batch(journal, protocol_directory, output,
           since=..., until=..., now=...)
verify_batch(output)
```

The first localboundedbatch reads an actual downloaded post-cost-install backup.
It is labelled **REUSED_HISTORY**, with zero prospectiveobservations. It is not
freshholdout, even though new hashes were produced now. Subsequentrecords can
only receive `PROSPECTIVE_COLLECTION_ONLY` when the window begins after the real
freeze and auditIDs exceed the bootstrap highwater. Qualification, evaluation
samples/stoprules and retuning decisions remain the separateT21 protocol.

Artifacts:

- `runs/c22-issue-closure-2026-10-28/forward/protocol/`
- `.../historical-first-batch/` and `historical-batch-verification.json`
- `.../collector-feature-red.log`, `collector-integrity-red.log`, `collector-green.log`
- `.../source-coordinates.json`, `paused-guards.json`, `frontier-tests.log`

Coverage remains explicit: auditrows are not rawticks; missingepochbrokerledger,
accountcashflows or costproof are UNKNOWN/NOT_CAPTURED, never zero. Requests,
responses,costviews and cyclepolls are not independenttrades. The source-manifest
bytes are frozen as provenance; they are not a newruntimeattestation.

T16 can close only when the collector plus a realboundedfirstprospectivebatch
and integrityreport exist with every requiredcoverage dimension either actual or
explicitly missing. Currentfirsthistoricalbatch alone is insufficient. A passive
postfreezeVMbackup can supply a firstobservedbatch; it cannot create absentticks/
cashflows or turn reusedhistory into qualification evidence. An actualcomplete
cashflow/costattachment seam remains required for broad economicqualification.

## T22 / #33 — lot compounding remains paused

**OWNER_PAUSED; documentation guard satisfied; never an executionfrontier task.**
Nativevolume is0.01fixed. No lotgrowth implementation, economiccampaign or MT5
change is authorized from ticketpublication or this review. Owner must explicitly
resumecompounding first. A laterresearchprotocol must freeze growthformula,
startingcapital/cashflows, minimumlot/gridrounding, riskcap, commission/swap,
restartaccounting and matchednativecomparison before using results. Pausedscope
is preserved in `paused-guards.json` and publishedT22. Keepingthebacklogvisible
satisfies its guard; it does not authorize unpausing to “close allrootcauses”.

## T23 / #34 — actual external delivery remains deferred

**OWNER_DEFERRED; blocked by T10 opt-in.** No testmessage was sent. The module's
existingdurable queue/retry mocks do not establish realreceipt or an off-VMoutage
observer. Approval must namechannel/recipient and outboundtestscope, then prove
actualreceipt,retry,recovery,privatecredentialstorage and nonfinancialpayloads.
Until then keepOFF. Localcollector/diagnostics are not blocked by this choice.

## Acceptance verdict

| Ticket | Verdict | Closure boundary |
|---|---|---|
| T10/#21 | OWNER_DEFERRED_DECISION_RECORDED | Reviewablechoices/privacy/credential/testplan prepared; external remainsOFF. |
| T12/#23 | LOCAL_INVARIANTS_PASS; OPERATIONAL_GAP_OPEN | Existingfirstsecond proofsafe; no robustalternativebrokerproof or financialpolicychange silently adopted. |
| T13/#24 | RECONCILIATION_PASS; RESOLUTION_INTERFACE_OPEN | Noresend/provedclosed tests; incident-specific reviewedunhalt stillmissing. |
| T16/#27 | V2_COLLECTOR_AND_FIRST_BATCH_PASS; COVERAGE_GAPS_OPEN | Follow-up froze exact deployed archive/config/account and full stream prefix. Actual38record/67.451871s postfreeze batch independently matches its source backup. Missing rawtick/currentcashflow packet remains UNKNOWN. |
| T22/#33 | OWNER_PAUSED_GUARD_RECORDED | Nativefixed0.01; explicitresumeprerequisite. |
| T23/#34 | OWNER_DEFERRED; OFF | No channel/recipient/outbound-test approval or realreceipt. |

The report author's audit did not mutate GitHub. Root's subsequent verified
closure/readback is recorded in `2026-10-28-c22-issue-closure-progress.md`.
The goal to close all23 issues remains incomplete. Missing evidence is not PASS;
paused/deferred financial or outbound work is not silently enabled.

## V2 follow-up — actual post-freeze collection

Independent review reproduced empty-manifest, foreign-account/stream, silent
excluded-denominator and missing cashflow-attachment gaps. V2 now verifies the
actual release archive/config hashes, account fingerprint, recent bootstrap
identity and complete audit prefix. Every in-window row is sealed; excluded,
malformed and ID-gap coverage remains explicit. Optional same-sender epoch
ledger bytes must pass original-time/account/source/count/cash checks.

Nine public tests pass, including manifest/account/rewind rejection, excluded
denominators, signed cashflow reconciliation and independent source-backup
verification. Final actual protocol frozen14:01:18.968493UTC, SHA256
c90147a355ddafaa514061f7ef8b9cad80d3b9a97e3dbc7545faa364cccb87e5.
Actual first batch14:01:19.968493–14:02:27.420364UTC contains38records,37CYCLE/
1HEALTH,28permission-blocked/unknown cycles,zero ID gaps. This is collection-only
prospective data; no performance holdout or qualifying trade sample is claimed.
No REQUEST/RESPONSE/LIFECYCLE was in the batch. Broker fills/net/full cashflows
and raw tick coverage remain unknown; #27 stays OPEN for those coverage inputs.
Original v1/failing artifacts are retained; none was relabelled as a v2 pass.
