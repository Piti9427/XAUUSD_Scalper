# Selected26b8 AP clock/transport measurement — preparation and actual bounded run

Status: ACTUAL BOUNDED MEASUREMENT VERIFIED29October2026; AP CAUSALITY/FIX
UNPROVED. Owner explicitly approved this separate operation. #13/#14 remain
open. The preparation sections below preserve their earlier source context;
actual execution and limitations are recorded at the end.

## Falsified hypotheses and remaining uncertainty

The preserved18:20UTC capture shows the native scan→handoff→lost loop continuing
through a sender restart. SDK initialize occurs once before the loop,not on every
cycle. Captured AutoTrading/expert flags are enabled while connected/account
availability fail. Thus no source evidence supports removing permission gates,
strategy cooldown or adding repeated SDK initialization. A terminal restart
preceded later recurrence at the next periodic scan; it is not a durable fix.
Native log timestamps alone cannot establish a kernel transport failure's order.

The corrected host two-second bracket bounds wall-minus-monotonic elapsed to
−1720..2720ns for that observation only. Guest elapsed was not measured. No guest
clock defect,network trigger or clock health over the whole incident is inferred.

## Verified executable identity,not guessed configuration

A passive process-only read at28Oct20:14:25.696746UTC observed sender PID126749
using `/home/ubuntu/c22-qemu-control/wine-11.0-source/bin/wine` and
`C:\tools\c22-runtime\Scripts\python.exe`. Its child126764 showed the same
Windows Python path. No environment file/variable,credential or key content was
read. These are observations at that time,not authority to launch a new process
or proof of the future runtime context.

Before any future execution,freeze the exact current loader/Python/prefix and
non-secret launch context from the approved public unit and process provenance.
Do not read private environment files to discover a path or invent python312,
display,library or prefix defaults. Missing required context means DEFERRED;
obtain a sanitized non-secret launch descriptor before proceeding. Do not
create a new prefix,install a runtime or change binfmt/terminal/network settings.

## Prepared probe and timing method

Private local preparation:
`runs/c22-ap-measurement-2026-10-29/guest_clock_probe.py`,
`host_smoke.py`,and `local-smoke.json`. The pure probe imports only Python
json/os/sys/time,never MetaTrader5. It accepts at most90sequence IDs and returns
nonce/sequence,guest wall nanoseconds,perf-counter before/after bracket,PID,
platform and clock implementation. No file,network,service or trading call.
Probe source SHA2562e0b73dddfa311c6e6736522b5ff3d85243fbdb2d3dcf4f34cbeb4fd9591990b.

Three local host protocol samples passed on macOS (`platform=darwin` in the
retained receipt); this initial checkpoint is explicitly NOT_VM. No Wine or
guest process was started at that checkpoint. The host controller must timestamp each
request-before/response-after with host monotonic time and verify exact nonce/
sequence. For successive responses,the possible host elapsed interval is
`[current_request_before−prior_response_after,
current_response_after−prior_request_before]`. Guest perf elapsed is bracketed
analogously. Keep roundtrip uncertainty and process-startup time separate;
receipt-to-receipt differences alone are not a clock-drift measurement.

Proposed VM measurement:90samples at approximately1second spacing,with a hard
3minute probe budget including startup/cleanup. Retain host UTC/monotonic
brackets,guest wall/perf samples,exact process/binary provenance and contemporaneous
native log line hashes. Sample existing terminal-owned socket metrics without
new privileges; sanitize peers in any public summary. Passive socket sampling
may not resolve a4ms handoff/lost interval. If kernel failure chronology remains
unobserved,label it UNKNOWN. No tcpdump/debugger/eBPF permission is implied.

## Execution-time safety boundary

Launching pure Windows Python in the existing Wine prefix is a guest-process
side effect even without an SDK call. It needs a separate concrete owner approval
after the launch context has been frozen. Do not execute this proposal directly.

Use the agreed fresh Demo flat/noorders/noactive/noUNKNOWN and consistent backup/
rollback checks. Any held/UNKNOWN exposure keeps its owned manager running and
defers maintenance. If an exclusive broker check is needed,the sender must not
run beside another SDK reader; an empty local journal is not account-flat proof.
The intentional entry pause,measurement and rollback together must fit15minutes.
Never force-close or reset financial state. Keep build/profile/source/policy/lot
fixed. Start only the explicitly reviewed probe process; terminate only that
child on timeout. No terminal restart,profile edit or runtime replacement.

Restore normal authorized sender operation and verify its original source,
single ownership,journal and terminal identity. A probe failure is evidence,
not permission to broaden the experiment or bypass gates. A future suspected
fix still requires reproduced before/after trigger,at least1hour repeat proof
and24hours including rollover. Normal eligible trading need not wait for issue
closure; genuine native signal→fill→BE→close remains a separate observation.

## Owner-approved bounded follow-up —29October2026

Owner selected option1: “ops 1 แต่ให้เน้นใช้ longterm และยังคงได้ profit”. This
authorizes the asked measurement scope,with long-term operational stability as
its purpose. It does not authorize profit guarantees,changed native rules,new
tariffs,automatic renewal,terminal/runtime changes or forced execution.

Current public unit/process evidence at11:44:46UTC freezes selected1c0453 sender,
terminalPID116183/start28Oct06:49:04UTC,existing Wine loader/Python/prefix and
senderunitSHA2764cc01…,policy07513b04…,review1726e848…. Credential files were not
read. The real journal backup is268,328,960bytes; raw/gzip SHA,tablecounts and
localSQLitequick_check pass. No old financialjournal will be restored over live
state. Ten local operational tests cover real-child timeout,wrong nonce,early
exit,uncertainty bounds and original-review/manager recovery. These are local
safety checks,not VM measurement or APfix evidence.

Frozen operation artifacts live in `runs/c22-ap-approved-measurement-2026-10-29/`.
The controller quiesces only new admissions,retains any owned manager until fresh
flat/noorders/noactive/noUNKNOWN/empty-outbox proof,then stops the sender for
exclusive read-only broker verification. Pre/post SDK reads are sequential;
there is never another SDK reader beside the sender. In between,one pure guest
clock process takes at most90samples while an unprivileged passive socket/log
observer runs concurrently. This is measurement with SDK attachment phases,
not an isolated causal test of a repaired APtrigger. Original review/source/
policy/unit and owned state are retained; the same sender is restarted and its
fresh cycle verified. Any unsafe precondition defers; failure still attempts
same-manager recovery. The3minute probe and15minute maintenance bounds remain.

## Actual outcome —29October2026,19:04Asia/Bangkok

The first bounded attempt ended with a clock-protocol JSONDecodeError before any
valid sample. Recovery restored senderPID175089 at11:54:43.984685UTC after
44.641572seconds of entry pause. TerminalPID116183,original review marker and
six protected financial keys were unchanged. No APfix or clock conclusion was
drawn from that attempt. Its first invalid stdout line was not retained,so its
exact content cannot now be asserted. A later socket wait timeout masked the
primary clock failure in the initial top-level result; the preserved clock
result retains the original error. Both are kept under the first operation's
`attempt-1/` evidence directory.

The measurement controller was corrected locally before the bounded retry:
independent socket cleanup cannot skip manager recovery; timing budgets reserve
recovery; raw stdout lines now retain original bytes and SHA; only the exact
observed Wine working-directory warning may precede protocol responses,at most
four times before the first valid response. Unknown output and wrong nonce/
sequence still fail closed. The primary clock error is recorded before any
observer cleanup. These corrections affect only the ignored measurement helper,
not the immutable selected sender or any financial calculation. Fifteen local
tests and independent source/test review passed. Both attempts and source
manifests are preserved; no earlier result was overwritten.

Fresh backup verification and independent safety review preceded the retry.
Real pre/post SDK packets confirmed Demo/hedging identity,flat/noorders and
complete reconciled history,with SDK reads exclusive while sender inactive.
The retry collected90actual Windows samples,sequence0–89,one nonce/PID2024 and
QueryPerformanceCounter. Original raw transcript contains90JSONresponses and
one exact Wine warning. All source/download hashes and timing arithmetic passed
independent recomputation. Guest/source/unit/policy/terminal/runtime pins stayed
unchanged. No order API,terminal restart,financial restore or cost renewal ran.

Sample observation spans12:00:22.135860–12:01:53.033914UTC. No guest perf or wall
clock regression was observed. The first response includes1,763.789ms startup
and roundtrip uncertainty; it is retained in the complete90sample result.
Separately,the post-first-response89sample interval bounds perf-minus-host
elapsed to−1.690494..+1.712683ms over about88.13seconds. That interval contains
zero. This is bounded timing evidence,not a statistical confidence interval,
proof of long-term clock health or explanation of an earlier APincident.

The concurrent observer captured89socket snapshots,zero candidate terminal
destroy events and five excluded UNBOUND events. No native APevent occurred in
that window. Terminal ownership does not establish a trading-AP role; no kernel
failure-before/after-handoff direction can be proved here. Quiet logs are not a
repair. #13 still lacks matched incident/transport/flow-role evidence; #14 still
lacks a reproduced confirmed trigger/fix and its required1h/24h repeat evidence.

SenderPID176044 was restored with a fresh observed cycle; retry entry pause was
130.721623seconds,total175.363194seconds across both attempts,within15minutes.
The six protected keys(identity,strategy snapshot,day,UTCboundary mark,last loss,
safety halt) and accepted review marker were unchanged. Audit/cycle records
continued; entire financialjournal byte identity is not claimed. Terminal
PID116183/start time and all installed unit/policy/review hashes remained pinned.
The separate read-only observation at12:04:19.463852UTC saw active sender/terminal/watchdog,
execute=true,WAIT/duplicate_bar,WAITING_SIGNAL,VALIDreview and no known blockers;
downstreamadmission remains NOT_PROVEN. No sender REQUEST/RESPONSE/LIFECYCLE
exists in that read. This is not absence of account-wide/manual trades.

Actual artifacts and independent review are retained under
`runs/c22-ap-approved-measurement-2026-10-29-r2/`. Original23issue scope remains
15closed/8open. Native26b8,0.01lot and risk/cost contracts remain unchanged.
Long-term profitability is still a separate prospective result,not established
by this operational measurement. No GitHub publication,commit or push occurred.
