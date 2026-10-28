# Selected26b8 shadow and Demo test

Latest actual sender-only cutover28October2026: `selected-1c0453dcf92db05d`,
execute=true, new source review accepted at08:46:31UTC. Terminal/watchdog/backup
remain on their existing bindings; auto-renew remains OFF. Actual broker proof
shows swap_long-490.8 stored versus-490.0 POINTS observed, so unchanged whole-policy
cost checks still block affected admission. Policy bytes/expiry remain unchanged.
See `docs/reviews/2026-10-28-c22-sender-cutover.md` and CORE6.64 for dated evidence.
The earlier sections below retain historical preparation/activation checkpoints.

Cost-blocker diagnosis completed28October2026: reproducible exact `swap_long`
drift, confirmed again by exclusive09:37UTC broker capture. A rebuilt one-time
changed-cost candidate was validated but has NOT been installed. Original policy
and review were restored exactly; source remains1c0453 and auto-renew OFF.
Changed economics require confirmed-Q4 review, fresh recapture and exact-policy
approval before activation. See `docs/reviews/2026-10-28-c22-cost-blocker.md` for
the concrete candidate, expiry effect, preserved cutoff and installation gates.

Historical activation evidence2026-10-25: `c22-selected-execution.service` was active with
execute=true/gate1 and verified Demo terminal AutoTrading. It is armed for Monday
and new completed market bars under explicit Demo-trial limits. Shadow services
are inactive. Earlier sections retain preparation history; use the final Monday
armed-trial section and `docs/reviews/2026-10-25-c22-monday-armed-demo.md` for the
that activation and remaining operational limits. This paragraph is not a fresh
VM status check. Local28October closure work and opt-in evidence preparation are
documented at the end; no VM rollout is implied.

Owner selected native Rules `26b8bcd69e043653` on2026-10-25. New snapshot
`RESEARCH-C22-SELECTED-20261025-26B8`,magic22261025, separate journal/cache.
This is a new version of C22 for shadow→Demo qualification. Old frozen
`1af968e9ac6a26ea` and release remain retained rollback evidence.

Exact contract: RSI7cross30 BUY/EMA50; SELL48/EMA50; closed H4EMA200; BUY
SL2.5ATR/TP3R, SELL SL2.5ATR/TP1.35R, both BE1R on completed bars. Fixed0.01,
cost-inclusive10% cap, daily10%/two negative completed exits per final exit UTC
day;30elapsed-minute negative-net cooldown compared with first signal quote.
Swap/commission/fee losses count even if price exit is BE. No lot growth/baskets.

## Local checks and default mode

```bash
PYTHONPATH=. .venv/bin/python -m scripts.c22_selected --verify-sources
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests/demo -p 'test_c22_selected*.py' -v
```

The Wine entrypoint is `scripts/ops/mt5_wine_c22_selected.py`. It defaults to
shadow regardless of inherited order-send environment. `--exec`/`--e`
abbreviations are rejected before MT5 initialization. Exact `--execute` now
requires envgate1, dedicated terminal and `--execution-review <path>` containing
new selected readiness plus explicit operator review. Default remains shadow.
This block does not assert broker readiness.
Do not route old `make bot-execute` to this candidate as a shortcut.

The config binds all25 named canonical/selected source files and selected
research completion/audit proof hashes. The runner adds selected source code to
the release/cohort identity and uses the existing shared broker lifecycle and
account writer guard. Its cooldown hook operates only during admission, never
blocks protection/reconciliation of an active position.

## Oracle shadow release

Build using `deploy/c22-demo/prepare_selected_release.py --out runs/<new-dir>`.
It uses the old explicit58-file allowlist plus new selected files/config,
produces deterministic archive/SHA manifest and a gate0 systemd shadow unit.
No credentials, journal, research runs or historical ticks enter the bundle.
Verify any differences in old runtime files before upload; expected list is empty.

New unit `c22-selected-shadow.service` uses its release directory directly,
`state/c22-selected-shadow.sqlite3` and `state/c22-selected-shadow-bars.csv`.
The old `current` pointer stays unchanged. New release `data` links to old
release `data` solely to share the same account writer lock. Service preconditions
require old shadow/execution units inactive and that exact guard directory.
Notifications are unset. Terminal AutoTrading remains disabled. A separate
execution unit is packaged for review; it is not installed or enabled.

Before handoff: fresh read-only unit/journal inspection → verify no managed
active/UNKNOWN position → consistent SQLite backup/download/restore check →
stop only old shadow → exclusive read-only broker flat/identity probe → new
shadow start. Preserve pending old outbox; do not mark it delivered. Enable
only the chosen gate0 shadow unit for boot, disabling old observer autostart.
Do not stop a financial manager if it has active/UNKNOWN exposure.

After startup verify new snapshot/rules ID,execute=false, release hash, latest
timestamp and journal/no order-intent evidence. Sunday stale quote and missing
cost policy are legitimate BLOCKED results. Bootstrap history is not prospective
qualification; start that evidence on fresh completed market bars.

## Remaining decisions and evidence

Archive parity compares49,729 bars and2,751 recorded entry geometries across6
cost/guard paths; it shares canonical helpers and does not certify independent
algorithm, full lifecycle or broker fill parity. New public cycle tests cover
BUY/SELL BE, cooldown/UTC/restart, daily2 and ambiguous lifecycle separately.

Fresh broker tariff/spec/calendar and account cost review remain required;
do not turn the existing COST_INCONCLUSIVE draft into an attestation. Old
feed exception and Monday waiting waiver do not transfer to26b8. New qualified
shadow observations/feed review and execution-time Demo decision precede sends.
Forward sample/review endpoints must be agreed before economic cohort freeze.
Real money remains prohibited. Historical DD40% is not a guaranteed future cap.


## Owner request for actual Demo execution — 2026-10-25

Owner explicitly requested actual MT5 Demo orders from selected26b8 using the
configured account. This authorizes the Demo execution task. It does not supply
swap entitlement, a qualified feed/prospective interval, or a cost attestation.
No real-money activity is authorized. The account fingerprint supplied by the
owner matches the VM identity; no credential update was necessary.

New CLI uses the same persisted broker lifecycle. Execution approval binds a
measured selected readiness report, exact account/release/config/policy hashes,
explicit owner authorization and reviewed cost/feed/backup/single-sender facts.
First acceptance requires a report/review within5minutes. Exact persisted approval
can resume the same cohort later while cost validity continues to be checked.
Removing/changing the review blocks new admissions. An active/UNKNOWN owned
position bypasses new-entry approval at restart to retain reconciliation/BE/
protection. Never stop its manager merely to repair an entry review.

Generate a new measured report using actual inputs, under ignored runs/:

```bash
PYTHONPATH=. .venv/bin/python -m scripts.ops.c22_selected_readiness \
  --journal <selected-shadow.sqlite3> --broker <fresh-broker.json> \
  --parity <selected-broker-parity.json> --cost-policy <reviewed-policy.json> \
  --since <aware-UTC> --out runs/<campaign>/readiness.json
```

A measured `AWAITING_OPERATOR_REVIEW` report still sets execution_authorized=false.
Operator review must separately verify all required facts. The generated template
in `runs/c22-selected-execution-2026-10-25/` intentionally has null approval time
and false confirmations. Do not turn a BLOCKED report into a permission file.

Staged execution unit uses `c22-selected-execution.service`, gate1, new execution
journal/cache and `state/c22-selected-execution-review.json`. It requires old
execution and both shadow units inactive, shares the account lock, has no boot
installation section and no Conflicts that would kill another financial manager.
Use only after fresh flat/backup/readiness checks and actual terminal permissions.
Old `make bot-execute` still targets old C22; it must not be used for this trial.

Current VM remains shadow/gate0. Quote is stale on closed Sunday; cost policy is
COST_INCONCLUSIVE. Standard new-candidate48h/96fresh-bars/UTC-midnight gates have
not passed; old Monday waiver remains inapplicable. No automatic activation timer
was created, AutoTrading was not enabled, and no broker order was sent.


## Selected duration waiver recorded — 2026-10-25

Owner now explicitly waives48hours/96bars for26b8 once remaining evidence is
ready. Use `--shadow-waiver <owner-duration-waiver.json>` on selected readiness.
This input is separate from feed acceptance and binds exact selected snapshot,
magic, account, runtime source/config cohort, aware acceptance time and exact
48h/96bar scope. Its hash participates in the report and subsequent execution
review. Retain actual elapsed hours/bar count; display criteria as waived.

UTC-midnight remains a separate gate (07:00 Asia/Bangkok); it was not named in
this narrower waiver. Require healthy continuous observation with <=120second
gaps, at least one genuinely new complete M15 still fresh at review, finite
current macro and every existing cost/feed/quote/identity/exposure/outbox gate.
Invalid or broader waiver blocks rather than silently changing the scope.

Owner has not checked Swap-Free. Keep account applicability UNKNOWN and runtime
cost policy COST_INCONCLUSIVE; do not attest zero swap. Broker credentials match
the configured account but do not establish swap entitlement. A browser check
could not proceed because local browser access is disabled; no account login or
credential transmission was attempted.

Current owner artifact is retained under ignored
`runs/c22-selected-waiver-2026-10-25/owner-duration-waiver.json` and staged only
in VM preparation. It is not an execution permission file. VM shadow observer now runs the reviewed execution-capable source release at
`selected-a6a67fcd01a2fcb8` with gate0 and notifications unset. Its source/config
cohort matches local hashes. Execution unit remains inactive/not installed;
terminal configuration was unchanged. No timer or
activation is implied by this waiver.

Qualification for this source cohort starts at2026-10-25T13:05:37.026470Z
(20:05:37 Asia/Bangkok), not the earlier version's cycles. The separate owner
waiver was rebound to measured current cohort using the same explicit decision;
the original decision/bindings are retained. Newmarket cost/feed and observations
must still be measured on that cohort before any execution review.


## Actual Monday armed Demo trial supersedes the waiting gates

Owner latest instruction is to have real MT5 Demo execution ready for Monday
market open. This supersedes the earlier retained UTC-midnight wait as well as
48h/96bars for this explicitly limited forward trial. There is no additional
waiting interval after actual fresh data and a valid strategy signal are ready.

`SELECTED_DEMO_ARMED_TRIAL` is separate from strict `SELECTED_DEMO_EXECUTION`
readiness. Its report is `ARMED_DEMO_TRIAL_WITH_LIMITATIONS`, never a fabricated
strict PASS. Initial approval binds fresh actual flat broker evidence, exact
Demo account, current source/config/policy and archive code agreement. It records
unknown swap entitlement, unqualified feed economic parity and waived soak.

The sender is armed before the market opens. Its entry gate starts no earlier
than2026-10-26T00:00 Asia/Bangkok (2026-10-25T17:00UTC), then waits for actual
fresh executable quotes and a completed UTC M15 after permission/start. The
strategy and existing90second entry window still determine entries. Full closed
H4 macro bootstrap is mandatory; old bars do not count as a prospective fill.
Market opening itself does not force an order. It needs the next eligible signal.

Current cost policy is explicitly CONSERVATIVE_REGULAR_SWAP_DEMO_ASSUMPTIONS,
using fresh actual SDK regular rates with published calendar as an assumption.
Account Swap-Free remains UNKNOWN; holiday exceptions and future costs are not
attested. Exact observed swap/commission drift guard remains, so lower actual
swap can also block later entries until review. Policy expires after its existing
168hour validity; renewal must use new evidence, never timestamp-only changes.

Use the execution journal/service for this trial, not the retained shadow or old
C22 service. Both shadow services and old execution must remain inactive while
selected execution runs. Do not casually restart/stop/kill Wine if a position
is active or UNKNOWN. Broker SL/TP and persisted manager state must be inspected.

```bash
sudo systemctl status c22-selected-execution.service --no-pager
sudo journalctl -u c22-selected-execution.service -f
```

Selected cumulative journal backup has its own `c22-selected-backup.service` /
`c22-selected-backup.timer`, every5minutes on the same VM. Downloaded Mac restore
proof is separate from local snapshots. No external notification delivery or
private cloud backup is asserted; execution is a Demo forward trial only.

## Verdict recovery update — 2026-10-26

Current operational source is described in CORE_STRATEGY6.55 and the deployment
record `docs/reviews/2026-10-26-c22-verdict-fixes.md`. Earlier sections above are
historical decisions; the execution service and its existing financial journal
remain authoritative. Native Selected26b8 rules and fixed0.01/risk/cost guards
are unchanged. BE10008 remains pending until actual broker confirmation; an
owned complete exit can reconcile while quote/trading admission gates are closed.

Persistent `c22-selected-terminal.service` plus selected execution units support
boot recovery from the same journal. Check actual enabled/active state; a staged
unit alone does not prove boot activation. No new sender runs concurrently with
old execution/shadow. Boot-registration helper only adjusts enable/disable
registrations after exact source/unit/review and fresh flat manager checks:

```bash
sudo python3 <actual-release>/deploy/c22-demo/enable_selected_boot.py \
  --release <actual-release> \
  --journal /home/ubuntu/c22-demo/state/c22-selected-execution.sqlite3 \
  --review /home/ubuntu/c22-demo/state/c22-selected-execution-review.json \
  --fingerprint c4020d69b754dfb5
```

Default prints a plan; `--apply` changes boot metadata only. Never use stop,
restart, Wine kill or rollback until owned active/UNKNOWN exposure is resolved.
Maintenance first revokes new admissions, waits for a completed cycle after
revocation proving flat/empty outbox, stops the manager and rechecks persisted
flat plus exclusive fresh broker/history evidence. Preserve journal and backups.
An attempted new sender start is an ambiguity boundary: inspect actual runtime
before any rollback that could interrupt its lifecycle.

Daily boundary sampling persists verified account equity only when the request
starts and completes inside the existing first UTC second. Missing/late proof
still blocks entries; restart/current equity must never reset daily allowance.

## Startup history/cache clarification — 2026-10-26

The initial100,000M1 request is historical, paged50,000 at a time, anchored at the
latest broker bars. It is not a requirement to observe201 new H4 after Monday or
after every restart. With the verified seed update, the existing
`--cache-output` CSV also has `<csv>.meta.json`; no new service flag is required.
At restart the source/account-bound CSV is checked against fresh overlapping
broker M1-derived M15, then only the new tail extends the saved prefix. Missing,
corrupt, future, changed-account/source or divergent seed falls back to verified
broker bootstrap. Never hand-edit metadata hashes to make an old cache pass.

Two different entry blockers now have distinct names:

- `macro_warmup_insufficient`: fewer than201 complete historical H4. Backfill is
  retried at most once per60seconds; do not wait201 new live bars by assumption.
- `macro_latest_h4_incomplete`: enough historical H4, but the latest closed H4
  bucket lacks16 complete M15. More old history cannot repair that bucket. The
  original archived rule deliberately keeps macro unavailable; do not carry an
  older EMA across it to force admission. Inspect `prior_h4_m15_count` and
  `next_h4_close_utc`. The scheduled close is not a promise of data completeness.

The captured26October2026 morning example had361 complete H4 and a7/16 Sunday
bucket. Next scheduled complete H4 close was04:00UTC=11:00Asia/Bangkok. Signal,
identity, cost, risk, daily/cooldown and execution checks still apply afterward.
`history_seed_status=restored` establishes validated cache reuse, not profitability,
broker parity or readiness to send without a strategy signal. Owned-position
management remains independent of these new-entry history gates.

Verified26October2026 13:30:55Asia/Bangkok on selected-98c2c73ed40ae408:
actual sender restored6,588 M15 bars and reports361/201 H4,WAIT/duplicate_bar,
execute=true; watchdog HEALTHY. The source-reapproval new-M15 gate cleared at
the13:30 close. Native entry signals and all other admission checks still apply.
Deployment and rollback/preflight evidence:
`docs/reviews/2026-10-26-c22-history-bootstrap.md`.

## Quote observation repair — 2026-10-26

Current operational release selected-9cfc54a3dc78f0ae preserves native26b8 config
and repairs clock handling across SDK reads. A quote generated after cycle start
can be valid when read; freshness now uses post-read observed UTC while keeping
strict future rejection and60second age. Entry-window time is refreshed after
the pre-send quote read. No signal,lot,risk,cost or BE rule changes.

For quote_stale inspect quote_rejection(future/stale),quote_requested_utc,
quote_observed_utc,quote_time_utc and quote_age_seconds in the cycle. These
diagnostics distinguish true stale/future feed evidence from processing delay;
do not increase time tolerance or fabricate a quote to force admission.

New source approval at15:32Asia/Bangkok requires a completed M15 after approval;
15:45 is the next scheduled close. The normal armed_trial_new_closed_m15_required
gate is different from historical warmup. Same-review restarts retain approval.
entry_ready is currently a SHADOW_ADMIT label: execute=true plus valid review and
actual lifecycle/reason determine the armed Demo state; false alone is not an
execution-off switch. Repair evidence and residual sampled-deadline limits:
`docs/reviews/2026-10-26-c22-quote-clock-fix.md`.
CLOSED diagnostics include day_start_day/source/valid. Polling aligns to midnight
without adding another concurrent SDK reader.

`c22-selected-watchdog.timer` reads service/journal independently. Its separate
SQLite state may never alias the financial journal. Owner explicitly chooses
local monitoring without external sends; deployed command has no `--notify`.
`WAITING_MARKET_DATA` with flat/quote_stale is quiet waiting, not proved session
health. Check its result with:

```bash
sudo journalctl -u c22-selected-watchdog.service -n 5 --no-pager
systemctl is-enabled c22-selected-execution.service c22-selected-terminal.service
systemctl is-enabled c22-selected-watchdog.timer c22-selected-shadow.service
```

Runtime cache CSV is exported on a new/reset causal prefix or when output needs
repair, avoiding repeated serialization. Explicit export still writes the whole
prefix. This optimization never caches or skips broker reads, source verification,
cost/account/exposure checks or admission/protection decisions.

## Operational repair staging — 2026-10-27

Local staged release `selected-3916d35b2d095b1a` adds safe identity flags from the
existing broker reads, source-bound review/cost diagnostics, known entry blockers
and observer incident continuity. **Not installed or activated on the VM by this
task.** Last read-only capture27Oct12:48:52Thailand still runs
`selected-9cfc54a3dc78f0ae`, senderPID52912/terminalPID34838,NRestarts0 and
`algo_permissions_required`. No new deployment health or flatness is implied.

Read the new cycle fields separately:

- `process_alive`, `position_protection`, `entry_availability.status` are distinct.
  `entry_ready` retains its old compatibility meaning; do not use it as a broker
  order promise. `KNOWN_BLOCKERS_ONLY` never claims all downstream checks ran.
- `known_blockers[]` provides finite code, since_utc, resume_condition,
  resume_not_before_utc when proved, next_check and requires_operator. An empty
  list alongside WAITING_SIGNAL still has downstream_admission=NOT_PROVEN.
- `execution_review` reports the exact source/account/policy validator outcome
  without accepting an approval. VALID is review/policy validity only. Due72/24/6h
  is advance review visibility, not automatic renewal or a delivered message.
- Monitoring RECOVERING lasts180continuous clear seconds by default. It is not
  the native30minute post-loss cooldown and does not delay trading decisions.
- Flat stale quotes eventually report market_data_wait_session_unverified.
  Closed-market waits can produce that diagnostic too because account/date
  session evidence remains unavailable. It asserts uncertainty, not market open.
- DELIVERY_DISABLED means local observer state/outbox only. External notification
  stays OFF; total-VM outage remains outside an observer on that same VM.

Operator resolution: fresh quote/reconnection, elapsed cooldown and UTC-day rules
re-evaluate on normal sender cycles with fresh valid signals. For missing review,
expiry, cost drift, source/account mismatch or latched safety_halt, inspect actual
evidence and follow reviewed maintenance. Restart is not incident resolution.
Never delete journal/halt/day state, touch reviewed_utc, or replace half a
policy/review binding to make an entry pass. Owned reconciliation/protection
continues while new-entry review fails, subject to valid broker prerequisites.

The archive and staged units under
`runs/c22-operability-fix-2026-10-27/staged-release/` contain no credentials or
financial journal. Actual cutover must preserve the existing private env, policy
bytes/expiry and all state, prove fresh flat/empty outbox/no UNKNOWN before stopping
a manager, install one sender only and create a fresh exact source/config-bound
review. Source reapproval requires its existing genuinely new completed-M15 rule;
do not backdate approval or fabricate a shadow/cost PASS. Never replace terminal
network settings or restart it speculatively to hide the unresolved AP loop.
Details: `docs/reviews/2026-10-27-c22-operability-fixes.md`.

## Failure drill-down staging — 2026-10-28

Local fixes from the System Design verdict are separate from the running VM.
The preparation does not install a service, accept changed costs or grant a new
source/config-bound execution review.

- `failure.code` and `failure.stage` distinguish the underlying failure from the
  compatible top-level reason. For example, `cost_policy_invalid_or_stale` can
  carry `cost_spec_mismatch` at `cost.spec`, with allowlisted numeric
  `details.field/expected/observed` from the existing spec read. Do not assume
  every such reason means expiry or that a mismatch is acceptable.
- `cause_chain` contains exception types and bounded repository-relative frame
  references; it excludes raw exception messages, SDK objects, credentials and
  frame locals. `correlation_id` links the diagnostic to the journal cycle.
  `root_cause_status=UNKNOWN` retains the distinction between a mechanical
  failure and an unproved deeper trigger.
- `operational_errors[]` and supplemental `OPERATIONAL_FAILURE` audits describe
  cache export/checkpoint and delivery failures without changing FILLED,
  MANAGING, BE or CLOSED truth. Delivery remains at-least-once; a failure audit
  never recursively enters the notification outbox. External delivery stays OFF
  unless separately configured and authorized.
- Cache faults retry on later sender cycles and preserve the prior file on a
  failed atomic CSV write. CSV plus metadata are not one atomic transaction; a
  torn pair must fail existing hash verification during restore.
- `DIAGNOSTIC_FALLBACK` in stderr/journald means supplemental diagnostic storage
  failed or CLI cleanup failed. Inspect the stage/cause and storage/service
  evidence. It does not clear a financial error or authorize a resend.
- Invalid policy reload remains invalid; an owned position still reconciles.
  Startup failures block initialization/entry. Cleanup attempts journal close
  and SDK shutdown independently and returns nonzero on cleanup failure.

The27Oct15:15/15:30Thailand FULL SELL refusals were isolated to the live-spec
comparison branch, but the old release did not retain the differing field.
This patch cannot reconstruct that missing historical value. After an approved
rollout, inspect a genuinely fresh failure from the existing sender; never
change `reviewed_utc`, bypass exact-spec comparison or replay the stale signals.

##28October2026 local closure and optional sender evidence

This section records local implementation, not a fresh VM observation. Review
`docs/reviews/2026-10-28-c22-complete-conditions-and-closure.md` and the matching
`runs/c22-closure-2026-10-28/` validation/release before proposing a source-bound
VM cutover. Keep the one-sender guard, existing journal/outbox and owned manager.
No runtime auto-renew, grant, external delivery or new financial rule is activated.

A prepared sender can opt in with `--broker-evidence-dir <private-directory>`.
The directory must be private, local and owned by the same operator as the sender.
The staged service does not enable this flag automatically. Do not run a separate
SDK reader to request evidence. Write a bounded `request.json` into that directory:

```json
{"request_id":"<32 lowercase hexadecimal characters>","requested_utc":"<actual aware UTC timestamp>"}
```

Use a new unique ID for each genuine capture. The running sender observes the
request on a completed normal cycle, writes `broker-<id>.json` with private file
permissions and atomic replace, and updates `receipt.json`. Existing packets are
not re-dated or replaced on retries/restart. A receipt may say CAPTURED while
`fresh_for_generation=false`; the original packet remains historical evidence and
the existing five-minute policy-builder freshness check still rejects it. Source/
config-context changes require a new request, preserving the old packet.

Capture requires current connected Demo/USD/hedging identity, policy-labelled
Standard Demo (not an SDK proof of tariff entitlement), flat/noorders, no journal
active/UNKNOWN/latched halt or same-cycle send, complete epoch history/count,
cash/balance/equity and per-position-volume reconciliation, complete finite spec,
and an observation window <=five minutes. Partial reads return a specific DEFERRED
receipt. No old cached read becomes a new capture. Requests arriving after a read
started wait for the next complete cycle. Missing fields never become zero swap.

Export IO occurs after the financial result. Faults carry safe stage/cause/resume
and OPERATIONAL_FAILURE audit; no new order, resend, manager stop, policy update or
notification delivery is triggered. Packet ledger is private and omits login,
server, password and deal comments; do not copy private evidence into public issues.
It is not a cost attestation or economic qualification. Review the actual full
charges and dated sources under the applicable generation before any renewal.

At this preparation checkpoint the offline planner did not return installation
authority. The next section records the later local coordinator implementation;
no machine grant or renewal activation has been installed on the VM.72hours means
preparation lead time, not a trading pause.

## Coherent renewal implementation —28October2026, local only

`selected-1c0453dcf92db05d` is the current locally verified package:87 payloads,
78 Python compilations,25 selected source bindings. Default generated units
contain no renewal flags. The older `selected-7e55d89979d50b0d` archive was only
staged in the VM preparation directory; neither package was activated by this
work. Last read-only observation28Oct07:04:07UTC still used `selected-9cfc54a3dc78f0ae`.
See `CORE_STRATEGY.md`6.63 and the root-cause closure report for evidence/limits.

The explicit configuration interface requires all four flags together, plus the
existing `--execution-review` pointing to the genuinely accepted original review:

```text
--renewal-grant <private owner-issued grant JSON>
--renewal-grant-sha256 <independently trusted SHA256>
--renewal-generation-root <private local generation directory>
--renewal-sources <private local source bundle JSON>
```

These are configuration fields, not an instruction to enable renewal. A missing
flag fails before SDK initialization. A path/hash alone does not issue a grant;
the exact owner/account/source/config/economics binding and original accepted
review are checked again. No new approval timestamp is synthesized. Do not copy
unit-test grant fixtures into operational configuration.

The source bundle has `packet` from `review_source_captures` and `captures` keyed
by `tariff`, `swap`, `calendar`. Each capture retains actual request/retrieval UTC,
approved source/final URL, HTTP status/content type, content SHA256 and original
body as `body_base64`. The sender does not collect HTTP evidence. An authorized
collector must supply genuine bytes; changing file mtime or packet reviewed_utc
does not refresh the capture. Actual raw tariff retrieval in this run lacked the
required clause, so its result is DEFERRED/source_claims_missing, not attested.

When configured, the normal sender starts preparation at age96hours and retries
on later normal cycles. Old valid policy can continue admitting eligible signals.
Install additionally needs original exposure timestamp<=5seconds, broker packet
<=5minutes, official review<=24hours, CLEAR applicable-cost audit, flat/noorders,
no active/UNKNOWN/halt and no same-cycle send. A slow read defers to the next real
snapshot; it does not re-date flatness or launch another SDK session.

Retain all sealed generations, append-only cost/adoption audits and the financial
journal. Never restore only `current.json`, erase a cost KV, rewind a journal or
reset a cutoff. Missing/ancestor pointers, unresolved costs or revoked authority
block new entries with a specific reason. Owned protection/reconciliation still
runs. Expired complete context can plan its replacement, but cannot authorize
an order. A failed candidate cannot overwrite the old whole context.

Generation state and financial journal live in separate stores. Durable final-flat
intent permits recovery of only an already authorized direct-child switch after
a crash; a post-replace durability error is not silently called rollback. POSIX
tests do not prove Windows directory fsync or a hard-power-loss guarantee.

VM preparation created a consistent read-only SQLite backup and extracted the
older approved-for-review archive under `preparation/`, without touching units,
terminal, env, costs, approval or journal state. Actual cutover still follows T01:
explicit execution-time owner approval, fresh flat/noUNKNOWN/empty outbox proof,
one sender, exact source-bound review and rollback. AP maintenance is a separate
one-factor experiment; no speculative terminal/runtime change is bundled here.
