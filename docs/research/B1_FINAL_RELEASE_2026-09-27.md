# B1-FINAL release package — 2026-09-27

**PRD:** [Finalize B1 for Standard Demo](../specs/b1-final-standard-demo-prd.md) · **Plan:** [implementation plan](../plans/b1-final-standard-demo.md) · **Runbook:** [B1-FINAL runbook](../ops/B1_FINAL_RUNBOOK.md)

## Verdicts (separate by design)

| Area | Verdict |
|---|---|
| Implementation | `IMPLEMENTATION_VERIFIED` (Strategy Tester scope) |
| Target account (Standard Demo, actual equity) | `ACCOUNT_BLOCKED` |
| Hypothetical $100 | `ACCOUNT_BLOCKED` |
| Strategy | `STRATEGY_NO_GO` |
| Exit selection | `FIXED_EXIT_FROZEN_BE_DISABLED` — frozen release is `B1-FINAL-v1` (`ExitMode=0`) |
| Deployment / Demo orders / real money | `NO_GO` — not authorized, not enabled |

Why these verdicts:

- **Account blocked:** the configured Demo connects, is Demo, is in hedging mode and has `XAUUSDm`. But at 1% risk of $1,173.46 the budget is $11.73, and the cheapest 0.01-lot stop over the whole window cost $12.16 (median $20.98). The EA rejected all 558 signals with `RISK_BELOW_MINIMUM_LOT` and never rounded a lot up.
- **Strategy no-go:** there were no executable trades on the target account. On a separately labelled $10,000 research-capital fixture, the fixed-exit baseline stays profitable only with no extra cost reserve. With the 0.10R reserve, profit factor is 0.968 and return is −2.54%; with 0.20R, return is −11.96%.
- **Exit not promoted:** cost-covering stop after +2R (v1.1) fails the required 0.10R and 0.20R gates (profit factor ≤1 at both). Real costs are also unmeasured, so this exit cannot be promoted in any case.

## Delivered components

| Component | Path |
|---|---|
| Deterministic indicator core (unchanged, frozen) | `mql5/B1FinalCore.mqh` |
| Incremental indicators, checkpoint, integrity-checked state, atomic store | `mql5/B1FinalState.mqh` |
| Execution engine behind broker / sink / store interfaces | `mql5/B1FinalEngine.mqh` |
| MT5 adapter + EA (Tester-only order mode) | `mql5/B1FinalEA.mq5` |
| Fault-injection tests of the engine (fake broker, runs in Tester) | `mql5/B1FinalEngineTests.mq5` |
| Tester wrapper for the frozen parity probe (probe source unchanged) | `mql5/B1FinalParityRunner.mq5` |
| Read-only preflight probe + pure evaluator | `scripts/ops/b1_final_preflight_probe.py`, `scripts/ops/b1_final_preflight.py` |
| Durable outbox consumer (dry-run sink only) | `scripts/b1_outbox.py` |
| Wine compile / Strategy Tester runner | `scripts/ops/mt5_wine_tester.py` |
| Release evidence, parity, reconciliation, exit gates | `scripts/research/b1_final_release.py` |

Execution path: completed UTC M15 bar → incremental B1 detector → pending signal (valid only in the next M15 interval) → gates (trusted state, incident, 12% latch, unresolved request or remainder, owned/foreign exposure, owner lock, spec, risk tier) → broker profit/margin sizing with floored volume and fee reserve → stop geometry → `OrderCheck` → **request identity persisted** → market order with original quote-anchored SL/TP → broker reconciliation → fill risk check → optional one-shot +2R stop → broker-confirmed close → outbox event.

## Evidence (executed and observed)

| Check | Result |
|---|---|
| Full unit suite `python3 -m unittest discover -s tests` | 574 tests PASS |
| New Python tests (preflight 15, release 10, outbox 8, runner 5) | PASS |
| MetaEditor compile (EA, engine tests, parity runner) | 0 errors / 0 warnings |
| Engine fault-injection tests in MT5 Tester | 106 / 106 PASS |
| Executed MQL5 indicator parity (frozen probe in Tester, 9,199 hashed bars) | ATR / RSI / HH30 / LL30 / direction: 0 mismatches at 1e-8 |
| Incremental vs batch, checkpoint-resume vs uninterrupted (9,199 bars) | Exact equality. A rolling 120-bar reseed is **not** equivalent (test asserts the difference). |
| MT5 risk-tier boundary export | Identical to Python tiers at 2.9999 / 3 / … / 12% |
| Read-only Demo preflight | `VERIFIED`: identity match, Demo, hedging, `XAUUSDm`, no exposure; `order_api_called=false`. UTC offset `UNVERIFIED_NO_FRESH_TICK`: the snapshot was taken on a weekend with a stale tick. |
| Real-tick Tester runs (May 14 → Sep 26, 30,483,724 ticks) | 7 runs on the final sources; signal parity on the EA-consumed bars 560 / 560 in every run (counted from the Tester start, not from the EA's first signal); every deal ledger reconciles to the cent with the event ledger and final equity; 0 outbox write failures; verdicts computed by `b1_final_release.py` |
| Determinism | Reruns of the fixed-exit runs produced byte-identical events and deal ledgers; the post-review rerun reproduced every metric |
| Outbox on real EA events (cost-BE run) | 354 confirmed events → 354 cards, 0 private fields leaked, replay → 0 cards |

### Real-tick Strategy Tester runs

Every run uses: `Every tick based on real ticks`, `XAUUSDm` M15, leverage 1:1000, seed anchor 2026-05-07 00:00 UTC, scoring May 14 → Sep 26. MT5 reports that real ticks were missing for 1,258 of 132,739 minute bars (one whole day, Sep 25), and generated ticks filled those minutes. The Tester accepts only whole-dollar deposits, so the actual-equity run used $1,173.00, not $1,173.46; this is conservative for sizing.

| Run | Deposit | Label | Trades | Net R | Return | Tick-equity DD |
|---|---:|---|---:|---:|---:|---:|
| `actual_equity_fixed` | 1,173 | account evidence | 0 | 0 | 0% | 0% |
| `hypothetical_100_fixed` | 100 | hypothetical | 0 | 0 | 0% | 0% |
| `research_10000_fixed` | 10,000 | research-capital fixture | 128 | +18.62 | +6.89% | 9.19% |
| `research_10000_entry_be` | 10,000 | control arm | 149 | +27.24 | +9.70% | 8.10% |
| `research_10000_cost_be` | 10,000 | v1.1 candidate | 149 | +27.33 | +8.24% | 8.49% |
| `stress_10000_*_delay2s` | 10,000 | 2 s modify delay | same as unstressed | | | |

The research-capital fixture exercises the real broker-adapter path (fills, SL/TP, modifications, closes). It does not qualify the target account, and it is not an untouched out-of-sample period, because this history was already examined in earlier research.

### Exit selection (baseline = fixed exit, $10,000 fixture)

| Scenario | Fixed: net R / PF / return | Cost-BE: net R / PF / return | Gate |
|---|---|---|---|
| 0.00R | 18.62 / 1.095 / +6.89% | 27.33 / 1.117 / +8.24% | pass (informational) |
| **0.10R (required)** | 5.82 / 0.968 / −2.54% | 12.43 / 0.969 / −2.46% | **fail**: PF ≤ 1 |
| **0.20R (required)** | −6.98 / 0.862 / −11.96% | −2.47 / 0.849 / −13.16% | **fail**: return, expectancy, PF, blocks |
| 0.10R + $0.10/oz adverse fill | 4.62 / 0.957 / −3.43% | 11.04 / 0.956 / −3.46% | fail |
| 0.20R + $0.10/oz adverse fill | −8.18 / 0.853 / −12.85% | −3.86 / 0.839 / −14.17% | fail |

Chronological blocks (boundary equity including floating PnL, 0.00R) for fixed / cost-BE:

- May 14–Jun: +5.68% / +3.74%
- Jul–Aug: +4.40% / +5.93%
- Sep 1–25: −3.13% / −1.50%

Trade-level attribution on the 109 trades that both arms share:

- Cost-BE saved 13 losers, worth +$998.68.
- It displaced 9 winners, worth −$1,200.52.
- 40 entries happened only in the BE arm and 19 only in the baseline, because the earlier exits changed which later signals could be taken.

The BE arm's higher raw net R therefore comes from the changed later entries, not from better handling of the same trades.

The stress scenarios ran only in part:

- **2-second modification delay:** ran in the Tester. Results were identical because no trade came back to the new stop within 2–3 seconds.
- **$0.10/oz adverse fill:** applied afterwards as a fixed cost per trade; the exit paths were not re-simulated.
- **Spread ×2:** not run. The MT5 real-tick Tester cannot widen recorded spreads.
- **Commission and swap:** the cost-BE arm assumed $0 commission, a labelled test scenario. Real costs remain an open qualification gate.

## Review fixes before freeze

A two-axis review (standards and spec) found defects. Each was fixed and has a regression test in `B1FinalEngineTests.mq5`, `tests/test_b1_final_preflight.py` or `tests/test_b1_final_release.py`:

- **Offline fills:** a fill that had already closed while the EA was not watching was reported with the requested price and volume. It now uses the broker's entry-deal price, volume and SL/TP.
- **Fill matching:** fills were matched only by order comment. The order ticket from the send is now persisted and also used, for both open positions and history.
- **Partial-fill remainder:** the remainder was only blocked. It is now cancelled (never topped up), and it still blocks new risk until it is gone.
- **Volume growth:** position volume that grows after adoption is now detected and re-verified against the budget.
- **Stop modification:** the broker's current stop is read back after every modification response. A rejected retcode with the stop already in place (for example `NO_CHANGES`) counts as confirmed. The freeze-level check now also covers the TP.
- **Persisted HWM:** the HWM is updated only after a successful write.
- **Fill risk:** the check uses the larger of the configured and the broker-reported entry commission.
- **Outbox:** the JSON number check is now strict, and the file is opened with `FILE_SHARE_READ`. Write failures are counted in `RUN_SUMMARY` and written to the journal.
- **Owner lock:** it now covers account, symbol and magic, whatever the version, because versions sharing a magic would otherwise manage each other's positions.
- **Timing and history:** the EA refuses a UTC offset that is not a multiple of 15 minutes, and outside the Tester it checks the server-minus-GMT offset. A history fetch failure after startup is retried instead of blocking permanently.
- **Preflight:** it now sizes exactly like the EA, including the fee reserve and admission reserve, and reports UTC-offset evidence.

## Known limitations and open gates

- **Scope note:** the $10,000 research-capital fixture was added so the real adapter and the three exits could be exercised on history. It is not the account's capital, it is not used for the account or strategy verdicts, and exit promotion would additionally need a qualifying account and measured costs.
- **UTC offset:** the broker's offset is configured (`BrokerUtcOffsetSec=0`, a fixed offset with no DST handling). The weekend preflight could not verify it, so a weekday preflight with a fresh tick must show `utc_offset_status=VERIFIED` before any Demo activation.

- Orders are Strategy Tester only in this release: `OnInit` fails outside the Tester, and on any account that is not Demo, before any order code is reachable. Enabling Demo orders requires a code change plus the separately authorized activation gates.
- Restart, timeout, partial-fill, duplicate-owner and corrupted-state behaviour is proven against the fake broker, using the same engine code. The MT5 adapter's history, cancel and read-back paths have only run in the Tester, where fills are synchronous, and must be re-verified on the broker before any Demo activation.
- The persisted HWM is saved with a +0.05% safety margin above the true peak. This avoids a disk write on every tick. After a restart the drawdown may read up to 0.05% too high, which is conservative and never raises risk.
- The research sensitivity reserves (0.10R / 0.20R) and the adverse-fill cost are applied after the run. Sizing and drawdown paths are not re-simulated with them.
- The reference-dataset bars (built from captured M1 data) and the broker M15 bars in the Tester differ on a few bars around session breaks. That is why parity is judged on the exact bars the EA consumed; on the capture dataset the signals differ at 13 missing and 18 extra timestamps.
- MT5 under Wine sometimes stays open after a finished test. The runner force-closes it 60 seconds after the Tester logs `thread finished`, and records this in `terminal_force_closed_after_finish`. None of the final seven runs needed it.
- Deployment qualification is still outstanding: independently measured costs, at least 100 closed out-of-sample trades after the freeze, broker-ledger Monte Carlo with at least 50,000 paths, and Demo forward evidence of at least 8 weeks and at least 50 closed trades.

## Frozen hashes (SHA-256)

Base commit before this work: `e38432a5508b19a349c7544f52bc1f8b686d4e90`.

| Artifact | SHA-256 |
|---|---|
| `config/B1-FINAL-v1.yaml` | `88c61fe344ffa0cb440fdce16f6a60a4dc5f81e0f328cba6b7d577e362d8b66e` |
| `mql5/B1FinalCore.mqh` | `da9f14347748d6da06220fd71bb598b501cfcd3eaf702f77fd7e5c9a125a6688` |
| `mql5/B1FinalState.mqh` | `32175fdac6e2b23e5d8ccde4acec2b936836730719d3aa6b81110fd948e3e471` |
| `mql5/B1FinalEngine.mqh` | `bbd841483f2c2d4ccd73c73fa8b426cee84f6909e69baa6662a7389dbad04d85` |
| `mql5/B1FinalEA.mq5` | `d0c8de7f838a5ecd7fbfd2a122dc78da03bfefcd2c584ce6c6771d3be5df8e52` |
| `mql5/B1FinalEngineTests.mq5` | `50e28f9215d1feb8c2585ee46e7a56ad451a10b7a4e85aa59f0a645232d36ed3` |
| `mql5/B1FinalValidationEA.mq5` (frozen probe) | `8ba1a90438f41c9dbc415184a59809990151945a6cc644b09c61db5aa06ffb28` |
| Release binary, tested in `actual_equity_fixed` (local, git-ignored) | `cd35dff3c22318f525b2719ef6e286451f4fd80d7241a1821e93a5ad22d9cb81` |
| EA-consumed M15 bars (all runs identical) | `9c61834bdb0075177dfba234cd1c3e9dfdb157550e56be9e3d62bd0afdbcc083` |
| Parity input (reference dataset) | `e2e9558dcd8dc3b7534d3cb5ba619145559fab6361cf639f407c6933fe206860` |
| `release_evidence.json` | `92c0715b11935e4ba7665072191f438b40d0255fea9d1e362e415643e30470c4` |
| `preflight_report.json` | `c65ea6455d4e6a81f098244394247b3e06fe67b52caa52b9b613586d8e4dd5e8` |
| `B1_engine_tests.csv` | `9450d3143d57cf08e69b47277bbb4ea826d1465288de81d42ffad6495f4dce73` |

MetaEditor builds are not byte-reproducible, so each run archives the exact binary it tested next to its outputs. Local evidence lives under `data/b1_final_release/` (git-ignored): the preflight snapshot and report, the parity run and result, the engine test run, the seven Tester runs (events, deal ledger, consumed bars, HTML report, agent journal, run manifest, binary) and `release_evidence.json`. Shared artifacts contain no login, password or server name. Private parameters are redacted in manifests and journals.

## Reproduce

```sh
# read-only preflight (terminal logs in with the ignored .env; no order API)
python3 scripts/ops/run_b1_d_wine.py --script scripts/ops/b1_final_preflight_probe.py --output data/b1_final_release/preflight_snapshot.json
.venv/bin/python -m scripts.ops.b1_final_preflight --snapshot data/b1_final_release/preflight_snapshot.json --output <new>.json

# Tester runs require the terminal to be closed first
python3 -m scripts.ops.mt5_wine_tester run B1FinalEA --sources B1FinalCore.mqh B1FinalState.mqh B1FinalEngine.mqh B1FinalEA.mq5 \
  --output data/b1_final_release/tester/<name> --model real_ticks --start 2026.05.14 --end 2026.09.26 --deposit 1173.46 \
  --param ExpectedLogin=env:XAUUSD_MT5_LOGIN --param ExpectedServer=env:XAUUSD_MT5_SERVER --param BootstrapState=true \
  "--param=SeedAnchor=2026.05.07 00:00" --param ExitMode=0

.venv/bin/python -m scripts.research.b1_final_release --run <dir> ... --compare research_10000_fixed:research_10000_cost_be \
  --account-run actual_equity_fixed --preflight data/b1_final_release/preflight_report.json \
  --engine-tests data/b1_final_release/engine_tests_tester_run/B1_engine_tests.csv --output <new>.json
```
