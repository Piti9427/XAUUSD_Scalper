# XAUUSD S1–S4 Research Readiness & Implementation Handoff v1

**Parent:** [Issue #2](https://github.com/Piti9427/XAUUSD_Scalper/issues/2) · **Ticket:** [Issue #4](https://github.com/Piti9427/XAUUSD_Scalper/issues/4)  
**Blocked-by (satisfied as documentation input):** [`xauusd-s1-s4-mechanical-v1.md`](xauusd-s1-s4-mechanical-v1.md)  
**Narrative:** [`xauusd-setup-experiment-v1.md`](xauusd-setup-experiment-v1.md)  
**Status:** Documentation / evidence review only — does **not** implement detectors, acquire paid data, run comparative backtests, enable trading, or freeze unresolved policies.

---

## 1. Mechanical-spec review → parent scenario routing

Every parent acceptance scenario from issue #2 is routed to a worked example, a downstream test requirement, or an explicit unresolved blocker.

| Parent # | Routing | Destination |
| --- | --- | --- |
| 1 | Worked example | Mechanical §5.1–5.8 |
| 2–5 | Worked/boundary + downstream detector/replay tests | Mechanical §6 B2–B5 |
| 6–12 | Boundary tables + detector tests | Mechanical §6 B6–B12 |
| 13–16 | Lifecycle ledger tests on orchestrator seam | Mechanical §6 B13–B16 |
| 17–19 | Ledger/summary + risk tests | Mechanical §6 B17–B19 |
| 20 | Provenance reason-code tests | Mechanical §6 B20; gates U1–U6 |
| 21 | Independent-sim harness requirement | Mechanical §6 B21 |
| Empirical PASS/FAIL | **Blocked** | Gates U1, U7, U8 |

---

## 2. Dataset evidence inventory

| Dataset / artifact | Verified in-repo? | Role |
| --- | --- | --- |
| `data/` CSV (historical project feeds) | Present locally; **not** certified Exness XAUUSD M5/H1 | Diagnostic / engineering only until provenance audit |
| GC=F / M15-as-M5 style proxies | Referenced in specs as non-qualifying | Diagnostic only — never broker qualification evidence |
| Bid/ask tick history aligned to Demo server | **Missing** | Required for executable fill claims |
| Point-in-time USD HIGH news history | **Missing / incomplete** | Missing ≠ “no news” |
| Warm-up bars for EMA200 / fractal rights | Policy proposed; coverage not audited | Must be measured per feed |

**Rule:** Missing evidence must not become zero cost, no-news, or favorable fills.

---

## 3. Evidence-to-readiness decision table

| Evidence question | Proceed-within-scope if | Blocked if |
| --- | --- | --- |
| Provenance | Broker symbol + TF + server documented | Proxy presented as XAUUSD M5 |
| UTC / closed-bar availability | All decision stamps timezone-aware UTC; forming bars unused | Naive timestamps or lookahead |
| Warm-up / coverage | Gaps counted; warm-up excluded from scored window | Silent gap fill |
| Bid/ask ordering | Sides recorded for entry/exit | Mid-only fills claimed as Demo-realistic |
| Costs | Spread/commission model versioned once | Double-count spread+fee |
| Historical news | Point-in-time availability or explicit `UNKNOWN_NEWS` | Treating unknown as clear |
| Intrabar dual touch | Labeled `AMBIGUOUS` | Favorable path invented |

---

## 4. Versioned run-manifest template

Copy to `docs/experiments/run-manifest-<id>.md` **before** inspecting candidate performance. Leave unknowns blank; do not fill after seeing results.

```markdown
# Run manifest <id>
rule_version: s1-s4-mechanical-v1
candidates: [S1, S2, S3, S4]
legacy_reference_included: true|false
dataset:
  symbol:
  broker_server:
  timeframes: [M5, H1]
  start_utc:
  end_utc:
  split: {dev:, validation:, oos:}
  provenance_attestation:
quotes:
  entry_side:
  exit_side:
  tick_size:
  tick_rounding:
  gap_policy:
  stale_policy:
orders:
  marketability_rule:
  preconfirm_zone_touch_policy:
  sweep_replacement_policy:
risk:
  initial_capital_source: live_balance|fixed_research
  risk_pct: 0.5
  daily_loss_gate:
  drawdown_halt:
  capacity_policy: independent_per_candidate
costs:
  spread_model:
  commission_model:
news:
  source:
  missing_policy: UNKNOWN_NEWS
session:
  admission_windows:
  time_exit: 20:45 UTC
  missing_quote_at_deadline: disclose
stats:
  primary_metrics: [net_expectancy, profit_factor, max_dd, sample_n]
  sample_sufficiency_rule:
  multiple_comparison_rule:
  resampling_rule:
approvals:
  data_owner:
  risk_owner:
  experiment_owner:
  date:
```

---

## 5. Shared controls, independent sims, Legacy isolation

- Shared across S1–S4: H1 bias, pools, sessions, displacement thresholds, SL cap/buffer, 2R baseline, TTL, 0.5% risk with floor/reject (no risk-increasing round-up).
- Simulate each candidate **independently** under the same capacity policy; do not let one candidate consume another’s slots.
- Legacy Reference keeps partial/BE/2.5R labeling; never treat Legacy vs S1 as one-variable structure A/B.
- Conflicts with operational ADRs (daily breaker, ownership isolation, Demo gates) surface here — do not silently override foundation policies from issue #1.

---

## 6. Pre-run registration requirements

| Field | Accepted now? | Notes |
| --- | --- | --- |
| Exact multi-year date range | No — proposal only | 3–5y discussed, not verified available |
| 60/20/20 chronological split | Proposal only | Register before outcomes |
| Sample sufficiency | Unfilled | Must not invent trades to meet quota |
| Net expectancy / PF / DD criteria | Framework only | No post-result threshold shopping |
| Stress / costs magnitudes | Unfilled | Version with manifest |
| Resampling / dependence | Unfilled | Disclose OOS reuse after rule changes |
| Regime/robustness add-ons | Later separate versions | Do not mix into core S1–S4 compare |

Illustrative performance tables in planning docs remain **examples**, not measured results.

---

## 7. Ledger → summary reconciliation fields

Required when an experiment runs:

- Signals, rejects, expiries, fills, exits
- Fixed initial R denominator; planned vs realized cash
- Costs once; MAE/MFE when available
- Session / news / regime metadata or explicit `unknown`
- Ambiguous trades visible in summary counts

Unavailable metadata stays unknown — never imputed to help a candidate.

---

## 8. Test matrix cross-check vs existing seams

| Concern | Existing seam (in-repo) | Gap |
| --- | --- | --- |
| Replay fill / same-bar SL | `tests/test_smc_orchestrator.py`, backtester path | Controlled Baseline 2R mode + ledger summary assertions |
| H1 / sweep / session detector | Detector integration tests | Protected-swing CHOCH + OB/overlap detectors **not** implemented for S2–S4 |
| Risk floor / reject | Lot sizing tests | Keep no-round-up invariant |
| Spread skip fill | Orchestrator spread guard | Must not erase broker-authoritative fills in live bridge |
| Doc contract | `tests/test_s1_s4_mechanical_spec_contract.py` | Docs only — does not prove Pine/broker parity |

Mocks at broker boundary only; do not mock away the detector under evaluation.

---

## 9. Handoff verdict

| Dimension | Verdict | Notes |
| --- | --- | --- |
| Documentation completion | **YES** | Narrative + mechanical §1–9 + this handoff |
| Implementation readiness | **PARTIAL** | Spec clear enough to start failing reproductions for S1–S4; production detectors/OB/CHOCH still incomplete |
| Data readiness | **NO** | Broker XAUUSD M5/H1 + ticks + news not attested |
| Experiment readiness | **NO** | U1–U9 open; run-manifest unfilled |

### Unresolved gates (owner required)

| Gate | Evidence needed | Decision-maker |
| --- | --- | --- |
| U1 Provenance | Attested broker dump | Data owner |
| U2 Quote sides / gaps | Written policy + sample audit | Experiment owner |
| U3 Pre-confirm touch | Explicit admit/reject rule | Strategy owner |
| U4 Sweep consumption | Versioned rule | Strategy owner |
| U5 Capacity/daily research profile | Frozen numbers vs live ADR | Risk owner |
| U6 News PIT | Source + missing policy | Data owner |
| U7 Split dates | Registered calendar | Experiment owner |
| U8 Stats protocol | Sufficiency + CI rules | Experiment owner |
| U9 Intrabar ambiguity | Keep AMBIGUOUS or tick feed | Experiment owner |

Unresolved material decisions **block affected downstream work** only — they do not prevent truthful completion of this documentation review.

---

## 10. Explicit non-actions (issue #4)

- No Pine / EA / production Python behavior changes in this ticket beyond doc contract tests.
- No comparative profitability run, orders, credential/deploy changes.
- No edits/closure of parent issue from this document alone (closure is a separate tracker action after review).
- TSS/GSS, confluence, rejection entry, live trials remain separately authorized.
- `ready-for-agent` ≠ profitability or real-money readiness.
