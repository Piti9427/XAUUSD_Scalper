"""Non-authorizing diagnostics: safe origin, evidence linkage and recovery hints."""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import sqlite3


ROOT = Path(__file__).resolve().parents[2]

# Shared with read-only availability reporting. These describe recovery; none
# grants entry or changes the financial predicate that raised the reason.
RESUME = {'account_expert_disabled': (True, 'verify_broker_account_trade_permission'),
 'account_trade_disabled': (True, 'verify_broker_account_trade_permission'),
 'active_reconciliation': (False, 'owned_position_resolved_and_all_entry_checks'),
 'alert_delivery_failed': (True, 'restore_configured_alert_delivery_then_retry'),
 'algo_permissions_required': (True, 'verify_connection_and_trade_permission_flags'),
 'another trial30 writer owns journal': (True,
                                         'restore_expected_runtime_identity_clock_and_single_writer'),
 'armed_trial_new_closed_m15_required': (False,
                                         'new_complete_m15_after_approval_and_all_entry_checks'),
 'armed_trial_not_started': (False, 'arm_time_reached_and_fresh_signal_and_all_entry_checks'),
 'availability_clock_must_be_aware_utc': (True, 'restore_aware_utc_observation_clock'),
 'bar_cache_divergence': (True, 'reconcile_verified_history_cache_without_overwriting_evidence'),
 'broker_profit_unknown': (True, 'restore_broker_profit_calculation_without_guessing_risk'),
 'broker_risk_invalid': (False, 'verified_broker_risk_within_unchanged_cap'),
 'cache_checkpoint_failed': (True, 'restore_optional_metadata_storage_and_retry_verified_cache'),
 'cache_export_failed': (True,
                         'restore_optional_cache_storage_and_retry_without_resetting_financial_state'),
 'capital_changed_before_send': (False, 'fresh_signal_and_fresh_capital_risk_checks'),
 'cli_cleanup_failed': (True, 'inspect_shutdown_close_evidence_and_single_sender_ownership'),
 'config_decode_failed': (True, 'restore_valid_json_expected_config'),
 'config_read_failed': (True, 'restore_readable_expected_config_file'),
 'cooldown': (False, 'fresh_signal_after_cooldown_and_all_entry_checks'),
 'cooldown_history_drift': (True, 'reconcile_persisted_loss_exit_with_broker_history'),
 'cooldown_history_missing': (True, 'restore_complete_loss_history_without_resetting_cooldown'),
 'cost_broker_deal_drift': (True, 'review_actual_cost_incident_before_renewal'),
 'cost_policy_changed': (True, 'restore_valid_source_bound_owner_review'),
 'cost_policy_expired': (True, 'restore_valid_source_bound_owner_review'),
 'cost_policy_future': (True, 'restore_valid_source_bound_owner_review'),
 'cost_policy_invalid': (True, 'restore_valid_source_bound_owner_review'),
 'cost_policy_invalid_or_stale': (True, 'fresh_cost_evidence_and_matching_review'),
 'cost_policy_missing': (True, 'restore_valid_source_bound_cost_policy'),
 'cost_policy_reload_failed': (True,
                               'restore_readable_valid_policy_without_automatic_attestation'),
 'cost_policy_unreadable': (True, 'restore_readable_valid_cost_policy'),
 'cost_spec_mismatch': (True, 'review_recorded_expected_observed_spec_before_policy_change'),
 'cost_spec_read_failed': (True, 'restore_existing_sender_symbol_spec_read'),
 'cost_swap_calendar_missing': (True, 'review_complete_dated_cost_evidence'),
 'cycle clock must be aware UTC': (True,
                                   'restore_expected_runtime_identity_clock_and_single_writer'),
 'daily_loss_limit': (False, 'proven_daily_budget_and_fresh_signal_and_all_entry_checks'),
 'day_start_floating_unknown': (True, 'genuine_boundary_equity_proof_or_next_proven_day'),
 'dedicated_terminal_path_required': (True, 'restore_reviewed_dedicated_demo_terminal_path'),
 'demo_identity_required': (True, 'verify_exact_demo_account_identity'),
 'diagnostic_persistence_failed': (True,
                                   'restore_observational_audit_storage_and_inspect_stderr'),
 'entry_availability_failed': (True, 'inspect_observational_availability_failure_origin'),
 'entry_window_expired': (False, 'next_fresh_signal_within_entry_window'),
 'explicit target Demo identity and XAUUSDm required': (True,
                                                        'restore_expected_runtime_identity_clock_and_single_writer'),
 'explicit_demo_order_gate_required': (True, 'restore_explicit_reviewed_demo_send_authorization'),
 'exposure_changed': (True, 'reconcile_changed_broker_exposure'),
 'exposure_unknown': (True, 'broker_exposure_confirmed_without_blind_resend'),
 'external_trade_api_disabled': (True, 'restore_reviewed_demo_trading_permission'),
 'first_quote_invalid': (False, 'valid_first_quote_only_within_original_entry_window'),
 'first_quote_late': (False, 'next_fresh_signal_with_timely_first_quote'),
 'first_quote_unknown': (False, 'retry_available_first_quote_only_within_original_entry_window'),
 'foreign_exposure': (True, 'resolve_foreign_exposure_then_reconcile'),
 'health_delivery_failed': (True, 'restore_configured_health_delivery_then_retry'),
 'history_balance_mismatch': (True, 'reconcile_broker_balance_with_complete_cash_ledger'),
 'history_bootstrap_timeout': (True, 'restore_verified_history_then_retry_without_forcing_entry'),
 'history_duplicate': (True, 'resolve_duplicate_broker_deal_identity_then_reconcile'),
 'history_position_mismatch': (True, 'reconcile_complete_owned_position_ledger_before_entry'),
 'history_unknown': (True, 'restore_complete_broker_epoch_history_and_count_then_reconcile'),
 'initialize_failed': (True, 'inspect_sdk_initialization_failure_without_resending_orders'),
 'insufficient_margin': (False, 'fresh_signal_with_verified_sufficient_margin'),
 'intraday_cash_adjustment': (True, 'reconcile_external_cashflow_and_daily_baseline'),
 'invalid_boundary_mark': (True, 'restore_genuine_account_bound_utc_boundary_evidence'),
 'invalid_capital': (True, 'verify_finite_positive_broker_balance_and_equity'),
 'invalid_day_baseline': (True, 'restore_proven_daily_equity_baseline_without_reset'),
 'invalid_history_cashflow': (True, 'restore_finite_broker_profit_commission_swap_fee_evidence'),
 'invalid_history_volume': (True, 'restore_valid_broker_volume_and_entry_type_evidence'),
 'invalid_initialize_timeout': (True, 'restore_valid_sdk_initialize_timeout'),
 'invalid_poll_or_cycle_limit': (True, 'restore_valid_local_poll_configuration'),
 'journal_account_mismatch': (True, 'reconcile_expected_account_and_journal_identity'),
 'journal_strategy_mismatch': (True,
                               'restore_expected_strategy_journal_without_discarding_exposure'),
 'macro_latest_h4_incomplete': (False, 'genuinely_complete_closed_h4_and_fresh_signal'),
 'macro_warmup_insufficient': (False, 'verified_historical_warmup_and_fresh_signal'),
 'max_daily_losses': (False, 'next_utc_day_and_fresh_signal_and_all_entry_checks'),
 'multiple_owned_positions': (True, 'reconcile_all_owned_exposure_before_new_entry'),
 'notification_failed': (True, 'restore_configured_delivery_then_retry_original_event'),
 'order_check_rejected': (True, 'inspect_broker_rejection_then_recheck_fresh_signal'),
 'order_send_exception': (True, 'reconcile_pending_broker_intent_without_blind_resend'),
 'permission_check_failed': (True, 'verify_connection_and_required_permission_evidence'),
 'persistent journal required': (True,
                                 'restore_expected_runtime_identity_clock_and_single_writer'),
 'quote_changed_before_send': (False, 'next_timely_fresh_signal_and_fresh_broker_checks'),
 'quote_clock_invalid': (True, 'restore_verified_aware_utc_quote_clock'),
 'quote_invalid': (False, 'valid_executable_quote_and_all_entry_checks'),
 'quote_stale': (False, 'fresh_executable_quote_and_all_entry_checks'),
 'quote_unknown': (False, 'fresh_executable_quote_and_all_entry_checks'),
 'review_acceptance_unavailable': (True, 'restore_valid_source_bound_owner_review'),
 'review_binding_mismatch': (True, 'restore_valid_source_bound_owner_review'),
 'review_initial_stale': (True, 'restore_valid_source_bound_owner_review'),
 'review_input_binding_invalid': (True, 'restore_valid_source_bound_owner_review'),
 'review_inspection_unavailable': (True,
                                   'restore_read_only_review_inspection_and_inspect_origin'),
 'review_malformed': (True, 'restore_valid_source_bound_owner_review'),
 'review_missing': (True, 'restore_valid_source_bound_owner_review'),
 'review_oversized': (True, 'restore_valid_source_bound_owner_review'),
 'review_time_invalid': (True, 'restore_valid_source_bound_owner_review'),
 'review_unreadable': (True, 'restore_valid_source_bound_owner_review'),
 'risk_cap_or_volume': (False, 'fresh_signal_fits_unchanged_risk_cap_and_volume'),
 'runtime_blocked': (True, 'inspect_recorded_runtime_failure'),
 'runtime_exception': (True, 'inspect_stage_origin_and_correlated_failure_evidence'),
 'safety_halt': (True, 'reconcile_incident_and_explicitly_review_halt'),
 'selected_execution_review_invalid': (True, 'restore_valid_source_bound_owner_review'),
 'selected_rules_drift': (True, 'restore_reviewed_immutable_native_rules'),
 'shadow_mode': (True, 'reviewed_demo_execution_authorization'),
 'snapshot_config_mismatch': (True, 'restore_expected_source_bound_snapshot_configuration'),
 'source_drift': (True, 'review_expected_immutable_sources'),
 'stop_geometry': (False, 'fresh_signal_with_valid_broker_stop_geometry'),
 'strategy_diagnostics_failed': (True, 'inspect_optional_strategy_diagnostics_origin'),
 'symbol_spec_invalid': (True, 'restore_valid_broker_symbol_contract_specification'),
 'symbol_stops_invalid': (True, 'restore_valid_broker_symbol_stop_specification'),
 'symbol_unavailable': (True, 'restore_expected_symbol_availability'),
 'terminal_disconnected': (False, 'terminal_reconnected_and_all_entry_checks'),
 'terminal_missing': (True, 'restore_expected_terminal_connection'),
 'terminal_trade_disabled': (True, 'restore_reviewed_demo_trading_permission'),
 'unproven_day_baseline': (True, 'restore_genuine_daily_boundary_proof')}

DETAIL_STAGES = {"cost.policy", "cost.evidence", "cost.tariff", "cost.spec", "cost.calendar"}
DETAIL_CODES = {
    "cost_policy_missing", "cost_policy_version_unsupported", "cost_policy_account_mismatch",
    "cost_policy_account_type_invalid", "cost_policy_commission_unit_invalid",
    "cost_policy_commission_basis_invalid", "cost_policy_slippage_basis_invalid",
    "cost_policy_source_missing", "cost_policy_commission_source_missing",
    "cost_policy_account_evidence_invalid", "cost_policy_review_timezone_invalid",
    "cost_policy_review_future", "cost_policy_expired", "cost_policy_commission_invalid",
    "cost_policy_slippage_invalid", "cost_policy_spread_buffer_invalid", "cost_policy_input_invalid",
    "cost_evidence_hash_mismatch", "cost_evidence_source_missing", "cost_tariff_contract_invalid",
    "cost_spec_required_fields_missing", "cost_spec_stored_value_invalid", "cost_spec_read_failed",
    "cost_spec_mismatch", "cost_calendar_contract_invalid", "cost_calendar_rollover_invalid",
    "cost_calendar_value_invalid", "cost_evidence_input_invalid",
}
SPEC_FIELDS = {
    "trade_contract_size", "trade_tick_size", "point", "volume_min", "volume_max",
    "volume_step", "swap_mode", "swap_long", "swap_short", "swap_rollover3days",
    "UNRECOGNIZED_SPEC_FIELD",
}

for _code in DETAIL_CODES:
    RESUME.setdefault(_code, (True, "review_recorded_cost_evidence_without_automatic_acceptance"))
RESUME.update({
    "target_credentials_missing": (True, "restore_explicit_demo_credentials_without_logging_secrets"),
    "target_credentials_invalid": (True, "restore_valid_explicit_demo_credentials"),
    "boundary clock must be aware UTC": (True, "restore_aware_utc_boundary_clock"),
    "positive poll required": (True, "restore_positive_poll_interval"),
    # SelectedStrategy forwards these finite refusals from frozen geometry and
    # M1 aggregation helpers. Keep their cause visible without changing a gate.
    "risk_cap": (False, "fresh_signal_fits_unchanged_risk_cap_and_volume"),
    "margin": (False, "fresh_signal_with_verified_sufficient_margin"),
    "invalid_stop": (False, "fresh_signal_with_valid_broker_stop_geometry"),
    "missing M1 bars": (False, "verified_complete_m1_history_and_fresh_signal"),
    "no completed M1 bars": (False, "genuinely_closed_m1_history_and_fresh_signal"),
    "no complete M15 bars from M1": (False, "genuinely_complete_m15_from_all_15_m1_and_fresh_signal"),
    "invalid M1 timestamps": (True, "restore_verified_aware_utc_m1_history_without_fabrication"),
    "duplicate or unordered M1 bars": (True, "restore_unique_ordered_verified_m1_history"),
    "misaligned M1 bars": (True, "restore_verified_minute_aligned_m1_history"),
    "invalid_closed_M1_OHLC": (True, "restore_finite_positive_consistent_closed_m1_ohlc"),
    "now must be timezone-aware UTC": (True, "restore_aware_utc_observation_clock"),
    "ambiguous_position_identity": (True, "prove_owned_position_identity_and_review_latched_halt_no_resend"),
    "awaiting_fill_deal_costs": (False, "complete_owned_opening_deal_costs_then_reconcile_no_resend"),
    "awaiting_broker_reconciliation": (True, "prove_owned_broker_exposure_and_review_latched_halt_no_resend"),
    "position_ledger_unresolved": (True, "complete_owned_volume_cash_ledger_and_review_latched_halt_no_resend"),
    "awaiting_be_confirmation": (False, "broker_confirms_pending_stop_change_no_resend"),
    "be_geometry": (False, "later_completed_m15_with_valid_tighter_stop_geometry"),
    "be_geometry_changed": (False, "later_completed_m15_with_fresh_valid_tighter_stop_geometry"),
    "be_check_rejected": (True, "inspect_broker_stop_check_rejection_preserve_owned_manager"),
    "be_position_changed": (True, "reconcile_changed_owned_position_before_stop_mutation_no_resend"),
    "be_rejected": (True, "inspect_broker_stop_response_preserve_owned_manager"),
    "awaiting_safety_close_confirmation": (False, "reconcile_pending_owned_close_with_complete_broker_ledger_no_resend"),
    "safety_close_position_changed": (True, "prove_current_owned_position_before_close_no_resend"),
    "safety_ownership_unproven": (True, "prove_exact_owned_position_without_closing_foreign_exposure"),
    "safety_volume_unknown": (True, "prove_owned_residual_volume_before_close_no_resend"),
    "safety_ledger_unresolved": (True, "reconcile_complete_owned_ledger_before_close_no_resend"),
    "safety_position_type_unknown": (True, "prove_owned_position_side_before_close_no_resend"),
    "broker_evidence_export_failed": (True, "restore_optional_private_evidence_storage_and_retry_same_request"),
    "evidence_request_invalid": (True, "supply_private_bounded_request_with_new_hex_id_and_actual_utc"),
    "evidence_packet_invalid": (True, "preserve_existing_packet_and_inspect_corruption_before_new_request"),
    "evidence_packet_context_mismatch": (True, "retain_old_packet_and_request_new_capture_for_current_source_context"),
    "evidence_utc_required": (True, "restore_actual_aware_utc_evidence_timestamps_without_backdating"),
})

# Finite project-owned renewable-evidence refusals. Hints never grant entry.
RESUME.update({
    'cost_generation_aware_utc_required': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_binding_invalid': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_identity_invalid': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_identity_mismatch': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_original_review_immutable': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_original_review_required': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_policy_hash_drift': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_policy_invalid': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_position_binding_immutable': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_position_binding_invalid': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_state_audit_invalid': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_state_audit_mismatch': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_state_invalid': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_transaction_owned_elsewhere': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_generation_unknown': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'cost_history_balance_mismatch': (True, 'reconcile_complete_unchanged_epoch_history_cash_and_exposure_without_reset'),
    'cost_history_count_mismatch': (True, 'reconcile_complete_unchanged_epoch_history_cash_and_exposure_without_reset'),
    'cost_history_duplicate_ticket': (True, 'reconcile_complete_unchanged_epoch_history_cash_and_exposure_without_reset'),
    'cost_history_epoch_window_invalid': (True, 'reconcile_complete_unchanged_epoch_history_cash_and_exposure_without_reset'),
    'cost_history_exposure_unknown': (True, 'reconcile_complete_unchanged_epoch_history_cash_and_exposure_without_reset'),
    'cost_history_future_deal': (True, 'reconcile_complete_unchanged_epoch_history_cash_and_exposure_without_reset'),
    'cost_history_invalid_identity': (True, 'reconcile_complete_unchanged_epoch_history_cash_and_exposure_without_reset'),
    'cost_history_invalid_numeric': (True, 'reconcile_complete_unchanged_epoch_history_cash_and_exposure_without_reset'),
    'cost_history_invalid_volume': (True, 'reconcile_complete_unchanged_epoch_history_cash_and_exposure_without_reset'),
    'cost_history_position_invalid': (True, 'reconcile_complete_unchanged_epoch_history_cash_and_exposure_without_reset'),
    'cost_history_position_mismatch': (True, 'reconcile_complete_unchanged_epoch_history_cash_and_exposure_without_reset'),
    'cost_incident_resolution_reference_invalid': (True, 'verify_original_generation_position_provenance_and_append_only_cost_audit'),
    'evidence_account_type_unproven': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'evidence_cash_not_reconciled': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'evidence_current_flat_reads_required': (False, 'fresh_verified_flat_noorders_noactive_noUNKNOWN_without_forced_close'),
    'evidence_demo_identity_unproven': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'evidence_history_invalid': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'evidence_not_flat': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'evidence_position_history_not_flat': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'evidence_read_window_stale': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'evidence_spec_invalid': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'generation_authority_invalid': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_aware_utc_required': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_context_binding_mismatch': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_cost_audit_invalid': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_current_changed': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_document_hash_mismatch': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_document_invalid': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_duplicate_json_key': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_expected_pointer_invalid': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_explicit_authorization_required': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_files_incomplete': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_fresh_evidence_required': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_fresh_flat_window_required': (False, 'fresh_verified_flat_noorders_noactive_noUNKNOWN_without_forced_close'),
    'generation_id_invalid': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_manifest_invalid': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_nonfinite_json': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_parent_mismatch': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_pointer_invalid': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_policy_evidence_mismatch': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_policy_invalid': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_review_candidate_required': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_semantic_validation_failed': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_store_invalid': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_switch_durability_unknown': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_symlink_rejected': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_trusted_binding_required': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_validator_required': (True, 'restore_one_complete_verified_generation_and_explicit_current_authority'),
    'generation_writer_busy': (False, 'retry_after_existing_generation_writer_completes_without_starting_another_sender'),
    'renewal_runtime_context_mismatch': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'renewal_runtime_cost_coverage_invalid': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'renewal_runtime_grant_invalid': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'renewal_runtime_installed_generation_invalid': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'renewal_runtime_not_configured': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'renewal_runtime_original_proof_invalid': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'renewal_runtime_position_provenance_missing': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'renewal_runtime_source_binding_invalid': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'renewal_runtime_switch_unknown': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'renewal_runtime_unresolved_cost_incident': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'selected_demo_readiness_pending': (True, 'verify_original_review_grant_source_and_cost_proof_preserve_owned_manager'),
    'source_aware_utc_required': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'source_capture_body_invalid': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'source_capture_hash_mismatch': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'source_capture_invalid_or_stale': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'source_capture_missing_or_malformed': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'source_claims_changed_or_ambiguous': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'source_claims_missing': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'source_holiday_limitation_missing': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'source_packet_binding_changed': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'source_packet_invalid_or_stale': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_actual_charges_contradict_standard_zero_tariff': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_aware_utc_required': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_complete_epoch_history_required': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_epoch_cash_does_not_reconcile': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_evidence_missing_or_malformed': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_flat_balance_equity_mismatch': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_flat_standard_demo_identity_required': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_fresh_broker_evidence_required': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_fresh_official_source_required': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_history_count_mismatch': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_invalid_deal_identity': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_invalid_deal_time': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_invalid_deal_type': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_numeric_evidence_invalid': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_numeric_evidence_required': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_published_wednesday_triple_must_match_spec': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_source_content_binding_invalid': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_source_packet_binding_mismatch': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
    'trial_cost_supported_points_swap_mode_required': (True, 'verify_actual_official_bytes_dates_rates_and_bound_packet_without_attestation_fallback'),
})


RESUME.update({
    "generation_historical_clock_invalid": (True, "verify_sealed_historical_context_without_authorizing_expired_entry"),
    "renewal_runtime_generation_lineage_invalid": (True, "reconcile_pointer_with_append_only_adoption_and_verified_switch_intent"),
    "renewal_runtime_generation_pointer_missing": (True, "restore_exact_complete_adopted_generation_without_legacy_fallback"),
    "renewal_runtime_explicit_configuration_required": (True, "supply_complete_explicit_source_bound_renewal_configuration"),
    "renewal_runtime_preparation_failed": (True, "inspect_actual_source_and_broker_evidence_preserve_old_valid_context"),
})
DETAIL_STAGES.add("renewal.generation")
DETAIL_CODES.update(code for code in RESUME if code.startswith((
    "renewal_runtime_", "generation_", "cost_generation_", "cost_history_", "source_", "trial_cost_")))


def safe_details(details):
    """Reject arbitrary SDK objects/messages, even on a custom exception."""
    if type(details) is not dict:
        return {}
    clean = {}
    for key, allowed in (("stage", DETAIL_STAGES), ("code", DETAIL_CODES),
                         ("field", SPEC_FIELDS), ("document", {"tariff", "spec", "swap_calendar"})):
        value = details.get(key)
        if type(value) is str and value in allowed:
            clean[key] = value
    for key in ("expected", "observed"):
        value = details.get(key)
        if type(value) in (int, float):
            try:
                clean[key] = value if math.isfinite(value) else {"state": "NONFINITE"}
            except OverflowError:
                clean[key] = {"state": "NONFINITE"}
        elif (type(value) is dict and type(value.get("state")) is str
              and value["state"] in {"MISSING", "NONFINITE", "INVALID"}):
            clean[key] = {"state": value["state"]}
    value = details.get("exception_class")
    if type(value) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", value):
        clean["exception_class"] = value
    return clean


def public_reason(error):
    """Only fixed project-owned refusal strings may enter a public reason."""
    try:
        value = str(error) if isinstance(error, ValueError) else ""
    except Exception:
        value = ""
    return value if value in RESUME else type(error).__name__


def exception_chain(error):
    chain, seen = [], set()
    current = error
    while current is not None and id(current) not in seen and len(chain) < 4:
        seen.add(id(current))
        frames = []
        cursor = current.__traceback__
        while cursor is not None:
            frame = cursor.tb_frame
            try:
                path = Path(frame.f_code.co_filename).resolve().relative_to(ROOT).as_posix()
            except (ValueError, OSError):
                path = "external"
            if path.startswith("scripts/"):
                frames.append(dict(path=path, function=frame.f_code.co_name, line=cursor.tb_lineno))
            cursor = cursor.tb_next
        chain.append(dict(exception_type=type(current).__name__, frames=frames[-8:]))
        current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
    return chain


SQLITE_PRIMARY_NAMES = frozenset("ERROR INTERNAL PERM ABORT BUSY LOCKED NOMEM READONLY INTERRUPT IOERR CORRUPT NOTFOUND FULL CANTOPEN PROTOCOL EMPTY SCHEMA TOOBIG CONSTRAINT MISMATCH MISUSE NOLFS AUTH FORMAT RANGE NOTADB NOTICE WARNING".split())

SQLITE_RESULT_NAMES = {
    name: value for name, value in vars(sqlite3).items()
    if name.startswith("SQLITE_") and type(value) is int
    and name.split("_", 2)[1] in SQLITE_PRIMARY_NAMES
    and re.fullmatch(r"SQLITE_[A-Z0-9_]{1,64}", name)
}

def _error_attribute(error, name, default=None):
    try:
        return getattr(error, name, default)
    except Exception:
        return default

def _sqlite_failure_fields(error):
    if not isinstance(error, sqlite3.Error):
        return {}
    raw_code = _error_attribute(error, "sqlite_errorcode")
    result_code = raw_code if type(raw_code) is int and 0 < raw_code <= 0x7fffffff else None
    raw_name = _error_attribute(error, "sqlite_errorname")
    result_name = (raw_name if type(raw_name) is str and result_code is not None
                   and SQLITE_RESULT_NAMES.get(raw_name) == result_code else "UNKNOWN")
    return dict(sqlite_errorcode=result_code, sqlite_errorname=result_name,
                sqlite_primary_code=(result_code & 0xff) if result_code is not None else None)


def failure_record(error, *, stage, code=None, correlation_id=None, now=None, details=None):
    """Mechanical failure evidence only; deeper unproved triggers stay UNKNOWN."""
    reason = public_reason(error)
    known = reason in RESUME
    clean = safe_details(details)
    # Native SQLite metadata is useful for runtime writes too. It grants no retry or entry authority.
    clean.update(_sqlite_failure_fields(error))
    stage = clean.get("stage", stage)
    code = clean.get("code", code or (reason if known else "runtime_exception"))
    operator, resume = RESUME.get(code, RESUME.get(reason, (True, "inspect_recorded_runtime_failure")))
    chain = exception_chain(error)
    frames = [frame for item in chain for frame in item["frames"]]
    origin = frames[-1] if frames else dict(path="external", function="unavailable", line=None)
    signature = hashlib.sha256(json.dumps(dict(code=code, stage=stage, origin=origin),
                                         sort_keys=True).encode()).hexdigest()[:16]
    stamp = now or datetime.now(timezone.utc)
    return dict(schema_version=1, code=code, stage=stage,
        classification="GATE_BLOCK" if known and code not in {"runtime_exception"} else "FAULT",
        exception_type=type(error).__name__, cause_chain=chain, origin=origin,
        root_cause_status="UNKNOWN", correlation_id=correlation_id,
        evidence_ref=f"audit-correlation:{correlation_id}" if correlation_id else "stderr",
        incident_key=signature, captured_utc=stamp.isoformat(), details=clean,
        requires_operator=operator, resume_condition=resume,
        next_check="NEXT_SENDER_CYCLE", resume_not_before_utc=None)


def fallback(record, *, persistence_error=None):
    """Independent sanitized sink; never recurse through journal or notifier."""
    payload = dict(kind="DIAGNOSTIC_FALLBACK", diagnostic=record)
    if persistence_error is not None:
        payload["persistence_failure"] = dict(exception_type=type(persistence_error).__name__,
                                             cause_chain=exception_chain(persistence_error),
                                             **_sqlite_failure_fields(persistence_error))
    try:
        print(json.dumps(payload, sort_keys=True, allow_nan=False), file=sys.stderr, flush=True)
    except Exception:
        # There is no reliable sink left. Financial callers retain their own
        # exception/exit behavior; optional diagnostics must not mask it.
        pass
