# Selected26b8 unit and shared-data metadata follow-up

Status: bounded read-only evidence collected at31October06:16:06UTC
(13:16Asia/Bangkok). The candidate rollout remains unapproved and its recovery
design is awaiting the owner's answer. This observation does not close #13/#14,
establish the SQLite cause or prove current broker flatness.

Six fixed units were queried for allowlisted properties: selected execution,
terminal, watchdog service/timer and backup service/timer. All property reads
exited0. FragmentPath matches each expected installed unit; DropInPaths is empty
and NeedDaemonReload is no for every unit at its recorded capture time.

The execution fragment hash remains
`2764cc011add28bd4c25a9aef5a34b4962d270982aba6d70e125f6524ddc8040`.
The sender PID/cwd match before and after the short collection, in the known
selected1c0453 release. This is not process-start identity proof. Data symlink
resolution matches the exact shared guard directory required by the existing
unit and remains unchanged across the metadata read. Market-data contents and
writer-lock ownership were not read.

Execution and terminal are active. Watchdog and backup timers are active; their
oneshot services were inactive between scheduled runs. That is an observed unit
state, not proof of external delivery, successful recent backup, broker health or
complete watchdog coverage. Individual unit observations have different times;
this is not one atomic system snapshot.

The collector never queries Environment or ExecStart argument payloads. It reads
no credential file, SDK or database, and performs no remote mutation. Known unit
files are hashed through a bounded16,385-byte read; unexpected drop-ins are not
opened and would require review. The effective ExecStart, private environment,
accepted financial review marker, outbox, broker exposure and current backup/
restore proof remain outside this collection.

Static independent review and root lint/compile checks preceded execution.
The exact executed collector SHA256 is
`8398e2c207890283db3a0af00072bc697af58679b66d3b9a50b4f835843d9b01`.
SSH exit0; output SHA256 is
`bd5d488b3f87577d6b25a57aac011c6cc1c919a57aa32f51ae6fb74c70d07d52`.
Root validated its receipt, all six properties, unchanged execution unit, stable
data pointer and unchanged531canonical source/test hashes against the prior full
PASS. No test suite was unnecessarily repeated.

Evidence is under the latest capture's
`claude-handoff/diagnostics-rollout-preparation/`:
`effective-unit-metadata.json`, `.receipt.json`,
`effective-unit-collector-independent-review.json` and
`effective-unit-postcapture-review.json`. Raw operational metadata stays local.

Independent metadata preparation is now complete for this scope. Repeating the
same service/status reads cannot resolve the pending recovery decision or supply
missing deployment authority. Continue the controller only after that material
choice; require actual execution-time safety/backup evidence and approval before
any VM change. The original goal remains20/23closed, with #13/#14/#34 open.
