# Pure B1 Exness broker-bar parity — 2026-09-29

**Status:** Read-only research evidence. No Demo order, broker fill, Telegram alert or real-money authorization.

## Exact data and commands

- Target terminal: configured Exness Standard Demo, USD, symbol `XAUUSDm`; account login is omitted from this report. `scripts/pure_b1/capture.py` verifies login/server/trade mode and writes account fingerprint.
- One-hour Bid/Ask tick window: **2026-09-29 12:00–13:00 UTC**, 11,969 ticks. MT5 rate request also included 30 days of indicator warmup: 29,679 Bid M1 rows, 1,982 direct M15 bars, and 1,955 canonical M15 bars reconstructed from M1 intervals with all 15 minutes present.
- Immutable local artifact: `data/b1_pure_broker_capture_v2_2026_09_29_1200_1300/`, manifest SHA-256 `74fb25f88d86e852411daca86e2f783baa7a7db5849cfe1351e27ccf4ce3be0e`. This `data/b1_*/` directory is gitignored; preserve it locally or export separately before deleting workspace.
- Capture command under configured Wine environment: set `PURE_B1_CAPTURE_START_UTC`, `PURE_B1_CAPTURE_END_UTC`, `PURE_B1_FREEZE_AT_UTC`, `PURE_B1_CAPTURE_OUTPUT`, then run `.venv/bin/python scripts/ops/run_b1_d_wine.py --script scripts/ops/mt5_wine_pure_b1_shadow.py`. Comparison: `.venv/bin/python -m scripts.ops.pure_b1_compare_capture --capture data/b1_pure_broker_capture_v2_2026_09_29_1200_1300 --output <new-report-path>`.
- `freeze_at` in this bounded capture labels the capture window only. It is **not** a preregistered strategy freeze, and this tape does not qualify the strategy under ADR-0030.

## Finding

The saved replay's `reference_bars.csv` was constructed by `scripts/research/data.py:bars`, which **drops M15 intervals lacking 15 Bid M1 bars**. Direct `MetaTrader5.copy_rates_range(TIMEFRAME_M15)` includes some partial rollover intervals. In the shared 30-day comparison, direct M15 had **26 additional bars** inside the common reference window; all 1,812 shared OHLC rows matched exactly. Feeding direct M15 to `pure_b1_bars` changes RSI, EMA and ATR history even when shared candles match.

The implemented Shadow adapter now reconstructs M15 from broker M1 using the archived 15/15 rule. New capture parity:

| Comparison | Result |
| --- | --- |
| Canonical M15 vs Bid ticks, complete capture hour | 4 shared bars, 0 OHLC mismatches |
| Canonical M15 vs saved Exness reference | 1,812 shared bars, 0 missing bars, 0 OHLC mismatches |
| Target signal/indicator on shared bars after 500-bar warmup exclusion | 1,312 comparable bars, 0 direction mismatches; maximum RSI 0, EMA50 1.22e-7, ATR 0 (tolerance 1e-6) |
| Direct terminal M15 vs canonical M15 | **FAIL:** 26 extra direct M15 bars in shared window |

One read-only Shadow cycle on the same Demo terminal logged `bar_open_utc=2026-09-29T13:30:00+00:00`, `direction=0`, `reason=no_signal`, `order_api_called=false`. It started after UTC midnight, so `day_start_equity` is unknown and any future admission must fail closed until a valid day-start snapshot exists.

Subsequent review tightened Shadow admission: a day-start snapshot is accepted only in the first UTC second, later balance changes and foreign positions block signals, and broker trade mode plus stop/freeze distances are checked. JSONL now includes canonical bar hash, strategy contract hash, indicators and broker specification. Existing one-cycle log predates these changes; it is **not** evidence of those guards running against MT5. Cost policy remains operator-attested, including account-specific evidence hash and round-trip commission unit; neither account type nor swap-free entitlement can be independently established by `account_info`.

Post-review read-only cycle on the same Demo terminal used a new log `data/pure_b1_shadow_post_review.jsonl`: same closed 13:30 UTC bar, `direction=0`, `reason=no_signal`, `day_start_status=day_start_unknown`, `order_api_called=false`. JSONL contains canonical bar/contract hashes, indicator values and broker specs. Since signal was absent, this cycle did not exercise broker admission against a live quote; fake-MT5 tests cover that path.

The target tick replay was rerun into a new local output directory `data/b1_pure_target_replay_recheck_2026_09_29/`. Its `results.json` is byte-identical to the prior result: spread-only **-33.51% / 4 trades**, and hypothetical 0.10R fee plus current-spec swap **+150.31% / 49 trades**. This reproducibility does not fill the missing historical execution-cost evidence.

## Limits

Comparison covers one hour of fresh ticks and the 30-day broker-rate overlap, not the full six-month replay period. Indicator/direction parity does not establish per-bar SL/TP or 10% admission parity because historical account equity, quote timing and verified cost snapshots are missing. Fixed 500-bar exclusion is an observed comparison window, not proof of general warmup sufficiency. No Pure B1 fill, commission ledger, swap ledger, slippage or historical swap-free entitlement was observed. The 10%/40% guards are covered by fake MT5 tests; this single flat Shadow bar does not demonstrate broker order readiness. Pure B1 remains research-only; Demo automation and real-money remain NO-GO.
