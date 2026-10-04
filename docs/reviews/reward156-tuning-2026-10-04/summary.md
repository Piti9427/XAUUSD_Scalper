# Reward156 paired tuning verdict

**No candidate qualifies to replace trial30.** All three fail frozen35%DD ceiling on continuous paths. H4EMA100 has positive swap-scenario net in all four continuous cells but DD39.22–64.96%.

| Contract | A base net / DD | A stress net / DD | B base net / DD | B stress net / DD |
|---|---:|---:|---:|---:|
| trial30 | $-145.87 / 73.74% | $-146.08 / 75.65% | $-90.71 / 47.79% | $-91.82 / 48.24% |
| reward156_original | $-140.71 / 73.56% | $-134.88 / 70.80% | $-90.53 / 68.85% | $-93.84 / 65.72% |
| reward156_no_pause | $+103.66 / 72.85% | $-164.91 / 85.49% | $-85.52 / 74.57% | $-109.79 / 76.13% |
| reward156_h4_ema100 | $+223.35 / 39.22% | $+139.10 / 40.98% | $+383.22 / 64.96% | $+362.78 / 54.73% |
| reward156_h4_ema200 | $+287.61 / 37.16% | $+214.14 / 41.44% | $-73.37 / 58.00% | $+449.43 / 49.96% |

Results above use independently replayed current-spec swap sensitivity. FixedUSD200/0.01lot/cap10%/daily20% shared; separate entry/exit/protection for each strategy.

120cells,120complete-result fresh matches. Baseline48cells persisted before tuning72cells. Ledger cashflow reconciles, admitted risk<=10%, lot0.01 in all cells; source/checkpoint hashes match.

No-swap and swap paths can differ substantially because debits change subsequent admission and account trajectory. Net-before-swap attribution on modeled path is not the independent no-swap counterfactual.

Both datasets in-sample. Historical rollover/rates, commission0 and target Demo fill parity unverified: COST_INCONCLUSIVE. Archived indicative results do not prove live profitability.

No qualified candidate: sealedJul-Sep2025 not opened; no grid expansion, no runner/shadow/cutover, Demo stays trial30.

See [full matrix](report.md), [JSON](results.json), [CSV](report.csv), [completion proof](COMPLETE.json), [validation](validation.json).
