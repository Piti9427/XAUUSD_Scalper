# Selected26b8 — agent continuation manual

Checkpoint:31October2026, Asia/Bangkok. Workspace:
`/Users/nopparuj/my-agents/XAUUSD_Scalper`.

**Latest local preparation task is complete at a verified handoff boundary.
Original23-issue goal is incomplete:20CLOSED,3OPEN (#13/#14/#34).** No new VM
deployment was performed. This manual supersedes stale pending-choice/capture
headings in earlier handoff checkpoints; it does not supersede strategy source,
AGENTS.md, exact approval boundaries or the current tracker/runtime.

Document review found an unresolved implementation concern: the local controller
checks broker age against an earlier observation timestamp. A disposable delayed-
read counterexample permits INSTALL after the required five seconds have passed.
Local tests/package completion therefore do not qualify real effect-time
freshness. Close this proof/Interface gap before any rollout; see sections8–9.
[Review findings and corrections](../reviews/2026-10-31-c22-handoff-document-review.md).

## 1. Start here

Read in this order before changing anything:

1. Root `AGENTS.md` and applicable nested instructions. Query Codegraph before
   indexed code lookup; docs/logs/runs may be read directly. Preserve the dirty
   tree. Never read `.env*`, credential files or key contents.
2. This manual, then [OFF-handoff preparation plan](c22-diagnostic-off-handoff-plan-2026-10-31.md).
3. [Notification evidence](../reviews/2026-10-31-c22-notification-handoff-evidence.md),
   [local rollback verdict](../reviews/2026-10-31-c22-fresh-rollback-local-verdict.md),
   and [diagnostic implementation](../reviews/2026-10-31-c22-runtime-diagnostic-implementation.md).
4. `CORE_STRATEGY.md` sections6.50–6.54 and6.69–6.70, current selected config/source
   and [selected runbook](c22-selected-demo.md). These files contain historical
   sections; newer exact decisions do not silently rewrite old evidence.
5. Machine `HANDOFF-CHECKPOINT.json`, test receipts and source inventory in the
   preparation directory defined below. Verify actual file hashes before use.

Do not restart exhaustive tuning, repost #25, repeat a consumed export, or
mistake a previous healthy cycle for current broker/VM safety. No researcher or
maintenance operation is waiting for polling at this checkpoint. Previous agent
turns ended or errored on quota; a draft file/lock alone is not a live process.

## 2. Goal, user intent and current scope

The owner wants a profitable, deployable Demo trading bot grounded in actual
market data, with measurable backtests, MM/DD/risk and explainable failures.
Selected26b8 remains the principal strategy. Max-terminal-profit research was
preferred under observed DD≤40%; this is not a guaranteed future DD ceiling or
permission to remove risk gates. Compounding/lot-growth work remains paused.

The active issue goal is the original GitHub #12–34 in
`Piti9427/XAUUSD_Scalper`. Closed status is often bounded to a study, local
implementation or observed scenario. It does not mean every capability is
activated on VM or future profitability is qualified. Latest filtered tracker
snapshot at31October12:19:47.498UTC found all23issues:20closed and these three
open. This is retained tracker evidence, not a live lookup on every manual read:

| Issue | Actual missing closure evidence |
| --- | --- |
| [#13](https://github.com/Piti9427/XAUUSD_Scalper/issues/13) AP timeline | Incident-matched terminal-owned transport facts, exact process/profile provenance and aligned host/guest timing. Native handoff→lost ordering alone is insufficient. |
| [#14](https://github.com/Piti9427/XAUUSD_Scalper/issues/14) AP repair | Confirm/reproduce one trigger, attempt disproof, change one factor, matched before/after repeat, at least1hour repeat and total24hours including rollover. A healthy interval is insufficient. |
| [#34](https://github.com/Piti9427/XAUUSD_Scalper/issues/34) External alerts | Owner-selected channel/recipient and outbound-test permission, actual receipt/retry/recovery and independent off-VM outage detection. Owner currently chose OFF/DEFERRED. |

The AP observation period does not impose a24hour entry cooldown. Intended
maintenance pause is separately limited to15minutes including recovery. Do not
close these issues merely to make the tracker empty. Do not ask the owner to
choose an alert channel again without a changed need; keep #34deferred.

### Original23issue ledger

| IDs | State | Meaning / caution |
| --- | --- | --- |
| #12 | CLOSED | Bounded staged sender/watchdog verification; new diagnostic candidate is not deployed. |
| #13–14 | OPEN | Causal AP timeline and confirmed repair still missing. |
| #15 | CLOSED | Renewal authority design; does not activate auto-renew. |
| #16–18 | CLOSED | Broker export, dated sources/calendar and cost-incident preservation implementation/evidence. |
| #19–20 | CLOSED | Coherent-generation and opt-in renewal implementation; auto-renew stays OFF on VM. |
| #21 | CLOSED | Alert decision preparation records ownerOFF; delivery #34remains open. |
| #22 | CLOSED | Classifier/report; retained gaps can remain UNKNOWN. |
| #23 | CLOSED | Local account-read timing implementation; local runner change is not deployed. |
| #24 | CLOSED | Operator-resolution implementation; not permission to clear a real incident. |
| #25 | CLOSED | Genuine native signal→fill→BE→close and2brokerdeals audited; exact approved publication completed. |
| #26 | CLOSED | Approved reboot/retry recovery scenario; deep terminal crash cause remained UNKNOWN. |
| #27 | CLOSED | Collector and bounded first batch; not full rawtick/feed parity or profitable forward qualification. |
| #28–32 | CLOSED | Bounded H4/MM/DD/Net-BE/daily-addon studies and synthesis retain native26b8; no new winner/deployment. |
| #33 | CLOSED | Lot compounding remains paused until explicit owner resume. |
| #34 | OPEN | Owner-deferred external delivery and off-VM detection. |

Read the current issue body/comments before any new closure proposal. Public
comment/close is a separate external write requiring exact owner approval.

## 3. Strategy and research context

Active rules ID:`26b8bcd69e043653`; snapshot:
`RESEARCH-C22-SELECTED-20261025-26B8`; magic22261025. Current declared selected
contract uses completed UTC M15 from complete15M1 bars, RSI7cross30 BUY, prior48bar
SELL breakout, EMA50 and closed H4EMA200 context. BUY stop2.5ATR/target3R;
SELL stop2.5ATR/target1.35R; both BE1R under the exact archived geometry/rounding.
Read actual `strategy.py`/archived detector for inequalities and timing; this
summary is not a replacement numerical implementation.

Keep fixed0.01lot, single position, cost-inclusive10%equity cap, Daily10%/two
negative-net exits per UTCday and two M15bars/30minute negative-net cooldown.
Keep fresh quotes, identity/exposure/history/source/spec/cost/margin and
persisted UNKNOWN/no-resend gates. Startup history may bootstrap from genuine
past bars; every new permission still needs a fresh complete prospective M15.
Never synthesize a signal to prove execution. No baskets, martingale or second
sender on the same account.

The frozen5184profile grid is already COMPLETE/audited. It evaluated15552raw
paths plus174cent paths;54profiles qualified under matched conditions, six
selected repeats matched and the independent audit covered15726paths.
Selected26b8 rawbase net1945.3340/final2145.3340USD/DD34.274997%; rawstress net
1471.8700/DD37.730125%; rawfee DD38.671021%. These modeled results start atUSD200,
fixed0.01; retained profit does not automatically increase lot. Read section6.50
and `docs/reviews/2026-10-25-c22-exhaustive-tuning.md` for all matched views.
Its actual quote interval is2024-09-01T22:05:06.129Z through
2026-10-23T20:57:59.517Z:171171013Bid/Ask quotes and49729complete M15bars.
Selected rawbase has460trades, rawstress/fee458. Every view includes modeled swap;
base uses recorded Bid/Ask, stress adds0.20USD/oz spread and0.10adverse slippage,
fee adds hypothetical7USD/lot round-trip to stress. These assumptions differ
from the later Demo policy; do not mix their profits or infer an annual return
without the exact interval and declared compounding convention.

All history is exposed discovery data; COST_INCONCLUSIVE, unverified historical
broker rates/calendar/fills/margin and feed completeness remain. New economic
research must include modeled swap in every base/stress view; missing metadata
blocks it. Never rerank a new no-swap result or reopen frozen pins to improve it.
Four subsequent bounded studies retained native26b8. One observed profitable
Demo lifecycle does not establish future profitability/backtest parity.

## 4. Codebase map and actual runtime path

| Area | Role / first lookup |
| --- | --- |
| `scripts/c22_selected/__main__.py` | Selected entrypoint into shared CLI. |
| `scripts/c22_selected/runner.py` | SelectedDemoRunner and reviewed admission; subclasses DemoRunner directly. |
| `scripts/c22_selected/strategy.py` | Selected rules/geometry, research source pins, H4 cache. |
| `scripts/c22_selected/history.py` | Genuine historical bootstrap/cache binding; never relabel old data. |
| `scripts/c22_selected/execution.py` | ExecutionReview validation and exact accepted-review persistence. |
| `scripts/c22_selected/evidence.py`, `source_packets.py`, `parity.py` | Existing-sender export/source/feed evidence. |
| `scripts/c22_selected/{renewal,renewal_runtime,cost_generations,generations,trial_costs}.py` | Reviewed local renewal/generation seams; not implicit activation. |
| `scripts/demo_runtime/runner.py` | Cycle ordering, broker reads, protection status and optional delivery. |
| `scripts/demo_runtime/admission.py` | Native signal, gates, durable intent before dispatch. |
| `scripts/demo_runtime/lifecycle.py` | Fill/UNKNOWN reconciliation, BE, full close and safety close. |
| `scripts/demo_runtime/broker.py` | Identity, exposure, history, quote/spec and UTC baseline. |
| `scripts/demo_runtime/journal.py` | SQLite KV/audit/outbox and writer lock; never reset financial state. |
| `scripts/demo_runtime/{diagnostics,status,cli,host,costs}.py` | Safe error evidence, availability, launch/watch and cost validation. |
| `scripts/ops/attended_maintenance/` | Local C-v2 typed AP/reboot/cost plans, durable Store, classify/continuity. No production host adapter. |
| `deploy/c22-demo/` | Release builder, units, exact retained launch/probe/ops source. Reading/importing operational scripts is not permission to execute them. |
| `scripts/research/` | Frozen offline campaigns and verifiers. Paths are hashed; do not relocate. |
| `scripts/c22h4/`, `scripts/trial30/` | Retained old contracts/rollback adapters and compatibility imports; never concurrent with selected sender. |
| `scripts/{pure_b1,smc,webhook,reward156}`, `main.py`, `smc_main.py`, `mql5/` | Legacy/research stacks, shared imported helpers and native sources. Not the active selected execution interface. |
| `tests/demo`, `tests/ops`, `tests/research`, other `tests/` | Deterministic tests; real MT5 smoke test is a separate live action. |
| `config/`, `specs/`, `data/` | Versioned contracts, pins and historical inputs. Do not read credential-bearing config/env blindly. |
| `docs/ops`, `docs/reviews`, `runs/` | Runbooks; human Markdown reviews; ignored raw artifacts/checkpoints respectively. |

Actual execution sequence:

```text
c22-selected-execution.service → selected __main__ → shared CLI
→ SelectedDemoRunner / DemoRunner.cycle
→ identity / UTC baseline attempt → exposure + history
→ if owned: reconcile_closed BEFORE spec/quote; complete exit may return here
→ otherwise spec + fresh quote
   → if owned remains: reconcile fill/UNKNOWN/protection using owned state
   → if flat: complete M15 + detector → admission/cost/risk/margin/source/review
             → persist intent BEFORE order_send → reconcile response/UNKNOWN
→ cycle protection diagnostics + journal/audit → optional notification flush
```

The ordering matters: quote_stale can prevent later active protection work,
but does not automatically prevent the earlier broker-history close
reconciliation. Trace `_cycle` on the exact deployed source; the local runner
has a different account-read timing implementation. Do not treat the diagram as
evidence that every guard/protection branch ran during a particular outage.

One account, one sender and no overlapping SDK reader. Legacy `make bot-run`,
`make bot-execute`, main.py, webhook or nativeEA must not launch this version.
For exact seam relationships read `docs/architecture/codebase-layout.md`.

## 5. Deployed versus local: never copy the dirty tree

Observed deployed package:`selected-1c0453dcf92db05d`; service
`c22-selected-execution.service`; Linux Oracle free-tier VM with retained
Wine/QEMU runtime. Remote observations below have their own timestamps; no
claim of a live healthy process is made at handoff.

| Source | Observed deployed | Local / staged |
| --- | --- | --- |
| diagnostics.py | e5e2a1466d37dee4c8f403cc858d3621c20fd76672254dc2a391324af4143cc4 |162f597f97a0680f04b60f6a5327ee5fd86ad72aeacde70f4e4b0d16da267603 locally approved002c patch |
| shared runner.py | ea904a373dbcbc7afd3832d93aeac7dff2aaf18cf90dcc0a8b636fe9a540fd19 |60bab9883f2aff13dc83667caf886b21f0634b608d191239e658b7f2486a0d4b includes local-only midnight timing fix |
| journal.py |0a2c6b85183dd80d7d7ab00f3a99e17c20afd2fcec7e144f04215c9f7a7d9922 |Same retained canonical source; no financial schema repair applied |
| broker.py |b84eef66a94af66872a6ac75eae0ac1fc123a3345dee9755f9443d8d688e9e30 |2805ec74381b3a11a8ad48ff7e3cba1ff329ff54924a5960ad26350d90cd992f; differs from deployed source |

Diagnostics-only package candidate:`selected-f62a174bc1997fe1`, archive
`6a77b78bd1ca4e083053443c1de3899fb878b798bda2ed48942459a8bab351f3`.
It is rebuilt from the exact original archive, preserving deployed runner/broker
and changing diagnostics plus its required config pin.87payloads/78Python
compilations/25bindings verified. Separate candidate sender unit preserves the
exporter flag and changes only two release paths. It is NOT deployed.

Local financial/strategy changes require their own decision and CORE_STRATEGY
update. The old constructor/resource patch4465… remains unapplied and outside
the approved diagnostics002c patch. Do not stack it silently.

## 6. Real evidence and unresolved failure paths

### Native lifecycle: completed, do not repeat publication

Native SELL29October16:15UTC passed through a transient UNKNOWN to FILLED without
resend; BE confirmed next morning and broker close30October06:47:16.472UTC.
Two matching broker deals reconcile netUSD33.84. Independent audit/journal and
owner-approved public comment closed #25 at31October05:57:46UTC:
[approved comment](https://github.com/Piti9427/XAUUSD_Scalper/issues/25#issuecomment-6539815388).
Read `lifecycle-final-audit/approved-publication-execution-receipt.json` before
any tracker work. Approval is consumed; do not repost or reclose.

### Runtime SQLite fault

Actual deployed Journal.put raised OperationalError and sender restarted.
Native SQLite code/root cause was not retained by the old diagnostics. Point-in-
time reader locks do not prove historical cause. No retry, kill, journal-mode or
constructor change is justified from that observation alone.002c adds safe
SQLite code/name/primary-code evidence locally; it is observability, not a proven
repair. Map deployed traceback lines with the frozen deployed source, not the
different local runner. Latest retained restart counter129at06:16UTC does not
prove all restarts share one cause or that sender remains live now.

### Notification capture and reviewed historical CRITICAL

Owner-approved exact collector0e905fd7… ran read-only09:05:12UTC. Snapshot highwater
226307:four rows FILLED/CRITICAL/BE_MOVED/CLOSED, allsent0,2111payloadUTF8bytes.
Private gzip SHAa7423d735aaafd58a0496ebf6e83bf1ef4edb55bab089c62038997034c4ddbdf.
Independent review checked schema, raw digest, exact old cohort and all four
event-value/identity joins in53941contiguous retained audit IDs149901–203841.

CRITICAL reason:`position_unreconciled_180s` at29October21:02:02.891269UTC.
quote_stale/unknown began20:59:02; sender returned MANAGING/confirmed22:00:30.339994
and the same position later BE→closed. This proves historical diagnostic recovery,
not broker SL absence or continuous protection. Public market-break timing is
supporting context, not account-specific session attestation or AP causality.

Owner has NOW acknowledged review of the exact historical raw CRITICAL hash
ef047d12… and selected preparing the OFF-handoff plan. Private acknowledgement
binds the genuine answer reference. This is NOT incident-clearance, current
empty-unresolved proof, deliveryOFF/no-inflight evidence or VM execution consent.
No real operation handle has been prepared from the five-key capture.

STRICT_ZERO maintenance refuses this queue. Normal trading admission does not
gate on pending notification count. `flush(None)` retains rows. Do not send,
delete or mark events sent to manufacture eligibility. Current transport state
and full current protected journal baseline remain unproved.

### Costs and permission age

Original policy raw07513b…/canonical766539… and review1726… remain the retained
bindings. Policy expiry5November09:20:46.969923UTC (16:20:46.969923Thai), based on
the approved29October generation. Recheck genuine files/time; never renew by
touching timestamps.−492POINTS was the approved one-time BUYswap; later−488 and
−474.7observations are not accepted economics. Exact drift, even cheaper, can
block new entries. SELLswap0does not establish Swap-Free entitlement.
Auto-renew remains OFF. Cost blocking is separate from maintenance eligibility.

## 7. Authorization ledger

| Scope | Current authority |
| --- | --- |
| Native26b8 actual Demo trial | Previously armed under exact account/source/config/policy. No real-money or forced order. Revalidate live state before operational claims. |
| Local002c diagnostic patch/tests | Approved and applied locally; no VM deployment. |
| Local held-midnight timing fix | Approved/tested locally; not in deployed runner or diagnostics-only candidate. |
| Sender/watchdog/reboot/cost/export past operations | Only their exact completed scopes. Not reusable blanket maintenance grants. |
| One-shot deal export31October | Consumed; previous request restored. Do not issue another request under it. |
| Bounded notification capture | Specifically approved and completed once. No queue mutation/delivery. |
| Fresh original-source rollback review | Owner chose local preparation. Actual source-bound review issuance/restart still needs execution-time grant and genuine evidence. |
| Historical CRITICAL review + OFF plan | Owner acknowledged exact old row and chose plan preparation. No incident clear, actual OFF use/deploy/SDK/restart/order grant. |
| External alerts/#34 | OFF/OWNER_DEFERRED; no channel/recipient/outbound authorization. |
| Compounding/#33 | Remains paused; no new lot research or increased lots. |
| Commit/push/public closure/new deployment/permission escalation | Require applicable explicit owner approval. Do all concrete reviewable preparation first. |

Do not ask again for already answered design choices or completed capture.
Ask only for genuinely new material scope after exact code/proofs/rollback are
reviewable. Automatic review previously rejected raw payload collection; owner
subsequently approved that specific scope, which completed. That old rejection
is not a current capture blocker or permission for unrelated access.

## 8. Local artifacts: exact roles and validation

Define these path abbreviations for navigation only:

```text
CAP = runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31
PREP = CAP/claude-handoff/diagnostics-rollout-preparation
```

| Artifact | Verified status / limitation |
| --- | --- |
| CAP/local-runtime-002c-implementation/full-rerun-after-fixture |1630tests run:1628passed,2skipped,exit0;531source/test pins stable. Original fixture failures and unrelated ResourceWarning retained. |
| PREP/isolated-source-root/runs/diagnostics-only-release |Diagnostics-only sender package. Not deployment authority. |
| PREP/fresh-rollback-controller |Immutable STRICT_ZERO parent coref09119a2… /tests9cb7b661…;46PASS, Ruff/compile, independent46PASS. |
| PREP/notification-capture-readonly |Executed private capture/owner acknowledgement/independent review. Files0600, directory0700. No secrets or raw rows in public docs. |
| PREP/notification-handoff-candidate |Separate OFF candidate core90ed54a1… /tests2753d89d…;63PASS root+independent; canonical classify reused, exact snapshots and strict delivery proof. Not operationally applied. |
| PREP/native-control-bundle/validation-receipt.json |Generated core79726505…;10packaging tests+63unchanged behavior tests+isolated local import pass. Ten canonical modules copied unchanged. No production host. |
| PREP/host-adapter-source-inventory.json/md |Eight SourceHost methods mapped to26exact retained/current sources; historical scripts have top-level effects and must not be imported/executed as libraries. |
| PREP/read_native_python_metadata.py |Draft stdlib metadata collector. NOT executed on VM; independent preflight receipt absent. Do not infer native runtime compatibility from local test. |
| CAP/lifecycle-final-audit |Final observed lifecycle/approved #25 delivery; do not redo consumed writes. |
| CAP/complete-capture-verification.json |Frozen15successfulpages,48900rows IDs154942–203841; failed page15attempts remain excluded/preserved. |
| runs/c22-closure-delivery-2026-10-30/current-progress.json |Current progress pointer; original goal incomplete. Earlier blocked receipts are historical. |

`1630PASS/skipped2` in historical receipts means a successful1630-test run
including two skips, not1630passed tests plus two more skipped tests.
The ten copied bundle modules match pinned LOCAL canonical source; the six
attended_maintenance modules were not part of the original deployed archive.
The63generated-core behavior tests use repository canonical modules/fixtures
loaded through the source root. Only the separate isolated import loads the
bundled closure. Neither proves that closure's complete behavior on the VM.

Use exact receipts, not abbreviated hashes, for verification. The native
generator reads pinned canonical TRIAL_CONFIRMATIONS via AST and substitutes
identical literal data, avoiding an otherwise unnecessary pandas import chain.
Only that import AST changes; validation rejects source/manifest/import drift.
Build to a new output path, never edit generated files. Independent static review
of generator/probe found no blocker; it did not rerun packaging tests. Native
Python/fcntl/SQLite compatibility on the actual VM remains unobserved.

The source inventory is a frozen historical map. Its method/source references
remain useful; paragraphs saying placement/AST extraction was unselected are
superseded by the validated local native-control-bundle. Do not reopen that
answered local packaging choice. Actual VM placement/compatibility and the
production Adapter are still unproved.

The handoff verifier checks only bytes of explicitly listed files and the531
canonical source/test pins. PASS does not rerun tests, recursively follow every
receipt, verify human authority, refresh GitHub/VM/broker state or establish
readiness. The revised checkpoint explicitly pins the principal test/lifecycle/
package receipts and retained sources listed in the transfer manifest; frozen
old checkpoints retain their original narrower scopes.

Representative LOCAL-ONLY commands (from repository root):

```bash
.venv/bin/python -B \
  runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31/claude-handoff/diagnostics-rollout-preparation/verify_handoff_checkpoint.py \
  --root /Users/nopparuj/my-agents/XAUUSD_Scalper

PYTHONPATH=. .venv/bin/python -B -W error::ResourceWarning \
  runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31/claude-handoff/diagnostics-rollout-preparation/notification-handoff-candidate/test_core.py

.venv/bin/python -B -W error::ResourceWarning \
  runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31/claude-handoff/diagnostics-rollout-preparation/native-control-bundle/test_generator.py

python3 -I -S -B \
  runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31/claude-handoff/diagnostics-rollout-preparation/native-control-bundle/isolated_import_probe.py \
  --bundle runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31/claude-handoff/diagnostics-rollout-preparation/native-control-bundle/bundle
```

Do not rerun stable full1630tests without changed canonical source or a concrete
new concern. Local63behavior tests run scientific fixtures in normal local env;
the separate isolated import proves stdlib loading only. Neither substitutes for
actual Wine/SDK/systemd or AP evidence.

### Controller Module and Interface

The runs-only `CutoverController` Module has this caller Interface. It is not
the canonical C-v2 `Maintenance.prepare/run/inspect` Interface, which retains
its typed AP/reboot/cost families. Do not add another public family or wrapper
Module just to make source-cutover orchestration look deployed.

| Interface | Caller contract |
| --- | --- |
| `prepare(plan, host) -> Handle` |Validates supplied current facts and freezes exact plan/baseline. May create/write separate private `.maintenance.sqlite3` operation store; financial journal stays read-only. Not an inspection command for a real account without operational authority. Repeated exact operation/plan returns original stored Handle without refreshing host/journal proof; changed plan rejects. |
| `inspect(handle) -> receipt` |Reads persisted operation only. No host observation, new proof, effect or recovery. |
| `advance(handle, None, host) -> receipt` |Returns stored/local-prepared state without host effects or fresh runtime attestation. |
| `advance(handle, authority, host, recover=False) -> receipt` |Advances the same operation/phase using exactly bound authority. Once bound/persisted by the first granted advance, authority cannot change; this precedes sender review acceptance. Recover must be strict bool and does not override guards. Driver must reobserve the same Handle after uncertain outcomes. |

`SourceHost` is an internal Seam used by the implementation; `RecordingHost` is
a disposable test Adapter. A production Adapter and finite execution driver do
not yet exist. Eight closed methods keep ordering, continuity and effect intent
inside the Module; callers must not reproduce this state machine in shell.
This provides Locality for fixes and Depth through the small caller Interface.
There is not yet a second operational Adapter proving the Seam works on VM.

| Receipt / error | Required interpretation |
| --- | --- |
| PREPARED / READY / LOCAL_PREPARED_ONLY |Local stored progress; not a grant or trading readiness. |
| WAIT_EFFECT_OBSERVATION |Dispatch returned, but actual effect completion still needs observation. |
| WAIT_UNCERTAIN_EFFECT |Effect/observation may have occurred. Keep same Handle and intent; never resend blindly or create a new operation to escape uncertainty. |
| DEFERRED |Guard failed before admission hold; preserve current manager/state. |
| OPERATOR_REQUIRED |Guard failed after hold. Record exact stage/code and use only already-authorized safe management/recovery. No force-flat or unreviewed source switch. |
| COMPLETE / RECOVERED |Supplied-fact flow/post-start proof completed. Receipt still says `execution_readiness=NOT_PROVED`; not full risk/market/broker or economic readiness. |
| Raised exception / no receipt |Plan/Handle/store/lock/initial prepare failures can escape receipt conversion. Missing receipt is not proof that nothing happened; inspect same operation before any retry. |

Failures retain sanitized stage/code/type and separate primary/cleanup/recovery
categories; raw operational facts remain private. The implementation does full
journal/audit work and synchronous effects; it has no proven wall-time/IO upper
bound. The Interface's timing obligations remain requirements, not a completed
production performance qualification.

## 9. Next work queue: concrete, in dependency order

### A. Finish production host adapter locally

Read the source inventory with its supersession note above. First close the
effect-time freshness concern described below through an explicit Interface/
implementation proposal and delayed-read regression. Preserve frozen candidate
pins; do not silently change money/execution behavior during document review.
Then implement/review the production Adapter and finite driver around the closed
SourceHost Seam, with simulated subprocess/files/clock and disposable SQLite.
Do not execute/import historical scripts with top-level operations. Keep public
C-v2 families and frozen parent/candidate pins intact; a new host scope belongs
in a separate local campaign until reviewed.

| Method | Required proof / missing seam |
| --- | --- |
| observe |Pinned sole physical financial journal/account/store identity; expected unit/process/source/policy/pointers/data; current deliveryOFF/no-inflight/unresolved facts; no credential contents. |
| hold_review |Conditional expected raw pointer transition; durable intent before effect; admissions only, owned management preserved. |
| stop_sender |Fresh post-hold flat/noUNKNOWN, exact PID/start/cohort; verify actual inactivity after ambiguous acknowledgement. |
| collect_broker |One reviewed owned probe, only after exclusive stop; exact Demo/hedging/currency/identity/history/ledger, positions0/orders0, connected/trade permission and request-start/spec timestamps. No order method. |
| cleanup_probe |Exact operation/boot/PID/start/source and owned group; no reused PID, broad kill, terminal/wineserver termination or second reader. |
| install_sender |Expected unit/source artifact CAS and durable receipts; preserve terminal/watchdog/backup/transport and exporter bytes. |
| publish_review |Immutable exact fresh review, conditional pointer/absence transition; original policy/expiry unchanged; no marker DML. |
| start_sender |Only exact selected target, no reader/second sender; observe actual process, canonical acceptance and post-start cycle before claiming recovery. |

Shared gaps: actual delivery barrier, physical journal aliases/alternate copies,
current consistent backup and restore check, non-secret native/guest launch
descriptor, actual runtime metadata, conditional file/unit ownership and cleanup
after timeout. Current local account claim proves one configured store only;
do not claim global exclusion. Source facts supplied as booleans by a fake host
are not real attestations.

Keep tests for lost acknowledgements/crash at every effect, malformed/foreign
bindings, source/policy/pointer races, pending/changed rows, CRITICAL review,
old/new acceptance, stale broker proof, deadline/cleanup, active/UNKNOWN and
sanitized independent primary/cleanup/recovery errors. All original event
id/rawpayload/sent and protected KV presence/value/audit prefix survive.

### B. Prepare concrete runtime rollout for owner review

After adapter/package tests and independent review, produce exact source/probe/
unit/controller hashes, immutable old/new bindings, private reviewed-row scope,
finite duration, backup, recovery and failure actions. Then ask execution-time
approval covering its actual effects. Current plan selection is insufficient.
Do not connect broker SDK or start a maintenance round before that approval.

Before any real effects require current deliveryOFF/no-inflight, exact queue/
lineage and no unresolved critical facts; fresh expected-source journal flat/
noactive/noUNKNOWN/nohalt, full backup and effective identity proof. Hold new
entries; wait for new post-hold flat cycle; verify sender stopped; one probe;
cleanup and full context/continuity recheck. Broker proof request-age/span≤5sec
at actual install/start is REQUIRED. Current candidate calls host.observe before
full journal/continuity/classification/acceptance reads and checks age using that
earlier `observed.at`. A disposable delayed-read counterexample advanced six
seconds before INSTALL; it still dispatched at request age6.17seconds. Thus
snapshot-time checks are implemented, but effect-time enforcement is not proved.
See PREP/document-review-2026-10-31/snapshot-age-gap.json and its reproducer.
Review controller clock sampling after expensive work and an effect-side
authoritative freshness check at the Adapter Seam; current methods do not by
themselves establish this. Decide the smallest valid Interface/proof change
before implementation. Do not widen thresholds or reuse the63tests as proof
that this counterexample is fixed. A slow probe or hash pass must invalidate
earlier proof before effects.

First hold boot/monotonic/UTC origin persists. Stop new work by720seconds, reserve
180seconds within900total intentional pause, preserve authorized cleanup/recovery.
Reobserve ambiguous effects under the same handle; no duplicate SDK/start attempt.
These checks use supplied observations between calls; synchronous OS IO/network
can still overrun.900seconds is a budget/overrun-reporting obligation, not a
verified hard timeout. A production driver/Adapter must prove deadline behavior
while preserving authorized cleanup/recovery and the original time origin.

Actual marker plus globally latest canonical acceptance audit chooses recovery:
original acceptance→conditional exact original review; candidate accepted→fresh
original-source review from genuine current evidence under explicit grant.
Never restore stale review/reset acceptance/restore financial DB/backdate. A new
review needs its new prospective complete M15. Preserve possible live managers;
automatic restart of an already inactive owned/UNKNOWN manager is unsupported
and operator-required, not permission to force-flat or switch source.

### C. Diagnose actual faults and close the remaining issues

Retained-source and passive #13 analysis can proceed independently of diagnostic
rollout. Any fresh VM collection still follows its exact read-only scope and
privilege limits; no second SDK reader or configuration change is inferred.
The diagnostics rollout is needed for the proposed native SQLite error-code
instrumentation, not as a blanket prerequisite for all AP evidence. After a
genuinely approved rollout, reproduce/collect that native code before selecting
a persistence fix. Match #13 process roles/clocks/transport, not host-global counters.
Choose one evidence-backed #14trigger, freeze protocol, disprove alternatives,
one-factor change, matched repeat and1hour/total24hour rollover observation.
Keep #34OFF pending a new owner decision. Prepare exact closure payloads only
when each issue's own acceptance is proven; public write still needs approval.

## 10. Failure rules and invalid shortcuts

- Quote_stale during scheduled closure can be expected, but does not prove AP
  fixed or protection continuous. Keep market-state and transport hypotheses
  distinct. No guessed IP, undocumented binary config or permission widening.
- Revoked/stale entry permission must not abandon owned/UNKNOWN management.
  Do not force a close, clear a halt or reset day/equity/peak/loss/cooldown state.
- Exact cost/spec drift cannot be auto-accepted because cheaper. No fabricated
  calendar/zero swap/Swap-Free entitlement or policy refresh.
- Diagnostic failure needs fixed stage/code/type and validated native details,
  not raw exception/SQL/credential/account values in public logs. Preserve the
  first failure and separate cleanup/recovery outcomes.
- Do not infer all open issues closed from test count, a manifest, one native
  profit or a handoff document. Match evidence to the exact acceptance scope.
- Do not delete/relabel completed artifacts or failed experiment breadcrumbs.
  `runs/` is ignored and must never be committed. Human reports are Markdown;
  machine JSON/CSV/logs belong in runs.

## 11. Supersession, transfer and copy-ready agent prompt

Older checkpoints saying raw capture pending/rejected, owner CRITICAL review
pending or fresh-rollback choice unanswered are historical. Those decisions
were answered and captured as above. VM OFF use/cutover/SDK/restart/incident-clear
are still unapproved. The earlier count3BLOCKED audit was reset by concrete new
progress; do not reuse its count. Final goal-tool read reports `usageLimited`,
not complete or owner-paused. This tool-controlled state does not change the
original objective or grant any missing VM authority; resume from this manual
when the receiving agent can continue.

The prior long handoff has been snapshotted in runs. Its old immutable manifests
refer to their historical bytes, not this current manual. Use the new checkpoint
manifest to verify this delivery. If another agent shares this workspace, give
it this manual and the preparation directory. A Git-only clone lacks all ignored
runs evidence and cannot resume safely. Do not upload private packets to GitHub
or send credentials/raw account artifacts to an outside service. Transfer only
owner-authorized evidence through an approved private path.

PREP/HANDOFF-TRANSFER-MANIFEST.json lists exact file/hash groups for native bundle
inspection, local Adapter/test continuation, sender-package reconstruction and
historical evidence replay. It is a LOCAL inventory, not permission or an
executed transfer. Native import needs the bundle closure; behavior tests need
the source/config fixtures and compatible existing local dependencies. Historical
replay additionally needs its selected raw packets; package reconstruction needs
the original archive and retained builder inputs outside PREP. Copying PREP alone
is insufficient for those latter claims. Missing packets defer their dependent
claim only; they do not block unrelated local design/source work. No clean-clone,
full-backtest or whole-repository reproducibility is claimed by these groups.

Copy this prompt to the receiving agent:

```text
Continue in /Users/nopparuj/my-agents/XAUUSD_Scalper. First read AGENTS.md and
docs/ops/c22-agent-continuation-manual-2026-10-31.md, then its checkpoint manifest
and OFF-handoff plan/source inventory. Preserve dirty tree and frozen pins.

Original goal: close GitHub #12–34; latest20closed, #13/#14/#34open. Selected26b8
remains active Demo contract. Latest local packaging task is validated; no VM
rollout was performed. Owner acknowledged exact historical CRITICAL and chose
preparing OFF handoff plan only. Actual delivery/barrier/current safety facts,
production host adapter and execution-time rollout/SDK/restart approval remain
missing. Do not repeat capture/export/publication, ask already answered choices,
read secrets, clear incidents, change financial rules or operate VM from a plan.

Next: inspect exact native bundle/source inventory; close documented snapshot-
time versus effect-time freshness gap with a reviewed proposal/regression before
operational use. Implement/review production Adapter/driver locally with failure
tests, then prepare concrete source-bound
rollout/recovery for owner approval. Keep real AP/SQLite cause UNKNOWN until
evidence and complete #13/#14acceptance; keep #34OFF. Verify each claimed step
against current source/artifacts/runtime. Do not mark original goal complete
while any required issue/evidence remains open.
```
