# Debug ledger — expansion breakout and rejected-order alerts

Scope: resolve the three Python findings from the September 13 review. Preserve Pine work and unrelated dirty files. All experiments offline; fake market/broker/news/Telegram boundaries, real detector/orchestrator/execution adapter where relevant. No live trading loop with external services.

## Ranked hypotheses and disproofs

1. Global breakout gate suppresses an unrelated valid sweep. Disproof: hold OHLC, session, bias and risk constant; move only PDL. If both return the same result, this explanation fails.
2. Rejection alert comes from missing result handling in the caller. Disproof: keep order intent identical and flip only broker retcode. If rejection already suppresses the alert and clears pending state, this explanation fails.
3. Session/bias/SL rejection explains the missing signal instead. Disproof: identical valid fixture with only the other liquidity reference moved; debugger reaching breakout `break` excludes earlier gates.
4. Existing regression independently protects body-close behavior. Disproof: delete body-close checks via temporary runtime mutation and run it; a passing test disproves adequate coverage.

## Experiments

| ID | Change / command | Observed result | Conclusion |
|---|---|---|---|
| E01 | Re-ran `python3 scripts/debug/reviews/reproduce_expansion_breakout_review.py` before edits | Original stale-sweep rejected; cross-level false negative reproduced; body mutation survives | Prior review reproduces on current workspace |
| E02 | `python3 -c 'import smc_main'` | Imports successfully | Offline live-loop test seam available |
| E03 | Added deterministic BUY/SELL cross-level and separate body/wick/boundary/fresh-sweep tests; ran detection module | 11 tests, two subtest failures, both cross-level | Desired preservation behavior fails; other controls pass |
| E04 | Added one-iteration loop tests with real orchestrator and adapter, fake broker retcodes | Accepted order passes; rejected order sends one alert, test fails | Broker failure demonstrably reaches notifier |
| E05 | `pdb` at detection line 176 with conditional breakpoint | Generator scope produced `NameError` for inspection variables | Probe placement invalid; no code conclusion from those prints |
| E06 | `pdb` at live loop notification branch, then stepped to send | `res.success=False`, pending present, intent `PLACE_LIMIT`; reached send with false result | Failure path confirmed at caller |
| E07 | Repositioned `pdb` to detection line 180 on isolated cross-level fixture | `i=18`, levels `[2010.0, 2020.0]`, close `2017.5`, sweep unset; returned `None` | Global break, not risk/session gate, owns failure |

Production fixes remain pending until differential disproof checks are recorded below.

| E08 | Kept OHLC/session/bias/risk fixed; bypassed breakout only for unrelated PDL 2020 using runtime patch | Exact baseline signal restored | Hypothesis 1 survives disproof; hypothesis 3 rejected |
| E09 | Flipped only fake broker accepted/rejected retcode through real loop/orchestrator/adapter | Both produced one alert and retained pending state | Hypothesis 2 survives disproof; downstream does not reconcile rejection |
| E10 | Removed body checks temporarily; ran new separated BUY/SELL body/wick cases | Exactly two body subtests failed; no errors | New checks kill mutation that escaped original test |

E01–E10 agree: invalidate only the affected liquidity reference; handle failed placement before chart/notification and remove its local pending state. Production patch now justified. No persistent lifecycle abstraction or dependency needed.

| E11 | Applied per-level scan pruning and execution-failure handling; ran `python3 -m unittest discover -s tests` | 58/58 passed | Cross-level preservation and rejection notification/state regressions fixed; original stale-sweep rejection preserved |

Full suite also emitted SQLite `ResourceWarning` messages from existing tests with unclosed connections. New loop tests use in-memory SQLite and register connection cleanup. Warnings do not certify runtime resource handling; unrelated cleanup was not included.

| E12 | Updated standalone reproduction to compare frozen a551b62 with working tree; added new-test mutation check; executed it | Original stale sweep still rejected; cross-level restored; new tests kill body mutation | All original and new breadcrumbs consistent after patch |
| E13 | Reviewed final production/test diff; ran `git diff --check` | No whitespace errors; two production files changed | No unrelated runtime changes needed |

Scoped findings resolved. Remaining limits: live broker/Pine validation, broader lifecycle reconciliation and simulation labeling, existing SQLite test cleanup warnings. See updated review for exact boundaries.

## Refactor / readiness continuation

| ID | Experiment | Outcome / interpretation |
|---|---|---|
| R01 | Froze post-debug sources; started full runner under cProfile | Baseline source retained in `.scratch/python-readiness/baseline`; first attempt to read profile was too early (FileNotFoundError), later completed normally |
| R02 | Inspected data/runtime and completed profile | GC=F M15, 4,432 rows; no local MT5 module. 23.307 s profiled total, 21.025 s detector; repeated pandas row construction dominates |
| R03 | Added worker-thread/cancellation controls before async edits | Two new tests failed: synchronous news/chart on loop thread; cancellation swallowed |
| R04 | Nearest-swing lookup, news/chart offload, cancellation propagation, SQLite cleanup | 60 tests passed; no new broker concurrency |
| R05 | Ran initial repeated comparison and after-profile | Outputs equal; exploratory benchmark overlapped profiler, so timings not accepted as final |
| R06 | Executed legacy accounting/causality counterexample script | Four defects reproduced: volume/PnL mismatch, TP-before-SL ledger, omitted fill-bar stop, current-hour H1 input |
| R07 | Read screenshot and official platform docs | Screenshot is Demo Pro. Desktop MT5 fits existing Python integration; browser is manual cross-check |
| R08 | Ran new read-only collector locally | Exit 2 / METATRADER5_UNAVAILABLE; no account or history read; no trading call |
| R09 | Collector export/loader round-trip test before loader edit | 23 rows loaded instead of 24 because Yahoo header reader consumed broker row |
| R10 | Added plain CSV header branch and clarified M15 proxy labels | 62 tests passed; 24 rows retained with aware UTC |
| R11 | Re-ran benchmark without concurrent profiler | v1 2.814 -> 0.983 s; v2 5.024 -> 1.208 s, medians of three. All 8,757 detector outputs per paired profile pass, ledgers and summaries equal |
| R12 | Sanitized settings inspection | Direct PyYAML import unavailable; existing loader fallback worked. Local config is v0, SMC risk config not established; credentials absent in local config |
| R13 | Memory sample and dependency inventory | Python heap peak essentially unchanged (~1.57 MB sample). PyYAML, python-telegram-bot, MetaTrader5 absent; tests alone do not certify deployed dependencies |
| R14 | Final tests, original breakout reproducer, new backtest blocker reproducer, diff check | 62 passed; breakout fixes preserved; four legacy blockers still reproduced; whitespace check passed |

Final readiness report: `docs/reviews/2026-09-13-python-live-readiness.md`. Refactor verified; financial engine correctness and broker/runtime evidence still block live-money readiness. No secret from the user was written to artifacts.

## Demo continuation (supersedes R14 financial-defect status)

| ID | Experiment | Outcome / interpretation |
|---|---|---|
| D01 | Opened authenticated Demo in Chrome; selected XAUUSD M5 table | Balance/equity USD 2,254.16; OHLC visible; no orders placed |
| D02 | Inspected chart/script/export surfaces | Table virtualized, Indie editor, content export unsupported; complete history not obtained |
| D03 | Re-ran four counterexamples before edits | All four reproduced again |
| D04 | Recorded actual orchestrator lifecycle in offline subclass; volume-based cash; closed-H1 and confirmed-fractal inputs | 67 tests passed, four counterexamples now regression checks; diff check passed |
| D05 | Re-ran existing GC=F proxy runner | v2 4 trades, -USD 34.35, PF 0.53; not Exness/account results |

See `2026-09-13-exness-demo-backtest-status.md` for broker-data blocker, export range, remaining financial defects, and strategy parity limits.
