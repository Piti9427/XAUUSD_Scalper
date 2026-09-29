# Pure B1 target refactor research

- Target: `scripts/strategy.py` pure M15 detection, new tick replay caller, then live runner only after replay review.
- Existing reference: `run_b1_breakdown.py` uses prior-30 Donchian, RSI14 EWM span14, EMA50 EWM span50, ATR14 simple rolling mean, strict RSI 30–70.
- Archived +342%: `scripts/research/b1_hybrid_six_month.py` uses `b1_final.reference_bars()` with Wilder RSI buy <=75 / sell >=25 and no EMA50. Preserve its source and outputs.
- Convention: `unittest`; `tests/test_strategy.py` covers legacy strategy, `tests/test_b1_hybrid_six_month.py` covers replay engine.
- Acceptance: deterministic target signals on completed UTC bars, strict thresholds, no lookahead, shared signal caller for replay, preserved old results, risk and cost accounting, no broker/notification side effects.

## 2026-09-29 Pure B1 Shadow implementation

- Scope: read-only broker M15/tick capture, bar/index adapter, one shared Pure B1 decision, daily/exposure gates, append-only Shadow evidence.
- Pre-agreed seam from the approved plan: fake MT5 rates/ticks -> UTC adapter -> `pure_b1_bars` -> `check_fixed_lot_risk` -> JSONL; assert no `order_send` or Telegram.
- Existing helpers: `scripts/smc/broker_rates.py` returns RangeIndex; `scripts/strategy.py` requires UTC DatetimeIndex. `scripts/research/shadow_capture.py` captures bounded ticks with manifest. `scripts/ops/run_b1_d_wine.py` runs read-only scripts under Wine.
- Data contract: `CORE_STRATEGY.md`; archived input/source hashes in `data/b1_pure_target_replay_cost_gated_2026_09_29/contract.json`. Broker costs/fills remain unobserved.
