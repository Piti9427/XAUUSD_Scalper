# Public discovery and drawdown admission results

**Goal not met. No qualified candidate. Demo BLOCKED.** Four preserved runs /1,296 trial evaluations, including336 new drawdown contracts repeated on two datasets and under stricter RR screening. Do not count repeated runs as additional unique strategies.

| Run | Trials | Pass | Highest full net with>=60 trades | DD | WR | RR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| strategy_public_activation_campaign_2026_10_01 | 288 | 0 | $168.91 | 21.93% | 15.57% | 8.665 |
| strategy_drawdown_campaign_2026_10_01 | 336 | 0 | $32.03 | 46.30% | 14.04% | 6.727 |
| strategy_drawdown_strict_campaign_2026_10_01 | 336 | 0 | $32.03 | 46.30% | 14.04% | 6.727 |
| strategy_public_drawdown_campaign_2026_10_01 | 336 | 0 | $231.13 | 14.78% | 21.98% | 7.318 |

Public drawdown diagnostic trial309: core/buy-only/boundary SL, daily5%, protectionoff, drawdown_steps. Full base net+$231.13/DD14.78%/WR21.98%/RR7.318/91trades; stress net+$185.43/DD22.53%/WR20.21%. Core baseline WR30.61%; therefore WR and stressDD fail, halves screened out. This is not a winner.

Rows above are diagnostics, not selected strategies. Every candidate failed at least one discovery gate. Missing screened half metrics are not evaluated, never assumed passes.

## Selection and evidence

Protocol3 drawdown336 is original floor-only RR screen; preserved separately. Protocol4 rerun336 adds RR greater than each defined parent, restoring owner explicit request "realized RR เพิ่ม". Undefined core RR skips comparison only; candidate still requires RR>=1. Neither screen found a winner. Full and both halves must beat both parents profit/WR, lower DD<=20%, minimum60/20 trades, base and stress; partial windows cannot qualify.

[All evaluated contracts, metrics and frozen protocols](2026-10-01-public-drawdown-results.json). Local ledger/equity artifacts and source snapshots hash-verified for all four runs. [Acquisition provenance and holdout constraints](2026-10-01-public-tick-acquisition.md). Ten months audited, three ZIP-only sealed; actual twelve-month tick coverage not yet verified. No sealed-price reading or future-data selection.

## Validation

| Requirement | Evidence |
| --- | --- |
| Fixed0.01 entry rejection after drawdown | test_drawdown_steps_reject_high_risk_entry_after_two_losses |
| Strict RR improvement including undefined parent | test_strict_rr_rejects_below_defined_parent_and_allows_undefined_core |
| Missing minute excludes incomplete M15 | test_import_excludes_incomplete_m15_without_filling_missing_minute |
| Reversed source rejects | test_import_rejects_reversed_source_ticks |
| Focused tests |45 passed |
| Full suite |706 tests, skipped2, exit0 |
| Ruff |check passed |
| Public strict resume |336 cached trials verified, same0-pass verdict |

Mypy unavailable: static type validation incomplete. No MT5 execution smoke test or Demo parity claimed. Swap/commission and historical broker specs remain unverified assumptions. Two scoped code reviews completed; RR mismatch fixed and importer tests added. Review Standards initially assumed RR floor was final owner instruction; actual user answer requested RR increase, hence strict protocol4.

## Research state

All four catalogs completed. No background research process remains after completion. Repeating them cannot create independent evidence. Need next falsifiable entry/exit hypothesis; retain rejection evidence, untouched holdout and conditional parity/Shadow/Demo gates. No promotion or live order.
