# Selected26b8 research ticket closure frontier

Review time28October2026,13:40UTC; implementation checkpoint13:48UTC. Scope: published T11,T17–T21
(GitHub #22,#28–#32). No GitHub mutation,broker reader,VM mutation or new
economic replay was performed in this review.

**T18 now has one new bounded,hash-frozen offline hypothesis. T19 needs its new
versioned implementation and audited12-cell matrix. Session/H4/addon/forward
tickets remain incomplete; the completed old12-profile study cannot substitute
for those deliverables.**

## Requirement-by-requirement findings

| Ticket | Evidence now verified | Missing evidence / next concrete work | Closure assessment |
|---|---|---|---|
| T11 / #22 | Existing observed11/16H4 mechanism and3causal regressions pass; fixtures distinguish missing M1 from a claimed session closure | Dated account/symbol schedule provenance plus classifier/report matching actual intervals; fixtures must also cover official rollover,DST,holiday and unexpected missing feed | OPEN; existing synthetic mechanism does not attest a broker session |
| T17 / #28 | Existing native closed-H4 policy and no-future-backfill regression provide a control | T11 dated scope; new carry/session-completeness/age rules and source ID frozen before matched6-view full-tick replay; opportunity-cost matrix and independent audit | OPEN; no candidate economic matrix exists |
| T18 / #29 | Verified old12-profile study; new B2 hypothesis/spec/catalog/ranking/costs/DD40/stop conditions frozen before economic runs | Review this exact preregistration; implementation and campaign-source pins are T19 work | Ready for protocol-level closure after parent review; no profitability claim |
| T19 / #30 | Inputs exist and all hashes match; original D1/P1/B1 tests26PASS; new versioned B2 loop and10public regressions PASS | Independent code review,new campaign source freeze,12primary cells,6fresh repeats and independent cash/swap/eligibility/full-tick DD audit | OPEN; old72paths are not the new matrix |
| T20 / #31 | Existing feasibility report requires one-account native-priority scheduling and exposes independent-net summation error | Freeze one exact addon and arbitration; implement joint continuous-account replay; daily MTM/core-missed-trade/coverage matrix and matched audit | OPEN; feasibility is not an experiment result |
| T21 / #32 | Existing bounded studies retain native26b8 and COST_INCONCLUSIVE; future cohort helper rejects retrospective freeze | T16 first sealed batch; completed T17/T19/T20 comparisons; any selected changed candidate needs exact future window/sample/stop rules frozen before reading unopened observations | OPEN; no valid final combined-study verdict yet |

Published acceptance criteria remain authoritative. This review does not replace
them with a smaller task or close dependent work from a plausible hypothesis.

## New T18 hypothesis and its causal seam

[Prerequisite protocol](../../specs/c22-next-risk-2026-10-28.md) defines two
profiles only: native26b8 and`B2-recovery-entry-NetBE`,candidate
`b7431d3dc4c30161`. B2 freezes at entry whether pre-entry balance is strictly
below the prior realized closing-balance peak. Only those recovery positions
use first accrued-cost Net BE; other positions retain native BE. There is no
new numeric threshold or parameter sweep. D1/P1/pause remain OFF in this study.

Rationale is the completed B1 trade-off: base profit fell11.45% while DD improved
1.86814percentage points; streak/minimum/recovery did not improve. Restricting
the changed stop to actual recovery episodes is a new falsifiable hypothesis,
not evidence it will work. No new target or floor was chosen after B2 outcomes.

The implementation must preserve the frozen old engine. Existing source trace:

- `scripts/research/c22_risk_replay.py:249` closes from actual executable ticks;
  commission was already deducted at entry and final balance updates at264.
  The new loop must update the closing-balance peak after that finalized balance,
  not from net-before-fee,control-path trade outcomes or intratrade equity peaks.
- `scripts/research/c22_risk_replay.py:560` builds the admitted position;
  `balance -= fee` occurs at594. Freeze recovery eligibility using balance before
  that fee deduction,then persist its evidence on the position.
- `scripts/research/c22_risk_replay.py:376` through439 selects stop management.
  Existing `overlay.net_be_first` is global; B2 needs a per-position selected
  mode consistently across activation,accrued-swap computation,stop calculation,
  first-success freeze and adjustment audit. Changing only one branch gives
  mixed native/B1 behavior and invalid results.
- `scripts/research/c22_risk_policy.py:152` supplies validated signed-cost Net BE.
  Reuse it read-only. The independent new verifier must derive recovery
  eligibility from continuous account history,not trust the candidate's bool.

The protocol preserves exact native control results in all6views,initial200USD,
fixed0.01/cap10%/native daily10%/loss2/cooldown30min and all native signal/SL/TP
rules. All views include the same declared historical swap. Today's operational
Demo swap rate-490.0 is not substituted into the historical comparison.

Selection keeps unchanged legacy floors,positive net/survival/DD<=40% in every
view,then raw-base net/raw-stress net/lower worst DD,native winning ties. A
profit-improvement claim additionally preserves every matched native6-view net
and strictly increases raw-base net. No winner is required. Changed source/risk
rules remain offline and cannot be adopted on Demo from this report.

## Actual verification and resources

Integrity recheck independently hashed110current source files and their frozen
snapshots,4parent artifacts,78saved economic payloads,the protocol/completion/
catalog bindings,all4input files and the input manifest: **PASS**. Prior audit
record is PASS over72cells and6fresh repeats; this review verifies those records'
integrity and does not claim to have re-executed the entire old full-tick audit.

Actual regression commands executed:

```text
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests/demo -p test_c22_h4_gap_rootcause.py -v
3 tests PASS in0.279s
PYTHONPATH=. .venv/bin/python -m unittest discover -s tests/research -p 'test_c22_risk_*.py' -v
26 tests PASS in0.113s
```

Those29tests validate existing mechanisms. New B2 implementation now exists in
`scripts/research/c22_recovery_be_replay.py`; its public-seam suite
`PYTHONPATH=. .venv/bin/python -m unittest tests.research.test_c22_recovery_be_replay -v`
passed10tests in0.207s. Scoped Ruff and Python compilation pass. These are
deterministic regressions,not new no-swap economic comparisons.

| B2 requirement | Exact new test |
|---|---|
| Control unchanged in6cost/accounting views | `test_disabled_control_matches_complete_native_result_in_all_cost_accounting_views` |
| BUY/SELL protection and swap retained | `test_disabled_control_preserves_buy_sell_protection_and_swap_in_all_six_views` |
| Realized peak and entry-frozen gate | `test_recovery_gate_is_frozen_before_entry_fee_and_peak_uses_closed_net` |
| Entry commission cannot create eligibility | `test_entry_commission_cannot_create_a_recovery_gate_or_change_native_be` |
| Cent loss flags do not erase a real below-peak balance | `test_cent_loss_flags_do_not_round_a_small_realized_balance_loss_out_of_gate` |
| First debit NetBE,rounding,BUY/SELL and later swap loss | `test_recovering_buy_and_sell_cover_debit_once_and_keep_later_swap_loss` |
| Geometry retry until first successful adjustment | `test_recovering_geometry_failure_retries_until_first_success` |
| Credit cannot accelerate original1R | `test_swap_credit_does_not_activate_before_native_one_r` |
| Credit cannot loosen initial stop | `test_recovering_swap_credit_never_loosens_initial_stop` |
| Strict configuration and missing swap fail | `test_enabled_mode_requires_explicit_swap_and_strict_bool` |

Existing tape: three1,369,368,232byte NumPy arrays plus3,061,141byte bars CSV.
Available disk at check13,025,280,000bytes; filesystem97%used. Existing risk run
67MiB and exhaustive run8.9GiB must remain preserved. Use memory maps,one worker
initially and>=2GiB free before each saved cell. No additional4.108GB tape copy.

Prior78cells/repeats: median2.455s,max6.53s,total188.31cell-seconds. Launch to
verified final delivery was about16m45s including independent audit. This bounds
the observed old workload only; no B2 ETA or current process-health claim is
made. New B2 implementation and full-tick audit have not been launched.

Artifacts under`runs/c22-issue-closure-2026-10-28/research/`:
`prior-study-integrity.json`,`next-risk-catalog.json`,and
`next-risk-hypothesis-freeze.json` and its explicitly superseding
`next-risk-hypothesis-freeze-v2.json`. The hypothesis was frozen
2026-10-28T13:40:27.699706Z before any B2 outcome. A pre-economic wording correction
replaces an inaccurate DST description with the already-bound parent algorithm's
UTC-midnight calendar; no scenario or gate changes. The earlier freeze remains
preserved. Historical inputs remain
exposed; COST_INCONCLUSIVE,unknown historical broker swap parity and missing
prospective qualification remain explicit.
