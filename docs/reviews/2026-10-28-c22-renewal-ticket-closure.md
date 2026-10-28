# Selected26b8 renewal tickets — acceptance audit, 28October2026

**Implementation verdict: T04–T09 / GitHub #15–#20 satisfy their published acceptance criteria.** These tickets cover contracts, evidence packets and the opt-in implementation. Their execution boundaries explicitly separate installing a machine grant and activating unattended renewal on the VM. Neither activation was performed by this audit. Closing implementation tickets must not be described as enabling auto-renew or guaranteeing future trading/profit.

Audited HEAD: `35423c989811d1fb04f2aae510c6b3e323be3819`. Runtime implementation commit: `d06ef9c0cf3cc52bdb4e7e5a471b5ccd89856c9e`. These are local commit identifiers; this report does not claim a public push. Authoritative acceptance text: `runs/c22-grill-confirmation-2026-10-28/published-bodies/T04.md` through `T09.md`.

No code change was needed: the smallest complete action is to verify existing behavior, attach bounded evidence and close the implementation scope. Codegraph was queried first; its selected-package index lists eight older files and omits the new renewal modules. Direct source reads were used for those omitted modules and their seams.

## Fresh verification

Executed eight focused modules through `PYTHONPATH=. .venv/bin/python -m unittest ... -v`: **97 tests,35.439seconds,OK**. Modules: `test_c22_selected_renewal`, `test_c22_sender_evidence`, `test_c22_official_source_packets`, `test_c22_selected_trial_costs`, `test_c22_cost_generations`, `test_c22_generation_store`, `test_c22_renewal_runtime`, `test_c22_renewal_sender`, all under `tests/demo/`.

Machine evidence: `runs/c22-issue-closure-2026-10-28/renewal/focused-tests.log` and `validation.json`. The latter pins the eight inspected implementation files. This audit did not rerun the full repository suite; the earlier 1,439-test result remains historical evidence, not a fresh full-suite claim.

Actual source captures were reopened from disk, every body length/SHA256 checked, and both saved packets reconstructed using their original review times. All six bodies match and both packet objects reproduce exactly. This is historical integrity verification, not a new retrieval or refreshed freshness timestamp.

## #15 / T04 — bounded renewal authority

| Published criterion | Authoritative evidence | Result |
|---|---|---|
| Same Demo/account/source/config and exact economics/spec | `renewal.py:42` `economic_scope` binds the complete economic spec and calendar formula; `:130` `_binding` includes account, rules, source/config and economic hashes. `test_changed_account_sources_config_or_cost_scope_never_renews` and `test_lower_swap_commission_slippage_or_spec_drift_requires_review` | PASS |
| Immutable owner grant separate from renewable evidence; no regenerated approval | `renewal.py:143` `_grant_error` requires an independently supplied pin and explicit owner fields. `renewal_runtime.py:169` `_proof` checks original accepted review bytes against grant and journal; original review is retained in sealed documents. `test_matching_renewal_and_restart_keeps_original_approval_after_base_expiry` | PASS |
| 168h, unchanged freshness and lower-swap drift; conservative labels | `renewal.py:20` `_LIMITS`, `:42` economic labels/calendar; `source_packets.py:182` packet retains UNKNOWN/COST_INCONCLUSIVE. `test_legacy_exact_168h_policy_boundary_and_no_serialized_approval_refresh`, `test_higher_lower_swap_and_excess_fee_incidents_survive_new_review_and_restart` | PASS |
| Revocation/out-of-scope/review-required/binding/audit; no activation inference | `renewal.py:143`, `:166`; `renewal_runtime.py:119` durable intent and `:138` adoption audit. `test_grant_expired_revoked_future_or_lifetime_widening_requires_review`, `test_grant_document_mutation_without_new_trusted_pin_is_rejected` | PASS |
| 72h preparation while trading, flat-only install, old-valid fallback and incident continuity | `renewal.py:166`, `runner.py:180`, `:224`, `generations.py:325`; tests cover exact boundary, held/UNKNOWN, failed preparation, expiry and restart incidents | PASS |

**Closure scope:** confirmed authority contract and enforced implementation. No machine grant or scheduler was installed by this audit.

## #16 / T05 — existing-sender broker evidence

| Published criterion | Authoritative evidence | Result |
|---|---|---|
| Same reader ownership, timestamps/hash/sanitized identity | `runner.py:121` completes financial cycle before optional export; `:193` captures already-read facts. `evidence.py:42` `_packet` omits account login and deal comments; `:115` export hashes exact bytes. `test_capture_adds_no_sdk_calls_compared_with_disabled_path` | PASS |
| <=5min, connected, Demo USD hedging, flat/noorders, full epoch/count/cash | `evidence.py:42`; native builder validation in `trial_costs.py`; public tests construct a valid policy from the emitted packet. Standard account type is explicitly the existing policy label, not an SDK entitlement claim | PASS |
| Disconnected/nonflat/UNKNOWN/stale/incomplete defer | `evidence.py:106`, `:115`; `test_native_fill_and_unknown_defer_export_without_changing_send`, `test_incomplete_and_disconnected_reads_never_reuse_previous_snapshot`, `test_unreconciled_history_or_pending_orders_defer_without_inventing_proof` | PASS |
| Public seam validity/no trade side effects, independent of AP fix | Nine `SenderEvidenceTests` use `SelectedDemoRunner.cycle`; enabled/disabled SDK call counts match and shadow export never invokes `order_send` | PASS |
| Original observation times retained, no fake refresh, owned management continues | `test_restart_retains_original_capture_time_and_never_turns_old_packet_fresh`, `test_request_after_read_start_and_slow_cycle_cannot_claim_fresh_capture`; financial cycle precedes optional IO | PASS |

**Closure scope:** optional export seam and public-flow regressions. It creates neither execution authority nor a second SDK reader. VM opt-in export activation is separate.

## #17 / T06 — dated source/calendar packets

| Published criterion | Authoritative evidence | Result |
|---|---|---|
| Actual retrieval/content/hash/outcome; missing/stale/changed/ambiguous reasons | `source_packets.py:144` validates exact URLs, original request/retrieval times, HTTP/content/bytes/hash and visible terms. Six real bodies and two saved packet reconstructions match in current audit | PASS |
| Dated rollover/POINTS/triple/weekend/DST and missing-day rejection | `trial_costs.py` existing native builder, `renewal.py:42` exact calendar reconstruction, `test_dated_calendar_uses_native_points_conversion_and_us_dst_without_missing_zero`; `CostGenerationTests.test_unbound_position_or_missing_original_generation_calendar_is_not_guessed` removes one dated day and observes `cost_swap_calendar_missing` | PASS |
| UNKNOWN/COST_INCONCLUSIVE/holiday-not-attested preserved | `source_packets.py:182`, `renewal.py:42`; actual saved packets and assertions retain all labels | PASS |
| Validated **or deferred** packet/report; assumptions distinct from account attestation; no self-renewal | Published criterion expressly accepts `validated/deferred`. Actual 27Oct packet is DEFERRED with `tariff: source_claims_missing`; actual 28Oct three-HTTP403 packet is DEFERRED with role-specific `source_capture_invalid_or_stale`. `source_packets.py` has no network, policy installation or owner-grant operation | PASS, DEFERRED output |
| Source <=24h at generation creation; 168h unchanged; no timestamp-only renewal | `source_packets.py:193` rechecks original reviewed bytes and original retrieval timestamps; `generations.py:226` fresh install evidence; `test_snapshot_replay_cannot_refresh_or_substitute_reviewed_content`, `test_stale_candidate_cannot_install_even_while_policy_still_within_168_hours` | PASS |

Actual evidence: `runs/c22-root-closure-2026-10-28/official-sources/{captures.json,reviewed-packet-final.json}` and `runs/c22-cost-blocker-2026-10-28/official-sources/{captures-20261028.json,reviewed-packet-20261028.json}`. Readable source limitations are recorded in `docs/reviews/2026-10-28-c22-root-cause-closure.md` and `2026-10-28-c22-cost-blocker.md`.

**Closure scope:** a truthful validated/deferred evidence pipeline and actual deferred deliverable. This does **not** mean automated source supply is currently usable for renewal. HTTP403 or missing visible tariff terms remains a real renewal blocker. Manual official-page review used for the separately approved one-time cost installation is not substituted for raw source-packet bytes.

## #18 / T07 — cost incident continuity

| Published criterion | Authoritative evidence | Result |
|---|---|---|
| Position/exit applicable generation, old policy and complete cash ledger retained | `cost_generations.py:124` immutable registration/original cutoff; `:152` immutable binding; `:225` full historical audit. `test_position_binding_is_immutable_and_review_reference_never_clears_drift` | PASS |
| Audit before checkpoint; duplicate/out-of-order/incomplete cannot skip exits | `cost_generations.py:172` full epoch/count/cash/volume proof; `:225` scans all relevant closed ledgers. Late-exit, incomplete/duplicate/cash mismatch tests | PASS |
| Higher/lower swap and excessive fees remain blocked across renewal/restart | `test_higher_lower_swap_and_excess_fee_incidents_survive_new_review_and_restart` explicitly loops those drift cases; clean path separately passes | PASS |
| Exit counts/cash/resolution provenance persist; financial state unchanged | `cost_generations.py:110` atomic evidence-state/audit write; `:312` resolution references do not clear incidents. Matching-costs and foreign-transaction tests assert unchanged financial state | PASS |
| Renewal cutoff cannot erase unaudited exit/incident | Original cutoff is immutable in `:124`; KV deletion/rewind compared with append-only audit in `:71`. `test_append_only_cost_audit_detects_incident_reset_or_deleted_state`, `test_missing_or_changed_old_deal_is_sticky_and_does_not_advance_checkpoint` | PASS |

**Closure scope:** applicable-generation ledger implementation. Opt-in generation tracking remains separate from the current legacy VM cost checks; a one-time manual policy update is not the proof for this ticket.

## #19 / T08 — coherent generation installation

| Published criterion | Authoritative evidence | Result |
|---|---|---|
| Validate before atomic switch; one complete snapshot | `generations.py:185`, `:270`, `:325` seal/validate seven documents and replace one pointer; `renewal_runtime.py:145` adopts the returned whole snapshot. Concurrent reader test verifies whole generations | PASS |
| Crash/tamper/partial produce old valid context or explicit block | Store tamper/missing/stage/precommit/postcommit tests; `renewal_runtime.py:87` lineage blocks A→B→A and only recovers authorized direct children | PASS |
| Fresh broker flat/noorders and journal noactive/noUNKNOWN; owned management survives failed review | `generations.py:349` fresh flat predicate and final age recheck; `runner.py:121` catches auxiliary restore failures before owned financial cycle; public sender revoke/corrupt-cost tests | PASS |
| Exact expiry/calendar/restart/revocation/owned tests; no financial rollback | Store expiry/missing-calendar, runtime revoke/restart, sender held-BE tests; no journal restore in installer | PASS |
| No forced close; candidate can be staged while held, install defers; stored position generation retained | `GenerationStore.stage` accepts held-state deferred candidate; install rejects held/UNKNOWN. `test_pending_held_active_unknown_and_missing_state_keep_whole_old_snapshot`; ledger binding immutable | PASS |
| Failed candidate keeps old complete context; expired/invalid blocks new entry, owned reconciliation continues | `renewal_runtime.py:404` retains `old_policy` for pre-switch failure and marks post-switch ambiguity explicitly; sender preparation-failure/revocation/owned tests | PASS |

**Closure scope:** atomic installer/public integration. No generation switch or grant activation was performed on the VM in this audit. POSIX test results do not establish hard-power-loss behavior on every filesystem or Windows directory-fsync behavior.

## #20 / T09 — default-off same-scope renewal public flow

| Published criterion | Authoritative evidence | Result |
|---|---|---|
| Default disabled; real pinned grant; no manufactured approval | `renewal.py:166` disabled path and grant checks; CLI all-or-nothing opt-in; `test_partial_cli_opt_in_never_initializes_a_second_broker_reader` | PASS |
| 72h preparation while old-valid trading continues | `runner.py:180` policy age96h, `renewal.py:166`; exact boundary and public optional-preparation-failure tests | PASS |
| 168h, broker<=5min, sources<=24h, actual dates/calendar | Planner/builder/source/store enforce unchanged intervals; source stale/date substitution, store stale candidate/final-flat tests | PASS |
| Exact economics/account/source/config; missing/drift/revoked defer/block | `renewal.py:130`, `:143`; runtime authority/source proof and changed economics tests, including lower swap | PASS |
| Flat/noorders/noactive/noUNKNOWN only; no forced close or abandoned manager | `runner.py:224`, `generations.py:349`; public filled/owned BE after revocation and slow-history tests | PASS |
| Failure preserves old context, expiry/reason/next check explicit, incidents retained | `RenewalPlan` includes reason/next_check_at; runtime finite failure diagnostics; planner fallback/expiry and sticky ledger tests | PASS |
| Public same-scope success/72h/fallback/expiry/revocation/crash/restart/owned proof; VM rollout separate | Eight `RenewalSenderTests` run actual runner/CLI paths; twenty coordinator tests and seventeen store tests cover crash/restart/lineage. `test_real_sender_renews_then_restarts_after_original_policy_expiry_without_resend` demonstrates complete fixture flow | PASS |

**Closure scope:** default-off implementation and public-flow tests. All broker fixtures here are deterministic tests, not genuine MT5 forward fills or economic performance evidence. Actual VM auto-renew, machine grant and scheduler remain OFF unless separately rolled out under a concrete reviewed grant.

## Remaining operational work is not concealed

The six implementation closures do not close AP trigger repair/24h observation, a native signal→fill→BE→close lifecycle, actual reboot/restore, source-supplier availability or external alerts. Those acceptance criteria belong to separate tickets. Current fixed0.01/native26b8/source/risk behavior is unchanged. No external writes or VM changes were performed by this audit.
