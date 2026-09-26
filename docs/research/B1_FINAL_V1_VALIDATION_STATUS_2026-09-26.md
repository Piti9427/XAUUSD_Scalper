# B1-FINAL-v1 implementation validation — 2026-09-26

**Decision: NO-GO for Demo trading deployment and real money.** Frozen contract and deterministic Python reference implemented; compiled MQL5 parity probe prepared. Full execution EA and broker validation remain incomplete. No order API invoked.

## Active contract

Source: [user-provided handoff](B1_FINAL_v1_implementation_validation_handoff.md), SHA-256 `4905603e9a59412fbb7d05828256f4632c779cdc7277890af982615eed968932`.

Manifest: `config/B1-FINAL-v1.yaml`, SHA-256 `88c61fe344ffa0cb440fdce16f6a60a4dc5f81e0f328cba6b7d577e362d8b66e`.

- M15 Bid bars; previous 30 completed Donchian bars; strict close breakout.
- RSI14: long <=75, short >=25. ATR14; SL 2.5 ATR; TP 3.5R.
- First valid tick inside the immediately next M15 interval; one position; no partial/BE/trailing/grid/Martingale.
- Quote-anchored SL/TP, no actual-fill re-anchor. Nearest tick, positive-price half-up normalization. Actual fill risk reconciliation remains an execution gate.
- Equity HWM tiers: DD <3% risk 1%; <6% 0.75%; <9% 0.5%; <12% 0.25%; >=12% latch STOP_NEW_ENTRIES. Recovery does not clear latch. Existing trade continues under SL/TP.
- Daily hard stop disabled. Daily -2R/-3R telemetry is specified but not implemented in the execution runtime.

This supersedes the older 0.5% / 2.5R / hard-DD 8% validation policy. Old reports remain evidence, not active parameters. No RR neighbor search for this version.

### Explicit reference choices

Indicator seed anchors to the first bar of the hashed input sequence. Arithmetic seed of first 14 observations; first true range = high-low; first RSI delta = zero; flat RSI = 50. Wilder recursion thereafter. Require 100 completed bars before signals. Missing intervals are absent, not fabricated; completed-bar indexing continues across gaps. Invalid/NaN/misaligned/non-UTC input fails closed. MQL5 core implements this exact batch seed instead of assuming built-in RSI/ATR equivalence.

These implementation choices are reproducible but have not yet reproduced external handoff GetData/OANDA targets. A shorter rolling-history seed is not equivalent and must not replace the pinned seed silently.

## Executed historical replay

Command:

```sh
.venv/bin/python -m scripts.research.b1_final \
  --capture data/b1_d_exness_ticks_2026_full_retry \
  --output data/b1_final_reference_2026-09-26_final
```

31,780,274 actual Exness Bid/Ask ticks, May 7–September 25, 2026. Complete tick-derived M15 Bid bars; May 7–13 warmup, scoring from May 14. Source daily hashes validated. Four independent runs start at Demo snapshot $1,173.46; splits are not additive profits. Dataset already exposed, not untouched OOS. Python tick replay is **not** MT5 Strategy Tester.

| Window | Minimum-lot rejections | Executed trades | Net USD |
|---|---:|---:|---:|
| Development May 14–June | 194 | 0 | 0 |
| Validation July–August | 258 | 0 | 0 |
| Confirmation September | 101 | 0 | 0 |
| Continuous May 14–September 25 | 553 | 0 | 0 |

Base 1% gives $11.7346 nominal risk budget. Minimum 0.01 lot nominal SL risk over the 553 continuous signals is $12.676–$59.927. All rejected without rounding up. RR cannot fix affordability of a fixed SL. PF/expectancy undefined; zero DD is not evidence of profitability, risk-controller effectiveness in broker execution, or acceptance.

Fresh read-only Demo probe on 2026-09-26 verifies Exness-MT5Trial7, USD equity/balance $1,173.46, XAUUSDm min/step 0.01, contract 100, tick size 0.001, loss/profit tick value 0.1. Snapshot: `data/b1_final_demo_spec_2026-09-26.json`. Historical replay uses the capture-time spec and explicitly assumes current-spec swap at UTC midnight; actual historical commission/slippage/margin approval/rollover remain unmeasured. Generic 0.1R costs are not substituted for final broker costs.

Outputs: `reference_bars.csv`, `parity_input.csv`, four decision/trade ledgers, risk-state checkpoints, manifest with source/config/input hashes, `COMPLETE` in `data/b1_final_reference_2026-09-26_final/`. COMPLETE means research replay completed, not qualification PASS.

## Engineering evidence

| Handoff requirement | Evidence |
|---|---|
| RSI14 / ATR14 known vectors | `test_known_flat_rsi_and_atr_vector`, `test_wilder_seed_and_recursive_known_vector` |
| Donchian previous-30 indexing / warmup | `test_previous_30_excludes_signal_bar_and_requires_100_bar_warmup` |
| Exact breakout and RSI boundaries | `test_strict_breakout_and_rsi_boundaries` |
| NaN / gap bars / causal timestamps | `test_missing_invalid_or_non_utc_data_fails_closed`, `test_completed_gap_bars_preserve_prior_completed_bar_indexing`, `test_causal_prefix_does_not_change_with_future_bars` |
| All risk-tier boundaries | `test_all_risk_tier_boundaries` |
| Intratrade equity HWM / STOP_NEW_ENTRIES | `test_tick_equity_hwm_and_hard_stop_latch_survive_recovery`, `test_intratrade_hard_dd_does_not_panic_close_but_blocks_next_entry` |
| HWM persistence / corruption | `test_restart_preserves_hwm_stop_and_detects_corruption`, `test_restored_hwm_controls_sizing_and_reported_drawdown` — local research checkpoint, not broker restart reconciliation |
| Quote / SL / TP / equity sizing | `test_reference_ask_entry_stop_target_and_equity_budget`, `test_half_tick_rounding_contract` |
| Never force minimum lot | `test_minimum_lot_rejection_remains_risk_safe` |
| Config drift protection | `test_manifest_drift_refuses_modified_alpha_or_risk` |
| Parity comparator detects drift | `test_parity_gate_detects_indicator_signal_and_timestamp_drift` — comparator fixture, not executed EA parity |
| Regression command | `.venv/bin/python -m unittest discover -s tests -p 'test_b1*.py'`: 30 tests PASS |
| Full repo regression | `.venv/bin/python -m unittest discover -s tests`: 530 tests PASS |
| MQL5 compilation | `B1FinalValidationEA.mq5`: MetaEditor 0 errors / 0 warnings; offline tester-only parity probe, **no orders** |

MQL5 artifacts: `mql5/B1FinalCore.mqh` and `mql5/B1FinalValidationEA.mq5`. Core contains independent indicator/signal recursion, equity tier functions and a runtime-symbol `OrderCalcProfit`/`OrderCalcMargin` sizing helper. Helper has only compile evidence; broker execution tests are pending. Probe refuses chart attachment outside Strategy Tester and exports indicators/risk boundaries from a pinned CSV. It is not a production EA.

## Gate status and remaining work

| Gate | Status |
|---|---|
| Frozen contract / Python reference / regression | Implemented and tested; source/build hashes recorded |
| GetData/OANDA regression targets | UNVERIFIED — original datasets/ledgers absent from supplied handoff |
| Indicator / signal Reference↔MQL5 parity | PENDING — compile is not runtime parity |
| Intended / actual trade parity | PENDING — no admitted historical trades and no execution EA |
| OrderCheck / OrderSend / OnTradeTransaction / retry / partial fill | NOT IMPLEMENTED in this probe |
| Persistent order identity / broker restart / duplicate-instance recovery | NOT IMPLEMENTED in this probe |
| Actual broker-cost MT5 real-tick Tester | PENDING — no tester report/deal ledger |
| Non-overlapping OOS >=100 trades | PENDING — historical dataset exposed, sample has zero trades |
| Monte Carlo >=50k paths on final broker ledger | PENDING — final broker-realistic ledger unavailable; no fabricated empty-ledger Monte Carlo |
| Demo >=8 weeks AND >=50 closed trades | NOT STARTED; deploy only exact build after prior mandatory gates pass |
| Small-live / production | NO-GO; separate user approval after mandatory gates |

Known negative evidence retained: handoff reports 2012–2022, 3,765 trades, expectancy -0.0137R, PF 0.981, total -51.5R, max DD 106R. These are **handoff assertions, not independently reproduced results**. Regime dependence/long-history failure remain unresolved. Positive recent figures in handoff are also unverified here.

Next sequence: execute pinned CSV through MQL5 probe, compare every indicator/signal, then implement/test broker execution and recovery separately. Before trading deployment, resolve the account/minimum-volume feasibility constraint while preserving the frozen risk cap and alpha rules. Do not raise risk, weaken DD limits, or retune RR to force a pass.
