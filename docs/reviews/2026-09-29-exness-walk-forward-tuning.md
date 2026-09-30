# Exness tick tuning and retrospective walk-forward — 2026-09-29

**Verdict: no robust replacement qualified. Research only; Demo orders and real money NO-GO.**

The user requested optimization against real price history. This run reproduces the frozen core, verifies the raw capture against the replay tape, and evaluates 15 neighboring configurations. No runtime configuration or execution path was changed. No orders were sent.

## Data evidence

- Archived Exness Demo XAUUSDm Bid/Ask capture; March 21–September 28 exclusive including warmup. Raw capture hashes verified for all 191 daily files.
- 45,671,201 raw ticks exactly match time/bid/ask tape arrays. Chronology, finite positive prices, noncrossed quotes, and per-day boundaries checked.
- Independently rebuilt M1 from raw ticks, then M15 using only 15 complete minutes: all 12,100 reference bars match within 1e-9 price tolerance. Timestamp storage units normalized without changing instants.
- Evaluation: March 28–September 28 exclusive, 40,267,449 ticks. Market closures and missing minutes are not fabricated. This audit establishes consistency with saved capture, not independent confirmation that the broker archive contains every market tick.
- Baseline reproduced: $132.98, -33.51%, 4 trades, max tick equity DD 36.12%.
- Prefix invariance checked for core plus all 15 candidates: adding later bars does not change earlier indicators/signals.

## Frozen research protocol

- Donchian 40/48/56/64/72; TP 3.0/3.25/3.5 ATR; SL 2.5 ATR; RSI off; EMA off.
- Fixed 0.01 lot, $200 per run, 10% equity risk cap, 40% UTC daily admission halt, no recovery. These controls remain in force.
- Saved Bid/Ask spread; zero commission under published [Exness Standard tariff](https://www.exness.com/standard-accounts/) checked September 29. No invented 0.10R fee. Base case adds neither slippage nor swap; historical swap entitlement and actual broker fills remain unknown.
- Expanding training begins March 28. Select using training data only: at least 20 trades, positive return, DD <=40%; maximize return/DD. Deterministic tie break: lower Donchian then lower TP. No eligible row means cash.
- DD <=40% is an analyst-declared research screen, not owner-approved live risk tolerance. Protocol persisted before search outcomes.
- Each monthly test starts fresh at $200 and closes open positions at last available tick before boundary. Do not add/compound fold returns or interpret them as a continuous trading account.
- This is **retrospective walk-forward, not untouched out-of-sample evidence**: all six months already informed earlier 54-row and 60-row searches and this grid design.

## Walk-forward results

| Test window (UTC, end exclusive) | Selected from preceding training | Return | Trades | Tick equity DD |
| --- | --- | ---: | ---: | ---: |
| 2026-06-28 → 2026-07-28 | Donchian 48, TP 3.5 | +52.70% | 28 | 43.79% |
| 2026-07-28 → 2026-08-28 | Cash: no eligible training row | 0% (cash) | 0 | 0% (cash) |
| 2026-08-28 → 2026-09-28 | Cash: no eligible training row | 0% (cash) | 0 | 0% (cash) |

First selected test earned +52.70%, but DD 43.79% exceeded the 40% research screen. Hypothetical extra spread of $0.20/oz (Bid -0.10, Ask +0.10, signal bars unchanged) gave +52.62%, 28 trades, DD 43.80%. This is a quote stress scenario, not measured slippage or proof of cost robustness. The later two folds selected nothing; they provide no profitable-trading confirmation.

## Full-window sensitivity (descriptive; not selection evidence)

| Donchian | TP ATR | Return | Final USD | Trades | Tick equity DD |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 40 | 3.0 | +209.26% | 618.53 | 302 | 46.47% |
| 40 | 3.25 | +202.61% | 605.21 | 293 | 49.38% |
| 40 | 3.5 | -45.61% | 108.77 | 15 | 60.44% |
| 48 | 3.0 | +166.81% | 533.62 | 266 | 56.89% |
| 48 | 3.25 | -26.21% | 147.58 | 74 | 58.75% |
| 48 | 3.5 | +207.74% | 615.49 | 220 | 40.58% |
| 56 | 3.0 | +209.50% | 619.01 | 236 | 56.18% |
| 56 | 3.25 | +28.70% | 257.40 | 177 | 61.68% |
| 56 | 3.5 | +233.15% | 666.30 | 225 | 42.10% |
| 64 | 3.0 | +84.68% | 369.36 | 217 | 53.97% |
| 64 | 3.25 | +32.10% | 264.19 | 134 | 64.77% |
| 64 | 3.5 | +148.00% | 496.00 | 210 | 43.64% |
| 72 | 3.0 | -16.93% | 166.15 | 133 | 64.85% |
| 72 | 3.25 | +14.00% | 228.00 | 159 | 60.96% |
| 72 | 3.5 | +18.47% | 236.95 | 203 | 64.84% |

Donchian 48 / TP 3.5 has the lowest full-window DD of this grid (40.58%). Donchian 56 / TP 3.5 has the highest return (+233.15%), with DD 42.10%. Neither passes the 40% full-window screen. The already-seen 48 / TP 3.0 headline has DD 56.89%; the intermediate TP 3.25 loses 26.21%. This is not a smooth robust parameter region. The fixed-lot cap makes admission depend on prior equity; small changes can change which later trades are admitted. These results show sensitivity, not proof of its sole cause.

## Limits and next research decision

- No candidate adopted into the frozen core. Keep 48/3.5 and 56/3.5 only as explicit research hypotheses if further data is obtained. Expanding the grid on this tape will increase selection bias.
- Next evidence needed: additional Exness history outside this tape, with the same symbol/account conditions and capture audit. Freeze candidate and acceptance rule before reading that holdout. Future paper/shadow monitoring can provide chronological evidence; no order permission is implied.
- Tick replay uses a shared Python engine: TP fills at target, SL fills at first crossing quote; simplified margin proxy and current broker specification. It does not model verified historical margin changes, broker approval, queueing, measured slippage, or swap entitlement.
- Existing output field `cost_cap_rejections` combines risk-cap and margin-proxy rejections. Do not report it as a pure risk-cap count.
- DD is the existing engine tick-equity metric, not a broker statement. Daily loss policy rejects new admissions; it is not a guaranteed maximum realized daily loss.
- Existing shadow parity remains blocked per the preceding handoff; these research runs do not resolve that gate.

## Reproduce and verify

```bash
.venv/bin/python -m scripts.research.exness_walk_forward --output data/exness_walk_forward_NEW
.venv/bin/python -m unittest discover -s tests -p test_exness_walk_forward.py
.venv/bin/python -m unittest discover -s tests
```

- Focused checks: 2 passed. Full suite: 661 ran, 659 passed, 2 skipped; exit 0. No MT5 connectivity or execution smoke test run because no connector/runtime change was made.
- `WalkForwardTests.test_selection_prefers_return_per_drawdown_and_never_falls_back`: ranking, trade-count/DD/profit boundaries and cash fallback.
- `WalkForwardTests.test_audit_rebuilds_bars_and_rejects_tape_and_raw_corruption`: exact reconstruction, incorrect bars, changed tape, and changed raw archive rejected.
- Initial audit attempt stopped on pandas timestamp resolution mismatch (`ms` vs `us`), before tuning. Comparing equal instants at the reference resolution fixed the validator. Failed attempt preserved without a COMPLETE marker.

- Complete local evidence: `data/exness_walk_forward_2026_09_29_v2/results.json`, `protocol.json`, per-fold JSON, `COMPLETE`.
- Results SHA-256: `bc9a5f1bed2a032a16db813a32a460a7c4d5f176dd99ebe523c1e2ea98506576`.
- Source hashes, raw manifest hash and all three tape hashes are embedded in results.json. A compact tracked copy accompanies this review as `2026-09-29-exness-walk-forward-results.json`.
