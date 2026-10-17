# Exness Demo config search — 2026-09-29

**Decision: research candidate only. Demo orders NO-GO. Real money NO-GO.**

The current `CORE_STRATEGY.md` contract stays the frozen research target. This note records a searched candidate that beat that contract on one saved tape. It does not replace the contract and does not authorize an order.

## Cost and engine

- Tape: `data/b1_hybrid_baseline_6mo_fixed_2026_09_28` Bid/Ask ticks, symbol `XAUUSDm`, 2026-03-28 inclusive to 2026-09-28 exclusive.
- Spread comes from those Bid/Ask prices. Commission is 0 USD per lot round turn from the published Standard tariff, not from a deal ledger.
- No hypothetical 0.10R fee, no added slippage, no swap accrual. Historical swap entitlement and broker fills are missing.
- Fixed 0.01 lot, 10% current-equity cap, 40% UTC day-start loss halt, no recovery. Quote rule `first_fresh_quote_age_60s_lateness_90s`.
- Engine: `scripts/research/exness_demo_config_search.py` on `Replay`. `order_api_called` is false.
- Calibration of the current core on the full window reproduced **$132.98 / -33.51% / 4 trades**.

## Selection rule

Halves are fresh $200 accounts: 2026-03-28 to 2026-06-28, then 2026-06-28 to 2026-09-28. A candidate must be positive with at least 8 trades in each half. Among those, the selected row is the one with the higher worse half. The full window is reported after selection.

## Selected candidate

Donchian 48, no RSI guard, no EMA50, stop 2.5 ATR, target 3.0 ATR.

| Window | Return | Trades |
| --- | ---: | ---: |
| First half, fresh $200 | +151.32% | 114 |
| Second half, fresh $200 | +159.90% | 133 |

Full tape, one $200 path: **$533.62 / +166.81% / 266 trades / max tick equity DD 56.89%**.

733 signals on the full tape, 118 rejected by the 10% cap, 0 daily-loss rejects, 0 recovery legs.

## Current core on the same run

Donchian 30, RSI strictly inside 30–70, EMA50, stop 2.5 ATR, target 6.25 ATR: **$132.98 / -33.51% / 4 trades / DD 36.12%**. The first half was -26.34% (3 trades) and the second half was -38.60% (5 trades).

The selected candidate has a higher full-window balance. Its drawdown, 56.89%, is larger than the core's 36.12%.

## Neighbors that also beat the core

These passed both halves but lost the worse-half ranking:

| Config | Worse half | Full return | Full trades | Full DD |
| --- | ---: | ---: | ---: | ---: |
| Donchian 48, no RSI, SL 2.5, TP 3.5 | +132.58% | +207.74% | 220 | 40.58% |
| Donchian 40, no RSI, SL 2.5, TP 3.0 | +111.01% | +209.26% | 302 | 46.47% |
| Donchian 32, no RSI, SL 2.5, TP 3.0 | +34.25% | +137.80% | 355 | 46.99% |

The first-half maximum in the earlier 54-row grid, Donchian 40 with archived RSI 75/25 and TP 6.25, made +261% in the first half and -33.4% in the second. It was not selected.

## Limits

One six-month tape, two search passes (54 signal rows, then 60 Donchian/stop/target rows with RSI off). This is not an untouched future sample. Swap, slippage, margin approval, and broker fills were not measured. Live execution remains NO-GO.
