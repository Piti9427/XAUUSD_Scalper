# Six-month XAUUSDm Hybrid reconstruction on requested Exness Demo

**Verdict: 20% HWM halt after two baskets; no recovery leg opened.** On this six-month historical window, the declared $200 fixed-lot B1_TP25 basket policy did not reproduce +275.2%. Research result is **-$37.53 (-18.77%)** under the previously used cost scenario; observed-spread-only result is **-$33.87 (-16.93%)**. This is a separate, idealized Python tick replay. It is not a claim that the current bot executed these orders or that Demo broker would approve every modeled fill.

## Frozen environment and window

- Requested account was verified through `.env` at MT5 initialization: Exness Demo, USD equity/balance **$200**, leverage **1:1000**, hedging margin mode. No credentials are copied to artifacts. `order_send` was never called.
- Symbol **XAUUSDm**. Current broker snapshot: contract size 100 oz/lot, minimum/step 0.01 lot, tick size 0.001, current long swap -567.4 points and short swap 0.
- Window **2026-03-28 00:00 UTC to 2026-09-28 00:00 UTC**, end exclusive. Captured March 21 onward for signal warmup. Fresh capture: **45,671,201 real Bid/Ask ticks**; scoring: **40,267,449 ticks**. Last scoring ticks are on September 27 UTC.
- Signal input is completed M15 Bid bars. B1_TP25 means Donchian 30 breakout with RSI14 filter, SL 2.5 ATR14, individual TP 2.5R. Market entry at first recorded Ask (BUY) or Bid (SELL) after bar completion. The existing `BasketManager` emits pending limit intents rather than these market entries, so this is a declared reconstruction rather than runtime parity.
- Fixed initial lot **0.01**; recovery lot **0.02**, maximum two legs. Recovery requires an adverse open basket and new same-direction signal. Two explicit recovery hypotheses were replayed: legacy M15 MSS as the current BasketManager call path suggests, and a new B1 signal as the matched-strategy alternative. Native M5 SMC/MSS parity is not claimed.
- Basket budget freezes at min(15% entry equity, $30). Individual broker-like SL/TP, combined basket stop, and after-recovery strictly-positive combined TP are evaluated in chronological tick order. Single legs keep 2.5R TP. Daily new-basket limit: 15% of UTC day-start equity and two baskets per UTC day. Floating equity HWM 20% closes and permanently halts. Estimated margin admission uses notional / 1,000; broker order approval/stop-out remain unverified.
- Two cost columns: actual observed Bid/Ask spread only; or observed spread plus a **hypothetical 0.10R fee** and current-spec swap with UTC midnight rollover. Historical commission, slippage, and actual swap ledger are unavailable. The second column reproduces prior cost assumptions; neither column is certified historical net profit.

## Results

| Recovery trigger | Cost column | Final balance | Return | Baskets / legs / recoveries | Win rate | Tick-equity DD | Final status |
|---|---|---:|---:|---:|---:|---:|---|
| MSS | Spread only | $166.13 | -16.93% | 2 / 2 / 0 | 0% | 20.006% | HWM halted |
| MSS | Spread + scenario | $162.47 | -18.77% | 2 / 2 / 0 | 0% | 20.044% | HWM halted |
| B1 | Spread only | $166.13 | -16.93% | 2 / 2 / 0 | 0% | 20.006% | HWM halted |
| B1 | Spread + scenario | $162.47 | -18.77% | 2 / 2 / 0 | 0% | 20.044% | HWM halted |

Under the scenario-cost MSS run, first short entered **March 30, 00:15:00 UTC**, budget $30, and closed at **00:20:55** after the combined mark crossed the cap. Loss **$30.0319** includes the scenario fee; price crossing can overshoot a stop. Day-loss guard blocked further entries that day. Second long entered **March 31, 01:30 UTC** with frozen budget **$25.4952** and was closed at **02:41:03** by the 20% HWM latch, losing **$7.4985**. No third basket was admitted for the rest of the window. The HWM percentage is measured from observed peak equity, so final balance can be down 18.77% from initial $200 while peak-to-trough tick DD is 20.044%.

Both recovery triggers tie because neither emitted an eligible same-direction signal before the two basket exits. The result **does not rank MSS against B1 recovery in a functioning two-leg sample**. No +275.2% conclusion is supported. The older +275.2% Matrix comes from clipping completed Pure trade losses after the fact; its source is inspected in `B1_MATRIX_DEMO_READINESS_2026-09-28.md`.

## Data-integrity correction during this run

An independent week-versus-day MT5 query comparison exposed a boundary issue in the old capture helper: asking each day through `23:59:59.999` lost ticks in the day's final second because the Python MT5 API interpreted the datetime at second precision. The first week lacked 21 ticks in daily files. The helper now queries through next UTC midnight and filters returned `time_msc` to `[day, next day)`.

The complete six-month capture and all results above were regenerated **after** that fix. All 191 daily files passed their SHA-256 manifests. Their counts equal independent weekly broker queries in 26 complete weeks. The final partial week has four additional ticks in the daily capture's last second, consistent with the earlier weekly query ending at `2026-09-27 23:59:59.999`. Prices were not generated or interpolated. MetaTrader's [copy_ticks_range reference](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py) documents datetime range arguments and UTC handling; the specific final-second behavior was established with broker query comparison here.

## Validation and limits

- Three causal prefix checks passed for reference indicators. B1 and legacy MSS direction prefixes also matched recalculation at two cuts.
- Full tape chronology, finite Bid/Ask and non-crossed quotes checked. Baseline/capture hashes matched.
- Four basket/leg ledgers reconcile `200 + cumulative net = balance`. An independent existing one-position tick-cap runner produced the **same two trades, final balances and tick DD** when no recovery occurred.
- Five focused chronology/risk tests and 68 existing BasketManager/orchestrator/B1 tests passed: **73 total**.
- Current production code still has the readiness blockers from the Matrix audit: no proven runtime construction of `BasketManager`, untargeted close intents rejected by live adapter, optimistic close state before broker confirmation, and bar-level checks bypassed by `open_position`. Thus research replay does not qualify the bot for Demo order submission.
- Research entry assumes immediate market fill; runtime currently emits a limit intent. Historical broker commission, margin approval, stop-out, spread at an actual submitted execution and slippage are not certified. Live account behavior may differ materially.

## Artifacts and reproduction

- `data/b1_six_month_coverage_2026-09-28.json`: read-only seven-day MT5 history probes.
- `data/b1_hybrid_exness_6mo_fixed_2026_09_28/`: daily tick capture, hashes, M1 bars, account/symbol snapshot.
- `data/b1_hybrid_baseline_6mo_fixed_2026_09_28/`: hashed canonical tick tape and reference M15 bars.
- `data/b1_hybrid_replay_6mo_verified_2026_09_28/`: frozen contract with source, settings, baseline and capture hashes; four basket/leg ledgers, `results.json`, `validation.json` and completion marker. Final ledgers matched the independently checked run byte for byte.

```bash
.venv/bin/python -m scripts.research.b1_hybrid_six_month \
  --baseline data/b1_hybrid_baseline_6mo_fixed_2026_09_28 \
  --capture data/b1_hybrid_exness_6mo_fixed_2026_09_28 \
  --output data/b1_hybrid_replay_NEW
.venv/bin/python -m unittest tests.test_b1_hybrid_six_month tests.test_basket_manager \
  tests.test_smc_orchestrator tests.test_b1_final tests.test_b1_d_ticks tests.test_b1_d_comprehensive
```

**Decision for the requested Demo:** retain this as offline evidence. The observed policy halts before any recovery leg, and the live execution path is incomplete. Do not set `dry_run=false` or submit Demo orders based on this result.
