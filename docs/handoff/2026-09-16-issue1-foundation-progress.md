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
| 0.5% risk floor/reject (pre-existing) | `scripts/smc/risk.py`, `tests/test_smc_risk.py` |
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
| Demo 12w protocol + Oracle ARM64 checklist (docs) | `docs/ops/2026-09-16-foundation-demo-12w-protocol.md`, `docs/ops/2026-09-16-oracle-arm64-runtime-checklist.md` |
| GH close paste pack for #2–#4 | `docs/handoff/2026-09-16-github-close-ready.md` |

## Still open for issue #1

| Gap | Notes |
| --- | --- |
| Live Exness connect smoke with real credentials | Run `python3 scripts/smoke_broker_identity.py` with MT5 session; needs broker evidence |
| Oracle ARM64 runtime soak | Checklist ready; needs executed soak evidence |
| Forward Demo 12-week protocol execution | Protocol registered; prospective after Gates B/C |
| Close/comment issues on GitHub | Local work committed; MCP read OK; **write still 403** (PAT lacks issues write); `gh` keyring invalid |

## Sibling issues #2–#4

Documentation deliverables are in-repo (`xauusd-s1-s4-mechanical-v1.md`, research handoff, contract tests). Tracker closure blocked by the same write-auth issue.
