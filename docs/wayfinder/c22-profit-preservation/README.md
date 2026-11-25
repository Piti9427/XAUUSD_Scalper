# Local Markdown tracker operations

Canonical map: [Preserve C22 trend profits from a $200 starting balance](map.md).

Implementation continuation: [C22 optimization handoff](../../reviews/2026-11-13-c22-optimize-implementation-handoff.md).
Read it before resuming; research passed, runtime implementation/adoption remains separate.
Ticket metadata lives in YAML front matter. `parent` and `blocked_by` contain
stable local IDs, not filenames. Human-facing references use linked titles.

## Inventory and frontier

Read the map first, then ticket front matter. Open tickets are intentionally not
listed in the map. Initial ticket inventory:

| Ticket | Dependencies |
| --- | --- |
| [Verify the $200 native baseline and replay](baseline.md) | None |
| [Choose the BUY exit and break-even mechanism](buy-exit-be.md) | Baseline |
| [Choose a causal pre-entry suppression rule](entry-suppression.md) | Baseline |
| [Freeze the protocol and promotion evidence](protocol.md) | Both mechanism decisions |

The frontier consists of tickets with `status: open`, `assignee: null`, and all
`blocked_by` tickets closed. Initial frontier: **Verify the $200 native baseline
and replay**. Work BUY exit/BE before entry suppression; the dependency graph
allows both to become visible after baseline resolution.

## Claim and resolve

1. Inspect current metadata immediately before claiming. Set `assignee` to the
   developer driving the session before starting ticket work. Another assignee
   means claimed; coordinate rather than overwrite. Local files do not provide
   atomic multi-user locking, so use one writer per ticket.
2. Open only relevant evidence. Agree domain terms and material decisions with
   the owner in chat; do not answer the owner's side of a HITL decision.
3. Append a dated `## Resolution comment — YYYY-MM-DD` containing the answer,
   owner decision/context pointer, evidence links and remaining limitations.
   Leave the original question intact. Do not close on an unverified hypothesis.
4. Set `status: closed`; append one linked title and a one-line gist to the map's
   Decisions so far. The full answer belongs only in the ticket.
5. Create newly precise tickets first, then wire dependencies; remove their fog
   from the map. Resolve at most one decision ticket per session. Release an
   unfinished claim by returning `assignee` to null with a progress comment.

## Scope and evidence discipline

If a ticket proves out of scope, close it with the reason and link it under
Out of scope, not Decisions so far. This tracker has no native blocking support;
`blocked_by` is the local dependency convention. Charting closes no tickets.

Before future economic execution, resolve the relevant decisions and obtain
authorization for that next work. Save machine outputs under ignored runs/;
link artifacts rather than pasting trade dumps into tickets. Never publish this
local map externally or commit it without explicit authorization.

## Offline implementation and reproduction

Owner subsequently invoked implement with iterative rechecks. Research adapter:
scripts/research/c22_profit_preservation.py. Campaign entry point:
scripts/research/c22_profit_preservation_campaign.py. This does not activate Demo
behavior. Read [the completed campaign verdict](../../reviews/2026-11-12-c22-200-profit-preservation-verdict.md)
before starting another run; the original two mechanism budgets are exhausted.

For a separately authorized new primary campaign, from repository root:

```bash
.venv/bin/python -m scripts.research.c22_profit_preservation_campaign freeze runs/<new-campaign>
.venv/bin/python -m scripts.research.c22_profit_preservation_campaign run runs/<new-campaign>
```

Freeze refuses an existing protocol, records source/input hashes and copies
Python source snapshots. Run verifies those hashes before loading data. Existing
local ignored input datasets and archived native cell/config are required;
missing inputs fail rather than trigger acquisition. Use a new output directory
after failure; automatic resume and overwrite are intentionally unsupported.
Unit checks need no historical tick datasets:

```bash
.venv/bin/python -m unittest tests.research.test_c22_profit_preservation
```
