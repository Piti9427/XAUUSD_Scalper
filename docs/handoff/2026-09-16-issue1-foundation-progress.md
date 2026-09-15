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

## Still open for issue #1

| Gap | Notes |
| --- | --- |
| Gate A remaining material decisions | Fib anchors freeze, cash-flow pause, quote-side/stats protocol, data provenance |
| Full broker reconcile (partial residual, cancel races, restart after submit) | INTENT/UNKNOWN started; not complete lifecycle |
| Shared-account vs bot PnL separation | Manual losses affect gates, not bot expectancy |
| Bid/ask tick replay economics | Mid/OHLC still used in places |
| Live Exness symbol/account identity verification | Spec requires broker-confirmed metadata |
| Oracle ARM64 runtime soak | Infra gate, not strategy |
| Forward Demo 12-week protocol | Prospective evidence only after Gates A–C |
| Wire risk_halt file path end-to-end in Demo loop | Module+orchestrator ready; file load/save not fully wired while live loop remains disabled |
| Close/comment issues on GitHub | Local work committed; tracker write currently 403 (PAT lacks issues write); `gh` keyring invalid |

## Sibling issues #2–#4

Documentation deliverables are in-repo (`xauusd-s1-s4-mechanical-v1.md`, research handoff, contract tests). Tracker closure blocked by the same write-auth issue.
