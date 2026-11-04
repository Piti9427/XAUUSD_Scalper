# Selected26b8 attended maintenance deepening

Status: C-v2 LOCAL VERIFIED; NOT DEPLOYED.
Owner selected Attended maintenance and confirmed
coverage of AP measurement,reboot and cost installation with separate adapters,
then selected C: typed plans with a durable operation handle. The final local
implementation contract was approved with the C-v2 addendum. No VM
execution,renewal,financial-policy change or deployment is authorized here.

30October review addendum: exact saved guards conflate pending notifications
with a zero-outbox maintenance prerequisite. C v2 proposes an explicitly
approved,notification-preserving handoff with stronger row continuity proof:
`c22-attended-maintenance-notification-handoff-2026-10-30.md`. The owner approved
this for local source/tests only. Existing strict-zero VM approvals remain
authoritative. Implementation evidence:
`docs/reviews/2026-10-30-c22-attended-maintenance-local.md`.

## Problem and intended outcome

Future campaign authors should supply a reviewable operation and its exact
approval without recreating safety sequencing,recovery and evidence linkage.
The module must concentrate this knowledge rather than wrap `systemctl` calls
while leaving their ordering with callers. It serves future campaigns only.
Historical campaign files,tests,source pins and evidence remain immutable.

An actual AST comparison verifies identical Journal guard functions in cost,
AP and reboot workflows,and identical same-review manager recovery in AP and
preboot. Cost generation recovery and uncertain reboot handling are different
rules. Source hashes and comparison results are retained in
`runs/c22-goal-close-frontier-2026-10-29-late/architecture-source-pins.json`.

## Confirmed decisions

- Owner selected Attended maintenance after the four-candidate review.
- First version covers all three evidenced operation families with separate
  action adapters,approval scopes and recovery rules.
- Owner selected C: typed plans plus a durable operation handle. The proposed
  three-entry-point refinement below still needs final contract review.
- Existing owner Q1–Q9,one-account/one-sender,exact economics/spec review and
  the intended maximum15minute pause remain applicable. Preparation is not a
  trading cooldown. A new-entry hold and owned Reconciliation are distinct.
- Frozen Selected26b8,0.01lot,risk/cost gates and financial Journal stay unchanged.
- A plan,fixture,local test or prior approval does not create authority for a
  new operation. Old fulfilled reboot/cost approvals cannot authorize new runs.

## Three interface alternatives

### A Single operation entry point

`run(approval_ref)` starts or continues the operation identified by that exact
reference. The module hides preparation,quiescence,proof,action and recovery.
Repeated calls inspect the same operation; they cannot repeat an irreversible
dispatch. Strong depth and low caller knowledge. Preparation/discovery must
still be separately inspectable so an operator can review what would happen.

### B Explicit event and effect interface

`open`, `inspect`, `advance` and `dispatch` expose a versioned operational state
machine. A deterministic reducer selects legal effects and records their intent
before dispatch. Excellent forensic replay and explicit interruption handling;
largest interface and highest schema/versioning cost. It risks becoming a
general workflow engine despite having only three justified operation families.

### C Typed plans and durable operation handles

`prepare`, `start` and `advance` accept a closed plan family: AP measurement,
approved cost installation or attended reboot. Preparation produces a reviewed
manifest and never grants permission. Start requires exact execution-time
approval. Advance observes or continues the same recorded operation after a
timeout or reboot. The module owns sequencing and action-specific recovery;
callers do not supply callbacks,phase overrides or shell-command step lists.

C was selected for repeated reviewed campaigns. Use A's small caller surface
and B's durable intent/uncertainty principles internally. Refine the external
interface to `prepare`, `run` and read-only `inspect`: `run` starts or continues
the exact approved operation identified by its durable handle; `inspect` never
executes recovery or starts a reader. This avoids making a status check a
mutation. Names,receipt shape and resume authority remain proposed until final
contract review. No new public contract has been implemented.

## Required invariants

1. Validate exact operation ID,owner approval,allowed changes,account,source,
   config,units,review,cost generation and verified backup before mutation.
   An operation cannot grant or widen its own authority.
2. Require one sender and fresh flat/noorders proof plus no active/UNKNOWN,
   safety halt. STRICT_ZERO additionally requires zero pending notifications;
   approved C-v2 local handoff instead preserves each classified OFF queue row.
   Journal state and broker evidence are
   distinct. A MANAGING position defers maintenance; no forced close.
   The ordering is fresh Journal flat proof,post-hold Journal proof,verified
   sender inactivity,then exclusive fresh broker flat/noorders proof. Never
   obtain overlapping pre-stop SDK proof.
3. Hold new Admission and verify a fresh post-hold cycle before stopping.
   If quiescence is unproven,preserve the manager. After a stop request,verify
   actual inactivity; a timeout does not prove the process stopped.
4. Prove exclusive SDK ownership before the existing read-only broker proof.
   No second reader may overlap the sender or an existing probe. Probe cleanup
   binds host,boot,PID/start identity; do not kill by a broad process name.
5. Start pause accounting at the first actual Admission hold. Each action must
   fit its approved work allowance and recovery reserve within the total
   intended maximum900seconds. Expiry stops new work; it does not justify
   abandoning an owned manager. Report actual overruns and timing uncertainty.
6. Preserve primary failure independently of cleanup and recovery failures.
   Cleanup failure cannot replace the primary evidence or skip eligible recovery.
7. Financial Journal access is read-only. Verify original audit prefix and
   protected-value presence/cohort. Never restore an old financial database,
   clear incidents,reset daily equity or erase later broker events.
8. Legitimate later runtime events must be attributed. A day transition or
   accepted generation is not silently overwritten to satisfy equality. If its
   continuity cannot be proven,report unverified continuity and preserve facts;
   the module does not invent replacement financial semantics.
9. Persist an irreversible dispatch attempt before sending. Crash between
   intent and acknowledgement yields uncertainty,not proof of non-dispatch.
   No claim of transactionally exactly-once execution across SQLite/systemd.
10. On SSH timeout,reobserve the same durable operation/process/boot identity.
    Never create a replacement action solely because observation timed out.
    Serialize different operation IDs per account as well as competing callers
    of the same operation. A handle alone is not an idempotency guarantee.
11. Recovery may use only the action and fallback scope actually approved for
    that operation. Expired approval is not authority for fresh work. Passive
    inspection and the existing owned-management obligations remain distinct
    from permission to perform another maintenance action.
12. Restored permission is not proof of entry readiness or profitability.
    Existing Admission independently evaluates each new order.
13. After the manager is restored,flat admission prerequisites no longer act as
    stop conditions. Preserve a live owned manager if later proof,source or
    protected state drifts. Return an unverified outcome; never stop or rewind
    that manager solely to make maintenance verification pass.

## Proposed effect and recovery contract

The work deadline and any expiry explicitly present in an owner grant are
different constraints. The deadline ends new work; it does not create a broader
grant. Required recovery must already be in the exact plan/owner approval.
There is no newly invented periodic approval expiry. Reinstating an unchanged
expired review never renews it or makes it eligible for new entries.

| Effect | Repeat and deadline behavior |
|---|---|
| Passive inspect | Read the existing receipt/handle and non-SDK observations. No mutation or permission restoration. |
| Owned probe cleanup | Allowed only for the exact recorded owned child and approved cleanup scope. Reobserve identity before signalling; never relaunch because of timeout. |
| Same-review restoration | Conditional completion of approved recovery only when the exact held artifact and destination are proven safe. Occupied/drifted destination requires operator review. No expiry extension. |
| Coherent cost recovery | Consult the persisted acceptance marker and existing independent validators. Retain the accepted generation where required; unknown marker forbids guessing or reset. |
| Manager start/fallback | Only if explicitly in this operation's recovery approval and no live/competing manager or reader exists. Reobserve before start. A running owned manager is preserved. |
| Reboot dispatch | One recorded dispatch attempt only. Ambiguous outcome permits observation,not redispatch or generic preboot start. |
| Postboot permission restoration | Requires the approved recovery scope,changed boot,source/Journal/cache proof and expected startup evidence. Distinguish automatic retry from explicitly authorized fallback. |

If an effect lacks authority or safe proof,return OPERATOR_REQUIRED without
inventing permission. Record primary,cleanup and recovery failures separately.
Each action has a stable effect identity and class: repeatable observation,
conditionally completed mutation,or irreversible non-repeatable attempt.

For the first version,any protected day/value transition not proven by the
existing independent verifier produces CONTINUITY_UNVERIFIED. Keep the observed
manager and all later facts; do not label an appended audit record as financial
attribution proof. Robust held-midnight proof remains #23.

Cross-boot time needs a trustworthy outside observer with a recorded bracket.
Absent that evidence,return TIMING_UNVERIFIED alongside the host-UTC interval.
Do not call a host-UTC difference a clock-independent bound or report completion
of the timing gate solely because the numeric difference is below900seconds.

## Distinct recovery adapters

| Family | Recovery knowledge retained by its adapter |
|---|---|
| AP measurement | Independently clean up the owned probe; restore the exact original review; preserve or recover the approved manager and verify a fresh cycle. Do not restart terminal implicitly. |
| Cost installation | Use the persisted acceptance marker to retain/restore one coherent authorized generation. Never pair an old policy with an accepted new review or rewind the marker. Economics validators remain independent. |
| Attended reboot | One durable dispatch attempt. After ambiguity,observe the existing attempt. Verify changed boot,source,Journal/cache continuity and expected boot invocation before restoring exact permission. Distinguish automatic retry from specifically approved fallback. |

## Dependencies and test surface

Filesystem and SQLite are local-substitutable dependencies: use real temporary
files and SQLite in tests. The financial Journal opens read-only; the operational
receipt is separate. SSH/process/time observations use recording adapters and
the existing host adapter. Broker proof is a true external dependency with the
existing exclusive reader and a deterministic test adapter. Neither adapter
exposes order sending. Tests and future callers cross the same module interface.

Required observable scenarios include stale/foreign proof,source or approval
drift,owned exposure during quiescence,stop timeout with live handle,lingering
reader,dual primary/cleanup failure,pointer interruption,accepted/unknown cost
generation,crash around reboot dispatch,unchanged boot,uncertain cross-boot time,
budget reserve exhaustion,append-only continuity,protected-key presence change,
controller restart,competing account operations and a manual fallback mislabelled
as automatic recovery. Assert the financial SQLite bytes/prefix/protected-value
presence independently in tests; the module's own PASS receipt is insufficient.

Archive tests and independent accounting verifiers remain preserved. New
interface tests replace duplicated shallow tests only for future callers after
equivalent coverage exists. The new local interface has39passing focused tests.
Full-suite results and legacy clock-sensitive failures are recorded separately;
no actual production adapter or VM result is inferred.

## Relationship to the23issue goal

This design can reduce recurrence and make future AP maintenance easier to
verify. It does not close #13/#14 without actual causal/fix evidence, #23 without
a valid held-midnight proof method, #25 without observed lifecycle/cashflow,
#28 without its distinct H4 evaluation, #32 without its remaining study/protocol
criteria,or #34 without the owner's external-delivery decision and receipts.
Fresh GitHub state reads retain16closed/7open. Latest read-only native checkpoint
at29October16:53UTC still shows the one owned SELL managed with initial protection;
no BE or completed close has yet been observed.

## Remaining design decisions

Owner confirmed C-v2 local implementation and tests. The separately verified
launcher diagnostic bug fix is outside this proposed module and does not grant
its execution authority. Any later VM use needs
its own concrete execution-time approval and fresh operational proof; current
held exposure is not eligible for maintenance. No architecture choice reuses
fulfilled prior VM approvals or enables auto-renew/external delivery.

## Approved local implementation scope

The selected contract is implemented as a new operational module under
`scripts/ops/attended_maintenance/` with its three closed action adapters and
behavioral tests under `tests/ops/`. It exposes `prepare`, `run` and read-only
`inspect`,using existing standard-library facilities and repository conventions.
No new dependency,public network API or financial Journal schema change.

The first delivery is local source and deterministic verification. Existing
campaign controllers remain preserved evidence,not migration targets. Tests use
recording host/process/broker adapters and real temporary files/SQLite. No real
SSH/SDK/systemd/broker invocation,VM installation,policy renewal,forced order,
public GitHub write or Git commit accompanies implementation.

The owner review should confirm this scope and the preceding invariants/effect
matrix. Any later production adapter use,source cutover or VM diagnostics needs
its own concrete proposal and execution-time approval. Local completion does
not substitute for #13/#14 live causality/fix validation or close those issues.
