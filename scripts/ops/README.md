# Operational interfaces

Current Demo commands remain in root Makefile:

| Command | Role |
| --- | --- |
| `make bot-status` | Local journal/watcher status |
| `make bot-once` | Read-only Demo cycle |
| `make bot-run` | Watcher interface; use current runbook/environment gates |
| `make bot-execute` | Demo order-sending interface, existing readiness/owner gates |
| `make trial30-*` | Retained rollback |

Implementation launchers and Wine script paths stay in this folder because
watcher detection and account identity depend on them. Probes/history/export and
legacy validation programs are separate commands, not alternative senders.
[Runbook](../../docs/ops/c22h4-demo.md) ·
[Module/folder map](../../docs/architecture/codebase-layout.md).
