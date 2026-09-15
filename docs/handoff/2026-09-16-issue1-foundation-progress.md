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
| Fill-and-stop same bar recorded (pre-existing) | `tests/test_smc_backtester.py` |

## Still open for issue #1

| Gap | Notes |
| --- | --- |
| Gate A remaining material decisions | Fib anchors freeze, cash-flow pause, quote-side/stats protocol, data provenance |
| Broker ownership isolation + reconcile | Bot-only cancel/close; durable intent; partial fill residual |
| Shared-account vs bot PnL separation | Manual losses affect gates, not bot expectancy |
| News blackout + unknown/stale block | Partial news module exists; point-in-time archive + block-on-unknown incomplete |
| Bid/ask tick replay economics | Mid/OHLC still used in places |
| Affordability report on live Exness spec | USD 500 / 0.01 lot distance audit |
| Oracle ARM64 runtime soak | Infra gate, not strategy |
| Forward Demo 12-week protocol | Prospective evidence only after Gates A–C |
| Close/comment issues on GitHub | Local work committed; tracker write currently 403 (PAT lacks issues write); `gh` keyring invalid |

## Sibling issues #2–#4

Documentation deliverables are in-repo (`xauusd-s1-s4-mechanical-v1.md`, research handoff, contract tests). Tracker closure blocked by the same write-auth issue.
