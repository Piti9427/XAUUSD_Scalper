# Selected26b8 — attended reboot and artifact restoration proposal

Latest29October2026: owner approved the original plan; one actual reboot and
exact review restoration completed. Automatic recovery and source/journal proof
are recorded in `docs/reviews/2026-10-29-c22-attended-reboot-verdict.md`. The
original approved bytes/SHA are preserved under
`runs/c22-approved-reboot-2026-10-29/approved-proposal.md`. No public issue write
or commit was authorized by the reboot operation. A separate subsequent approval
authorized the exact public#26summary/closure; readback passed15:56:35UTC. No
additional VM change or commit accompanied publication. The original proposal below is
retained as its execution context.

Scope: GitHub#26/T15. This proposal does not authorize itself. The earlier AP
measurement approval has been fulfilled and does not cover a VM reboot.
An ordinary reboot necessarily restarts OS,terminal and sender processes. Their
approved binaries,configuration and runtime versions remain unchanged.

## Current evidence and fixed scope

Read-only VM observations on29October2026 verify all four selected boot links:
execution,terminal,watchdogtimer and backuptimer are enabled and target their
actual installed units. Old selected/shadow execution paths are inactive and
disabled or absent. Both immutable source releases pass their SHA manifests and
share the same account writer-guard directory. No boot registration change is
needed. Exact private evidence is under `runs/c22-reboot-readiness-2026-10-29/`.

The intended current bindings are deliberately retained:

- Sender release: `selected-1c0453dcf92db05d`.
- Sender unit SHA256: `2764cc011add28bd4c25a9aef5a34b4962d270982aba6d70e125f6524ddc8040`.
- Terminal unit SHA256: `c156e82c6aaede73ec13ba6a93e188d4cb57f33ad8648904d774370bb97ca5f7`;
  its retained launcher references `selected-9cfc54a3dc78f0ae`.
- Cost policy SHA256: `07513b047e2aafe0ab227026494e7620753d7800f1c48385abbb6262aa7e6985`.
- Execution review SHA256: `1726e848809920770eda905e9340d65d0b66bb3641779da20e536b8383ec3a95`.
- Policy/review remain symlinks to the approved29October cost-export generation;
  expiry stays5November2026 at09:20:46.969923UTC. No renewal or cost acceptance.
- Native26b8,fixed0.01lot,all existing risk/ownership/source/cost gates and the
  financialjournal remain unchanged. No private credential/prefix backup is read.

Do not run `enable_selected_boot.py --apply` or replace units to make its old
packaged-unit equality check pass. It expects both installed units to match one
release manifest; the separately approved exporter unit and retained terminal
binding are an intentional later operational state. Actual installed pins and
their approved provenance govern this test. This is not permission to bypass a
financial or identity gate.

## Honest boot and restore semantics

On a flat account,missing execution review causes runner-factory startup to exit
before SDK initialization. The existing unit then retries every10seconds. It
does not start a healthy flat manager while the review is held. Active/UNKNOWN
ownership follows its existing management exception; never stop that manager.
Source trace: selected `__main__.py` runner factory → `execution.py`
`install_execution_review`/initial check → shared `cli.py` factory/exception path.

Therefore use a two-phase test,with distinct outcomes:

1. Actual boot with new admissions deliberately held: prove the new boot ID,
   enabled units and automatic service invocation. The expected missing-review
   startup refusal is labelled `BLOCKED_BY_PLANNED_MAINTENANCE`,not healthy
   manager proof or an unexplained APfailure.
   Capture the actual stderr/stage/code and prove the deliberate held-review
   state. The public startup reason can be `selected_execution_review_invalid`
   at `cli.runner_init`; do not invent a literal `review_missing` log event.
2. After source/state checks,restore the exact original review artifact and let
   the existing automatic restart recover the sender. Do not manually start a
   service and call that automatic recovery. This proves recovery after artifact
   restoration; it does not claim an unassisted cold start without the hold.

## Bounded execution plan,only after explicit approval

1. Re-read the pinned units,releases,public binaries,review/policy and enabled
   links. Require fresh Demo/identity/flat/noorders/noactive/noUNKNOWN/nohalt and
   empty sender outbox. Capture a new consistent private journal backup,download
   it and verify raw/gzip SHA,SQLitequick_check and rowcounts before entry pause.
   Existing AP backups are earlier evidence,not substitutes for this fresh step.
2. Move only the exact review symlink into a unique owned maintenance directory.
   Wait for a completed sender cycle after revocation proving persisted flat and
   empty outbox; then stop only the flat sender. Take the stopped journal/state
   proof. If exposure/UNKNOWN appears,retain its manager and defer the reboot.
3. Use one exclusive read-only SDK probe while sender inactive. Require fresh
   Demo/hedging identity,complete reconciled cash/deal history,flat/noorders,
   preserved source/policy and a valid quote. Close the SDK reader and verify it
   ended. Preserve six financial keys,accepted review marker,audit highwater and
   original payload-prefix hashes. Capture stable cache+sidecar hashes,owners/
   permissions and review/policy symlink targets. No DB checkpoint/reset/restore.
4. Recheck freshness and no state drift. Keep the original review held. Request
   exactly one ordinary VM reboot. Record the preboot ID/time; do not perform a
   second reboot,power cycle,package update or boot registration change.
5. Reconnect with the same existing strict SSH identity. Require a changed boot
   ID and actual automatic unit invocation evidence. Inspect current source/
   unit/dependency/link/guard/binary hashes and journal/cache continuity before
   restoring admission permission. A missing/stale review remains an explained
   planned hold; kernel/SSH/terminal/AP failures remain separate outcomes.
6. Restore only the held original review symlink with its exact target and SHA.
   Do not rebuild it,change timestamps/expiry,reset its persisted marker,or
   overwrite an unexpected replacement. Wait for the existing automatic retry;
   no manual `systemctl start` or restart in the automatic-success path.
7. Verify the new automatic invocation,a fresh source-bound execute cycle,single
   sender/account writer guard,same cohort,cache reuse,watchdog/backup timers and
   preserved six financial keys/audit prefix. Attribute any legitimate later
   broker events from original records rather than restoring old financialstate.
   Existing sender reads supply postboot broker observations; no second SDK
   reader runs beside it. No forced signal/order or fabricated fill proof.
8. Record actual review-artifact restoration and hashes separately from journal
   continuity. Healthy process startup,market/admission readiness,native fill/
   BE/close and profitability are separate results. AP/quote/signal refusal can
   remain a valid gate even after boot recovery succeeds.

## Time budget and recovery

Plan an attended15minute maintenance window,including reboot,entry hold,checks
and recovery; preparation/download checks happen before entry pause. Keep time
for restoring the original review and manager. If automatic restart does not
recover after review restoration,record automatic recovery as FAILED/UNPROVED.
An explicitly approved fallback may start the exact original sender only when
inactive and no conflicting/owned manager exists. Keep any active/UNKNOWN
manager; never kill it or rewind financialstate to make the test pass.

If VM/SSH does not return,the local operator cannot guarantee a15minute outage
limit or remotely undo a completed reboot. Owner assistance through the existing
Oracle console may be required. Do not broaden cloud permissions,read private
credentials,replace the VM or purchase infrastructure. Report the failure and
preserve all available evidence. A reboot approval must acknowledge this path.

No auto-renew,external notification,terminal/runtime binary or version change,
strategy/cost/lot change,real-money activity,GitHub publication,commit or push
is included. Successful
local preparation is not#26completion. Actual observations and a separately
reviewed publication payload are still needed before closing the public issue.
