# Pure B1 Demo verdict — 2026-09-29

**Decision: Demo orders NO-GO. Real money NO-GO. This review does not authorize a Demo probe.**

Shadow is not passed. The parity ledger gate is BLOCKED because required rows have no verified cost snapshot, and some rows have no quote or unfinished warmup.

## What was run

- `.venv/bin/python -m unittest discover -s tests` — 659 tests ran, 657 passed, 0 failed, 2 skipped.
- Read-only ledger on the saved capture `data/b1_pure_broker_capture_v2_2026_09_29_1200_1300` against `data/b1_hybrid_baseline_6mo_fixed_2026_09_28/reference_bars.csv`. Output: `data/b1_pure_parity_ledger_2026_09_29/compare.json`, SHA-256 `4487c5085e2ff790af352253aa21079ce2fe461945134f5a279432470ac08b3e`. No new MT5 session was opened for this review.
- Labeled replay in `data/b1_pure_target_replay_labeled_2026_09_29/`. Hashes and scenario labels are in [the evidence pin](2026-09-29-pure-b1-evidence-pin.md).

`order_send` was not called. Telegram was not called. `order_api_called` on the ledger and replay output is false.

## Ledger

Field rows over the 1,812-bar overlap:

| Status | Count |
| --- | ---: |
| match | 16,599 |
| mismatch | 0 |
| blocked | 5,145 |

Gate: **BLOCKED**. `shadow_passed`: false. Unexplained mismatches: 0.

| Field | match | mismatch | blocked | Why blocked |
| --- | ---: | ---: | ---: | --- |
| OHLC | 1,812 each | 0 | 0 | Shared bars match |
| RSI, EMA50, ATR, direction, signal time | 1,337 | 0 | 475 | Warmup comparison holds only from 2026-09-07 03:30 UTC. Earlier bars are `warmup_unproven`. The proof dropped one prefix bar and compared the suffix. It is not a fixed 500-bar pass. |
| SL / TP | 1,333 | 0 | 479 | 475 warmup rows, plus signal rows whose saved ticks do not cover the 90-second window (`quote_timing_unavailable`). No late entry was created. |
| 10% risk decision | 0 | 0 | 1,812 | `cost_snapshot_unverified`. Historical equity was not invented. |

Other saved-capture checks, same command:

- Canonical M15 vs Bid ticks for 2026-09-29 12:00–13:00 UTC: 4 bars, 0 OHLC mismatches.
- Canonical M15 vs reference: 1,812 bars, 0 missing, 0 OHLC mismatches. Signal parity after the warmup proof: 1,337 bars, max EMA50 absolute difference 3.31e-7, RSI 0, ATR 0.
- Direct terminal M15 vs canonical: FAIL. 1,955 shared bars match. 27 terminal bars are absent from canonical 15/15 M15, including 2026-08-30 22:00 UTC. The overlap window used by the bar comparator counts 26 of those extras; the file-start Sunday bar is the 27th. Cause on every extra bar: `not_in_canonical_15_of_15`.

## Replay

The three labeled scenarios are research reconstructions. They are not expected Standard Demo results. The hypothetical 0.10R path that previously printed +150.31% was not used as the Standard scenario. Broker fills and historical swap entitlement remain missing. Details and hashes: [evidence pin](2026-09-29-pure-b1-evidence-pin.md).

## Tests

The suite covers the fake-MT5 seam from rates through the UTC adapter, detector, risk, daily baseline, exposure, and JSONL. Added coverage includes forming and incomplete M1 events, warmup failure, stale quote, restart day-start, unreadable and mismatched day-start, missing position symbol, exact 10% equality, zero commission with a source, missing commission, declared slippage, tick rounding, and `order_send` / Telegram source counts of zero. Exact 40% daily loss was already covered.

Focused tests are not broker parity. The ledger above is the broker-data check, and it is blocked.

## Still absent

- A verified commission tariff from a Demo deal. Published Standard zero is a named source, not a `symbol_info` reading and not a fill.
- Measured slippage. 0.10 and 0.20 are declared stress inputs.
- Historical swap-free entitlement and any overnight swap on a Pure B1 position.
- Per-bar account equity, so every 10% risk row stays blocked.
- Forward Demo fills, margin approval, and `history_deals_get` reconciliation.

Demo strategy automation and real money stay NO-GO until those gaps are closed under a separate approval. This document does not approve a probe.
