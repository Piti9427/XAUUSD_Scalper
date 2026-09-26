# B1-FINAL-v1 validation probe

`B1FinalValidationEA.mq5` is a **non-trading, tester-only indicator parity probe**, not the completed order EA. `OnTick` is empty. `OnInit` rejects attachment outside Strategy Tester. No OrderSend or notification side effects.

Compile with MetaEditor, keeping `B1FinalCore.mqh` next to the source. Compilation alone does not pass parity or the final real-tick gate.

For a parity run, copy `data/b1_final_reference_2026-09-26_final/parity_input.csv` into the test agent's `MQL5/Files` sandbox as `B1_FINAL_parity_input.csv`. Use identical hashed bars; retain the full oldest-bar seed. Run the probe in Strategy Tester. Save `B1_FINAL_mql_indicators.csv` and `B1_FINAL_mql_risk.csv` from the agent's Files directory. Input transfer, tester execution and output retrieval have not yet been automated or executed.

Compare indicators and directions:

```sh
.venv/bin/python -m scripts.research.b1_final \
  --compare-mql /path/to/B1_FINAL_mql_indicators.csv \
  --reference-bars data/b1_final_reference_2026-09-26_final/reference_bars.csv \
  --output /path/to/new-parity-result.json
```

Comparator requires every timestamp in exact order, matching missing-value positions, absolute numerical tolerance 1e-8 and exact directions. Nonzero exit means FAIL. It does not validate trade parity. Risk-boundary CSV requires separate comparison; current Python boundary tests do not prove executed MQL5 parity.

Sizing helper uses broker `OrderCalcProfit` and `OrderCalcMargin`. OrderCheck, actual send/fill reconciliation, partial fills, retries, persistent idempotency and broker restart recovery remain work for the execution EA. Do not deploy this probe as a trading bot.

API references: [CopyRates](https://www.mql5.com/en/docs/series/copyrates), [OrderCalcProfit](https://www.mql5.com/en/docs/trading/ordercalcprofit), [MT5 testing](https://www.mql5.com/en/docs/runtime/testing).
