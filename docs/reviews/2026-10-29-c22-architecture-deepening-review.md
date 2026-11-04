# Selected26b8 architecture deepening review

Status: ATTENDED MAINTENANCE SELECTED; LOCAL CONTRACT CONFIRMATION PENDING.
The owner selected all three action adapters and C:typed plans/durable handle.
The proposed prepare/run/read-only-inspect contract is in
`specs/c22-attended-maintenance-deepening-2026-10-29.md`; the new module has not
been implemented. No financial-policy change,Demo rollout or performance
improvement is claimed. This review follows the existing glossary and runtime/
operations changes. It does not reopen frozen research or replace missing
forward evidence. Original23issue scope is16closed/7open after the separately
approved#26publication; remaining#13,#14,#23,#25,#28,#32,#34 stay open.

Evidence update at29October16:42UTC: a genuine native26b8 SELL filled and
initial broker SL/TP were confirmed. BE modification and completed net close
remain unobserved. #25 stays open. See `2026-10-29-c22-native-entry-partial.md`;
this forward evidence changes no architecture candidate or trading rule.

## Recommended first candidate

Deepen attended maintenance for future campaigns. Cost transition,AP measurement
and reboot controllers repeat journal guards and recovery knowledge. The guard
function in cost activation and the AP/reboot guard modules has identical AST;
the AP and preboot `restore_manager` implementations also match. Recent failure
injection exposed why cleanup and manager recovery must remain independent and
why an ambiguous reboot cannot use unconditional restart.

Relevant evidence: `runs/c22-cost-export-2026-10-29/activate_remote.py:73`,
`runs/c22-ap-approved-measurement-2026-10-29-r2/guards.py:31`,
`runs/c22-approved-reboot-2026-10-29/guards.py:31`,and the AP/reboot recovery tests.
These are preserved campaign artifacts,not a supported reusable module today.

A deep operational module could concentrate proof,quiescence,durable action
records and recovery classification while measurement,reboot and cost actions
remain distinct adapters. Existing command/process and temporary SQLite adapters
provide real seams. The deletion test is meaningful: removing that module would
redistribute the same invariants across three callers. Extracting only command
helpers would leave complexity with those callers and add little depth.
Locality improves when one behavioral fix covers all future workflows; leverage
comes from testing the same interface used by operational callers. Preserve all
historical controller bytes and source pins. Financial validation and coherent
cost-generation rules remain their own responsibilities. Strength: Strong.

## Runtime candidates

**First quote and cooldown.** Lifecycle BE management calls the runner's first
quote path (`scripts/demo_runtime/lifecycle.py:188`;`runner.py:371`),which forwards
to selected Admission (`scripts/c22_selected/runner.py:26` and`:38`). That module
combines the quote read with cooldown interpretation,temporary candidate deals
and an active-ownership exception. Current management protection is deliberate;
this is interface friction rather than a newly reproduced trading defect.
Deepening the broker quote module and retaining cooldown decisions locally in
Admission would improve locality. Tests should still cross the public cycle
with existing SDK/deterministic adapters and preserve timing,bar consumption,
cooldown and confirmed BE behavior. A new forwarding module fails the deletion
test. Strength: Worth exploring.

**Startup phase ownership.** Shared CLI imports MetaTrader5 before runner
construction and review validation (`scripts/demo_runtime/cli.py:118`,`:145`),
then initializes it later (`:160`). Selected runner construction and review
installation span `scripts/c22_selected/__main__.py:70` and `execution.py:201`.
A deeper startup module could own SDK-free context preparation,review/ownership
classification,SDK load/init and cleanup. SDK-free local preparation is not
necessarily pure or read-only. Preserve the active/UNKNOWN management exception
and exact review marker/cohort. Existing injected SDK and temporary filesystem/
journal adapters support a real seam. Import,initialize,entry approval and owned
management remain different events. No evidence establishes SDK import/unload as
the cause of the terminal's first exit. Strength: Worth exploring.

**Owned ledger facts.** Admission (`scripts/demo_runtime/admission.py:209`),
selected cooldown (`scripts/c22_selected/runner.py:48`) and Reconciliation
(`scripts/demo_runtime/lifecycle.py:47` and`:94`) reconstruct overlapping identity,
signed volume,cash and exit-time facts. A deep read-only ledger module could
concentrate shared interpretation while callers retain distinct decisions and
ownership strictness. Broad strategy-prefix matching must never replace exact
active-position evidence. Preserve swap-inclusive net,UTC,volume tolerance and
UNKNOWN/no-resend behavior. Keep independent exporter/accounting verifiers
separate so runtime code does not certify itself. This candidate touches money
facts and needs material design review before implementation. Strength: Worth
exploring.

## Artifacts and verification

The Word artifact uses the requested retained System Design template. Every
final page was rendered and visually inspected. The7page document preserves
section geometry,source styles,numbering,bookmarks,footnote,diagram extent and
all preserve-only package parts byte-for-byte. Only the five declared editable
parts changed. The original reference remains unchanged. Full reproduction and
package checks are under `runs/c22-system-design-review-2026-10-29/`.

The HTML report is in the OS temporary directory as required by the invoked
architecture skill. Four candidates include before/after visuals,source links,
deletion tests,strength and test surfaces. Static markup/source-link checks and
six standalone SVG renders passed visual inspection. Live HTML rendering is
NOT_VERIFIED: sandboxed Chromium failed at macOS MachPort registration,and the
in-app browser rejected localfile protocol. No alternate browser surface or
policy workaround was used. The user can open the delivered local HTML file.
Mermaid and Tailwind use the requested CDNs; inline SVG/CSS remain readable when
those dependencies do not load. Responsive layout and live Mermaid execution
are not claimed tested.

The initial recommendation led to the selected typed-plan family; exact local
implementation confirmation remains pending. It is not permission to change a
financial contract. ADR0029's existing
Python execution direction is retained; historical SMC risk rules are not
Selected26b8 policy. The initial candidate review changed no runtime code.
The later separately reproduced local launcher diagnostics fix passed17tests;
see `2026-10-30-c22-maintenance-and-diagnostic-frontier.md`. No VM configuration,
broker order,additional GitHub payload,commit or dependency installation occurred.
