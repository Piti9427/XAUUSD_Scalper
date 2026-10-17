# C22 frequency tuning — research QUALIFIED

Selected `b823f4aefe10fc72`. Both base+swap and stress+swap pass every original
research gate: net>0 and >=same-input baseline, every-tick equity DD<=40%, mean
>=15 entries/full UTC month, positive equity/no bankruptcy, fixed lot/cap and
conservative terminal gate. COST_INCONCLUSIVE remains. No Demo replacement,
untouched validation, broker stop-out parity or future-return claim.

## Search and frozen scope

Continued after disk recovered,2 workers. Completed entire300-new-variant
campaign before selection,608 cells including baseline/3 replayed seeds,4 frozen
rounds (71/76/78/75 neighbors). Deduplicated against original300 configs.
Three qualifiers; stopped between campaigns as specified, not at first passing cell.
Prior failed attempt/source pins retained separately; no partial result reused
as a final cell. Original completed evidence remained hash-valid.

Input167622055 quoted Bid/Ask ticks,48465 completed UTC M15 bars,2024-09 onward.
Fresh current-month download/check from this campaign retained. Requested end
2026-10-06T17:22:04.296998+00:00, actual last quote
2026-10-05T23:59:59.969000+00:00. No gap filling. Equity, peak and indicators
continuous. Monthly frequency covers25 full UTC months through2026-09, including
warmup/zero months; October partial reported separately, not counted in mean.

## Selected behavior

Research snapshot: `config/research-c22-qualified-b823f4aefe10fc72.json`.
BUY archived RSI7cross25, EMA50+slope, SL1.5ATR, TP2 rounded R, BE1R.
SELL Donchian96, EMA50+slope, SL2.5ATR, TP2 rounded R, BE1R. SELL precedence,
ATR14, closed H4EMA200 both directions and canonical fill/rounding/BE unchanged.
Daily loss10%; losing-exit count unlimited (`max_daily_losses=0`), cooldown0,
all entry sessions, static initial admission risk10%, fixed0.01/single position.
USD200 once; no topups/recovery/martingale. Initial cap excludes future swap;
gaps/swap may exceed admitted loss, and BE may close net negative.

## Results

| Metric | Base+swap | Stress+swap |
|---|---:|---:|
| Selected net USD | 741.0958 | 499.1840 |
| Final balance USD | 941.0958 | 699.1840 |
| Baseline net USD | 297.4922 | 284.6542 |
| Net improvement USD | 443.6036 | 214.5298 |
| Max equity DD % | 29.6368 | 37.0976 |
| Mean entries/full UTC month | 16.12 | 16.04 |
| Trades including partial month | 404 | 402 |
| Win rate % | 34.1584 | 32.8358 |
| Profit factor | 1.2401 | 1.1620 |
| Minimum tick equity USD | 182.5448 | 181.9378 |
| Maximum admitted initial risk % | 9.7192 | 9.6821 |
| Mean admitted initial risk % | 2.4028 | 2.6443 |
| Cost proxy/trade USD | 0.3418 | 0.7058 |
| Swap debit USD | 55.6052 | 53.9030 |
| Swap credit USD | 0 | 0 |

Terminal risk blockage false both views; tail activity classification `exposed`,
not a no-signal/mixed-reason inference. Profit/month/year and WR/RR remain
diagnostics, not added gates. Worst DD has2.9024 percentage points margin below
40%; lower frequency16.04 exceeds15 by1.04 entries/month on this reused sample.

Winner ranking unchanged: worst-case net, worst DD, worst per-trade cost proxy,
worst mean admitted risk%, ID. Ordered qualifiers:
`b823f4aefe10fc72`, `5a5bf3d2fbedd58b`, `6a3141978395c1ec`.

## Accounting and verification

Base quoted spread; stress +0.20 USD/oz spread and adverse0.10 USD/oz slippage.
Pinned model commission0/lot, broker point0.001, contract100, swap modepoints,
BUY -567.4 points (fixed0.01 gives -0.5674USD per modeled weekday weight),
SELL0 points. UTC weekday rollover, Wednesday triple, weekend no charge;
model/calendar assumptions not verified against broker history.
Cost proxy=(quoted spread proxy+slippage+commission-signed swap)/trades; spread
proxy already contains stress widening, never charged twice or deducted from net.

Independent audit passed608 cells/236677 scenario trades: cash, fixed lot,
admitted risk, non-overlap, signed calendar swap, UTC monthly entries including
zero months, spread cost attribution, DD witnesses/minimum equity, admission/
rejection counts, original gates and frozen parent/neighbor/global dedup.
Original frozen baseline parity passed both mandatory swap views. Baseline,
all3 qualifiers (fewer than top5) and frequency diagnostic champion freshly
replayed both views; complete cell equality passed. Completed resume with
`--max-cells 0` preserved706 content hashes, no new cells.

Code unchanged from implementation commit `a013b35`. Focused24 tests and full
916 tests (skip2) passed again after saving the selected research config,
62.006seconds; log debug/qualified-full-tests.log. Scoped Ruff passed. Standards review0;
Spec safety-precedence finding fixed/red-green regression/re-review0 before this
source was frozen. No repository typecheck command configured.

## Evidence

Ignored machine directory: `runs/c22-tuning-loop-2026-10-07/`.
Root COMPLETE verdict QUALIFIED; root results SHA256
`5cca8cc79b9844c9e9c0d0097d077566d05d3f373af2542cc8fa9f63dc7f8d4f`.
Campaign results SHA256
`06a27da6a487140d402fcffbf4626ef5bcd10847901532166ff67ecc0bd5258e`.
Full audit `campaign-01/independent-audit.json`; repeats/search source snapshots
and ledgers under campaign-01; resume proof debug/resume-proof.json.

Research target achieved on frozen retrospective data. Demo section6.33 and
frozen artifacts unchanged. No push/deploy/cutover; real money prohibited.
