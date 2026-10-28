# Selected26b8 UNKNOWN operator resolution — implementation audit

**Local implementation complete; no live incident resolved.** The actual passive
VM observation28Oct14:37:54UTC shows sender126749/terminal116183 still active on
their prior starts,active=false,safety_halt=false,with AP-related permission
blocking. This is journal evidence,not current broker-flat proof. No SDK call,
order,source/config/policy change or VM rollout occurred in this work.

## Problem and correction

Automatic reconciliation can prove a complete owned exit while retaining a
latched UNKNOWN safety halt. A generic restart/time-based clear would erase the
reason without proving the outcome. The new explicit operator seam first binds
the persisted incident,request/position and complete CLOSED evidence to actual
full broker cash/volume history. Ambiguous/no-fill/held outcomes cannot pass.
An independently pinned owner review then authorizes only that exact scope.

Code: `scripts/ops/c22_unknown_resolution.py`. Runbook and review/activation
boundaries: `docs/ops/c22-unknown-resolution.md`. It never imports an SDK,sends an
order,controls a service or manufactures owner approval. The three allowed halt
codes are identity/ledger UNKNOWN only. Wrong account/source/config,financial
scope,history,cash,outcome or review retains the halt. Final flat proof<=5seconds;
planning proof<=5minutes. A real new capture may refresh observation time only
while its approved deal/financial/incident scope remains exact.

Both existing colocated account and journal writer guards are acquired before
applying. The append-only OPERATOR_UNKNOWN_RESOLUTION record and halt clearing
commit together; injected audit failure rolls both back. A new private receipt
is reserved before mutation. A later receipt IO failure is resolved against the
durable journal record,never a blind retry/reset. The existing daily/loss/
baseline/peak/lastbar/cost state remains unchanged.

Root review identified two gaps in the first local implementation: tampered
top-level aliases could mislabel an otherwise bound incident,and an empty
notification-outbox prerequisite would indefinitely block resolution while
delivery was intentionally OFF. Negative controls reproduced both. Final code
validates aliases/restricts UNKNOWN scope and preserves pending notification
events without interpreting them as pending trade orders. This does not weaken
flat/noorders/active/owner/source/cash proof or grant new entry permission.

## Requirement and evidence

| Published T13/#24 criterion | Public test / observation |
|---|---|
| request→history/exposure→proved outcome; ambiguous remains UNKNOWN | `test_stale_foreign_missing_history_or_changed_costs_cannot_prove_outcome`; module requires causal CLOSED after the latched incident and bound owned opening/exit |
| explicit review/account/source/incident/reason; financial state retained | `test_no_owner_review_wrong_incident_or_unpinned_review_keeps_halt`, `test_proved_closed_resolution_changes_only_halt_and_retains_append_only_review_after_restart` |
| reconciliation distinct from manual decision; all new-entry gates retained | plan returns REVIEW_REQUIRED/no mutation; apply returns new_entry_authorized=false; module has no runner/admission/order dispatch |
| wrongincident/stale/foreign/restart/provenclosed/noapproval cases | `test_plan_alias_tamper_and_non_unknown_financial_halt_never_resolve`, `test_final_stale_proof_and_new_cashflow_scope_keep_halt`, `test_live_writer_and_new_active_intent_refuse_resolution` |
| unchanged real observation refresh and atomic failure | `test_new_observation_time_only_can_refresh_flat_proof_without_new_authority`, `test_audit_failure_rolls_back_halt_resolution_atomically` |
| no false orderqueue/cooldown or lost receipt | `test_disabled_notification_outbox_is_preserved_without_blocking_proved_close`, `test_cli_reserves_receipt_before_any_resolution_mutation` |

Ten focused tests PASS0.086s. Fullrepository1471tests PASS305.233s,skipped2.
Focused Ruff/compile/whitespace checks pass. No typechecker/coverage percentage
was measured for Python. Initial CLI receipt RED used the not-yet-added clock
test seam and failed on TypeError; it is not claimed as a historical production
failure reproduction. The public final ordering/guard/rollback assertions pass.
The actual UNKNOWN state machine regressions remain separate from fixtures
proving operator-tool behavior. No real broker fill or live unhalt is inferred.

Standards review: private artifacts under ignoredruns,report Markdown only,no
dependency/runtime binding change; writer/audit contracts reused. Spec review:
all four published implementation criteria map above. Actual use still requires
its concrete incident-specific approval and real fresh proof; closing the
implementation ticket is not that approval. Final review was by root because
independent-agent quota was unavailable,not a separate final-agent certification.

Root's GitHub write was initially rejected by automatic approval review. Owner
then explicitly approved publishing the prepared #30/#24 summaries and closing
them at implementation/research scope. No account identifier,secret,endpoint or
raw private broker packet is included in public issues. The approval does not
authorize an actual incident resolution or VM rollout.
