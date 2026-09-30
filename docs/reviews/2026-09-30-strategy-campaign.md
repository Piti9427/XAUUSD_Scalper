# Strategy campaign: actual discovery verdict

**NO_QUALIFIED_CANDIDATE**. 384 unique configs evaluated in8 batches. 0 passed all discovery gates. Demo BLOCKED. Existing184-day tape reused; no unseen validation performed.

Net / DD / WR / realized RR / trades:

| Contract | Base | Stress |
| --- | --- | --- |
| Frozen core | $-67.02 / 36.12% / 0.00% / undefined / 4 | $-67.62 / 36.32% / 0.00% / undefined / 4 |
| Donchian48 comparator | $333.62 / 56.89% / 48.50% / 1.171 / 266 | $179.76 / 58.65% / 47.53% / 1.166 / 263 |
| Highest full net with>=60 trades, trial201 | $428.99 / 34.60% / 49.33% / 1.199 / 223 | $411.56 / 38.09% / 49.10% / 1.201 / 222 |
| Lowest full DD with>=60 trades, trial360 | $187.39 / 33.45% / 43.30% / 1.524 / 194 | $135.22 / 32.37% / 43.09% / 1.476 / 188 |

These diagnostic rows are not selected candidates; every full/half scenario must pass. Configurations are recorded in the linked result JSON.

| Batch | Trials | Passing all gates | Zero full-base trades |
| --- | --- | --- | --- |
| 1 | 1–48 | 0 | 32 |
| 2 | 49–96 | 0 | 48 |
| 3 | 97–144 | 0 | 48 |
| 4 | 145–192 | 0 | 32 |
| 5 | 193–240 | 0 | 32 |
| 6 | 241–288 | 0 | 48 |
| 7 | 289–336 | 0 | 48 |
| 8 | 337–384 | 0 | 32 |

## Reproducibility

Implementation commit: `4f66709`. Local immutable run: `data/strategy_campaign_2026_09_30_v3`. Protocol SHA256: `4ce410dd0d6bde12a620e602c4ed78aa189bc19140f3935ccb6fb43ee1faf8b0`. Verdict SHA256: `c02ded5db10dabc0e6089e75ace7e9861524e511d5dbbfe208e230931ab44ce0`. [All config/metric results](2026-09-30-strategy-campaign-results.json). [Frozen spec](../specs/2026-09-30-strategy-campaign.md).

45,671,201 audited raw ticks;12,100 canonical bars; same broker specification, capital and costs across parents/candidates. Source/input hashes in protocol. Each trial stores full/half base/stress ledger, equity checkpoints, rejections and cost attribution. Tick-level DD uses all visited quotes. Equity artifact is compact checkpoints, not a full every-tick export.

Base commission0 is archived research assumption. Stress extra spread0.20/oz and adverse slippage0.10/oz per market fill. Swap absent; entitlement/history missing. No sourced all-in broker-cost qualification.

## Verification

695 unittest cases, skipped2, exit0. Focused34 tests passed. Ruff and compileall passed. Mypy unavailable; static type checking not completed. Two-axis code review againstdevelop, scoped to campaign: initial2 Spec/1 Standards findings fixed, re-review0 unresolved. Deliberately corrupted baseline and selection metadata copies each rejected on resume. Valid resume of all384 cached trials passed; final verdict SHA256 unchanged.

Interrupted v1/v2 development runs preserved locally; v3 alone is final campaign evidence. No thresholds were changed after v3 protocol freeze. No strategy adopted; CORE logs research changes.

## Standards

Initial1 finding: baseline resume evidence lacked hash verification. Fixed with baseline completion hashes and fail-closed checks. Re-review:0 unresolved findings. No material smell findings.

## Spec

Initial2 findings:12 duplicate configurations and cached selection metadata trusted during resume. Fixed with384 unique configuration assertion/regression, six-artifact hash verification and metric/qualification reconstruction. Re-review:0 unresolved findings. Winner-dependent MQL5/Shadow requirements remain explicitly blocked; no readiness claim.

## Remaining gates

Need>=12 months verified nonempty true Bid/Ask and>=3 months untouched validation. Freeze a discovery-qualified candidate before evaluating unseen>=30 trades. No such candidate currently. MQL5 EA port, real-tick delay/parity and Shadow>=20 tradingdays/>=30eligible decisions remain gated. Separate owner approval required for Demo orders. Campaign exhausted; no endless retries on reused data. A new campaign requires a new explainable hypothesis and frozen protocol.
