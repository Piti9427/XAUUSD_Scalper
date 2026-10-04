# Reward156 profit/survival v2 — measured verdict

Selected: **NONE**. Holdout: `NOT_OPENED_NO_QUALIFIER`.
Evaluated 65 configurations; 584 cells; 64 fresh complete-result matches.
Demo: unchanged trial30. Profit/survival qualification applies to modeled research scenarios.

## Policy relaxation

| Rule | Frozen v1 | Owner-approved v2 |
|---|---|---|
| Full profit | >0 and above trial30 | >=USD50 and above BOTH controls |
| DD | <=35% | <=45% |
| Reset-half profit | >0 and above trial30 | >=-USD20 |
| WR/RR | strict baseline comparison; RR>1 | report-only; undefined preserved |
| BUY+SELL | each full/half cell | full cells only |
| Cost views used for qualification | current-spec swap | no_swap AND swap plus swap0.5x/1.5x finalists |
| Risk/lot/capital | 10% ceiling/fixed0.01/USD200 | same |

## Configuration result

Highest-ranked measured candidate: `variant_1af968e9ac6a26ea`; continuous passes **4/8**, worst net **$29.74**, worst DD **35.60%**.

```json
{
  "strategy": "reward156",
  "formula": "archived",
  "rsi_period": 14,
  "rsi_threshold": 25,
  "sell_lookback": 96,
  "sell_ema": 50,
  "macro_span": 200,
  "buy_pause_drawdown": 0.0,
  "stop_atr": 2.5,
  "buy_stop_atr": 1.5,
  "buy_target_rr": 2.0,
  "sell_target": "atr3",
  "protect_mode": "break_even",
  "buy_protect_mode": "off",
  "daily_loss_limit": 0.1,
  "max_daily_losses": 1,
  "cooldown_bars": 0,
  "entry_session": "all",
  "risk_mode": "static",
  "risk_cap": 0.1,
  "name": "variant_1af968e9ac6a26ea",
  "group": "signal",
  "parent": "05af628f79141404"
}
```

## Paired continuous accounts

| Dataset | Cost/view | trial30 net | Original Reward156 net | Candidate net | Candidate DD% | Trades | Failed v2 gates |
|---|---|---:|---:|---:|---:|---:|---|
| A | base/no_swap | -145.87 | -141.34 | 37.63 | 24.64 | 32 | net_floor, trade_count |
| A | base/swap | -145.87 | -140.71 | 37.06 | 24.85 | 32 | net_floor, trade_count |
| A | stress/no_swap | -146.08 | -134.88 | 30.31 | 25.47 | 32 | net_floor, trade_count |
| A | stress/swap | -146.08 | -134.88 | 29.74 | 25.68 | 32 | net_floor, trade_count |
| B | base/no_swap | -90.71 | -89.96 | 188.07 | 35.60 | 72 | PASS |
| B | base/swap | -90.71 | -90.53 | 186.93 | 35.60 | 72 | PASS |
| B | stress/no_swap | -91.82 | -93.27 | 293.67 | 28.29 | 72 | PASS |
| B | stress/swap | -91.82 | -93.84 | 292.53 | 28.29 | 72 | PASS |

## Diagnosis and scope

Per-side net/loss/MAE/MFE and multi-loss days: `diagnostics/`. Independently replayed swap/no-swap admission divergence: `cost-path-divergence.json`. `swap_on_losing_non_tp_exits` includes losing SL/end exits; it is not a protection-only metric.
A: Sep2024–Jun2025 discovery10months; B: Oct2025–Sep2026 discovery12months. Halves reset USD200 account state; profits are not added to continuous account results.
Base: archived spread, modeled slippage/commission0. Stress: spread+0.20USD/oz, slippage0.10USD/oz, commission0. Current-spec swap and assumed UTC rollover are sensitivity scenarios; historical rates/rollover/DST/entitlement and live broker parity remain unverified.
Archived seeds retain their own RSI formula; frozen Reward156 retains zero-loss RSI semantics. Strategy-specific filters/exits/circuits differ explicitly. Market/account/cost environments stay paired.
Historical holdout opening is conditional on a locked discovery qualifier; holdout is not prospective.

## Completion evidence

Full suite:831tests/21.448seconds/OK (skipped=2). Changed-Python Ruff and syntax compilation passed. No configured static typechecker; compilation is not typechecking. Standards/Spec findings fixed and re-reviewed.
Independent `verify_campaign.py`: source/input/checkpoint hashes, complete ledger cashflow, lot/risk invariants, recomputed policy/adaptive catalog, fresh-repeat attestations and v1 control full-result parity. See `validation.json` and `completion-audit.md`.

V1 performance/qualification artifacts remain immutable. A complete finite experiment can end with the profit objective unmet.
