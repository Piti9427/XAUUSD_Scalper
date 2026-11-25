---
id: c22-protocol
title: Freeze the protocol and promotion evidence
labels: ["wayfinder:grilling"]
parent: c22-profit-preservation
status: open
assignee: null
mode: HITL
blocked_by: [c22-buy-exit-be, c22-entry-suppression]
---

## Question

Which fully specified, owner-reviewed protocol should govern future economic
testing, and what evidence would justify proposing a fresh forward shadow rather
than retaining native?

## Decision inputs

- Carry forward the $200 baseline, fixed 0.01 lot, cost-inclusive 10% cap and
  mandatory base+swap/stress+swap views. Missing swap evidence blocks runs.
- Freeze source/config/input hashes, cost rates/calendar, catalog, metrics,
  numerical comparison precision, LOYO selection/tie-breaking and native
  fallback before any economic run. No post-result gate changes.
- In each held-out fold, choose using training folds only. Every segment must
  have net >= native and Max DD <= native in both views, with at least one net
  improvement. Specify how these gates apply to the final fixed candidate and
  the LOYO-selected policy without conflating the two.
- Define continuous-account acceptance explicitly before execution; report net,
  Max DD, minimum equity, risk-cap rejections and lock duration. Carry positions,
  daily controls and mechanism state through boundaries without deposits/resets.
- Specify regressions for native parity, UTC/day boundaries, daily-loss reset,
  BE timing, state carry, accounting and deterministic reproduction. An engine
  regression blocks economic claims until repaired and reverified.
- Define what constitutes a failed mechanism and record the primary plus at
  most one derived iteration. No-go mechanism decisions may yield native-only
  fallback without forcing a campaign.
- All history has been viewed. Treat existing forward-window data as seen;
  choose a genuinely subsequent shadow period with sample sufficiency and
  stopping criteria before observing it. No automatic adoption.
- Future run artifacts remain under ignored runs/. Check resource headroom;
  historical guidance caps workers at two, but actual safe limits and abort
  thresholds must be set before execution. Do not run external scratch scripts
  without inspecting them.

## Resolution required

Decision-complete protocol specification, go/no-go and explicit remaining
execution authorization. If no hypothesis survives, retain native and record no
improvement found. If shadow design remains uncertain, create a new blocked
decision ticket and move that fog out of the map; do not silently leave choices
to the implementer. Runtime implementation, CORE_STRATEGY.md changes and Demo
activation require a separate owner-reviewed next step.
