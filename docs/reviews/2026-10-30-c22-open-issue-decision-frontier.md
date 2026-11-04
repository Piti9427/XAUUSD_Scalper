# Selected26b8 remaining issue decisions and evidence

Latest evidence, 31 October: read-only SSH now works with the owner-identified
existing key. Fifteen verified pages retain all 48,900 IDs 154942–203841. Native
BE and close are observed; reported net is +$33.84. #25 remains open for retained
deal-level ledger reconciliation. Actual existing exporter inventory contains
only two packets captured before the native fill. Sender restart counter reaches
95 at 03:23 UTC; native SQLite cause remains unproved. Exact historical algo/cost
refusals and AP limits are documented in
[the current review](2026-10-31-c22-native-lifecycle-and-runtime-frontier.md).
The earlier transport and no-BE/no-close checkpoints below are superseded.

Status: ORIGINAL23ISSUE GOAL INCOMPLETE. Tracker scope now19closed/4open.
The owner-approved comments for #23/#28/#32 were published and read back exactly;
all three issues are CLOSED/completed. A fresh GitHub read31October00:52UTC
confirms the remaining original-scope issues are #13/#14/#25/#34. These closures
cover local implementation and completed research, not VM deployment or forward
profit qualification.

Latest continuation: storage recovered, final standard suite1,620tests passes
with327application/203test pins stable and independent#23review49PASS. H4B now
VERIFIED_COMPLETE after12paths+6fresh repeats and12full-tick audits. Its net is
lower and DD exceeds40% in all views; retain native. Four-study synthesis covers
15policies/108primary/24repeats, with no new candidate selected or forward
qualification. The managed Matrix is updated and strict TypeScript has0errors.
Earlier storage-blocked sections below are historical, not the current blocker.
No VM deployment or actual broker/SDK operation accompanied these closures.

At30October16:51UTC the owner-approved exact comments were published and issues
23,28,32 closed. Every comment was read back byte-exact and every state verified
closed/completed. Original scope is19closed/4open:13,14,25,34. Receipt:
`runs/c22-closure-delivery-2026-10-30/approved-execution-receipt.json`.
This supersedes the preceding pending-publication checkpoint. No VM change or
commit accompanied closure. Issue23 closes local implementation,28closes the
bounded no-improvement study,32closes the retain-native research verdict.

## Current local preparation and required inputs

The first prepared #25 collector was independently tested before use. Synthetic
fixtures reproduced unbounded row payloads, whole-journal JSON parsing outside
the requested range, misleading continuation snapshots, future-cursor clipping,
and a native-log growth race. V1 and its failing witnesses are retained.

Its separate V2 replacement passes19focused tests, repeated by root, and an
independent review with7additional controls including31five-ID presence masks.
V2 pins the initial journal highwater and state to one read transaction, returns
only complete contiguous rows within row/raw-UTF8-byte limits, refuses missing
IDs/future cursors explicitly, and omits later state from continuation packets.
Supplementary host/log observations carry separate capture times; unverified
native wall clocks are not labelled UTC. The8MiB audit-payload cap is not a cap
on the whole serialized packet. Raw journal packets remain private and unredacted.
Source and local synthetic validation:
`runs/c22-native-lifecycle-followup-2026-10-30/reader-v2.py` and its `review/` folder.

No V1/V2 collector has run on the VM. On31October the resumed goal and refreshed
Termius view exposed the existing VM tab and Ubuntu shell prompt. Coordinate
actions still fail with `noWindowsAvailable`; AX/paste/key attempts produced no
visible command or execution output, so no agent-run VM command is verified.
The local host alias still fails DNS. The actual endpoint was identified from
existing Termius connection metadata, but strict BatchMode SSH to that endpoint
timed out. The endpoint is retained privately, not published here.

The owner approved the bounded read-only SSH sandbox escalation on31October.
That exact preflight reached SSH authentication but exited255 with
`Permission denied (publickey)`. The UTC/hostname/UID command did not run, so
remote identity and journal compatibility remain unverified. Host-key checking
stayed strict, updates/multiplexing were disabled, and no new credential or key
was supplied. The approved stop condition for unavailable authentication applied.
The next required input is an existing Mac-terminal SSH alias/agent that can
authenticate, or confirmation that the owner uses only Termius. No credential
file/key/password is requested. The timeout-to-authentication transition shows
that the external attempt reached SSH; it does not fully diagnose the earlier
sandbox network path. Receipt:
`runs/c22-native-lifecycle-followup-2026-10-30/approved-ssh-attempt-2026-10-31.json`.
No SDK reader, service change or order is authorized by this collection. Proposal:
`runs/c22-native-lifecycle-followup-2026-10-30/transport-escalation-proposal-2026-10-31.json`.
Existing29October lifecycle evidence remains historical. #13/#14/#25 stay open.

The separate Journal error-attribution/resource-ownership patch is also still
unapplied, pending the already-requested local-only approval for SHA
`4465b6463da22758537432cb5c28afb74ecf75b0bab4ed19b161a4e3e253033e`.
Its33focused tests and candidate-overlay1,620test pass do not constitute canonical
application or VM rollout. #34 remains OWNER_DEFERRED/OFF.

## Historical implementation and storage checkpoint (superseded)

#23 now uses the actual interval around its existing account_info call, then
validates identity/terminal/capital before persisting the original proof. Root
also reproduced and fixed a diagnostic gap: held management previously discarded
the existing baseline error and a later identity check erased its timing. Public
and persisted results now retain original timing and day_start_valid/reason;
MANAGING and lifecycle exit-day validity remain unchanged. No SDK/baseline call,
financial formula or admission gate was added.76focused tests and8additional
independently designed controls repeated by root pass. The final continuation
has root review; independent reviewers reached their usage limit. Expanded
124focused tests pass after aligning two existing diagnostic/clock fixtures.
The complete1,615test run first identified those two fixture mismatches. Final
rerun then encountered disk exhaustion and97errors; all327app and203test hashes
remained stable, but integration PASS is unproved. Storage is now also blocking
the full regression. Evidence:
`runs/c22-midnight-implementation-2026-10-30/continuation-validation.json`.

H4B is implemented as candidatecbc135c0102a8f92 with16producer tests and18
independent-verifier tests passing. Source/input/cost/ranking/sample and forward
limits are specified before outcomes in `specs/c22-h4-carry-2026-10-30.md`.
Preflight passes; the actual freeze stopped before protocol/cells because disk
free was1,298,432,000bytes,below the fixed2GiB reserve.0/12primary paths and0/6
fresh repeats have run. Only the empty campaign lock exists. Preserve it and
review this lock-only failed freeze after freeing disk; do not bypass the reserve
or delete prior results. No economic winner or independent campaign PASS exists.
Evidence: `runs/c22-h4-carry-2026-10-30-preparation/freeze-blocker.json`.

The sections below retain the preceding decision/proposal checkpoint. Their
unselected/unimplemented wording is historical and superseded by this section.

## Issue23 account-read timing

The current wrapper measures the entire identity call,which includes both
account_info and terminal_info. A deterministic fixture starts the account read
00:00:00.020UTC and returns00:00:00.040,but terminal_info completes at1.140.
The unchanged first-second boundary predicate rejects the wrapper interval.
The same predicate accepts the actual account-return interval. Slow account
response,missing account,foreign identity,disconnected terminal and invalid
capital remain negative controls. This is a concrete avoidable loss of proof,
separate from the general impossibility of recovering an unobserved midnight.

A proposal records timing immediately around the existing single account call,
then completes all existing identity/terminal/capital checks and journal binding
before persisting anything. It retains the one-second rule,first-proof
immutability and original timestamps through failures/restart. No current-equity
reset,window widening,second SDK reader or monetary arithmetic change is proposed.
The broker/runner source has not been changed by this proposal.

Root repeated the candidate's10existing boundary tests and10new regressions;
both passed. Current source retains exactly one expected fast-account/slow-
terminal failure with six passing controls. The patch applies cleanly and binds
original/candidate hashes. See
`runs/c22-midnight-frontier-2026-10-30/implementation-proposal.md` and its receipt.

AccountInfo documents current data as a named tuple,or None on error. That does
not provide a documented atomic broker equity timestamp for midnight. The
proposal removes post-account response latency only; slow/unavailable account
reads and genuinely missed prior midnights remain unproved and block new risk.
[Official account_info reference](https://www.mql5.com/en/docs/python_metatrader5/mt5accountinfo_py).

Owner review is required because accepting an additional genuine mark may enable
daily budget/admission,even with unchanged arithmetic. The prepared approval
scope is local implementation/tests/documentation only,no VM/deployment. #23
cannot be closed from this proposal or from local fixture success alone.

## Issue28 exact H4 options

Two unselected proposals now specify availability,age,causality and data scope:

| Option | Exact hypothesis | Main trade-off |
|---|---|---|
| A public-proxy session M1 | A partial H4 may use actual M1 if every minute with any OPEN/CLOSE_ONLY second is present; waive only fully CLOSED minutes under an explicitly retrospective public calendar. Publish at H4close; age<4h. | Adds genuine observed H4 closes to EMA sequence,while importing unverified historical calendar assumptions. |
| B strict H4 bounded carry | Retain native16/16H4 and its exact EMA200 sequence; use the most recent closed finite macro only while age<8h. Exactly8h refuses; no clock reset or synthetic candle. | Avoids calendar extrapolation but admits one additional interval of older trend context; effect may help or harm. |

Native M15 remains15actualM1 per bar in either case. Both retain fixed0.01,
cost-inclusive10%,daily10%/loss2,cooldown,protection and DD<=40 study gate. A new
full candidate descriptor must bind the H4 policy even if native28field Rules
hash remains26b8. The research gate must be applied to raw_direction before the
existing macro mask; replacing macro after masking cannot restore lost signals.

The new26October public ticks are diagnostic and outside the frozen economic
window. They must not be spliced into the older archive or called Trial7 proof.
Before any economic result,owner selects exact policy/scope,then candidate and
inputs/source/cost/domain are preregistered. Matched native controls,all six
swap-inclusive views,full-tick independent accounting and opportunity/recovery
trade-offs remain required. No candidate has been selected or run.
Proposal: `runs/c22-h4-candidate-review-2026-10-30/review-options.md`.

## Other remaining original requirements

- #13/#14 still need AP causal timing/flow-role evidence,confirmed one-factor
  repair and1hrepeat/total24hrollover observation. A healthy passive scan and a
  safer maintenance module are not AP repair.
- #25 still needs actual eligible BE and completed closed broker cost/cashflow
  evidence. Existing29October18:08UTC capture is historical,not a current VM
  check; no new real SDK/VM read or forced order occurred in this local work.
- #32 still depends on matched H4 research. If a changed candidate is selected,
  an owner-frozen prospective window/sample/stop/assessment contract is required
  before unopened observations. A frozen no-improvement verdict may retain
  native, as the actual issue permits. Historical cadence and already seen
  native trades are not new efficacy samples in either case.
- #34 remains OWNER_DEFERRED/OFF. Local queues do not prove external delivery;
  no channel/recipient/test approval or off-VM receipt is manufactured.

The owner answered both earlier questions: approve local#23fix/tests without VM
deployment and research optionB first. These answers authorize neither a VM
cutover,external message,real-money activity nor public issue closure.

## Environment failure exposed an additional diagnostic gap

The disk-failed full run includes89explicit ENOSPC errors, SQLite open/full
errors and later writer-guard refusals. Source tracing found Journal.__init__
maps every OperationalError from BEGIN IMMEDIATE to another-writer, suppressing
its cause. A separate in-memory mock reproduced SQLITE_BUSY, SQLITE_FULL and
SQLITE_IOERR all becoming `another trial30 writer owns journal`, with the same
single connection/guard close. No actual journal was opened by the probe.

Writer refusal remains fail closed; its attribution can nevertheless mislead an
operator during disk/I/O failure. This is a newly reproduced local diagnostic
follow-up, not proof of a VM writer conflict. Journal source is unchanged; it
needs its own narrow reviewed fix/tests retaining all ownership protections.
Evidence: `runs/c22-local-combined-validation-2026-10-30/journal-error-attribution-probe.json`.
