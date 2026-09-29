# Pure B1 target test plan

1. Add synthetic M15 tests for Donchian exclusion, RSI and EMA gates, ATR/levels, invalid UTC data, and causal prefix invariance.
2. Implement pure target detection in `scripts/strategy.py` while retaining legacy class under its existing name.
3. Add new target replay caller using saved baseline/ticks and existing `Replay` execution engine. Verify output provenance and results.
4. Review target metrics against archived +342% before connecting runner to order execution.

## 2026-09-29 Pure B1 Shadow test plan

1. Test closed-M15 conversion rejects RangeIndex/duplicate/stale data and matches reference indicator signal on deterministic bars.
2. Test pure decision through public seam for fixed 0.01/10% cost cap, quote age, single position/pending, day-start 40%, missing policy and tick rounding.
3. Test injected fake MT5 cycle to JSONL, restart/dedupe behavior, account mismatch, and zero order/notification calls.
4. Test bounded M15/tick capture manifest/hash and comparison to reference; run focused files, then full suite once.
