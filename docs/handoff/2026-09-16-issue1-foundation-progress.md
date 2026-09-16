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
| Tick CSV bar annotation helper | `scripts/smc/tick_feed.py`; `tests/test_smc_tick_feed.py` |
| Broker identity smoke CLI (no orders) | `scripts/smoke_broker_identity.py` |
| Demo 12w protocol + Oracle ARM64 checklist (docs) | `docs/ops/2026-09-16-foundation-demo-12w-protocol.md`, `docs/ops/2026-09-16-oracle-arm64-runtime-checklist.md` |

## Still open for issue #1

| Gap | Notes |
| --- | --- |
| Live Exness connect smoke with real credentials | Run `python3 scripts/smoke_broker_identity.py` with MT5 session; needs broker evidence |
| Full backtester tick CSV walk-through | Helper ready; `SMCBacktester.run` still OHLC-only unless caller annotates bars |
| Oracle ARM64 runtime soak | Checklist ready; needs executed soak evidence |
| Forward Demo 12-week protocol execution | Protocol registered; prospective after Gates B/C |
| Close/comment issues on GitHub | Local work committed; `gh` keyring invalid + API rate limit / issues write 403 |

## Sibling issues #2–#4

Documentation deliverables are in-repo (`xauusd-s1-s4-mechanical-v1.md`, research handoff, contract tests). Tracker closure blocked by the same write-auth issue.
