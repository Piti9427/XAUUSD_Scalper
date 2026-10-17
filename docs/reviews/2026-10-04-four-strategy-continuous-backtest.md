# Four-strategy continuous backtest — 2026-10-04

Owner requested only trial30, original Reward156, circuit22+H4EMA200 and fine6+H4EMA200. No tuning or config selection expansion performed.

Requested window: 2024-09-01T00:00:00+00:00 through 2026-10-04T11:19:48.476278+00:00. Actual quote coverage: **2024-09-01T22:05:06.129000+00:00 — 2026-10-02T20:57:59.885000+00:00**.
Input: **167,366,065 original Bid/Ask ticks**, **48,367 completed UTC M15 bars**. All25 full calendar months Sep2024–Sep2026 plus partial Oct2026; imported original Jul–Sep2025 archives and current Oct archive. No missing intervening month, no fabricated quotes/bars.

Each strategy/cost-view starts independent USD200 once. Fixed0.01 lot, maximum cost-inclusive admission risk10%, single position. No account, peak, day/risk-state or indicator reset at dataset/month/year seams. Strategy-specific detectors/exits/daily circuits remain distinct. Original controls daily20%; tuned candidates daily10%/one losing exit perUTCday, no BUY pause.

Base: archived actual spread/slippage0/commission0 assumption. Stress: same quotes with spread+0.20USD/oz, adverse market-fill slippage0.10USD/oz, commission0 assumption; existing TP fill contract retained. No-swap and current-spec swap independently replayed, not post-hoc subtraction. Same current broker metadata/assumed UTC rollover calendar as prior paired campaign. Historical commission/swap/rollover and live execution parity unverified: COST_INCONCLUSIVE.

Data provider labels tick history indicative rather than target-account execution evidence: [Exness tick history](https://www.exness.com/tick-history/).

## Main comparison — including current-spec swap

| Strategy | Base net USD | Base final equity USD | Base DD% | Stress net USD | Stress final equity USD | Stress DD% | Worst DD across4 views% | Trades base/stress |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| trial30 | -155.60 | 44.40 | 78.46 | -144.95 | 55.05 | 76.22 | 78.46 | 59/41 |
| Reward156 original | -143.34 | 56.66 | 77.64 | -154.72 | 45.28 | 79.70 | 79.80 | 90/91 |
| circuit22+H4EMA200 | +291.55 | 491.55 | 39.28 | +278.71 | 478.71 | 37.82 | 39.28 | 120/116 |
| fine6+H4EMA200 | +333.97 | 533.97 | 39.43 | +272.44 | 472.44 | 40.95 | 40.95 | 117/114 |

## All16 scenarios

| Strategy | Cost | Swap view | Net USD | Return% | Max DD% | WR% | Realized RR | Trades | BUY/SELL |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| trial30 | base | no_swap | -155.60 | -77.80 | 78.46 | 30.51 | 1.1189 | 59 | 0/59 |
| trial30 | base | swap | -155.60 | -77.80 | 78.46 | 30.51 | 1.1189 | 59 | 0/59 |
| trial30 | stress | no_swap | -144.95 | -72.48 | 76.22 | 26.83 | 0.9981 | 41 | 0/41 |
| trial30 | stress | swap | -144.95 | -72.48 | 76.22 | 26.83 | 0.9981 | 41 | 0/41 |
| Reward156 original | base | no_swap | -143.96 | -71.98 | 78.03 | 34.78 | 1.3428 | 92 | 3/89 |
| Reward156 original | base | swap | -143.34 | -71.67 | 77.64 | 34.44 | 1.3471 | 90 | 3/87 |
| Reward156 original | stress | no_swap | -154.73 | -77.36 | 79.80 | 33.33 | 1.3377 | 84 | 3/81 |
| Reward156 original | stress | swap | -154.72 | -77.36 | 79.70 | 34.07 | 1.3511 | 91 | 3/88 |
| circuit22+H4EMA200 | base | no_swap | +295.52 | +147.76 | 39.08 | 48.33 | 1.3701 | 120 | 21/99 |
| circuit22+H4EMA200 | base | swap | +291.55 | +145.77 | 39.28 | 48.33 | 1.3651 | 120 | 21/99 |
| circuit22+H4EMA200 | stress | no_swap | +246.81 | +123.41 | 37.61 | 47.01 | 1.3938 | 117 | 21/96 |
| circuit22+H4EMA200 | stress | swap | +278.71 | +139.36 | 37.82 | 47.41 | 1.4150 | 116 | 21/95 |
| fine6+H4EMA200 | base | no_swap | +337.37 | +168.69 | 39.23 | 49.57 | 1.3784 | 117 | 21/96 |
| fine6+H4EMA200 | base | swap | +333.97 | +166.98 | 39.43 | 49.57 | 1.3737 | 117 | 21/96 |
| fine6+H4EMA200 | stress | no_swap | +225.87 | +112.94 | 40.74 | 46.55 | 1.4080 | 116 | 21/95 |
| fine6+H4EMA200 | stress | swap | +272.44 | +136.22 | 40.95 | 47.37 | 1.4295 | 114 | 21/93 |

## Interpretation

Both tuned candidates profitable and above both controls in all4 continuous environments. circuit22 has higher worst-scenario net (+246.81 vs fine6+225.87) and lower worst DD (39.28 vs40.95%). fine6 has higher base+swap profit (+333.97 vs+291.55). This supports circuit22 for the more balanced retrospective comparison; neither has DD<=35% on full continuous history.

Previously reported fine6 worst DD29.39% applied to independent A/B accounts; full continuous replay includes previously excluded Jul–Sep2025, carries capital/risk state and H4 EMA prefix into B, and adds Oct2026. Its current worst DD40.95% supersedes no old result; it answers a different window/state question.

Trial30/original Reward156 do not bankrupt in this model but suffer worst DD78.46/79.80% and no admitted trade for approximately404–410 final calendar days. Trial30 is terminal risk-only blocked; original Reward156 has mixed risk-cap/BUY-pause rejection, so risk-only flagFalse does not imply healthy activity. Tuned candidates admitted trades into lateSep/Oct2026, do not show terminal risk-only blockage or nonpositive modeled equity.

Swap can change subsequent risk admission and trade sequence; a swap scenario may finish higher than no-swap despite negative debits. Full-result independent replay and admission/ledger evidence preserved. No counterfactual profit calculated by subtracting swap after simulation.

Every remaining position liquidated uniformly at last available quote as END_OF_SAMPLE, if present. No additional prices invented up to frozen asof. Gap losses may exceed initial admitted risk; cap is entry budget, not guaranteed total-DD ceiling.

## Exposure and Demo status

Explicit owner request opens Jul–Sep2025 for this retrospective whole-history comparison. It is now exposed and cannot serve as untouched independent holdout for these strategies in future work. Prior v1/v2 holdout-not-opened claims describe their historical campaign status only; no prior verdict/artifact relabeled.

No claim of full v2 A/B/half/swap-sensitivity qualification, prospective validation or executable Demo readiness. Reward156 execution blockers from demo-replacement scrutiny remain unresolved. No Demo config/process/journal or order API touched.

## Verification and reproduction

16 completed cells,16 fresh COMPLETE-result matches (32 actual replay calls). Independent verifier recomputed all16 row metrics and drawdowns from equity checkpoints, reconciled1,494 closed-trade ledger rows across scenarios, verified initial-stop cost risk/entry equity/10% cap/fixed0.01/single-position non-overlap, and source/archive/tape/bar/protocol hashes. Raw ledgers/equity/admission events retained locally.

Existing engine/detector regression run: `.venv/bin/python -m unittest tests.test_reward156_search tests.test_reward156_tuning tests.test_breakout_logic`:65tests/0.528s/OK, exit0. Artifact runner/verifier Ruff and syntax compilation pass. Runtime strategy modules unchanged; no full-suite rerun needed for artifact-only replay.

Artifacts: `data/research_output_four_strategy_full_history_2026_10_04/` contains `results.json`, `summary.csv`, `protocol.json`, `validation.json`, `COMPLETE.json`, source snapshots,16 cell/proof files, diagnostics and input manifest. Raw inputs/results ignored by Git.

```bash
.venv/bin/python -m data.research_output_four_strategy_full_history_2026_10_04.run
.venv/bin/python -m data.research_output_four_strategy_full_history_2026_10_04.verify
```

Default rerun resumes only exact frozen source/input/runtime and candidate IDs. New/latest source refresh requires a separate output/version, never overwrite pinned archives or prior results.

Results SHA256: `2a993336b057e835f86d53bd85475e05847db7498d99690aded9b50d6af17d43`.
Protocol SHA256: `6fece45aea84ff8eda66dfdbe0f18357437f7929119260ab515920d5b8da0584`.
