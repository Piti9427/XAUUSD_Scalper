# Trial30 Demo implementation and review

Owner-selected `RESEARCH-D48-SELL-BE1R-20261001-T030` now runs through an isolated MT5 Demo execution path on existing Wine. Fixed SELL0.01, D48, ATR14 SMA, SL2.5ATR/TP3ATR, cost-inclusive10% admission, UTC daily20% and first-post-close-quote BE1R remain pinned. No recovery. This authorizes research Demo testing; frozen D30 qualification and real-money readiness remain separate.

Review base: `develop` (`a24114097988e4b3669d48d6be19773c502c3924`). Implementation scope starts at `4b463194217847d3585c213be11b1a362f57b8e6`; pre-existing branch changes are distinguished from this patch. Implementation commit `946068d`; protective-quote/BE fix `979dc2c`.

## Verified runtime

Read-only Wine identity at 2026-10-01T05:00:31Z confirmed requested Demo identity, USD hedging, balance/equity200, enabled trading permissions and no positions/orders. Actual execution watcher was verified at 06:45 UTC: `execute=true`, heartbeat age0.77s, process41905 alive, completed06:45 bar `WAIT/no_sell_signal`, no active claim, no safety halt, no broker events. Journal baseline200 reconstructed from reconciled history. No synthetic order was submitted.

Watcher uses ignored local credentials, cost policy, journal and logs. Managed terminal session owns process; PID is operational and may change after restart. Operations and stop/restart semantics: [runbook](../ops/trial30-demo.md). Cost policy expires24h after review; stale policy blocks new admission while existing position protection remains active. Published zero commission and declared slippage allowance are assumptions pending actual deal evidence; overnight swap is reconciled, not modeled in admission.

## Validation

| Check | Observed result |
| --- | --- |
| Full repository unittest suite | 738 tests, 736 passed, 2 skipped; 10.062s |
| Public runner and CLI tests | 31 passed |
| Mypy scoped implementation | 9 files, success |
| Ruff repository lint | Passed |
| Scoped formatting | 13 files passed |
| Compile, dependency consistency, diff whitespace | Passed |
| Research detector parity | 12,100 bars, zero direction/ATR mismatches |
| Original mismatch repro using dedicated detector | PASS; legacy detector remains separate |

Full suite output: local `/tmp/trial30-full-suite-20261001.log`. Global format check still fails11 files already failing at starting HEAD: existing Pure B1 cost/parity/shadow, research replay/search and related test files. Preserved unrelated and hashed source artifacts; no format churn.

Public seams cover actual cycle request math, broker-approved fill notifications, restart/BE/close reconciliation, risk/daily/cost/margin/exposure gates, timeout UNKNOWN without retry, partial and invalid fills, safety close only owned ticket, durable outbox and one local writer. CLI tests cover explicit execution gate, pinned configuration and rejection of real accounts.

## Standards review

Initial review: one major finding, protective quote could become stale during broker check. Fixed by elapsed submission clock and refreshed quote/identity/position plus geometry before protection send. Regression `test_be_rechecks_quote_age_after_slow_broker_check` passed. Final Standards re-review: zero unresolved scoped findings; reviewer ran27 runner tests successfully.

## Spec review

Initial review: two major findings, BE activation used later quote instead of first post-close quote, and protective submission lacked fresh post-check quote/geometry. Fixed with persisted first activation quote and refreshed submission guards. Regressions `test_be_restart_uses_first_post_close_quote_not_later_profitable_quote`, `test_be_rechecks_geometry_after_broker_check_price_change` and slow-check regression passed. Final Spec re-review: zero unresolved scoped findings; reviewer ran5 focused regressions successfully.

## Remaining evidence

Live broker fill, BE modification, close and restart parity await genuine forward SELL signals. Unit tests and connected watcher establish implementation/readiness for this Demo experiment, not those unobserved broker outcomes or profitability. Inspect journal broker events and MT5 deal history as signals arrive; never reset journal/baseline to bypass a block.
