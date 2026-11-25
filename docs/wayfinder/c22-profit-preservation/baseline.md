---
id: c22-baseline-200
title: Verify the $200 native baseline and replay
labels: ["wayfinder:grilling"]
parent: c22-profit-preservation
status: open
assignee: null
mode: HITL
blocked_by: []
---

## Question

Which pinned source/config/data/cost set can credibly represent native
`26b8bcd69e043653` at $200, and what evidence must establish replay parity and
risk-cap lock behavior before candidate research is authorized?

## Decision inputs

- Trace market input -> detection -> orchestration/admission -> execution ->
  broker lifecycle -> notification. Separate replay parity, runtime parity and
  broker verification; missing broker evidence must remain explicit.
- Compare the composed research engine with its native control. Inspect UTC bar
  completeness, fills, SL/TP/BE timing, costs, swap and equity accounting.
- Reconcile ledger net, starting balance and final_balance. The historical
  `loopeng.xrun` net_usd field reportedly assumes $200; verify rather than trust
  any convenience metric. Use ledger and final_balance as cross-checks.
- Cover independent segments 2020, 2021, 2022, 2023, 2024a, 2024b25 and 2026,
  plus a continuous $200 path. Pin actual boundaries and input hashes; the named
  segments are unequal periods, not seven interchangeable calendar years.
- Define continuous state carry, warm-up and boundary position handling before
  evaluation. No resets, deposits or relaxed admission to escape cap lock.
- Distinguish risk-cap rejection/lock from missing data, downtime and other
  admission blockers. Specify measurement of net, Max DD, minimum equity,
  risk-cap rejection counts and lock duration without future information.
- Cost evidence must identify both swap-inclusive views, rate units, dates,
  rollover calendar and limitations. No missing-zero substitutions.

## Resolution required

Owner-reviewed baseline manifest requirements, parity checks, accounting/lock
definitions, unresolved evidence gaps and a go/block decision for designing the
two research mechanisms. No new economic run is required to close a planning
decision; absent measurements must remain pending rather than fabricated.

## Evidence pointers

- [Losing-years diagnosis](../../reviews/2026-11-12-c22-losing-years-diagnosis.md)
- [Pause research verdict](../../reviews/2026-11-12-c22-losing-years-pause-verdict.md)
- [Availability attribution](../../reviews/2026-11-12-c22-availability-rootcause.md)
- Existing research entry point: runs/c22-26b8-tuning-loop-2026-11-11/loopeng.py.

## Progress comment — 2026-11-12

Claimed by Codex before investigation. Owner invoked implement and requested
bounded iterative tuning/rechecks in the current chat. Offline implementation
and swap-inclusive research are now authorized; no VM/runtime deployment is
authorized. Baseline resolution remains pending verified evidence and owner
review. Existing uncommitted availability fixes are outside this work.

## Progress comment — 2026-11-12, investigation complete

See [the $200 campaign verdict](../../reviews/2026-11-12-c22-200-profit-preservation-verdict.md)
for pinned manifests, 14/14 native control parity, carry-aware continuous account
results and reconciled ledger/event attribution. Two mechanisms and their single
derived iterations failed the declared improvement gate. No live/broker parity
or cost qualification is inferred. Keep this HITL ticket open pending owner
review; release the active claim before ending the implementation session.
