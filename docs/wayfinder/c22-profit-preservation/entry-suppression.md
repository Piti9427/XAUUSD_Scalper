---
id: c22-entry-suppression
title: Choose a causal pre-entry suppression rule
labels: ["wayfinder:grilling"]
parent: c22-profit-preservation
status: open
assignee: null
mode: HITL
blocked_by: [c22-baseline-200]
---

## Question

Can information available before order submission justify suppressing specific
native entries while preserving every segment's profit and drawdown at $200,
or should further entry-filter tuning stop?

## Decision inputs

- Work this decision after BUY exit/BE. Native entry generation remains intact;
  this mechanism may suppress entries, not add entry families or replacement
  signals. Do not combine with the BUY mechanism without a separately frozen
  combination decision and catalog.
- Revisit failed filters and displacement attribution before proposing another
  gate. A better aggregate ledger is insufficient evidence of a new entry edge.
- Distinguish ex-ante observable cost/market estimates from realized holding
  time, completed trade outcome and accumulated swap. No look-ahead features.
- Decompose retained, removed and replacement trades, including blocked trend
  winners and later equity/risk-cap admissions under the single-position rule.
- Freeze a bounded, causally justified catalog or choose no-go. Preserve native
  fixed sizing, cap and other controls outside the declared suppression rule.
- If primary evaluation fails, attribution permits exactly one derived iteration;
  stop thereafter rather than reopening thresholds until a backtest passes.

## Resolution required

Owner-selected causal gate/catalog or no-go, timestamp/data requirements,
predicted trade-level effect, leakage/displacement checks and stop rule. A no-go
closes this decision without requiring another filter campaign.

## Evidence pointers

- [Entry-edge and displacement verdict](../../reviews/2026-11-12-c22-entry-edge-loyo.md)
- [Regime-filter LOYO](../../reviews/2026-11-12-c22-regime-fix-loyo.md)
- [Losing-years diagnosis](../../reviews/2026-11-12-c22-losing-years-diagnosis.md)
- [Baseline decision](baseline.md)

## Virtual-native scope2026-11-13 (approved; mechanism unresolved)

[Virtual-native admission proposal](../../reviews/2026-11-13-c22-shadow-admission-proposal.md)
records the causal continuous-account displacement evidence and proposed stateful
pre-entry veto. Owner approved research-only scope in chat2026-11-13. Implementation and frozen
offline testing are authorized; runtime adoption remains unauthorized. Current H4 research is
separately authorized and continues independently. This note is not a resolution.

## Research evidence2026-11-13

[Virtual-native verdict](../../reviews/2026-11-13-c22-200-virtual-native-veto-verdict.md)
records the full eight-profile comparison pass, unchanged actual risk cap, separate
virtual/actual availability counts, and16pinned-prefix checks. Owner approval was
for research scope; mechanism/adoption resolution remains open for owner review.
