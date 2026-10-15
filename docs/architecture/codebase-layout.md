# Codebase layout and module interfaces

The active Demo module is C22H4. Keep operational commands and frozen research
paths stable; organize verification and evidence around those existing modules.
No new adapter layer or pass-through module is needed for folder organization.

```text
scripts/
  c22h4/                 Active Demo detector and sender interface
  trial30/               Admission, journal, broker reconciliation; rollback
  ops/                   Watcher launchers, status and read-only probes
  research/              Frozen campaign/replay modules; original paths retained
  debug/reviews/         Historical offline review reproducers
  smc/, webhook/, pure_b1/ Legacy/research stacks outside current Demo interface
mql5/                    Frozen/native EA, shared cores and no-order harness
config/                  Runtime and pinned research contracts; original paths
  native-frequency/      Native Tester attestation-gated presets
specs/                   Pinned C22 campaign declarations

tests/
  application/           Configuration, CLI, tooling and pipeline contracts
  demo/                  C22H4 and trial30 lifecycle/status/admission
  native/                Native MQL5 host regression tests and C++ harnesses
  pure_b1/               B1 target, capture, parity and safety regressions
  research/              Campaign, replay, search and accounting regressions
  smc/                   Detection, lifecycle, broker/risk/accounting regressions
  webhook/               Webhook setup/lifecycle regressions
  fixtures/              Shared versioned test inputs

docs/
  architecture/          Folder/module map and stable interfaces
  ops/                   Operator runbooks
  specs/                 Current implementation/behavior specifications
  reviews/               Human markdown reports only
  archive/               Historical plans/specifications/notes

data/research_output/review-fixtures/
                         Nine preexisting versioned review inputs, unchanged
runs/                    Ignored generated runs, ledgers, protocols and checkpoints
```

## Module interfaces and seams

| Module | Interface callers use | Implementation and locality |
| --- | --- | --- |
| Active Demo | `make bot-execute`, `make bot-run`, `make bot-status` | `scripts/c22h4` delegates shared admission/journal/reconcile to `scripts/trial30`; one account, one sender |
| Rollback | `make trial30-*` | Retained trial30 contract; concurrent sender remains forbidden |
| Frozen research | Existing `scripts.research.*` imports and CLI paths | Keep source/config/spec bytes and paths pinned; historical snapshots retain original locations |
| Native research | EA inputs and `make native-frequency-check` | Shared MQL5 core and native adapter remain in `mql5`; host regressions under `tests/native` |
| Verification | `python -m unittest discover -s tests` | Same tests/assertions; fixture imports are package-qualified after grouping |
| Archived evidence | Human reports link to immutable data fixtures | Raw outputs no longer mixed with review prose; new campaigns write `runs/` |

The interface is the test surface: Demo lifecycle tests exercise the same
strategy/admission/order-close-report seam as callers. Folder grouping adds
locality without changing that interface or introducing hypothetical adapters.
`main.py` and `smc_main.py` retain legacy roles; neither becomes a C22 sender.

## Paths intentionally retained

- `scripts/research` campaign source paths and byte hashes are contractual.
- `scripts/c22h4`, `scripts/trial30`, native source/include paths, active runtime
  configurations and pinned research JSON/spec paths stay unchanged.
- Historical ignored `runs/` snapshots and their source/artifact hashes are not
  migrated or rewritten. Their old test commands remain historical evidence;
  current commands are listed in `tests/README.md`.
- Only test-path strings change in the read-only scenario coverage inventory and
  GitHub unblock checklist. Scenario IDs, CLI and trading behavior do not change.
- `data/research_output/review-fixtures` is an explicit nine-file allowlist for
  already-versioned historical inputs. New JSON/dumps and every `runs/` output
  remain ignored. Archived no-swap results do not qualify current strategies.

## Verification

Run from repository root:

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m unittest discover -s tests/demo -t .
make native-frequency-check
```

No bot start, broker connection, order, deployment or attestation renewal is
part of a layout migration. Full suite and frozen-source checks establish the
verification scope; they do not establish broker/native economic parity.
