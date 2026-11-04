# Selected26b8 — actual attended reboot and exact artifact restoration

Status: ACTUAL OPERATION VERIFIED; OWNER-APPROVED#26PUBLICCLOSURE READBACK PASS.
Exact approved payload was published and read back15:56:35UTC29October2026.
Original23issue scope is16closed/7open. Earlier pending-publication statements
below describe their preparation checkpoints. This report coversT15/#26 only. APrepair,native execution
lifecycle and long-term profitability remain separate open evidence.

## Owner scope and preparation

Owner explicitly approved “อนุมัติ reboot และ fallback ตามแผนนี้”. The approved
proposal SHA256 is `7e99edbfbc5c8b5c1e9a5d8ed98749c9b39b20817745e4229ded9f12947355c8`;
its original bytes are preserved as `approved-proposal.md` under the ignored
operation directory. This approval included one ordinary reboot and a bounded
same-sender fallback,not a source/cost/lot change,financial restore,public write
or Git commit. Fallback was not used.

Before entry pause,the fresh269,819,904byte journal backup passed download/raw/
gzip SHA,SQLitequick_check and tablecounts149,726audit/12KV/0events/0deliveries.
The post-stop proof includes149,750audit rows. Source/operational controls passed
20local tests and independent review,including prefix tampering,protected-state
drift,pre-dispatch failure recovery,ambiguous reboot response,fresh UTC cycle and
manual-fallback exclusion from automatic proof. No runtime source was changed.

All four selected boot links were already enabled and matched their current
installed units. Old senders were disabled/inactive or absent. Both retained
source releases passed their manifests and shared the original account writer
guard. No enable/disable,unit replacement or dependency edit was performed.
The old boot-registration helper was not applied: its packaged-unit equality
does not describe the separately approved exporter/retained-terminal bindings.

## Actual boot and restoration

New admissions were held at12:38:57UTC after fresh sender-flat/noactive/noUNKNOWN/
empty-outbox checks. Only the flat sender stopped. The exclusive SDK probe then
proved the same Demo/hedging account,flat/noorders,complete reconciled history and
fresh quote. No SDK reader overlapped the sender. Cache/sidecar pairing,source/
binary/unit/permissions/review/policy pins and stopped journal state were checked
before one ordinary reboot command. No second reboot was requested.

Actual boot ID changed. The enabled units attempted startup without manual
starts. On the flat account,the deliberately held review caused explained
`selected_execution_review_invalid` at `cli.runner_init` before SDK initialization;
the existing automatic restart policy retried. This is an intentionally blocked
maintenance phase,not healthy unassisted flat-manager proof.

After new-boot source/guard/unit/cache/full-KV/original-audit-prefix verification,
the exact original review symlink was restored at12:42:37.057714UTC. Its target,
rawSHA1726e848…,accepted marker and original expiry remained unchanged. Existing
systemd retries then recovered senderPID2603 with terminalPID2088. No manual
`systemctl start` or restart was used after boot; no fallback marker exists.

The automatic proof at12:43:15.728958UTC observed a real UTC cycle8.96seconds old,
execute=true and the same selected cohort. Host UTC recorded258.638816seconds
from Admission hold to recovery verification,below900seconds on that clock.
Exact review restoration occurred earlier. A30October source audit found no
retained independent observer spanning reboot,so this interval is not a
clock-independent duration bound. No actual clock jump was observed. Reboot,
exact artifact restoration,automatic recovery and Journal continuity have
separate evidence. No old financialjournal was restored over the live database.

One initial cycle refused entry with `armed_trial_new_closed_m15_required` and
seed status `not_loaded`. The next observed cycle/audit at12:43:19.642413UTC
reported seed `restored`; later cycles reported WAIT/duplicate_bar and
WAITING_SIGNAL,knownblockers empty,downstreamadmissionNOT_PROVEN. Do not describe
this as a compulsory wait until12:45 or as proof an order would be admitted.

## Fresh broker and raw journal evidence

One new UUID request used the existing sender's SDK objects. Original request/
receipt/packet provenance was preserved. New packet captured12:47:04.046717UTC
matches its new request time/UUID,cohort,correlation and SHA68fe39e1…. It confirms
connected Demo/hedging,flat/noorders and43unique epoch deals matching preboot
history. These are account-history deals,not43native strategy samples. There
was no second SDK reader,forced order or new fee/swap attestation.

The270,176,256byte postboot backup passed raw/gzip SHA,SQLitequick_check and
149,900audit/12KV/0events/0deliveries. On the actual downloaded database,the
original149,750payload prefix hashes to
`5c5c888c7e0bc77d0cb30b3ff0997aca7f83e192c3a345a6f7352b8fe1a2ed1f`.
Original raw payloads,protected key presence/values and the accepted review
marker match the stopped proof; the earlier pre-pause backup prefix also matches.
New audit appends remain present. This is semantic continuity,not whole-file
byte identity across SQLite restart or normal new observations.

The separately captured103new audit records are contiguous and source bound:
90CYCLE/7HEALTH/3BROKER_EVIDENCE/1BLOCKER/1SIGNAL/1STATE. No new FULLsignal or
REQUEST/RESPONSE/LIFECYCLE exists. Raw M1/ticks,broker fill/BE/close and economic
qualification are not supplied by a cache or boot test. Native26b8,fixed0.01lot,
all risk gates and cost-policy SHA07513b04…/expiry remain unchanged. Auto-renew
and external delivery remain OFF; real-money activity was not performed.

Independent raw-SQL verification did not call the proof module: it re-hashed
the downloaded payloads using separate length-framed streaming code,compared
the149,726row prebackup prefix and149,750row stopped prefix,and checked key
presence/strict JSON values and SQLiteintegrity. The source DB raw hash was
unchanged before/after those reads. The complete postbackup has150new records:
133CYCLE/10HEALTH/4BROKER_EVIDENCE/1BLOCKER/1SIGNAL/1STATE,with no native lifecycle.

A final read at13:02:37.830611UTC/20:02:37Asia/Bangkok confirms senderPID2603 and
terminalPID2088 remain active. The fresh13:02:31cycle is execute=true,
WAIT/duplicate_bar,seed restored,WAITING_SIGNAL and no known blockers.
Watchdog and backup oneshot services actually executed after the new boot and
returned Result=success/ExecMainStatus=0 at13:01:53 and13:00:07UTC respectively;
their timers remain active. An inactive completed oneshot is not a stopped bot.
No manual fallback marker or native REQUEST/RESPONSE/LIFECYCLE exists in this
read. Original unit/policy/review bindings remain unchanged.

## Failures and remaining root-cause limits

| Observation | Evidence-supported interpretation | Remaining limit |
|---|---|---|
| Repeated runner-init review refusal during hold | Exact review was deliberately absent; restoring the same artifact allowed automatic retry. | Never count the blocked phase as an immediately healthy cold start. |
| First terminal invocation exited1 at12:40:47.550635UTC | One automatic restart at12:40:57UTC recovered the terminal; actual counter is1. | Deepest first-exit cause is UNKNOWN from retained logs; no permanent startup/APfix is claimed. |
| Wine working-directory warning | Appears in both failed and successful invocations; wrapper falls back to Windows directory. | Warning alone does not establish the fatal cause. |
| ALSA card0 messages | Sound-card resolution failed after the second terminal had started. | They do not explain the earlier first-exit event or prove a trading failure. |
| No native APevent in the bounded captured window | The window did not reproduce the historical handoff/lost trigger. | #13/#14 still need incident/transport causality and confirmed fix plus1h/24h evidence. |

One successful reboot with automatic recovery does not prove long-term APhealth,
broker economic parity or future profit. #25native lifecycle and#32prospective
qualification remain open. No financial baseline,cost cutoff,loss state or
equity peak was reset to obtain this result. All original failed checkpoints
and successful receipts are preserved.

## Evidence location and closure boundary

Private raw artifacts:
`runs/c22-approved-reboot-2026-10-29/`. Important files include the immutable
approved proposal/source manifest,owner decision,pre/post backups,actual preboot/
held/restore/automatic receipts,new broker packet,raw audit window,terminal boot
journal and local continuity verifications. These files are ignored; this
synthesized Markdown contains no credentials or remote endpoint.

The original#26criteria can be assessed from actual reboot,exact artifact
restoration,automatic recovery and financial/source continuity evidence. A
sanitized public summary subsequently received owner approval and#26closed with
exact-body readback. Its immutable payloadSHA2c9fa3a3… and closure receipt are
retained in the run directory. This does not complete the original23issue goal.
