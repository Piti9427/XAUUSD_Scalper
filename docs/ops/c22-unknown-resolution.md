# Selected26b8 proved-close UNKNOWN resolution

Status: local operator tool; no VM deployment or real incident resolution is
implied. Actual use requires explicit incident-specific owner approval. A generic
continue/issue-closure request is not that approval. No SDK/order/service-control
call exists in `scripts/ops/c22_unknown_resolution.py`.

Automatic broker reconciliation and manual halt resolution are separate. Keep
the existing manager reconciling/protecting any active/UNKNOWN position. This
tool can only resolve `position_identity_unresolved`, `ambiguous_position_identity`
or `position_ledger_unresolved` after a complete CLOSED/SAFETY_CLOSED event has
already set active=None. Unproved/no-fill/held outcomes stay blocked. Other
financial/risk/cost halts are outside this tool's scope.

## Evidence and review

1. Obtain a consistent journal observation and actual complete epoch broker
   packet from the existing read owner. No second SDK reader beside the sender.
   The ordinary evidence exporter defers while halted, so do not pretend it
   produced a resolution packet. If an approved exclusive probe is necessary,
   prepare that concrete maintenance separately, preserve the manager until
   closure is proved, stop only the sender safely, and end the probe before
   applying. No actual probe/maintenance was performed to implement this tool.
2. Packet must retain original request/observation times, exact Demo USD hedging
   identity/account/source/config, connected terminal, flat/noorders, complete
   epoch count and all signed cash components. Full cash and per-position volume
   must reconcile. The owned0.01 opening and complete exit must match the
   persisted request/position and CLOSED cash components. No missing→zero.
3. Read-only planning writes no approval or financial state. It binds the exact
   latched STATE incident ID/hash, CLOSED event/hash, account/current source/
   config, financial KV state, full historical deal bytes and resolver source.
   Packet age<=5minutes. The result remains REVIEW_REQUIRED.

```bash
PYTHONPATH=. .venv/bin/python -m scripts.ops.c22_unknown_resolution \
  --journal /absolute/path/execution.sqlite3 \
  --broker /private/path/actual-broker.json \
  --out /private/new-plan.json
```

The owner review is a separate supplied document, independently SHA256-pinned:
schema1, decisionRESOLVE_PROVED_CLOSED, exact scope_sha256, actual approved_utc,
expires_utc within15minutes, and owner_decision_ref. The tool never creates it,
refreshes its approval time, or treats an arbitrary file path as authority.
The pin must come from the reviewed decision workflow rather than being silently
computed and accepted from an unreviewed adjacent file.

4. Immediately before application, collect a new actual flat proof if needed.
   The final read must be<=5seconds old. New timestamps are permitted only with
   unchanged deal bytes, balance, account/source/config and incident/financial
   scope. Changed costs/cash/deals/state require a new review. Old evidence is
   never re-dated. Approval of one incident cannot resolve another.
5. Use the existing colocated account guard and target journal writer guard;
   any live writer refuses application. Custom relocated account-guard layouts
   are outside this first tool. Applying acquires no broker/terminal ownership
   and sends no order.

```bash
PYTHONPATH=. .venv/bin/python -m scripts.ops.c22_unknown_resolution \
  --journal /absolute/path/execution.sqlite3 \
  --broker /private/path/fresh-actual-broker.json \
  --plan /private/new-plan.json \
  --review /private/owner-incident-review.json \
  --review-sha256 INDEPENDENTLY_REVIEWED_SHA256 \
  --out /private/new-resolution-receipt.json
```

## State and failure semantics

The receipt is privately reserved before mutation. The financial commit appends
OPERATOR_UNKNOWN_RESOLUTION and clears only the reviewed safety_halt atomically.
Account/source/incident/proof/review/source hashes and the actual decision
reference remain in append-only audit. Audit failure rolls back clearing. A
post-commit receipt IO failure cannot roll back the financial journal; inspect
the durable event before any retry. A resolved/changed incident refuses reuse.

No day/loss/baseline/peak/lastbar/cost cutoff, active intent, execution review or
financial event is reset. Notification backlog remains unchanged and does not
act as an order queue: delivery OFF must not make a proved-close resolution
impossible. No external receipt is claimed. The next entry still needs the
runner's fresh native signal/quote and every original admission gate; resolution
itself authorizes no new trade.

Public tests in `tests/demo/test_c22_unknown_resolution.py` cover wrong incident,
untrusted review, stale proof, foreign/pending exposure, incomplete history/cash,
restart/guards, changed cashflow scope, refreshed real observation times,
financial/outbox preservation, non-UNKNOWN halt rejection and atomic audit failure.
