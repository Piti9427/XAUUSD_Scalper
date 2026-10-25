# C22 offline adoption preparation implementation

Implemented the five preparation work packages in
`scripts/qualification/c22/`, isolated from frozen research and current Demo
execution. Runbook: `docs/ops/c22-adoption-preparation.md`. Accepted scope:
shadow → separately reviewed Demo, fixed candidate through agreed forward
endpoints, improvements in a new version/cohort. No strategy/risk parameters
changed; CORE_STRATEGY section6.33 and6.50 remain intact.

## Delivered behavior

The public CLI builds a complete native Rules manifest and compatibility matrix,
compares independent supplied event snapshots, reconciles exported broker
positions/costs, manages immutable forward definitions and preserved evidence,
checks bounded CSV quality, and joins reports in a read-only dashboard.
`prepare` also exports a self-contained managed Canvas source. Outputs are
create-only under ignored `runs/`; exit0 means artifact generation, not readiness.

Current runtime lacks several research capabilities. The manifest exposes10
integration gaps for provisional26b8, including detector parameters, daily loss
count, BUY protection, cooldown and geometry. A compatible runtime adapter is
deliberately a later integration change after final research audit.

## Real evidence exercised

Final snapshot: `runs/c22-adoption-preparation-2026-10-25/implemented-final/`.

- Research manifest: `PROVISIONAL`,26b8bcd69e043653, full28-field Rules, snapshot
  coverage4,713/5,184 profiles. This is a frozen point-in-time preparation
  artifact; the research runner continues independently.
- Broker export:41records,38trade deals,19complete balanced position ledgers,
  3nontrade records,0invalid positions. All exported account positions remain
  explicitly unattributed to the proposed C22 candidate. Actual trade interval
  is2026-10-01 through2026-10-14. No historical cost comparison qualified;
  `COST_INCONCLUSIVE`,0compared positions, slippage `NOT_MEASURED`.
- Data quality:10,000 of49,729 declared bars scanned, explicit truncation and
  gap witnesses. Actual CSV path/size/declared-hash scope remains in provenance.
  Source completeness is `NOT_CERTIFIED`; feed parity/signal impact untested.
  The171,171,013 declared ticks were not rescanned by preparation.
- Forward protocol: `DRAFT_NOT_FROZEN`; review/sample endpoints and operational
  stopping criteria remain undecided. No actual cohort or forward process started.
- Dashboard: `PREPARATION_ONLY`; research, account-cost samples, draft forward
  definitions and any existing Demo evidence remain distinct. No combined PnL.

## Requirement and test evidence

The package's focused suite passes58 public-seam tests. Representative exact
tests below map the accepted requirements to observable behavior.

| Requirement from accepted spec | Evidence |
| --- | --- |
| "Contract, compatibility and offline parity" | `test_partial_manifest_preserves_native_rules_and_large_input_declarations`; `test_changed_buy_sell_geometry_admission_risk_cooldown_or_protection_fails`; `test_self_same_source_or_missing_adapter_never_passes` |
| "Observed cost reconciliation" | `test_partial_closes_preserve_signed_cash_and_expose_missing_cost_evidence`; `test_dated_calendar_applies_remaining_volume_at_exact_partial_exit_rollover`; `test_missing_calendar_and_current_spec_never_backcast_or_zero_fill` |
| "Prospective forward protocol" | `test_negative_evidence_retained_and_candidate_change_rejected`; `test_backdated_freeze_cannot_claim_prospective_data`; `test_changed_adapter_invalidates_freeze_append_and_review`; `test_shadow_cannot_be_recorded_as_broker_profit` |
| "Data and feed quality" | `test_reports_keep_actual_scanned_csv_provenance_for_each_input`; `test_missing_m1_minute_marks_m15_bucket_incomplete`; `test_bounded_scan_reports_truncation_without_inspecting_later_rows`; `test_weekend_gap_is_not_automatically_accepted_as_market_closure` |
| "Read-only evidence dashboard" | `test_observed_cost_sample_is_not_forward_profit`; final Canvas data equals `dashboard.json`; strict Canvas TypeScript check exit0 |
| Preserve completed evidence and source pins | `test_cost_command_writes_report_and_refuses_replacement`; `test_nonfinite_and_duplicate_keys_are_rejected`; all101 campaign source hashes match protocol |

Commands executed: focused `unittest discover -s tests/qualification/c22`,
Pyright on `scripts/qualification/c22`, Ruff on new code/tests, strict Canvas
TypeScript check, and repository-wide unittest discovery. Machine logs and
delivery checks remain under the ignored preparation run directory.

Validation outcome: focused58 tests PASS; Pyright0errors; Ruff PASS; Canvas
strict TypeScript PASS; frozen source pins101/101 unchanged. Repository-wide
discovery is **not green**: latest run1,096 tests,1error,2skips. Both full runs
failed the existing
`demo.test_demo_delivery.DeliveryTests.test_health_failure_path_never_reports_normal_heartbeat_for_critical`
at its first HTTP call with `RuntimeError("delivery_wall_deadline")`; it uses a
20ms wall deadline. The exact test passes when run separately. Both
`scripts/demo_runtime/delivery.py` and `tests/demo/test_demo_delivery.py` have no
diff against the starting baseline. Cause of the full-run timing failure is not
established here; no delivery/runtime change was made to conceal it. Preserve
`full-unittest.log`, `full-unittest-recheck.log` and `delivery-recheck.log`.

## Code review

Baseline:7356de4d985ef2049e4971744eb1084a44c3012b. Two independent axes reviewed
only this change's staged paths, excluding unrelated existing dirty work.

Standards: three findings resolved. Preserve scanned CSV references; reverify
manifest/parity dependency hashes at freeze/append/review; explicitly support
finite JSON metadata through256MiB while keeping the default32MiB input hashing
limit. Reviewer's actual33MiB metadata test passes and one-byte source changes
are rejected. Oversize metadata fails before JSON loading.

Spec: two findings resolved, covering the CSV source omission and stale adapter
dependency acceptance. Recheck22 forward/data tests passes. Additional root
regressions reject envelope identity drift, backdated cohort creation and
shadow financial claims. No unresolved material review finding remains in the
reviewed scope.

## Limits and next integration

Source hashes bind artifacts, not attestation that claimed code generated their
logs. PARITY_PASS is supplied event agreement, never broker fill parity or
economic qualification. Dated historical tariffs/spec/calendar and source
completeness remain unverified; missing evidence stays inconclusive.

Next: full-grid final audit → selected candidate adapter → end-to-end parity →
fresh broker/cost/feed evidence → prospective shadow assessment → owner
execution-time Demo decision. Historical DD≤40% is not a guaranteed forward
drawdown cap. Fixed0.01, cost-inclusive10% risk cap, single position, no recovery
and no lot growth remain. No broker connection, order, service activation,
attestation, cutover, real-money use or deployment occurred in this change.
