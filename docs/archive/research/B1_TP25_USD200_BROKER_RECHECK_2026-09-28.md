# B1_TP25 at $200 — fresh broker capture

## Result

Fresh MT5 XAUUSDm historical Bid/Ask capture completed on 2026-09-28. Replaying B1_TP25 with the original B1 drawdown-based position sizing admitted **zero trades** at $200. All 553 signals failed minimum-lot admission. Balance remained $200; return and tick-equity drawdown were 0%; win rate and profit factor are undefined. This is an account-feasibility result, not evidence of profitable or safe trading.

Minimum 0.01-lot stop risk across rejected signals was $12.676 minimum, $21.034 median, and $59.927 maximum. Available risk budget was $2 (1% of $200). Even the smallest stop risk required 6.338% of initial capital. No lots were rounded up and no risk policy was changed.

## Data and exact scope

- Source: fresh read-only `MetaTrader5.copy_ticks_range`, verified target Demo account, symbol XAUUSDm. No order API called.
- Capture: May 7–September 25, 2026 UTC; 31,780,274 ticks. Every daily file passed SHA-256 validation and matched the corresponding prior broker capture hash.
- Scoring: May 14–September 25, 2026 UTC; 30,483,511 ticks. Earlier days supply indicator warmup.
- Signals: completed M15 bars built from actual Bid ticks; Donchian 30 breakout with RSI filter; SL 2.5 ATR; TP 2.5R; one position at a time.
- Sizing: existing B1 drawdown tiers (1%, 0.75%, 0.5%, 0.25%), 12% drawdown entry halt, broker minimum/step 0.01 lot. This differs from fixed 0.01-entry/0.02-recovery handoff sizing.
- Costs: actual Bid/Ask spread included. Historical commission, swap and slippage are unmeasured and excluded, not asserted to be zero. With no positions, these exclusions do not create a profit result.
- Execution: Python historical replay; not MT5 Strategy Tester, broker-approved fills, or live execution validation. No recovery basket. Data previously exposed; not unseen validation.

## Verification

- 32 existing reference/tick/comprehensive tests passed.
- Three prefix-causality comparisons passed for recalculated reference bars.
- All 553 decision records independently checked: minimum-lot stop risk exceeds budget; every rejection is `RISK_BELOW_MINIMUM_LOT`.
- Tick chronology, finite positive Bid/Ask, non-crossed quotes and daily hashes checked by capture loader/replay.
- Initial runner attempt stopped before replay due to a pandas mask shape mismatch; fixed in research runner. Only the directory ending `_verified` contains the successful result and `COMPLETE` marker.
- Production code and live settings were not changed by this recheck. Existing basket edits were left intact.

## Evidence and reproduction

- Capture: `data/b1_tp25_broker_fresh_2026-09-28/manifest.json`
- Result: `data/b1_tp25_usd200_fresh_2026-09-28_verified/result.json`
- Signal/admission audit: `data/b1_tp25_usd200_fresh_2026-09-28_verified/decisions.csv`
- Empty trade ledger with headers: `data/b1_tp25_usd200_fresh_2026-09-28_verified/trades.csv`
- Tick coverage: `data/b1_tp25_usd200_fresh_2026-09-28_verified/tape/coverage.json`

```bash
.venv/bin/python -m scripts.research.b1_tp25_broker_recheck \
  --capture data/b1_tp25_broker_fresh_2026-09-28 \
  --output data/b1_tp25_usd200_NEW
```

The output path must not already exist. A fixed-lot recovery replay would be a separate money-management contract; neither +206.9% nor the handoff's +275.2% is reproduced by this run.
