# B1-FINAL MQL5

| File | Role |
|---|---|
| `B1FinalCore.mqh` | Frozen deterministic indicator/signal/risk-tier core (batch). No orders. |
| `B1FinalState.mqh` | Incremental indicators equal to the batch core, exact checkpoint, integrity-checked state document, atomic file store. |
| `B1FinalEngine.mqh` | Execution engine: admission gates, broker-calculated sizing, persisted request identity, reconciliation, HWM tiers and 12% latch, incidents, one-shot +2R stop, outbox events. Broker, sink and store are injected interfaces. |
| `B1FinalEA.mq5` | MT5 adapter and EA. **Order execution is Strategy Tester only**: `OnInit` fails on live charts, non-Demo accounts, identity/hedging/symbol mismatch. |
| `B1FinalOutbox.mqh` | Shared JSONL sink: stable event ID dedupe, write acknowledgment and torn-tail detection. |
| `B1FinalEngineTests.mq5` | Fault-injection tests of the real engine against a fake broker; run in the Tester, write `B1_engine_tests.csv`. |
| `B1FinalValidationEA.mq5` | Frozen non-trading parity probe (unchanged). |
| `B1FinalParityRunner.mq5` | Tester wrapper that ships the parity CSV to the agent sandbox and includes the probe verbatim. |

Compile and run through `scripts/ops/mt5_wine_tester.py` (MetaEditor cannot take paths with spaces, so builds happen in `C:\b1build`; each Tester run archives its exact `.ex5`). Evidence, verdicts and hashes: [release package](../docs/archive/research/B1_FINAL_RELEASE_2026-09-27.md). Operation: [runbook](../docs/ops/B1_FINAL_RUNBOOK.md).

Parity comparison of probe output:

```sh
.venv/bin/python -m scripts.research.b1_final \
  --compare-mql <agent Files>/B1_FINAL_mql_indicators.csv \
  --reference-bars data/b1_final_reference_2026-09-26_final/reference_bars.csv \
  --output <new-result>.json
```

API references: [CopyRates](https://www.mql5.com/en/docs/series/copyrates), [OrderCalcProfit](https://www.mql5.com/en/docs/trading/ordercalcprofit), [OrderSend](https://www.mql5.com/en/docs/trading/ordersend), [MT5 testing](https://www.mql5.com/en/docs/runtime/testing).

Correction evidence and state-schema-2 handling: [2026-09-27 update](../docs/updates/B1_FINAL_FIXES_2026-09-27.md). Compile commands must include `B1FinalOutbox.mqh` for both EA and engine harness. Old schema-1 state is rejected and preserved; old release metrics do not validate changed execution sources.
