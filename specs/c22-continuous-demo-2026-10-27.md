# Continuous Selected26b8 Demo — owner-confirmed requirements

Status: OWNER_CONFIRMED_REQUIREMENTS_NOT_ACTIVATED. On28October2026
(Asia/Bangkok), owner confirmed the Q1–Q9 grilling summary: “ยืนยันข้อสรุปตาม grill ด้วย”.
The agreed scope automates operational evidence/recovery within the exact
approved assumptions while preserving native trading rules. This confirmation
does not install a machine grant, activate auto-renew or change the running VM.

## Intended result

Continue evaluating and executing eligible native26b8 Demo signals without
manual weekly housekeeping when fresh evidence proves the approved assumptions
still hold. Make every remaining blocker actionable rather than silently stale.
This cannot mean unconditional orders or guaranteed future profit.

## Preserve native strategy and broker invariants

Keep native signals/SL/TP/BE, fixed0.01, initial10% risk cap, daily10% entry
threshold, loss2,30minute cooldown, one-position/account exposure checks,
90second signal window, fresh quotes, identity/permission, reconciled history,
stops/margin/order_check and persisted UNKNOWN/no-blind-resend. No timed clearing
of safety_halt. No real-money scope. No external notification channel enabled.

Existing cooldown/day reset, feed recovery and risk/margin reevaluation already
resume conditionally; do not add another generic pause/resume engine around them.
Any changed daily/cooldown/lot/risk rule is a distinct research candidate with
matched new backtests, not the historical26b8 winner unchanged.

## Confirmed operational design

Separate immutable owner authority from renewable evidence. The grant binds
Demo identity, exact source/config, explicitly permitted same-assumption refresh
and exact unchanged commission, slippage, swap rates and economic symbol spec.
A refresh record carries actual collection timestamps
and evidence hashes; it does not invent a new human approval or strict readiness.

Collect broker facts through the existing sender's read seam. Never launch a
second SDK reader beside an armed sender. Install a new generation only when
the broker is flat with no pending orders and the journal has no active intent
or UNKNOWN. Never force-close a position to renew. Active/UNKNOWN reconciliation and protection
continue with the original stored position costs and journal.

Validate fresh identity, spec, complete ledger/cashflow and dated source/schedule
evidence before installation. Preserve UNKNOWN Swap-Free entitlement and
COST_INCONCLUSIVE where appropriate. An unchanged downloaded page hash alone
does not establish account entitlement or unverified holiday exceptions.
Do not refresh reviewed_utc to bypass evidence requirements.

Preserve old evidence and audit actual closed charges under their applicable
generation before advancing a validation checkpoint. Renewal must not skip a
cost-drift incident by moving the review cutoff beyond an unreviewed exit.

Adopt policy/evidence/review bindings atomically as one validated generation,
including the running context. A partial write/crash retains the prior generation
and full journal. A missing or changed input does not become a passing renewal.

Start preparing genuine renewal evidence72hours before expiry. Preparation is
not a trading pause: the old generation can admit fresh signals while it remains
valid and every existing gate passes. Keep policy lifetime168hours and original
freshness: broker evidence≤5minutes and official-source review≤24hours when
building the generation. Evidence dates and dated calendar may change only by
the original approved formula; do not extend lifetime or backdate collection.

If a renewal candidate fails, preserve the entire prior generation and running
context. Continue using it only while still valid and all gates pass. When the
prior generation expires or becomes invalid, block new entries with a specific
reason; continue owned reconciliation/protection subject to broker prerequisites.

Expose entry availability separately from process liveness and protection:
all known blockers, first-seen time, next check, resume condition, requires-owner,
evidence validity/due time and delivery-disabled status. Existing source-bound
review errors need specific diagnostic causes without weakening their checks.
Local visibility is not a delivered alert; total VM outage requires a separately
authorized external observer/channel.

## Confirmed Q1–Q9 decisions

| Decision | Accepted behavior |
|---|---|
| Q1 | Automatic renewal only within the previously approved exact scope, once the concrete valid grant and implementation are installed. |
| Q2 | Plan bounded AP maintenance while flat/noUNKNOWN, one factor at a time, with backup/rollback. This is not an instruction to change the VM. |
| Q3 | Reproduce before/after, repeat at least1hour and observe a total24hours including rollover. This does not add an entry wait. |
| Q4 | Commission/slippage/swaprates/economic spec must equal approved values exactly; only genuine evidence/time/dated calendar refresh by unchanged formula. Changed economics require review. |
| Q5 | Install only brokerflat/noorders and journalinactive/noUNKNOWN. Keep an owned position's original cost generation and manager; no forced close. |
| Q6 | Intentional new-entry pause includes stop/change/rollback and is capped at15minutes per maintenance round. End an over-budget experiment and restore only when safe; never rewind the financial journal or abandon management. |
| Q7 | Failed new renewal preserves the complete old generation/context; trade only while oldvalid+allgatespass. Expired/invalid blocks new entries, not owned management. |
| Q8 | Prepare72hours before expiry while trading can continue. Keep168hour lifetime and freshness unchanged; no72hour cooldown. |
| Q9 | AP may close on complete AP evidence without a native FULL/fill. Forward signal→fill→BE→close remains NOT_OBSERVED wherever not observed; never force an order. |

These are confirmed requirements, not unresolved grilling questions. Machine
grant installation, scheduler activation and any VM cutover remain distinct
execution steps. Lot-compounding research remains paused; external delivery
remains OFF. Exact actual-cost drift, including lower swap, still blocks under
the native contract. No new Swap-Free or holiday entitlement is inferred.

## Validation before activation

- Native order geometry, loss/day/cooldown/risk decisions unchanged on matched
  fixtures; no new financial-backtest claim from operational tests.
- Same-assumption genuine refresh permits a later eligible admission; expired,
  missing, changed and malformed evidence does not.
- Exact authority/account/source/config binding; no false reapproval timestamp.
- Policy/calendar/review generation crash and restart coherence.
- Renewal preserves cost incidents, previous generations, journal and loss state.
- Active/UNKNOWN managers continue during renewal failure/revocation.
- No duplicate sender/SDK session, no forced test order, no external delivery.
- Targeted and full repository tests, immutable release manifest and concrete
  Demo rollout/rollback review before changing the running cost contract.

## Current evidence

Local failure-attribution and optional-output corrections are verified in
`docs/reviews/2026-10-28-c22-debug-verdict-closure.md`:1343tests PASS,skipped2;
prepared release `selected-21ebb6f4bded8a67` is not deployed by that work.
The two27Oct08:15/08:30UTC FULL SELL refusals were isolated to a live-spec
comparison mismatch; the exact old field was not retained. Neither an expiry
extension nor accepting a new cost is authorized to conceal that incident.

- `scripts/demo_runtime/costs.py:31`:168hour age; calendar and actual-cost drift
  independently checked at105+. Removing age alone is insufficient.
- `scripts/c22_selected/execution.py:93`: exact policy hash binding; accepted
  original review survives restart, first acceptance is fresh≤5minutes.
- `scripts/demo_runtime/cli.py:143`: reloads policy JSON every loop. Correction
  verified against the deployed CLI hash on27Oct2026. Policy reload already
  exists; a changed policy still fails the exact review-policy hash binding.
  Renewal must coordinate evidence/review generations rather than add a second
  reload mechanism or fabricate a new human approval.
- `scripts/c22_selected/trial_costs.py:48`: current builder uses fresh flat Demo
  capture;105+ requires fresh official-source review and generates8 dated days.
- Full source trace and45-case matrix:
  `docs/reviews/2026-10-26-c22-trade-policy-audit.md`.

This file records owner-confirmed requirements. It is not proof of an installed
grant, active renewal, deployed source or profitable broker-forward execution.

## Local implementation checkpoint —28October2026

Requirements remain confirmed and runtime activation remains separate. Local
closure work adds specific canonical/lifecycle refusal hints, opt-in same-sender
broker evidence export and a default-disabled offline exact-scope renewal planner.
No machine grant, atomic generation installer, scheduler, durable cost-incident
continuity or VM cutover is installed. See
`docs/reviews/2026-10-28-c22-complete-conditions-and-closure.md` and
`runs/c22-closure-2026-10-28/validation.json` for actual test/release status.
A locally constructed REVIEW_CANDIDATE is never installation authority.

## Later local implementation checkpoint —28October2026

The preparation-only checkpoint above is superseded locally by a default-OFF
same-sender coordinator, immutable seven-document generation store, durable
applicable-cost ledger and actual-content source packet validator. No operational
grant, collector schedule, renewal activation or VM cutover is installed.

Verified integration preserves original accepted approval and exact economics,
starts preparation72hours before unchanged expiry, adopts only fresh genuine
flat/noorders/noactive/noUNKNOWN proof, retains the complete old context on a
failed candidate, and keeps owned management during revocation/corrupt evidence.
Cost incidents cannot be hidden by a new review cutoff, restart or mutable-KV
rewind. Generation ancestry and crash intent prevent pointer rollback. Historical
expired context is retained only for integrity/planning; CLI reload/startup cannot
turn an expired policy into entry authority or erase the context needed to renew.

Full suite1439tests PASS, skipped2; source bindings25/25; frozen parent101 and
risk110 pins unchanged. Release `selected-1c0453dcf92db05d` remains local. Genuine
raw tariff capture still DEFERRED, AP deeper trigger and before/after1h/24h proof
remain open, native forward profitability remains unqualified. Exact requirement
mapping and separated Standards/Spec review status:
`docs/reviews/2026-10-28-c22-root-cause-closure.md`.
