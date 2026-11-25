# C22 $200 continued tuning: evidence ledger

Status: modeled comparison RESEARCH_PASS found2026-11-13; COST_INCONCLUSIVE.
See [final virtual-native verdict](2026-11-13-c22-200-virtual-native-veto-verdict.md). No runtime adoption authorized.
Owner requested continued tuning after the initial bounded campaign failed,
then explicitly chose broader entry parameters within the existing C22 family.

## Unchanged acceptance contract

- Compare every candidate to native `26b8bcd69e043653`, both starting at $200.
- Fixed 0.01 lot, cost-inclusive 10% cap, daily10%/loss2 and one position.
- All seven segments, both base+swap and stress+swap: net >= native, DD <= native,
  with a strict profit gain somewhere. Numerical tolerance remains 1e-8.
- Train-only LOYO uses the full prospectively frozen catalog, native fallback
  and the existing maximin-view profit ranking. No held-out pruning.
- The selected fixed candidate must also preserve continuous net, maximum DD,
  minimum equity and the observed risk-cap rejection-span proxy.
- A screen only rejects. Any screen survivor requires original-catalog LOYO and
  continuous confirmation before a research pass. No thresholds or gates are
  relaxed to promote a near miss.
- Costs remain COST_INCONCLUSIVE: archived long -567.4 POINTS, short0, point0.001,
  declared UTC-midnight calendar with Wednesday triple posted Thursday. This is
  modeled sensitivity, not historical/current broker parity or Swap-Free proof.
- All history has been seen. Frozen protocols/LOYO limit selection bias but do
  not remove adaptive catalog-design bias or establish future profitability.

## Completed blocks

Artifacts are under runs/c22-profit-preservation-200-2026-11-12/. Counts below are
case evaluations, not distinct strategies; later grids deliberately repeat
single-factor neighbors rather than remove known failures.

| Block | Alternatives | Observed outcome |
| --- | --- | --- |
| timing-block | 16 | 12 regression rejects; 4 no-gain rejects |
| headroom-block | 6 | 4 regressions; 2 no-gain rejects |
| swap-be-fixed | 3 | All regress in a range-period cell |
| swap-cost-fixed | 12 | No screen survivor |
| buy-target-block | 4 | All regress in 2026 base |
| sell-target-block | 6 | No survivor; SELL3R reaches 2021 stress before rejection |
| sell-volatility-block | 3 | No survivor; >=$20 gains $148.885 in 2026 base but DD +0.5198 pp |
| sell-coupled-block | 3 | No survivor; >=$20 reaches 2024b25 stress before rejection |
| sell-coupled-high-vol-block | 3 | All screen survivors; full confirmation below still FAIL |
| entry-neighbor-block | 4 | RSI threshold25/35 and Donchian24/96 each regress in 2026 base |
| entry-grid-block | 8 | No survivor; full3x3 RSI-threshold/Donchian grid including native |
| rsi-period-block | 2 | RSI14/21 regress in 2026 base despite substantially lower DD |
| rsi-exit-joint-block | 11 | No novel survivor; only previously studied RSI7 exit profiles survive |
| m15-ema-block | 3 | BUY EMA off / SELL EMA off / SELL EMA200 all regress in 2026 base |
| m15-ema-grid-block | 5 | All regress in 2026 base |
| rsi-smoothing-grid-block | 8 | No survivor; RSI14/25 and RSI14/35 regress in 2024b25 stress |
| entry-admission-block | 4 | Rollover suppression and three existing guards regress |
| closed-entry-grid | 323 | Full 324-profile static entry domain including native; no survivor |
| buy-headroom-target-block | 3 | All fail; >=9% gains $6.0078 but DD +11.75265 pp in 2026 base |
| stop-width-block | 4 | All fail; BUY2ATR gains $6.0082 but DD +1.28256 pp in 2026 base |
| stop-geometry-grid | 53 | Full54profiles including native; no survivor |
| entry-exit-intersection | 1295 | Full1296profiles including native; only three prior native-entry exit profiles survive |


Each block has protocol.json/SHA256, source/input hashes, source snapshots,
per-cell full ledgers and an explicit screening result. A regression rejects at
the first worse cell; this does not imply every rejected case ran all14 cells.
Completed attribution files decompose net changes into retained, removed and
replacement trades; entry studies distinguish changed signals from admissions.

## Why the promising exit screen was not promoted

Policy: native BUY, native small SELL; SELL3R plus bar-close BE0.5R only when
original admitted stop risk >=$25/$30/$40. The cap still determines eligibility;
an original risk >=$25 requires at least $250 equity before admission.

[Full original-catalog confirmation](../../runs/c22-profit-preservation-200-2026-11-12/full-sell-coupled-high-vol/result.json)
has protocol SHA256
`f69289f18abba5b7436fed39ce8569a10346707d06caf331d69c831ec239c995`.

- The >=$25 profile improves independent 2020 net by $0.097 base / $7.9048 stress,
  and 2026 base by $207.519. Other independent net cells are unchanged; DD never
  worsens. The same profile is selected in all seven LOYO folds.
- It fails continuous confirmation: base final $15.66 versus native $17.301;
  minimum equity $15.66 versus $16.946; max DD94.7213% versus94.3453%.
  Stress final/minimum $16.5844 is also below native $16.5888.
- >=$30 and >=$40 preserve continuous native paths exactly, but their only
  independent gain is 2026 base (+$181.1386 / +$11.68). They are not promoted by
  deleting the selected >=$25 case or changing the frozen ranking after results.
- Follow-up continuous decomposition: base retained-trade gain +$25.418
  versus replacement-trade loss -$27.059, with no removed native trades.
  The improved March2020 exit lifts equity enough to admit an August2020
  SELL loss; a later extra trade deepens account loss. Stress reconciliation:
  retained +$25.492, removed native net -$19.0356, replacement -$44.532.
  These are admission-path effects, not direct edits to later native signals.
- Verdict remains FAIL. Better independent-year results do not establish a
  better account that must survive earlier losses without resets or deposits.

## Engineering corrections and validation status

- Initial swap-be-block/swap-cost-block outputs are engineering-superseded.
  Review caught zero-debit Decimal recalculation changing native rounding and
  unexecutable cost coverage suppressing native protection. Both have RED->GREEN
  synthetic regressions. Fixed policy requires positive debit, preserves at least
  native BE and falls back to native BE if coverage lacks executable clearance.
  The identical catalogs were rerun under the *-fixed directories above.
- Native control spec must be empty and present; the historical26b8 signal
  recipe is pinned independently of its risk/exit RulesID at freeze/evaluation.
  All actual study catalogs used native={} and the correct reference recipe.
- Candidate entry frames use validated recipe overrides. Continuous indicators
  are prepared once over combined bars. Entry recipe identity joins account carry
  binding so a recipe cannot silently change mid-account.
- Signal-preparation metadata inherits legacy seed exit values; it is **not**
  the effective exit/risk contract. Effective behavior is native replay Rules
  plus explicit catalog overrides, with a separate signal recipe ID.
- Latest targeted run: 62 tests passed across preservation/frequency/neighboring
  replay suites. Mypy passed both research modules with check-untyped-defs.
- Full suite at the earlier 15-test preservation stage: 1,667 tests, one error,
  skipped2. The error was unchanged supervision test
  test_timeout_reaps_child_and_cancels_sibling reading an empty child PID log
  after its 0.2s timeout. Isolated rerun passed. This is not a clean full-suite
  result; serial full rerun remains pending after current research activity.
- Latest serial full-suite rerun with no economic worker: **1,677 tests,
  OK (skipped2)**, 284.040s. Mypy passed both research modules. Both review axes found
  no blocking finding in the side-specific stops/conditional targets.
- Lazy confirmation selector: 3 tests passed, including 320 seeded comparisons
  against the original eager selector across full-data/fold training sets. The
  callback forbids held-out access. Peer review found no blocking finding in
  the prepared full-catalog confirmation driver; it has not run economically.
- No VM access, order sending, deployment, package install, push or commit.
  Existing owner availability changes remain outside this research work.

## Current frontier

Owner explicitly approved side-specific SL1.5/2ATR, fixed lot/cap unchanged.
SL screening retained target R ratios, so tighter stops also shortened price targets.
SELL1.5ATR reduced risk rejections from71 to36 but retained-trade net fell $582.391;
replacement trades netted -$27.5684. More admitted trades did not improve profit.
BUY2ATR retained169 trades: retained delta -$17.9408, removed native net -$3.3014,
replacement net +$20.6476; total +$6.0082 still fails DD. Both target/headroom and
stop-width blocks have exact retained/removed/replacement reconciliation.
The derived54-profile stop/target/protection grid also failed. Stop geometry
family ends here. Next closed catalog crosses all324 entry recipes with native
SELL exits and each previously studied conditional SELL3R/BE0.5R floor25/30/40USD
(1296profiles including native). Stops revert to native2.5ATR throughout; full
original-catalog LOYO remains mandatory for survivors. This retains pure-entry
cases and all prior conditional controls rather than pruning historical losers. Keep every rejection and the same
acceptance gates. No current result authorizes Demo adoption or real-money use.

## Owner extension2026-11-13

Owner selected both H4 EMA100 and H4 filter off for research, same capital/lot/cap
and gates. Single-factor native-exit block frozen separately before economics.
Native reference remains span200; only candidate recipes may use100/0. The
allowlist expansion has RED->GREEN causality/Rules invariance coverage. Latest
focused suites:63tests OK; mypy2modules OK. Previous full1677test result predates
this one-key expansion; final full rerun remains pending.

The1296-profile EMA200 interaction screen produced no novel survivor. The all-seven
fixed selection is P7_T30_D48_B50_S50_all_E25.0, equivalent to the earlier profile
with a known continuous veto. This is no qualification; a full1296catalog LOYO
confirmation has not been executed. Training-fold decisions are not inferred
from global screen pruning.

H4 single-factor results: EMA1002026base net+$168.673/DD-3.44350pp, but
2024b25stress net-$270.6248; H4off2026base net-$462.5888/DD+8.94082pp.
Attribution: EMA1002024b25stress retained trade net change0; removed native net
+$99.735 and replacement net-$170.8898. A separately frozen324-profile derived
factorial crosses H4(200/100/0), RSI periods/thresholds, Donchian and the four
native/conditional exit profiles, preserving M15 EMA50/sessionall and financial
controls. Screening remains rejection-only, full catalog required for LOYO.

H4 derived324profiles completed: only prior H4200/native-entry conditional exits
survived; no novel survivor. Owner then explicitly approved research-only
[virtual-native admission veto](2026-11-13-c22-shadow-admission-proposal.md).
Implementation adds no sender or sizing override. Exact UTC-ms/direction lookup
ignores outcome fields; own risk cap remains effective even with virtual permission.
A reviewer found same-time sorting could inflate a merged duration benchmark;
RED->GREEN removed that merge entirely before economics. Conservative metric now
uses max(actual raw observed cap span,required virtual native raw span); native
self-comparison is exact and the candidate cannot be judged against a relaxed
baseline. Raw counts and both books remain separate.31focusedtests and mypy3modules
passed; full serial preflight and integration review pending before economic run.

Virtual-native preflight completed: full serial suite **1683tests OK (skipped2)**,
285.373seconds; mypy3researchmodules passed. Both peer review axes found no
remaining blocking module or campaign integration finding. Economic run starts
only after this preflight; none of these engineering checks claims profit.

## Final comparison result2026-11-13

The frozen eight-profile virtual-native campaign passes the original comparison
gates, including full-catalog train-only LOYO and selected-fixed continuous
acceptance. Selected profile sell3R_risk25.0_BE05_veto; strict matched gains in
2020base(+25.418),2020stress(+25.492),2026base(+55.677USD), with no matched net/DD
regression. Continuousfinal42.719/42.0808USD remains below initial200; MaxDD remains
85.71997%/85.68227%. Effective observed cap spans remain native; virtual vetoes do
not restore availability. Native/veto parity,1683tests, mypy3modules, all112 trade
attributions and16pinned-prefix checks passed. Detailed tables, limits and hashes
are in the final verdict linked above. Tuning stops at this research comparison
pass; unseen forward evidence and owner adoption decisions remain outstanding.
