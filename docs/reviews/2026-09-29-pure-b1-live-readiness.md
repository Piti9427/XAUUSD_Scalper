# Pure B1 real-money readiness review — 2026-09-29

**Verdict: NO-GO for real-money execution.** Reviewed working tree on `feature/smc-v2-hardening` against `develop` (`git diff develop...HEAD`) and the uncommitted `scripts/smc/risk.py` and `tests/test_smc_risk.py` diff. Spec supplied: `/tmp/XAUUSD_Scalper_Handoff_2026-09-29.md`; current strategy and safety contract: `AGENTS.md`. No order or notification was sent.

## Standards

1. **Hard — retired recovery path remains callable.** `AGENTS.md` requires Pure B1 single position and says not to re-enable recovery. `scripts/smc/orchestrator.py:512-545` still routes injected `BasketManager` to `on_recovery_signal`, bypassing standard `calculate_lot_size`. No production construction was found, so this is dormant in observed entrypoints, not evidence of a current recovery order.
2. **Hard — single-leg sizing conflicts with split-step rule.** `AGENTS.md` specifies fixed 0.01 lot. `scripts/smc/risk.py:126-150` floors to a minimum 0.02-lot step and rejects otherwise safe 0.01-lot setups as unsplittable. This code includes an uncommitted edit; current working tree was tested.
3. **Config conflict — older B1-FINAL contract remains separate.** `config/B1-FINAL-v1.yaml:11-12,40-67` defines 3.5R, 12% HWM stop, no daily hard stop, and `real_money_status: NO_GO`. These differ from the current declared 6.25/2.5 ATR, 10% cap, 40% daily-loss policy. No evidence that this legacy file controls current runtime.
4. **Judgment call — speculative recovery abstraction.** The optional `basket_manager` branch in `scripts/smc/orchestrator.py:512-545` retains a second execution policy after the Pure B1 pivot. Remove or isolate it from the active strategy path.

## Spec

1. **P0 — active Python alert entrypoint implements different signal.** Handoff says Pure B1 Breakout + RSI; `main.py:34,84-119` constructs `XAUUSDSniperStrategy`, whose `scripts/strategy.py:41-88` uses wick rejection/MSS and a session gate, with no Donchian or RSI guard. `main.py` does not place orders. `smc_main.py:63-70` rejects connected live execution. The webhook bridge takes external TradingView `SETUP_PENDING` events, not local Pure B1 detections.
2. **P0 — fixed 0.01 lot and 10% cap are not enforced end to end.** `config/settings.yaml:29-31,64-75` declares values, but `main.py` does not call a risk gate. `scripts/run_staging_bridge.py:71-76,94-95,154-181` passes webhook 5% risk and 2.5R target, not the declared Pure B1 contract. In the current working tree, `calculate_lot_size(balance=200,equity=200,entry_price=3000,sl_price=2995,risk_pct=.10,spread_buffer=0,min_lot=.01,contract_size=100,lot_step=.01)` returned 0.04 lot. At a $15 stop, a safe 0.01 lot is rejected by the two-leg rule. If BasketManager is injected, `scripts/smc/basket_manager.py:222-264` emits fixed lots without per-order 10% risk calculation.
3. **P0 — alerts can precede broker approval.** `main.py:97-119` sends Telegram on a signal without order submission or broker confirmation, contrary to `AGENTS.md` execution-alert alignment. Telegram is disabled in current config, but enabling it exposes this path.
4. **P1 — 40% daily-loss guard is config only for observed entrypoints.** `config/settings.yaml:66` is consumed by `BasketManager`, but that manager is not constructed by `main.py`, `smc_main.py`, or `scripts/run_staging_bridge.py`. The bridge instead uses `max_daily_losses: 2` at `scripts/run_staging_bridge.py:75`.

## Validation and remaining gates

- `make check` passed locally: compile, `pip check`, Ruff lint/format, 608 tests; 2 skipped. `git diff --check` passed. No broker smoke test or order test was run.
- MQL5 `B1FinalEA` is a different, older frozen contract; `mql5/B1FinalEA.mq5:270-273` rejects operation outside Strategy Tester and real accounts. Its `config/B1-FINAL-v1.yaml:67` says `NO_GO`.
- Handoff's `$200 -> $883.99` six-month result is not independently reproduced by this review. The older six-month replay document (`docs/research/B1_HYBRID_EXNESS_SIX_MONTH_2026-09-28.md:10-13,40-41`) explicitly reports assumed fee/swap and no broker execution parity. Historical commission, slippage, margin approval, and fill behavior remain unverified for the current contract.
- Before real money: freeze one executable Pure B1 contract and entrypoint; prove signal, fixed-lot/cap, single-position, daily loss, execution/notification parity against broker Demo orders; collect target-account costs and prospective Demo results; review a separate real-money GO decision. Keep `dry_run` enabled until then.
