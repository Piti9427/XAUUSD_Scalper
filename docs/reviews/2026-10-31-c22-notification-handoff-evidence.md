# Selected26b8 notification backlog — captured evidence and handoff boundary

31 October 2026. The owner specifically approved the private bounded capture
after automatic review rejected the earlier attempt. The exact approved
collector completed read-only at **09:05:12 UTC**, SSH exit0. It made no SDK,
service, queue-delivery or financial-state changes.

## Captured facts

The consistent snapshot at audit highwater226307 contains **four total rows,
all sent0**, kinds FILLED, CRITICAL, BE_MOVED and CLOSED. Payloads total2111UTF8
bytes; the private gzip is1419bytes, SHA-256
`a7423d735aaafd58a0496ebf6e83bf1ef4edb55bab089c62038997034c4ddbdf`.
Schema and length-framed raw-row digest passed. Capture files are mode0600 in a
mode0700 directory. No raw account/position identity is reproduced here.

All rows match the original selected1c0453 release/config, account and26b8
snapshot. Journal active is explicitly present and null; safety_halt is absent.
The accepted-review digest matches original1726. These five selected keys do
not prove fresh broker flatness, no orders, full protected journal continuity,
current notification transport status or current critical-incident resolution.

## Exact historical lineage and CRITICAL meaning

Each queued event joins by event identity and event value to retained audit
evidence: FILLED153045, CRITICAL157980, BE_MOVED169435 and CLOSED169977. The prior
5041rows plus the15manifest-selected successful packets form53941contiguous
audit IDs149901–203841. This historical prefix is distinct from the later226307
capture highwater; intervening audit rows were not newly fetched.

The CRITICAL reason is `position_unreconciled_180s`, emitted at
29October21:02:02.891269UTC. Nearby cycles show:

| UTC event | Sender observation |
| --- | --- |
| 20:58:58.728305 | Last confirmed MANAGING cycle before this gap |
| 20:59:02.435630 | BLOCKED/quote_stale; observed_positions1; protection unknown |
| 21:02:02.891269 | Uncertainty reaches180seconds; CRITICAL event |
| 22:00:30.339994 | First later MANAGING/confirmed cycle; critical false |
| Next day | Same position has retained BE confirmation and broker-confirmed close |

The exact deployed runner source ea904 emits this alert after sustained
uncertainty in its observation/status path. A stale quote prevents normal active
reconcile after closed-position reconciliation has already been attempted.
The diagnostic does **not** prove that broker SL was missing. Conversely,
recovery and later closure do not prove continuous broker protection throughout
the unknown interval. Historical sender recovery is observed; the AP/network
trigger and uninterrupted protection remain unproved.

The dated official Exness announcement places the pre1November weekday XAUUSD
pause at20:58–22:00:30UTC, followed by close-only until22:02. Those boundaries
shift one hour later after1November. Observed recovery is close to that public
boundary. This is supporting session context, not an account-specific calendar
attestation or proof of the AP cause. No session/risk/cost gate was changed.
[Exness dated DST schedule](https://get.exness.help/hc/en-us/articles/31342732737180-Trading-Hours-Update-End-of-US-Daylight-Saving-Time-01-Nov-2026).

## Why this blocks maintenance and what remains separate

STRICT_ZERO maintenance must refuse four pending rows. The normal runner's
entry path has no equivalent pending-event-count gate; notifications flush
after the trading cycle. `Journal.flush(None)` retains all pending rows.
Therefore an intentionally disabled notifier can preserve a queue indefinitely.
The actual current callback/transport state was not attested by this capture.
Sending, deleting or marking rows sent to manufacture eligibility is prohibited.

The previously reviewed local C-v2 OFF_NOTIFICATION_HANDOFF guard is the existing
alternative: require known deliveryOFF/no in-flight delivery, exact schema,
identity/cohort/lineage, every original id/raw-payload/sent byte preserved, and
explicit review of any CRITICAL row. Unknown or unresolved critical facts defer.
That local design approval is not approval to use the mode on this VM.

After reading this evidence, the owner explicitly acknowledged review of the
exact historical CRITICAL payload and selected preparation of an OFF handoff
plan. The private acknowledgement binds its original raw hash and answer
reference. It does not clear the incident, prove the current unresolved set,
or authorize OFF mode, deployment, SDK, restart or orders on the VM.

The separate draft source-cutover candidate now reuses the existing canonical
classifier. Root and independent runs each passed63tests; Ruff/compile passed.
The pinned STRICT_ZERO parent and531canonical source/test hashes remain
unchanged. Exact delivery booleans, known unresolved state, reviewed raw hashes,
original row lineage/cohort/bytes and per-event26b8 snapshot are checked before
effects. Unknown facts defer. No real operation was prepared from this five-key
capture; it is insufficient for the full safety baseline.

Remaining rollout prerequisites: production host adapter; one canonical journal
identity/account and sender; current full journal/outbox/source/unit/transport
proof; fresh broker flat/noorders/noUNKNOWN evidence; backup/restore and exact
probe cleanup; unchanged valid policy; then concrete execution-time approval.
No forced order, cost renewal, external alert activation or change to26b8 follows.

Original issues #13/#14/#34 stay open. This evidence resolves queue ambiguity
and identifies the exact historical alert; it does not close causal AP or repair
acceptance, nor delivered external alerts.

## Provenance

Private capture and sanitized independent reviews live under
`runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31/claude-handoff/diagnostics-rollout-preparation/notification-capture-readonly/`.
Read `execution-receipt.json`, `owner-approval-and-scope-receipt.json`,
`sanitized-initial-review.json`, `critical-window-review.json`,
`official-schedule-context.json` and independent notification review.
The actual owner acknowledgement is private in
`critical-owner-review-ack.private.json`. The unacknowledged proposal is retained
separately as historical evidence. The candidate's source, patch, exact test
names and independent review are in the sibling
`notification-handoff-candidate/` directory, status REVIEW_CANDIDATE_NOT_APPLIED.

An exploratory naive page glob hit a retained failed page15 output. Analysis
was corrected to the frozen successful-page manifest and exact gzip hashes;
failed outputs remain preserved. No missing packet was treated as empty.
