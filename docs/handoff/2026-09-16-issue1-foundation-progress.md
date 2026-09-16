# Issue #1 Gold Playbook Foundation — progress map

Tracker: https://github.com/Piti9427/XAUUSD_Scalper/issues/1  
Spec: `docs/specs/gold-playbook-foundation.md`  
Rule version for structure: `s1-s4-mechanical-v1` (ADR-0027)

This map is evidence of work-in-progress, **not** a claim that issue #1 is complete.

## Done (with tests)

| Requirement | Evidence |
| --- | --- |
| Protected-swing CHoCH ≠ latest-fractal MSS | `scripts/smc/structure.py`, `tests/test_smc_structure_choch.py`, ADR-0027 |
| Demo detection requires CHoCH | `detect_smc_setup(..., require_choch=True)` default in `smc_main.py`; rejection/accept tests in `tests/test_smc_detection.py` |
| Baseline no partial/BE default in Demo loop | `smc_main.py` `partial_tp_enabled` default False |
| Nearest opposing pool TP + min 1.5R | `scripts/smc/liquidity.py`, `tests/test_smc_pool_tp.py` |
| Fib/OTE research log without filter | `scripts/smc/fibonacci.py`, `tests/test_smc_fibonacci.py` |
| 5% DD + 2 losses / 1% daily halt persistence | `scripts/smc/risk_halt.py`, `tests/test_smc_risk_halt.py`; orchestrator honors `risk_halt.halted` |
| 0.5% risk floor/reject (pre-existing) | `scripts/smc/risk.py`, `tests/test_smc_risk.py`; webhook/staging default `risk_pct=0.005` (`test_create_app_defaults_to_half_percent_risk`) |
| Bot-only cancel/close (comment ownership) | `is_bot_owned_comment` + adapter cancel/close/rollover guards; `tests/test_smc_ownership.py` |
| Affordability distance at USD 500 / 0.01 lot | `scripts/smc/affordability.py`, `tests/test_smc_affordability.py` |
| News unknown/stale + blackout blocks new risk | `NewsManager.new_risk_allowed`, wired in `smc_main.py`; `tests/test_smc_news.py` |
| INTENT_SUBMITTED + UNKNOWN vs REJECTED | `ExecutionResult.status` in `mt5_adapter.py` |
| Manual vs bot vs cash-flow PnL separation | `apply_account_pnl_event` in `types.py`; `tests/test_smc_account_pnl.py` |
| Broker/Demo identity gate | `scripts/smc/broker_identity.py`; `tests/test_smc_broker_identity.py` |
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
| News pending cancel without force-closing positions (scenario 18) | `NewsManager.should_cancel_pending`; orchestrator + `smc_main`; staging wires `news_manager`; webhook `/internal/clock` cancels + `finish_setup` (incl. dry-run); `test_clock_cancels_unfilled_pending_on_news_blackout` |
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

## Still open for issue #1

| Gap | Notes |
| --- | --- |
| Live Exness connect smoke with real credentials | **Blocked on Mac:** native `MetaTrader5` missing; Wine IPC `(-10003)` / auth `(-6)`. Evidence: `docs/ops/2026-09-16-mac-live-gate-blocker.md`. Needs Windows/Oracle host + Exness Demo session. |
| Oracle ARM64 runtime soak | Checklist ready; needs executed soak evidence |
| Forward Demo 12-week protocol execution | Protocol registered; prospective after Gates B/C |

## Sibling issues #2–#4

Documentation deliverables in-repo. Tracker: **#3/#4/#2 closed** 2026-09-16 via `gh` on `feature/smc-v2-hardening`.
