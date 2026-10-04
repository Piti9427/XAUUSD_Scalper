# Pure B1 Shadow test status — 2026-09-29

Scope: canonical broker M1 to M15 adapter, pure decision/risk gate, read-only MT5 Shadow JSONL, bounded capture, bar/signal parity.

| Requirement | Evidence |
| --- | --- |
| Complete 15/15 UTC M1 bar adapter | `tests/test_pure_b1_broker_data.py` |
| Fixed 0.01 lot, 10% cap, quote/day/exposure rejection, broker trade mode and stop distance | `tests/test_pure_b1_decision.py` |
| Read-only Shadow, one record per bar, balance/foreign exposure rejection, zero order API | `tests/test_pure_b1_shadow.py` |
| Target Demo identity before bars and after ticks; immutable manifest | `tests/test_pure_b1_capture.py` |
| OHLC and signal mismatch detection | `tests/test_pure_b1_parity.py` |
| Full suite | `make test`: 641 tests, OK, 2 skipped |
| Static and dependency checks | `ruff check`, `ruff format --check`, `compileall`, `pip check`: passed |

Review found remaining evidence gaps: per-bar SL/TP/risk parity lacks historical account/cost snapshots; one-hour ticks cannot qualify six-month strategy; no measured fills, slippage or historical swap entitlement. `main.py` and EA remain outside Pure B1 Shadow path. Demo and real-money execution remain NO-GO.

## 2026-10-04 Reward156 paired tuning

Inline test pipeline plus independent Standards/Spec code-review. Initial provenance/repeat gaps fixed and reviewed again. Nine new seam tests passed; full suite819 tests,2skips,OK. Changed Python lint passed; syntax compilation passed (no configured static typechecker). Existing test metadata preserved and current research/plan appended. Complete-result matrix repeats remain independent acceptance evidence, recorded by research harness.
