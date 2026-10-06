# C22 frequency campaign — NO_QUALIFIER

Completed300 unique challengers,5 frozen adaptive rounds (29/80/77/74/40),602
search cells including baseline. **No candidate passed both scenarios.** No gate
was relaxed. Zero candidates achieved mean15 entries/full month in both views.
No strategy selected; C22H4 Demo contract unchanged. COST_INCONCLUSIVE persists.

## Same-input results

All cells: USD200 once, fixed0.01, single position, admission cap<=10%; continuous
account/indicators/daily state. Every scenario includes modeled swap.

| Contract | Scenario | Net USD | Max equity DD % | Trades | Mean entries/full month |
|---|---|---:|---:|---:|---:|
| Original C22H4 | base+swap | 297.49 | 39.28 | 120 | 4.76 |
| Original C22H4 | stress+swap | 284.65 | 37.82 | 116 | 4.60 |
| Highest-frequency challenger `318a661bf7d63472` | base+swap | 452.53 | 57.20 | 307 | 12.24 |
| Highest-frequency challenger `318a661bf7d63472` | stress+swap | 310.68 | 56.26 | 298 | 11.88 |
| First in search ranking `55c0ae13a8165e02` | base+swap | 705.08 | 29.54 | 139 | 5.52 |
| First in search ranking `55c0ae13a8165e02` | stress+swap | 539.06 | 35.56 | 135 | 5.36 |

Highest-frequency challenger disables BUY EMA and enables BUY BE1R; other baseline
parameters remain. It misses both frequency and DD requirements. First search-rank
candidate changes BUY SL2.5ATR/BE1R, SELL SL2ATR, cooldown2 and avoid21–24UTC entries;
it still misses frequency. These are diagnostic near misses, **not qualified
winners**. Neither received extra finalist repeat because no challenger qualified.

| Gate satisfied in both views | Candidates /300 |
|---|---:|
| Net positive and >= baseline | 75 |
| Max equity DD<=40% | 70 |
| Frequency>=15 entries/full month | 0 |
| Positive equity throughout/no bankruptcy | 300 |
| No conservative terminal risk-only blockage | 274 |
| Fixed0.01/admitted risk<=10% | 300 |
| Net and DD together | 29 |
| All gates | 0 |

25 full UTC months:2024-09 through2026-09, including zero/warmup months. October2026
is partial; baseline has1 entry there in each view. Entry UTC drives frequency;
exit UTC drives monthly/yearly realized net. Full monthly/yearly diagnostics,
WR/RR, tail classifications, cost proxies and admitted risk are retained per cell
and in results.json. Tail no-signal/mixed reasons are not future tradability proof.

Baseline cost proxy/trade: base0.25785USD, stress0.61019USD; signed swap debit3.9718USD,
credit0USD in each view. Mean admitted risk:5.82462%/5.50634%. Cost proxy uses spread
already widened by scenario, plus modeled slippage+commission-signed swap; it is
not another cash deduction. Initial10% cap does not reserve future swap; gap/swap
losses can exceed admitted risk and BE can close net negative.

## Inputs and assumptions

Fresh October archive downloaded into this campaign,8465440bytes,
SHA256 `6f3ca983e681edf68ecc77831c20cd3a0e1f9a606a53b371085bbf66f62b53d5`.
Historical completed prefix is frozen from the original verified comparison.
167622055 Bid/Ask ticks and48465 canonical M15 bars, each assembled from all15 M1.
H4 EMA uses only complete closed H4 per canonical implementation. No gap filling.

Requested start2024-09-01T00:00:00Z; requested end2026-10-06T16:04:52.777674Z;
actual first quote2024-09-01T22:05:06.129Z; actual last quote2026-10-05T23:59:59.969Z.
The provider directory lists years before2024; September2024 is this study's
fixed scope, not a verified claim that no earlier public ticks exist.

Base quoted spread; stress adds0.20USD/oz spread and0.10USD/oz adverse slippage.
Round-trip commission assumption0USD/lot. Swap points mode, point0.001,
long-567.4points/short0; fixed0.01 has factor1oz. Preceding-business-day UTC midnight,
Wednesday triple posted Thursday, no weekend double charge. Rates/calendar and
historical commission/fills are unverified broker assumptions. Retrospective
reused discovery, no untouched validation, stop-out parity or profit forecast.

## Verification and provenance

- Original frozen swap baseline full-result parity passed both scenarios before
  latest-data search. Old frozen base/stress nets291.5482/278.7102USD reproduced.
- Fresh latest-data baseline full-result repeat passed both scenarios. No top5
  challenger repeats were eligible because no challenger passed gates.
- Independent final auditor verified all602 cells and81304 scenario ledger trades:
  cash, initial risk%, fixed lot, non-overlap, independently computed calendar swap,
  entry-month counts, spread cost proxy, DD witnesses/min equity, admission/rejection
  accounting, both-view gates, round parent relationship and uniqueness.
- Completed resume with `--max-cells 0`:696 content hashes unchanged; no new cell.
- Full repo suite in existing `.venv`:909 tests OK, skipped2. Lint/format/compile
  and diff whitespace checks pass. No configured typecheck. Detailed test mapping
  and two-axis review limitation: [implementation review](2026-10-06-c22-frequency-implementation.md).

Machine evidence: `runs/c22-frequency-2026-10-06/` (gitignored).
Final root COMPLETE verdict NO_QUALIFIER; selected=null.

Protocol SHA256: `a6f23927c1ab8b726649eea6a9f87afe3eb8a6224441cee4ec7a584e37cce76e`.
Results SHA256: `17be3bd6a201718edbdce7d7a23b3632c12d9f067e73bea21630832765f62bce`.
Checkpoint SHA256: `c9f4c0554668a9dbee40599e8042f2c65f0d4b6f3af1822f37da7fe5a413856b`.

Implementation/research complete. No push, deployment or Demo cutover performed.
