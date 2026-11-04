# C22 attended Demo preparation, 2026-10-24

Goal: finish preparation possible while the market is closed; leave actual
market-data qualification and owner-approved attended Demo activation/lifecycle.

## Owner decisions and scope

Owner explicitly chose “เตรียม Demo trial บน feed นี้” after being shown the
3/40 direction/admission differences and identical-input controls. Frozen formulas,
actual broker history basis and source pins remain unchanged. The original
`parity_gate=false` remains preserved. A private owner review binds the original
parity document, account fingerprint and release/config cohort, accepting only a
prospective Demo trial. Readiness reports distinguish accepted feed from passed
historical parity; neither grants execution or economic equivalence.

Owner then chose “Demo trial แบบมีคนเฝ้า + backup บน Mac”. For this trial, an
operator-present SSH console and verified Mac snapshots replace deferred Telegram,
external alerts and private cloud recovery. This is an explicit temporary operating
decision, not unattended deployment approval. No paid resource was added.

Current procedure: [attended market-open runbook](../ops/c22-attended-market-open.md).
Earlier preparation/review reports remain historical evidence; their mandatory
cloud/Telegram wording is superseded only for this explicitly attended trial.

## Concrete preparation

- Added explicit cost review helper. It requires exact draft/broker hashes,
  genuine reviewer confirmations, fresh evidence/source checks, USD Demo identity,
  unchanged spec including point conversion, zero-commission historical consistency
  and complete next168-hour calendar. No timestamp-only renewal, overwriting
  financial/policy inputs, SDK calls or execution activation. Cost draft covers
  Oct24–Nov5 and remains unapproved with reviewed_utc=null; actual account-specific
  applicability/notices and cutover freshness must be checked at review time.
- Shadow and execution templates now share `state/cost-policy-runtime.json`.
  Shadow's previously hardcoded inconclusive filename would otherwise require a
  service change during qualification. New path is installed for shadow with
  identical COST_INCONCLUSIVE contents; no cost attestation was manufactured.
  Execution template remains uninstalled and no execution boot enablement exists.
- Staged documented terminal startup configurations with AutoTrading off/on,
  DLL imports off and account/profile-change protection. The enabling configuration
  is reserved for the execution-time approved activation test. Saved chart inventory
  contained32 charts with no `<expert>` sections; file inventory alone is not a
  universal claim about future terminal state.
- Added manual Mac SSH console. Fresh blocked entry is distinct from lost
  heartbeat, unknown protection, safety halt, service conflict or network failure.
  It never contacts MT5 or starts/stops senders. Its local bell cannot provide
  unattended delivery; operator must remain present with Mac awake.
- Actual Mac snapshot download verified SHA256, SQLite integrity and table counts:
  audit8672/events0/kv8, checksum
  `4b04836342e4df3a1af10540dbee4f6b81855dd6e4d28d5f2375bcbeeb934d61`.
  VM's existing cumulative seven-snapshot retention and original financial history
  are unchanged. Mac copies remain private and are not automatically pruned.
  A second snapshot contained9418 audit rows and preserved the original8672-row
  id/payload prefix exactly. The final19-file VM evidence bundle downloaded and
  all manifest entries verified;9 staged sources/configurations matched repository
  bytes. Bundle SHA256:
  `271d5b1456f922e5b52ba9b15bdb8348a4e5670781b7e0d27c983788477edc5c`.
- Offline replay of captured actual broker ledger reconstructed1812.21USD UTC
  baseline. Restart with doubled observed equity retained1812.21, and next-day flat
  reconstruction matched. Only a temporary synthetic journal was written; live day
  state was not seeded, reset or edited. Live market-day history must still reconcile.

## Verification and evidence boundary

Native focused tests cover cost evidence tamper/staleness/spec/currency/calendar,
private atomic publish/no overwrite, bound feed acceptance without rewriting failed
parity, unchanged readiness gates and attended-console failure handling. The final
focused command passed22 tests plus2 cold-history probe regressions. Final Demo
suite passed154 in72.852s; final full discovery passed1036 in117.648s,2skipped.
Compile, dependency,
lint and all9 changed/new Python format checks passed. Global diff whitespace
warnings originate in pre-existing `data/c22h4-demo-trades.md`; it was not edited.
Changed tracked runtime/runbook files pass scoped diff checks.

Actual Windows Python/Wine/QEMU smoke passed4 tests in240.180s on an isolated source
copy with synthetic SDK objects: execution gate before initialize, BUY stop/rounded
TP/no-BE contract, SELL BE on a new closed bar and confirmed partial safety-close
recovery. No real broker send was made. An earlier broader optional emulator run
was stopped to bound runtime; its partial successes are not presented as a complete
passing suite. The clean4-test smoke is the deployment-runtime evidence.

Raw machine evidence: ignored `runs/c22-market-open-finalprep-2026-10-24/` and
VM `~/c22-oracle-compat-evidence/final-preparation/`. Input snapshots/source manifests,
owner decision binding and original failed feed comparison remain retained.

Startup-control experiment caught a real configuration mistake: Enabled=1 with
AllowLiveTrading=0 returned terminal.trade_allowed=true. Shadow gate remained0,
no --execute or order_send existed, and the account stayed flat. The assertion
was preserved; off configuration changed to Enabled=0. Repeated actual SDK probe
then verified connected=true/trade_allowed=false/tradeapi_disabled=false at
07:55:34UTC and shadow restored. Initial cleanup returned1 because systemd had
already terminated the dedicated server; cleanup status is retained separately,
without changing financial/permission assertions.

After this deliberate terminal reset, initialize returned authentication code-6
once. The installed bounded-restart policy restarted once and recovered fresh
execute=false/flat state, no active position/halt/pending outbox, at07:59:52UTC.
This records recovery; it does not establish stable live-market authentication
or explain the broker-side reason. Backup timer remained active. Terminal
startup off/on permission behavior is distinct from successful broker fills.

Cold terminal also returned zero historical deals despite1812.21USD balance.
Probe now requests full epoch history, waits up to60seconds and requires finite
cash, SDK total/count agreement and balance reconciliation before publishing.
Regressions reject empty, count-mismatched and NaN histories, and prove successful
cold-empty→complete retry without order_send. A caller timeout now covers90second
initialize plus60second synchronization. Transient connection-unknown cycles after
explicit restarts are retained, not silently qualified as a successful market soak.

## Remaining actual-market test

Refresh supported costs before starting qualified shadow; record actual start and
observe >=48h/96 new complete M15 across UTC midnight. Retain expected session
closures and strategy rejections separately from unexpected connection/protection
failures for manual review; conservative report does not silently excuse them.
Recheck fresh prices/spec/deals/baseline/costs, approved attended console/snapshot,
one sender and flat reconciled cutover state. Owner approval then allows AutoTrading
enable verification and genuine-signal Demo fill/SL/TP/SELL-BE/close/recovery test.
No forced trade, relaxed risk gate, unattended start or real-money activation.
