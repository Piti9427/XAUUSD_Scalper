# C22 $200 virtual-native veto: research comparison passes

Status: **RESEARCH_PASS; COST_INCONCLUSIVE; research only.**

The owner-approved virtual-native entry veto produces a candidate that meets the original modeled-cost comparison gates against native `26b8bcd69e043653`. All accounts start $200, lot remains0.01, and the actual-account cost-inclusive10% risk cap remains active. No capital is added or combined between books.

## Selected behavior

- Candidate: `sell3R_risk25.0_BE05_veto`.
- Keep native RSI7/30, Donchian48, both M15 EMA50 filters, closed H4 EMA200, native BUY exits, both SL2.5ATR, daily10%/loss2 and cooldown2.
- On SELL with initial admitted SL risk >=$25, use target3R and bar-close BE0.5R. Other SELL trades keep native target1.35R/BE1R.
- Additional entry veto permits an attempt only when the separate corresponding native virtual book admits the same direction at the exact current quote millisecond. Candidate still checks its own account, position and risk. Gate reads no future profit/exit/MFE/MAE.
- Independent segments each start a separate actual and virtual $200 book. Continuous accounts each start once and carry all state across all six internal boundaries between the seven segments. Virtual equity is never spendable candidate equity.

## Acceptance evidence

- Fixed selected candidate:14/14 matched cells have net >= native and MaxDD <= native; strict net improvement in 2020|base, 2026|base, 2020|stress. Raw tolerance remains1e-8.
- Full eight-profile original catalog retained, including three ungated prior controls and native-veto parity control. No held-out pruning or changed ranking.
- LOYO held-out policy also passes14/14 net/DD gates with strict gains. The2020 fold selects the ungated25USD profile; all six other folds select the veto25USD profile. Continuous validation is for the selected fixed profile, not annual switching between fold policies.
- Selected fixed continuous profile passes both views for net, MaxDD, minimum equity and effective observed cap-span proxy.
- Native direct parity14/14; native-exit veto control ledger/DD/final parity14 independent +2 continuous.
- All112 non-native matched comparisons reconcile retained/removed/replacement net attribution. Every veto-profile entry is a subset of native admitted entries, with identical retained entry price, initial SL, lot and nominal riskUSD.
- Sixteen pinned-prefix validations passed: native indicators re-prepared from truncated bars, tick arrays physically truncated at each cutoff, no end liquidation; past admissions and gate behavior match full references. This validates the tested prefixes, not every possible future path.

## Fixed candidate independent cells

Net and minimum equity are USD; MaxDD is percent. Every view includes modeled swap.

| Segment | View | Native net | Candidate net | Delta | MaxDD native → candidate | Min equity native → candidate |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2020 | base+swap | -133.9170 | -108.4990 | +25.4180 | 77.9489 → 69.1569 | 66.0830 → 91.5010 |
| 2020 | stress+swap | -145.8132 | -120.3212 | +25.4920 | 81.8833 → 72.8898 | 54.1868 → 79.6788 |
| 2021 | base+swap | -174.7612 | -174.7612 | +0.0000 | 91.8196 → 91.8196 | 21.3152 → 21.3152 |
| 2021 | stress+swap | -173.5472 | -173.5472 | +0.0000 | 89.8386 → 89.8386 | 26.4528 → 26.4528 |
| 2022 | base+swap | -33.4690 | -33.4690 | +0.0000 | 63.8382 → 63.8382 | 72.3464 → 72.3464 |
| 2022 | stress+swap | -173.4178 | -173.4178 | +0.0000 | 88.0679 → 88.0679 | 23.8642 → 23.8642 |
| 2023 | base+swap | -102.7062 | -102.7062 | +0.0000 | 65.6610 → 65.6610 | 86.3228 → 86.3228 |
| 2023 | stress+swap | -172.5818 | -172.5818 | +0.0000 | 89.2332 → 89.2332 | 27.4182 → 27.4182 |
| 2024a | base+swap | -150.6902 | -150.6902 | +0.0000 | 82.0402 → 82.0402 | 35.9412 → 35.9412 |
| 2024a | stress+swap | -167.9374 | -167.9374 | +0.0000 | 85.0767 → 85.0767 | 29.8466 → 29.8466 |
| 2024b25 | base+swap | 927.8000 | 927.8000 | +0.0000 | 34.2750 → 34.2750 | 187.6636 → 187.6636 |
| 2024b25 | stress+swap | 773.9060 | 773.9060 | +0.0000 | 37.7301 → 37.7301 | 146.9740 → 146.9740 |
| 2026 | base+swap | 699.2058 | 754.8828 | +55.6770 | 52.8747 → 38.0066 | 152.9090 → 152.9090 |
| 2026 | stress+swap | 24.9228 | 24.9228 | +0.0000 | 69.7107 → 69.7107 | 120.9798 → 120.9798 |

## Independent admission availability

Actual risk-cap rejects can become zero because the additional virtual veto acts first. This is not recovered availability. Required virtual risk-cap rejects and actual vetoes remain visible; the effective duration proxy cannot fall below either book's original observed span.

| Segment | View | Risk rejects native / candidate actual / required virtual | Actual virtual vetoes | Effective cap span days native → candidate |
| --- | --- | ---: | ---: | ---: |
| 2020 | base+swap | 13 / 0 / 13 | 56 | 1.0312 → 1.0312 |
| 2020 | stress+swap | 29 / 0 / 29 | 73 | 4.9271 → 4.9271 |
| 2021 | base+swap | 102 / 0 / 102 | 137 | 32.7708 → 32.7708 |
| 2021 | stress+swap | 73 / 0 / 73 | 112 | 13.7500 → 13.7500 |
| 2022 | base+swap | 24 / 0 / 24 | 48 | 0.8854 → 0.8854 |
| 2022 | stress+swap | 449 / 0 / 449 | 454 | 102.3021 → 102.3021 |
| 2023 | base+swap | 0 / 0 / 0 | 32 | 0.0000 → 0.0000 |
| 2023 | stress+swap | 137 / 0 / 137 | 157 | 58.5417 → 58.5417 |
| 2024a | base+swap | 187 / 0 / 187 | 191 | 89.2708 → 89.2708 |
| 2024a | stress+swap | 190 / 0 / 190 | 194 | 90.0208 → 90.0208 |
| 2024b25 | base+swap | 1 / 0 / 1 | 17 | 0.0000 → 0.0000 |
| 2024b25 | stress+swap | 1 / 0 / 1 | 25 | 0.0000 → 0.0000 |
| 2026 | base+swap | 71 / 0 / 71 | 98 | 9.5729 → 9.5729 |
| 2026 | stress+swap | 413 / 0 / 413 | 422 | 70.2604 → 70.2604 |

## Continuous $200 account

**The continuous account still loses capital.** This is a relative backtest improvement, not proof of a profitable account over the full history or readiness for adoption.

| View | Net native → candidate | Final balance native → candidate | MaxDD native → candidate | Min equity native → candidate |
| --- | ---: | ---: | ---: | ---: |
| base+swap | -182.6990 → -157.2810 | 17.3010 → 42.7190 | 94.3453% → 85.7200% | 16.9460 → 42.3640 |
| stress+swap | -183.4112 → -157.9192 | 16.5888 → 42.0808 | 94.4537% → 85.6823% | 16.5888 → 42.0808 |

base+swap: native actual cap rejects 2769; candidate actual 0; required virtual 2769. Effective consecutive-observed cap span remains 1193.333328days (native 1193.333328). Raw candidate span is 0.000000days; the virtual floor prevents presenting that as improved availability.

stress+swap: native actual cap rejects 2808; candidate actual 0; required virtual 2808. Effective consecutive-observed cap span remains 1123.999998days (native 1123.999998). Raw candidate span is 0.000000days; the virtual floor prevents presenting that as improved availability.

The duration measure is a consecutive-observed-rejection span proxy. It does not measure uninterrupted wall-clock inability. The strategy preserves the native virtual book's restrictions rather than curing prolonged risk-cap lock.

## Causal attribution

- Continuous base: all204 native trades retained, no removed/replacement trades; changed exit net +$25.418. The previous ungated variant admitted two extra losing trades totalling-$27.059. The veto removes that displacement failure.
- Continuous stress: all178 native trades retained, no removed/replacement trades; changed exit net +$25.492.
- 2026base:172 retained trades,10 removed native trades (combined native net-$16.089), no replacements; retained exit change +$39.588, giving total +$55.677. Removed trades were selected by causal virtual admission state, not by realized outcome labels.

## Cost, engineering and adoption limits

- Archived broker assumptions: regular swap_long-567.4POINTS, swap_short0, point0.001, declared UTC-midnight rollover calendar with Wednesday triple posted Thursday. No unsupported metadata or zero substitution; historical/current entitlement and realized broker parity remain unverified.
- Base uses recorded bid/ask spread with no additional spread/slippage/commission. Stress adds0.2USD/oz spread and0.1USD/oz adverse market slippage; commission remains0 in both. Prefix cash reconciliation is pinned to these zero-commission scenarios.
- Full serial suite:1683tests OK (skipped2),285.373s; mypy3researchmodules passed. Both peer review axes found no remaining blocking finding. A merged-event ordering bug was RED→GREEN fixed before any economic run; current duration metric is max(actual,required virtual) with no reordering.
- All historical data have been seen and catalogs were adapted over many experiments. LOYO is not unseen forward evidence. Fresh forward shadow is required before any adoption proposal; operational support for a virtual book needs separate owner review.
- Active Demo strategy/config, sender and broker remain untouched. No VM access, orders, deployment, installs, push or commit. The earlier commit attempt was rejected by automatic approval review because explicit owner commit approval was absent.

## Reproducible artifacts

- Economic protocol SHA256: `bf52b24042cff762e6de712b4f052c4283b461b541c79d1c6820d2b5aa2ebb90`.
- Economic result: `runs/c22-profit-preservation-200-2026-11-12/virtual-native-admission/result.json`; source snapshots,112 independent cells,16 continuous summaries, native books, carry checkpoints and attribution remain beside it.
- Causality protocol/result: `runs/c22-profit-preservation-200-2026-11-12/virtual-native-prefix-validation/`;16 pinned-prefix checks passed.
- Verification logs: `virtual-preflight-full-tests.log`, `virtual-native-admission.log`, `virtual-native-prefix-validation.log` under the campaign root.
- Earlier failures remain in the [continued tuning evidence ledger](2026-11-12-c22-200-continued-tuning.md). Wayfinder mechanism/adoption decisions remain open for owner review; no automatic ticket closure or runtime adoption.

## Implementation continuation

[Continuation handoff](2026-11-13-c22-optimize-implementation-handoff.md) records
implementation gaps, evidence paths, safeguards and proposed next steps. It does
not grant runtime or commit permission.
