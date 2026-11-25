---
id: c22-buy-exit-be
title: Choose the BUY exit and break-even mechanism
labels: ["wayfinder:grilling"]
parent: c22-profit-preservation
status: open
assignee: null
mode: HITL
blocked_by: [c22-baseline-200]
---

## Question

Does causal BUY trade attribution support a small exit/BE change that can improve
the $200 native account without sacrificing any segment's profit or drawdown,
and which bounded hypothesis deserves an economic test?

## Decision inputs

- Inspect BUY profit give-back, MFE/MAE, native protection timing, spread/swap
  drag and cap-related path dependence. These are hypotheses until verified.
- Keep native entries and SELL management unchanged for this mechanism. Do not
  automatically adopt B2 or maxloss_1 from historical $313 aggregate results.
- Attribute retained trades, altered exits, removed trades and replacement
  entries separately. Follow equity and admission effects through later trades.
- Any live decision rule must use only information available at that timestamp.
  MFE after the decision and final realized swap are diagnostic labels only.
- Choose the smallest catalog justified by attribution, or reject the mechanism
  with a reason. Specify parameter ranges, timing assumptions and falsifiable
  predictions before economic execution; do not choose historical best profit.
- If the primary test later fails, require per-trade attribution and allow one
  derived iteration only. Record the consumed budget even if results disappoint.

## Resolution required

Owner-selected hypothesis/catalog or no-go, causal rationale, required parity
regressions, implementation seams and one-derived-iteration stop rule. Leave
profitability unclaimed until separately authorized frozen-protocol evaluation.

## Evidence pointers

- [Regime-filter and risk-mechanics LOYO](../../reviews/2026-11-12-c22-regime-fix-loyo.md)
- [Pause research verdict](../../reviews/2026-11-12-c22-losing-years-pause-verdict.md)
- [Baseline decision](baseline.md)
