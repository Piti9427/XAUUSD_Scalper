# C22 Oracle: attended Demo trial

Owner decisions, 2026-10-24:

- “เตรียม Demo trial บน feed นี้”. Use actual account feed, frozen C22 formulas,
  original 100000 closed-M1 bootstrap and complete-M15 aggregation. Original
  parity remains failed; explanations and identical-input controls are accepted
  only for this prospective Demo cohort. No research return transfer is assumed.
- “Demo trial แบบมีคนเฝ้า + backup บน Mac”. Operator remains present with Mac
  awake and reachable SSH; verified snapshots on Mac replace external alerts and
  private cloud backup temporarily for this trial. Unattended operation is not
  approved. Telegram remains deferred; no new paid resource was provisioned.
- Later instruction: start actual broker Demo trading when Monday's market opens.
  Owner explicitly selected “ยกเว้นเวลา shadow สำหรับ Demo trial มีคนเฝ้า”.
  For Monday2026-10-26 in Asia/Bangkok only, waive48hours/96bars/UTC-midnight
  waiting requirements. This exception is not a passed soak. Current healthy
  observation, at least one fresh prospective closed M15/finite H4 macro, cost,
  Demo identity, risk, ledger, single sender and attended execution-time approval
  remain required. Outside that dated trial, original duration gates still apply.

## Monday follow-up actually scheduled

A single local Codex heartbeat, `c22-demo-monday-readiness-check`, is active for
Monday2026-10-26 at04:45 Asia/Bangkok. Its job is strictly read-only readiness
inspection and notifying the owner to return for the attended session. Mac/app
must be awake and connected. It cannot install/start execution, enable AutoTrading,
attest costs or place/modify/close an order. No VM execution timer was installed.

Automatic approval review rejected the first proposed scheduled task because it
could activate broker Demo orders without attended execution-time authorization.
The created replacement explicitly prohibits every trading/state mutation; it is
not an indirect auto-cutover. Actual owner-approved activation happens separately
in the live attended session after fresh evidence. No additional48-hour wait for
the explicitly dated Monday trial is required.

## Prepared now

The existing Oracle shadow service starts automatically after boot and always
forces gate0 without --execute. Execution template is staged, not installed.
Both templates now use `/home/ubuntu/c22-demo/state/cost-policy-runtime.json`.
That file still contains COST_INCONCLUSIVE. A fresh reviewed policy can replace
this pointer without editing/redeploying the watcher. Original inconclusive and
reviewed evidence files must remain archived.

Private preparation directory: `/home/ubuntu/c22-demo/preparation/`.
It contains readiness/probe helpers, cost draft/review template, bound owner feed
review, terminal startup configurations and execution service template.
Runtime release and strategy pins stay unchanged.

Mac console, run from repository root while physically present:

```bash
caffeinate -i python3 deploy/c22-demo/attended_session.py --watch
```

Run this before and after trial for a new verified cumulative snapshot on Mac:

```bash
python3 deploy/c22-demo/attended_session.py \
  --snapshot runs/c22-attended-session/mac-backups
```

The console reads SQLite consistently through SSH. It never connects MT5 or
starts/stops a sender. Stale/unknown protection, missing heartbeat, safety halt,
network failure or conflicting units demand attention. Closed-session stale
quotes are entry blocking, not a false claim of failed protection. A terminal
bell is local only; do not walk away, close the Mac or regard it as Telegram.
Pending lifecycle delivery remains durable when Telegram is absent; inspect
journal/notes and preserve those events, never mark them sent merely to clear a gate.

## Market-open checks, in order

1. Refresh exclusive read-only broker evidence while flat. This deliberately
   interrupts shadow; do it before starting the qualification interval.

   ```bash
   python3 /home/ubuntu/c22-demo/preparation/prepare_market_open.py \
     --since "$C22_SHADOW_SINCE_UTC" \
     --feed-review /home/ubuntu/c22-demo/preparation/owner-feed-review.json
   ```

   `--since` requires an actual aware UTC timestamp in the past, including
   `+00:00`. The initial report can be BLOCKED: qualification has not run yet.
   Every probe restores shadow and preserves dated evidence. Do not rerun this
   exclusive probe merely to read status during the 48-hour interval.

2. Review Standard Demo tariff applicability, account swap status, current SDK
   spec/deals and dated broker notices. Update the draft if any field changed;
   never change only reviewed_utc. Draft currently covers Oct24–Nov5, including
   US DST. This is modeled dated evidence requiring review, not a claim that
   broker holidays/account exceptions have been checked in advance.

   Copy `cost-review.template.json` to a dated new review file. Supply actual
   reviewer, UTC review/source-check timestamps, exact draft/broker SHA256,
   findings and every confirmation. Template false/null values are intentional.
   Then run with `PYTHONPATH=/home/ubuntu/c22-demo/current`:

   ```bash
   python3 /home/ubuntu/c22-demo/preparation/review_cost_policy.py \
     --draft /home/ubuntu/c22-demo/preparation/cost-policy-v2.draft.json \
     --broker /home/ubuntu/c22-oracle-compat-evidence/market-open-preparation/broker-evidence.json \
     --review "$C22_COST_REVIEW_JSON" \
     --out "$C22_NEW_REVIEWED_COST_JSON"
   ```

   Inputs must be exact reviewed bytes; fresh capture/review within five minutes,
   source check within24hours, unchanged spec (including point conversion), USD,
   flat verified Demo and complete next168-hour calendar are required. Charged
   historical deals block this prepared zero-commission tariff. The helper never
   contacts MT5, starts execution or overwrites any policy/input.

   After checking the output, publish an atomic symlink from
   `state/cost-policy-runtime.json` to the dated reviewed file on this VM. Retain
   the dated source/review/broker evidence together. Shadow reloads the file each
   cycle; do not alter journal day, last_bar, active or halt. Record policy SHA256
   beside the qualification start. C22 v2 lasts168hours; cutover requires a genuine
   supported review within24hours, without automatic timestamp renewal.

3. Except for the explicitly dated Monday owner exception above, observe actual
   market data for >=48hours, >=96 distinct prospective complete
   M15 bars and UTC midnight, with one fixed release/config/account and the
   reviewed policy. History/bootstrap bars do not count. Read the live journal
   without restarting; retain scheduled closures and every rejection/unknown
   state for explicit review. The conservative report does not automatically
   excuse a scheduled quote_stale interval. Distinguish expected strategy/session
   rejections from operational failures using timestamped broker calendar evidence;
   never delete cycles or edit assertions to force a green report. Market-open
   connection, closed bars, bootstrap/entry latency and baseline are real tests.

4. After qualification review, refresh flat broker/spec/deal/cost evidence,
   restore shadow and require a fresh post-start cycle. Verify same-account old
   sender stopped, no trial30 trade on cutover UTC day, journal reconciled/no halt,
   empty pre-cutover outbox and off-VM restore. Compare retained cost/release/config
   hashes. The accepted feed review removes no other gate and never authorizes
   unattended or real-money operation.

5. Obtain execution-time owner approval for this attended Demo session. Only
   then stop the flat shadow and launch the dedicated terminal with
   `/portable /config:Z:\home\ubuntu\c22-demo\preparation\c22-terminal-execution.ini`
   through the existing private Wine launcher/environment. Read EnvironmentFile
   values with the existing Python/json loader; never shell-source credentials.
   Verify exact Demo fingerprint, terminal.connected=true, trade_allowed=true,
   tradeapi_disabled=false, account trade permissions and flat exposure through
   the exclusive read-only probe. Failure restores shadow, no sender start.

   MetaQuotes documents [startup Experts configuration](https://www.metatrader5.com/en/terminal/help/start_advanced/start).
   Actual VM probe showed `Enabled=1, AllowLiveTrading=0` still reports terminal
   trade_allowed=true. Global off configuration therefore uses `Enabled=0` and
   `AllowLiveTrading=0`, verified by SDK trade_allowed=false. Do not rely on
   AllowLiveTrading alone. Enabling uses both1, followed by actual SDK permission
   verification at approved activation. Inspect saved charts for EAs before enabling.

6. With approval/gates still valid, install staged execution unit as
   `/etc/systemd/system/c22-demo-execution.service`, daemon-reload and explicitly
   start it. Do not enable it at boot. Conflicts/After ordering stops shadow;
   verify exactly one unit/sender, new execute=true cycles and no unknown
   protection. A valid frozen C22 signal is required; do not force an order or
   modify 0.01lot, stops, TP, BE or risk limits merely to obtain a fill.

7. Observe request → broker-approved fill → stable position/ledger/SL/TP → SELL
   BE if applicable → complete close/costs. Unknown send/close must reconcile,
   never blind resend. Protection unknown or critical alert requires immediate
   operator investigation, not a casual restart or deleting a halt. While a
   position exists, keep its manager running; do not kill Wine/server to roll back.

8. End trial only after fresh broker-confirmed flat state and closing ledger,
   review persisted events and take verified Mac snapshot. Then stop execution,
   return terminal to `c22-terminal-shadow.ini`, verify AutoTrading off, start
   shadow and verify fresh execute=false/flat state. Leave execution disabled at
   boot. An open/unknown position uses the containment procedure, not these flat
   rollback steps.

Monday does not automatically enable orders. The dated exception removes only
the shadow waiting gates. Remaining work is current market-data/cost/identity
verification and owner-approved attended activation/lifecycle testing.
There is no additional strategy tuning or infrastructure purchase planned.
