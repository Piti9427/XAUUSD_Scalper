# C22 diversified tuning loop — BLOCKED

Historical blocked attempt. Later continuation completed and qualified:
[completed verdict](2026-10-07-c22-qualified-verdict.md). Evidence below preserved.

Research implementation complete; economic search incomplete. No winner selected.
Demo unchanged. Real money prohibited. Retrospective reused discovery remains
COST_INCONCLUSIVE.

## Diagnosis and change

Original300-config search expanded13 parents and never expanded its paired
frequency champion `318a661bf7d63472` (12.24/11.88 entries/month). Gate-count rank
matched original specification; exploration coverage limited frequency progress.
Risk-cap rejection was not primary admission bottleneck: champion risk rejection
7.1%/9.5%, with188/191 daily-loss-count rejections. Removing H4/EMA individually
did not solve frequency/DD gates. Evidence: ignored run debug/probes.json.

New bounded loop selects distinct frequency, balanced normalized gate-shortfall,
and original quality parents. Search300 globally new configs per campaign, max3
campaigns; finish whole campaign before selecting a qualifier. Reuse unchanged
adapter, qualification, winner rank, full ledgers and mandatory swap views.
Fresh baseline/seeds and baseline/top5-qualifier/diagnostic repeat checks retained.
Historical tape uses APFS clone with source-preserving portable fallback.

## Partial replay evidence — not final selection

Fresh current-month download and archive check performed. Requested end
2026-10-06T17:22:04.296998+00:00; actual last quote2026-10-05T23:59:59.969+00:00.
167622055 ticks,48465 completed M15 bars. No gap filling.

Attempt01 halted with ENOSPC after77 valid cells (38 paired configs plus one
unpaired cell). Highest paired frequency observed `495c82c251ae5681`:

| Metric | Base+swap | Stress+swap |
|---|---:|---:|
| Mean entries/full UTC month | 16.52 | 16.08 |
| Net USD | 317.58 | 243.27 |
| Equity DD % | 61.72 | 64.00 |

This diagnostic passes frequency but fails DD; stress net also falls below
baseline284.65. No profitability or qualification conclusion. Independent audit
reconciled all77 valid cells/21337 scenario trades: cash, initial risk/fixed lot,
non-overlap, signed calendar swap, monthly entry counts, cost attribution,
DD witnesses/min equity and admission/rejection counts. Partial audit is not
finalist repeat verification or full-loop coverage.

## Verification and review

Focused24 tests passed; Ruff passed scoped files. Full suite916 tests passed,
skipped2,62.489seconds; evidence debug/full-tests-final.log. No repository
typecheck command configured.
Two-axis code-review: Standards0 findings; Spec1 reproduced risk-precedence
finding fixed with red/green regression, re-review0 findings. Quality lane now
prefixes original rank with survival+risk safety. All77 actual partial cells were
risk-safe, so this finding did not affect observed partial ranks.

Source-pinned failed attempt preserved under
`runs/c22-tuning-loop-2026-10-07/attempt-01-blocked/`; source correction does not
rewrite it. Current root BLOCKED marker has selected=null. Disk preflight now
requires5GiB free before starting an incomplete loop. Identical freshly prepared
tape files hash-checked before deduplicating with immutable prior files; source
content unchanged. Prior completed campaign/frozen Demo contracts preserved.

## Remaining work

Free at least5GiB, then run command from docs/ops/c22-tuning-loop.md. Complete
up to3×300 new variants, finalist repeats, full-cell independent audits and
completed-resume invariance before issuing QUALIFIED/NO_QUALIFIER verdict.
Machine evidence: ignored `runs/c22-tuning-loop-2026-10-07/`.
