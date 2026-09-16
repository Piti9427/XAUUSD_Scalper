# Issue #1 Gold Playbook Foundation — progress map

Tracker: https://github.com/Piti9427/XAUUSD_Scalper/issues/1  
Spec: `docs/specs/gold-playbook-foundation.md`  
Rule version for structure: `s1-s4-mechanical-v1` (ADR-0027)

This map is evidence of work-in-progress, **not** a claim that issue #1 is complete.

## Done (with tests)

| Requirement | Evidence |
| --- | --- |
| Protected-swing CHoCH ≠ latest-fractal MSS | `scripts/smc/structure.py`, `tests/test_smc_structure_choch.py`, ADR-0027 |
| Demo detection requires CHoCH | `detect_smc_setup(..., require_choch=True)` **default True**; `evaluate_smc_setup` → `SetupDecision` with reject reasons; rejection/accept tests in `tests/test_smc_detection.py` |
| Foundation detection/TTL defaults | Defaults: sweep→MSS 8, MSS→FVG 4, body 0.45, SL cap $25, pierce $8, lookback 25, pending TTL 4; `test_foundation_detection_signature_defaults`; webhook create_app default `risk_pct=0.005` |
| Baseline no partial/BE default in Demo loop | `be_enabled` default False; `partial_tp_enabled` default False; `smc_main` + orchestrator; `test_foundation_baseline_does_not_move_be` |
| Risk uses min(balance, equity) | `calculate_lot_size(..., equity=)`; orchestrator passes `account.equity`; `apply_broker_capital` syncs live snapshots in `smc_main`; `test_lot_size_uses_min_balance_equity`, `tests/test_smc_account_sync.py` |
| Nearest opposing pool TP + min 1.5R | `scripts/smc/liquidity.py`, `tests/test_smc_pool_tp.py` |
| Fib/OTE research log without filter | `scripts/smc/fibonacci.py`, wired into `detect_smc_setup` → `SetupSignal.fib_*` + reason tag (ADR-0028); `tests/test_smc_fibonacci.py`, `test_detection_logs_fib_ote_without_filtering_admission` |
| 5% DD + 2 losses / 1% daily halt persistence | `scripts/smc/risk_halt.py`, `tests/test_smc_risk_halt.py`; orchestrator honors `risk_halt.halted` |
| 0.5% risk floor/reject (pre-existing) | `scripts/smc/risk.py`, `tests/test_smc_risk.py`; webhook/staging default `risk_pct=0.005` (`test_create_app_defaults_to_half_percent_risk`) |
| Bot-only cancel/close (comment ownership) | `is_bot_owned_comment` + adapter cancel/close/rollover guards; `tests/test_smc_ownership.py` |
| Affordability distance at USD 500 / 0.01 lot | `scripts/smc/affordability.py`, `tests/test_smc_affordability.py` |
| News unknown/stale + blackout blocks new risk | `NewsManager.new_risk_allowed`, wired in `smc_main.py`; `tests/test_smc_news.py` |
| INTENT_SUBMITTED + UNKNOWN vs REJECTED | `ExecutionResult.status` in `mt5_adapter.py` |
| Manual vs bot vs cash-flow PnL separation | `apply_account_pnl_event` + `scripts/smc/account_pnl_sync.py`; clock `sync_classified_account_pnl` → `ACCOUNT_PNL` lifecycle; `tests/test_smc_account_pnl.py`, `test_clock_syncs_classified_account_pnl_deals` |
| Broker/Demo identity gate | `scripts/smc/broker_identity.py` + hedging `scripts/smc/account_mode.py`; netting fails Demo gate; `tests/test_smc_broker_identity.py`, `tests/test_smc_account_mode.py` |
| Fill-during-cancel / partial residual reconcile | `scripts/smc/reconcile.py`; `tests/test_smc_reconcile.py` |
| risk_halt file load/save in SMC loop | `smc_main.py` + `observe_equity` before admission |
| Gate A research defaults | ADR-0028 |
| Bid/ask executable side + OHLC AMBIGUOUS | `scripts/smc/quotes.py`; orchestrator + backtester honor dual-touch `AMBIGUOUS` (no invented SL/TP PnL); tick-first exit via `first_exit_from_ticks` / `bar.ticks`; `tests/test_smc_quotes.py`, `tests/test_smc_orchestrator.py`, `tests/test_smc_backtester.py` |
| Tick CSV bar annotation + backtester feed | `scripts/smc/tick_feed.py`; `SMCBacktester.run(..., df_ticks=)`; `tests/test_smc_tick_feed.py`, `test_dual_touch_with_tick_feed_takes_tp_first` |
| Broker identity smoke CLI (no orders) | `scripts/smoke_broker_identity.py` |
| Webhook Demo admission: risk_halt + identity + news unknown | `scripts/webhook_bridge.py` (`risk_halt_path`, `identity_gate` / live identity); `tests/test_webhook_bridge.py::TestWebhookFoundationGates` |
| Two net losses update persistent risk_halt on TRADE_CLOSED | webhook + `smc_main.py` call `record_net_losing_trade`; test `test_two_net_losses_trip_risk_halt_on_next_setup` |
| TIME_EXIT max-hold accounting (P/L/flat) | `StrategyOrchestrator.max_hold_bars`; backtester `exit_reason=TIME_EXIT`; `test_time_exit_after_max_hold_bars_profit_loss_flat` |
| Setup identity + no revive after TTL (B16) | `scripts/smc/setup_identity.py`; orchestrator registry; detection stamps `setup_id`; `tests/test_smc_setup_identity.py` |
| Dataset provenance reason codes (B20) | `scripts/smc/provenance.py`; `tests/test_smc_provenance.py` |
| Drawdown halt flattens bot-owned exposure (story 10) | `scripts/smc/halt_actions.py`; webhook returns `flatten_actions`; `smc_main` clears local bot pending/position; `tests/test_smc_halt_actions.py` |
| Structure prefix/future-append invariance | `test_replay_prefix_invariant_under_future_append` in `tests/test_smc_structure_choch.py` |
| SetupFunnel stage counters + backtest wiring | `scripts/smc/funnel.py`; `SMCBacktester` bumps stages + `summary.funnel`; MAE/MFE R on trade log; `tests/test_smc_funnel.py` |
| Incomplete/stale account history gate | `RiskHaltState.history_ready`; `observe_equity(..., history_ready=)`; live webhook/smc_main treat missing equity as incomplete; `tests/test_smc_risk_halt.py`, `test_incomplete_broker_equity_blocks_without_resetting_marks` |
| Locked H1 warmup convention (1000 bars) | `scripts/smc/warmup.py`; smc_main requests/gates new setups; `tests/test_smc_warmup.py` |
| Incomplete Asian / prior-day pools unavailable | `compute_liquidity_levels` returns None Asian when incomplete; PDH/PDL `None` (no Asian fallback); detector skips null pools; `tests/test_smc_liquidity.py` |
| Smoke identity CLI import path fix | `scripts/smoke_broker_identity.py` adds repo root to `sys.path` |
| Pending fill survives spread blowout (scenario 15) | Orchestrator fills on price touch even if `current_spread > max_spread`; new risk still gated; `test_pending_fill_survives_spread_blowout` |
| Wall-clock TIME_EXIT without new bars (scenario 19) | `StrategyOrchestrator.on_clock` + webhook `POST /internal/clock` via `plan_clock_time_exits` / `list_open_fills`; notify gated by `may_notify_close`; `tests/test_smc_clock_exit.py`, `TestWebhookClockTimeExit` |
| Accepted vs fill notifications (scenario 20) | `format_order_accepted_card` + `notification_policy`; UNKNOWN→uncertain; TRADE_CLOSED notify requires broker evidence **and** known PnL (no invent-from-reason); Pine sends entry/initial SL/exit; `tests/test_smc_notification_policy.py`, `test_f4_custom_r_multiples_configured_via_create_app` |
| Frozen Wilson/sample protocol (scenario 23) | `scripts/smc/stats_protocol.py`; few trades → INCONCLUSIVE; `tests/test_smc_stats_protocol.py` |
| Mac-off / Oracle infra ≠ strategy PnL (scenario 24) | `scripts/smc/infra_verdict.py`; smoke CLI emits `infra_verdict`; `InfraVerdictTests` |
| News pending cancel without force-closing positions (scenario 18) | `NewsManager.should_cancel_pending`; `evaluate_pre_news_position` returns None (no ADR-010 BE/force exit); orchestrator + `smc_main`; staging wires `news_manager`; webhook `/internal/clock` cancels + `finish_setup` (incl. dry-run); `test_foundation_pre_news_holds_sl_tp_no_be_or_force_close`, `test_clock_cancels_unfilled_pending_on_news_blackout` |
| Dataset file SHA-256 hashes (Gate B) | `sha256_file` / `hash_dataset_files` in `scripts/smc/provenance.py`; snapshot `docs/ops/2026-09-16-dataset-hashes.json`; `tests/test_smc_provenance.py` |
| Risk-budget invariant + frozen initial R | `calculate_lot_size` rejects over-budget after floor; `frozen_initial_r`; webhook TRADE_CLOSED derives R from entry/SL/lot when missing; `tests/test_smc_risk.py`, `test_trade_closed_uses_frozen_initial_r_from_fill_geometry` |
| Trading vs operating cost layers (scenario 21) | `scripts/smc/cost_accounting.py`; `aggregate_deal_cashflows` used by adapter; `tests/test_smc_cost_accounting.py` |
| Demo 12w protocol + Oracle ARM64 checklist (docs) | `docs/ops/2026-09-16-foundation-demo-12w-protocol.md`, `docs/ops/2026-09-16-oracle-arm64-runtime-checklist.md` |
| GH close paste pack for #2–#4 | `docs/handoff/2026-09-16-github-close-ready.md` |
| MT5 `type_filling` from symbol `filling_mode` (Exness 10030) | `scripts/smc/mt5_filling.py`; wired in `mt5_adapter` PLACE_LIMIT + DEAL; `tests/test_smc_mt5_filling.py`, `test_live_place_limit_includes_type_filling` |
| Spread from ask−bid (3-digit Gold) | `MT5Connector.get_spread()`; `smc_main` uses price spread directly; `tests/test_mt5_connector.py` |
| Orchestrator `risk_pct` from config | `StrategyOrchestrator.risk_pct` → `calculate_lot_size`; `test_new_setup_uses_configured_risk_pct` |
| Smoke evidence artifact (`--out`) | `scripts/smoke_broker_identity.py`; `tests/test_smoke_broker_identity_cli.py` |
| Broker lifecycle reconciler (TTL / fill / close) | `scripts/smc/broker_lifecycle.py`; webhook `POST /internal/clock`; `tests/test_smc_broker_lifecycle.py` |
| Clock tick updates risk_halt on broker-only closes | `apply_broker_lifecycle_losses`; `tests/test_smc_risk_halt.py` |
| TRADE_CLOSED idempotent after lifecycle reconcile | `webhook_bridge` skips duplicate close + double loss count; `test_trade_closed_webhook_skipped_when_lifecycle_already_logged` |
| Lifecycle fill → ORDER_FILLED notify + idempotent TV | clock marks `ORDER_FILLED` processed + fill card; `test_clock_marks_order_filled_processed_after_lifecycle_fill` |
| SetupDecision reject reasons | **Done:** `evaluate_smc_setup` → `SetupDecision`; `smc_main` + backtester wired (`810d17c`) |
| Real-money approval boundary (story 49) | **Done:** `scripts/smc/real_money_approval.py`; dual env+config; Demo path unchanged (`810d17c`) |
| Shared behavioral lifecycle boundary (story 47) | **Done:** `tests/test_foundation_behavioral_lifecycle.py` |
| Open material decisions registry (story 48) | **Done:** `docs/handoff/2026-09-16-open-material-decisions.md` |
| MT5 initialize path helper (Wine/Mac IPC) | **Done:** `scripts/smc/mt5_init.py`; smoke `--path` / `MT5_TERMINAL_PATH`; connector+adapter wired |
| Research vs USD500 / shared-account replay labels (stories 39–40) | **Done:** `scripts/smc/replay_report.py`; backtester attaches `replay_report`; no shared-account parity without events |
| Trading vs operating profit on backtest summary (story 41) | **Done:** backtester `cost_report` via `summarize_profit_layers` |
| Frozen sample/Wilson on backtest summary (stories 42–43) | **Done:** `sample_verdict` + `wilson_interval` attached; few trades → INCONCLUSIVE |
| Nearest pool TP min-R / consumed (scenario 7) | **Done:** `tests/test_smc_liquidity_tp.py` covers nearest-not-farther, R&lt;1.5 reject, consumed skip |
| Live-gate readiness snapshot (no invent PASS) | **Done:** `scripts/ops/issue1_live_gate_readiness.py` → `docs/ops/2026-09-16-issue1-live-gate-readiness.json` (`issue1_closable:false` until real artifacts) |
| Partial fill / fill-during-cancel in lifecycle (story 34) | **Done:** `reconcile_pending_exposure` wired into `reconcile_broker_lifecycle`; residual TTL cancel; `tests/test_smc_broker_lifecycle.py` |
| Stale/unknown market+account+news admission (story 32) | **Done:** `scripts/smc/data_freshness.py`; wired in `smc_main` + webhook SETUP; `tests/test_smc_data_freshness.py`, `test_stale_event_time_blocks_setup_pending` |
| Missing broker margin/sizing metadata blocks new risk | **Done:** `scripts/smc/broker_metadata.py`; `get_risk_snapshot` requires `margin_free`; wired webhook + `smc_main`; `tests/test_smc_broker_metadata.py`, `test_missing_margin_free_blocks_live_setup` |
| Provenance gap/proxy cannot claim EVALUABLE (scenario 22) | **Done:** backtester attaches `provenance`; proxy/insufficiency overrides `sample_verdict`; `test_proxy_feed_cannot_claim_evaluable` |
| Development vs holdout window labels (Gate D proposal) | **Done:** `scripts/smc/eval_windows.py` refuses merge of development+holdout samples; wired into backtester `eval_window` / `sample_verdict`; `tests/test_smc_eval_windows.py`, `test_mixed_dev_holdout_bars_refuse_evaluable` |
| Dry-run verifier aligned to foundation + admission | **Done:** `scripts/verify_dry_run.py` uses fresh UTC times; TP1 expects reject under BaselinePlay defaults |
| Broker stops_level / point geometry (scenario 10) | **Done:** `scripts/smc/stops_geometry.py`; snapshot requires `point`+`stops_level`; webhook SETUP gated; `tests/test_smc_stops_geometry.py`, `test_stops_geometry_blocks_tight_sl` |
| Freeze_level blocks SL mods near market | **Done:** `sl_modify_freeze_allows`; adapter MOVE_SL + live TP1 pre-check; snapshot requires `freeze_level`; `test_live_be_rejected_inside_freeze_level`, `test_live_tp1_rejects_before_partial_when_freeze_blocks_be` |
| H1 EMA bias flip cancels pending (scenario 8) | **Done:** `pending_h1_bias_allows` + `resolve_h1_ema_bias`; wired `smc_main` / backtester / orchestrator; `test_h1_bias_flip_cancels_pending_and_blocks_revive` |
| Filled setup identity consumed (no revive) | **Done:** orchestrator `mark_terminal(..., "filled")` on pending fill; `test_fill_marks_setup_terminal_blocks_revive` |
| Required-scenario coverage matrix (1–24) | **Done:** `scripts/ops/issue1_scenario_coverage.py` → `docs/ops/2026-09-16-issue1-scenario-coverage.json`; scenarios 1–23 software_evidence_complete; 24 live_ops_required; readiness embeds Gate B summary |
| Setup registry survives process restart (scenario 8) | **Done:** `load_setup_registry` / `save_setup_registry`; `smc_main` loads `data/setup_registry.json`; `test_registry_survives_restart_after_ttl` |

## Still open for issue #1

| Gap | Notes |
| --- | --- |
| Live Exness connect smoke with real credentials | **Blocked on Mac:** native import missing; Wine `path=` → `-6` auth fail; terminal is **MetaQuotes-Demo** not Exness. Evidence: `docs/ops/2026-09-16-mac-live-gate-blocker.md`, `docs/ops/2026-09-16-mac-wine-initialize-path.json`. Needs Exness Demo session on host with working MT5 Python IPC. |
| Oracle ARM64 runtime soak | Checklist ready; SSH hunt to known hosts → publickey denied / timeout (`docs/ops/2026-09-16-host-reachability-hunt.json`) |
| Forward Demo 12-week protocol execution | Protocol registered; prospective after Gates B/C |
| GitHub API write for issue close comments | **Blocked 2026-09-16:** local `gh` token invalid (`gh auth status` → re-auth). Push to branch still works via HTTPS. Operator: `gh auth refresh -h github.com` then re-comment #1. |

## Sibling issues #2–#4

Documentation deliverables in-repo. Tracker: **#3/#4/#2 closed** 2026-09-16 via `gh` on `feature/smc-v2-hardening` (cannot re-verify via API until token refreshed).
