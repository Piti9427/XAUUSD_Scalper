# Selected26b8 maintenance and diagnostic frontier

Status: LOCAL DIAGNOSTIC FIX VERIFIED; MAINTENANCE DESIGN SELECTED. Fresh GitHub
state-filtered reads retain16closed/7open within original issues12–34. No new
public write,commit or VM change occurred. The full23issue goal is incomplete.

## Local launcher defect and fix

Source-bound offline reproductions demonstrated three distinct existing
preflight causes collapsing into one generic result. Further real ConfigParser
fixtures reproduced MissingSectionHeaderError,ParsingError and
DuplicateOptionError escaping the preflight catch. Two injected exec failures
escaped the catch because direct `execvpe` was outside it. These findings do not
explain the actual observed first terminal exit1 or AP reconnect cause.

The local launcher retains the existing BLOCKED/preflight reason/return2 and
adds allowlisted failure code,stage,exception type and integer errno where
available. Parser failures now become explicit preflight refusals. Exec OSError
becomes a sanitized terminal.exec failure/return1. Raw exception text,filenames,
parser contents,commands and environment are not printed. Existing guard logic,
argv,direct exec and Python ordergate0 are unchanged. No retry was added inside
the launcher; existing systemd Restart=always behavior remains separate.

Eight new tests first reproduced12errors against the old source. The fixed
launcher passed17 focused tests,including existing boot/release regressions;
an independent reviewer repeated the same17tests and traced the public path.
Compile,available global Ruff and whitespace checks pass. The first attempted
`.venv/bin/python -m ruff` was unavailable; no package was installed. No full
repository suite or actual Wine/Xvfb/VM test is claimed for this small change.

| Requirement | Concrete evidence |
|---|---|
| “ทุกอย่างถ้ามี error log ต้องมีเหตุผลบอกเสมอ” — distinct known preflight causes | `test_distinct_guard_causes_keep_existing_envelope_and_never_execute` |
| Same requirement — real parser and exec failure paths | `test_real_ini_parser_failures_report_safe_cause_and_refuse_exec`; `test_exec_os_failures_report_errno_once_without_retry_or_raw_path` |
| “Do not put secrets in code, logs, commits, or command arguments.” | Secret-marker assertions across the new suite; `test_unrecognized_value_and_key_causes_never_echo_exception_arguments`; `test_preflight_io_failure_exposes_errno_without_private_filename` |
| Preserve current terminal execution controls | `test_valid_launch_preserves_direct_exec_arguments_and_order_gate`; existing boot/release tests |
| Preserve cancellation semantics | `test_interrupt_is_not_converted_to_a_normal_refusal` |
| Actual validation | `.venv/bin/python -m unittest tests.demo.test_c22_selected_terminal_diagnostics tests.demo.test_c22_selected_boot_recovery tests.demo.test_c22_selected_release -v`:17PASS |

Remaining diagnostic gap: archived Xvfb/xauth stderr is routed to `/dev/null`.
Two matched offline redirect reconstructions demonstrate the loss route. Wine
child stderr is already forwarded and child status is propagated; adding Xvfb
capture cannot retrospectively recover missing evidence or prove an AP fix.
A per-invocation private error file remains a separate reviewed proposal.
No raw error-file capture or terminal rollout was added by this local fix.

Machine evidence is under
`runs/c22-goal-close-frontier-2026-10-29-late/diagnostic-loss/`,
`diagnostic-loss-repeat-1/`,`diagnostic-loss-v2/` and the local verification JSON.
Original source copies and frozen campaign inputs remain retained. Reproducers
pin the old source intentionally; the edited working source does not rewrite
their original evidence or bypass a source-drift refusal.

## Attended maintenance decision

The owner selected all three action families with separate adapters,then
C:typed plans and a durable operation handle. Three independent designs were
compared before selection. AST recomputation verifies identical Journal guards
across cost/AP/reboot and identical same-review recovery across AP/preboot.
Cost acceptance-marker recovery and ambiguous reboot dispatch remain distinct.

The reviewable contract is
`specs/c22-attended-maintenance-deepening-2026-10-29.md`. Proposed external
surface: prepare,run and read-only inspect. Internal knowledge includes
account-level serialization,quiescence,exclusive readers,pause/recovery reserves,
durable effect identities and operation-specific recovery. A status read cannot
mutate permission. Same handle alone does not imply safe redispatch.

The review clarified that post-start owned management survives later proof
failure; financial facts are never restored to force equality; midnight
attribution not proven by the independent verifier remains unverified; cross-boot
time requires an outside observer or an explicitly unverified timing result.
Local implementation confirmation is pending. No module execution or blanket
future maintenance authority is inferred from the interface choice.

## Reboot timing correction

The previously reported258.638816seconds comes from host UTC subtraction across
reboot. Retained preboot monotonic and postboot uptime cover separate portions;
no retained independent observer covers the entire interval. The number is
below900seconds on the recorded clock,but it is not a proven clock-independent
upper bound. No actual clock jump was observed. Local wording is corrected;
an exact sanitized public clarification is prepared but not published.

Actual reboot,exact review restoration,automatic recovery without fallback and
financial Journal continuity retain their separate evidence. This correction
does not establish a new failure or AP repair and does not itself mutate the
owner-approved public #26 closure.

## Remaining original acceptance evidence

| Issue | Current evidence | Remaining requirement |
|---|---|---|
|13 | Terminal-owned native/transport provenance,quiet-window guest elapsed probe and new diagnostic-loss reproductions | Incident-aligned flow role/clock bounds and direction of transport causality |
|14 | No one-factor confirmed AP repair | Failing reproduction,matched deployed fix,1h repeat and total24h rollover observation |
|23 | Boundary/restart fail-closed behavior | Genuine held-midnight proof method or reviewed financial semantics; no reset |
|25 | Native SELL fill and initial SL/TP confirmed; latest actual read29Oct16:53UTC remains MANAGING | Actual eligible BE and complete closed cashflow/cost/net evidence |
|28 | Session-gap classifier complete; unknown gaps retained | Exact distinct H4 candidate and matched swap-inclusive evaluation/audit |
|32 | Completed prior studies retain native; no global-best claim | Remaining H4 dependency and exact prospective protocol/evidence gates |
|34 | OWNER_DEFERRED/OFF | Explicit channel/recipient/test approval and actual off-VM receipts/recovery |

No issue is closed merely from the new module design or passing unit tests.
The running owned manager is preserved. No strategy,lot,entry,risk,cost rate,
policy expiry or financial calculation changed in this work.

## Final actual observation

A second read-only checkpoint captured29October17:32:04.116654UTC contains
4,433contiguous records throughID154333. Prior3,782and initial3,598raw payload
prefixes match exactly; source has one cohort. The651new records contain609
CYCLE,39HEALTH and3STATE observations. There is no new send,BE movement,close or
cost-failure event. Captured systemctl properties retain active/running
senderPID2603 and terminalPID2088.

Retain the adverse observation: CYCLE154300 at17:30:00.405913UTC reports
first_quote_unknown at lifecycle.reconcile and local protection observation
unknown. Subsequent state updates evaluate the quote/bar; they do not move SL.
Final cycle17:31:56.946104UTC is MANAGING with one position and confirmed
protection. This is not evidence that the broker removed SL during the transient
unknown observation,and the deeper quote-availability cause is not established.
The owned manager remains active;651new records are not651trade samples.

Independent raw recomputation passed. Compressed source SHA256:
`842994044b95050e9ce0275ae9a87005241ad61e9f09b6e5531f3c78e653142e`.
Originals,unit properties,all adverse observations and independent receipt are
under `runs/c22-goal-close-frontier-2026-10-29-late/native-final/`.
SDKcalls0,VMwrites0,service changes0. Final cashflow/profit and eligible BE remain
unobserved;#25stays OPEN. This confirms a live manager being observed,not a
missing/stopped worker or permission to launch a replacement sender.

The original intent records entry equity1811.97; historical research starts
at200. This is current-account lifecycle evidence,not a matched-capital return
comparison. Fixed0.01still has an equity-dependent admission cap. The already
observed entry cannot retrospectively become an unopened profitability sample;
freeze the separate prospective protocol before using genuinely new outcomes.
