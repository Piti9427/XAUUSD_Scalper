# Python modules

| Folder | Role | Entry point |
| --- | --- | --- |
| [c22h4/](c22h4/) | Current frozen Demo strategy | `make bot-run` / `make bot-execute` |
| [demo_runtime/](demo_runtime/) | Shared Demo execution, CLI/host/status | Used by both strategy adapters |
| [trial30/](trial30/) | Retained rollback strategy and compatibility imports | `make trial30-*` |
| [ops/](ops/) | Launch/status/history/read-only operations | Existing `python -m scripts.ops.*` commands |
| [research/](research/) | Frozen research and economic replay | Existing module paths; do not relocate pinned sources |
| [debug/reviews/](debug/reviews/) | Historical offline counterexamples | Read its README before running |
| [smc/](smc/), [webhook/](webhook/), [pure_b1/](pure_b1/) | Older stacks and research modules | Outside current Demo sender interface |

[Complete layout and seams](../docs/architecture/codebase-layout.md).
Root `main.py` remains legacy alerting; runtime commands/strategy contracts are
unchanged. No second sender on current Demo account.

Shared Demo execution lives in `demo_runtime/`; `c22h4/` supplies the selected
strategy, notes and cache, while `trial30/` retains its rollback adapter and
compatibility imports. Stage-specific tests/commands:
[architecture map](../docs/architecture/codebase-layout.md#debug-entrypoints).
