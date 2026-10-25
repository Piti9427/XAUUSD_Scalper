# C22 Selected26b8 actual Demo execution armed for Monday

The existing Oracle VM now runs `c22-selected-execution.service` with
`execute=true`, `MT5_ENABLE_DEMO_ORDER_SEND=1` and broker-verified terminal
AutoTrading enabled. It targets the configured USD hedging Demo account,
fingerprint `c4020d69b754dfb5`, using selected26b8. Both shadow observers and
old execution are inactive. This is an actual Demo sender waiting for permitted
market data, rather than another shadow-only release.

Owner explicitly requested Monday actual MT5 Demo orders when the strategy
matches the real feed. That latest decision supersedes48h/96bar/UTC-midnight
waiting for this limited forward trial. It does not establish historical broker
parity, economic qualification or permission for real money.

## What permits an order

The accepted permission is `SELECTED_DEMO_ARMED_TRIAL`, status
`ARMED_DEMO_TRIAL_WITH_LIMITATIONS`. No failed strict readiness report was changed
to PASS. Exact account/candidate/snapshot/magic/source/config/current-policy
hashes and explicit owner authorization are bound to the permission.

New entries cannot start before Monday2026-10-26T00:00 Asia/Bangkok
(2026-10-25T17:00UTC). The actual trading session still determines when quotes
arrive; a fixed opening minute was not invented. Entry then needs a newly
completed UTC M15 after approval/start, fresh executable quote, finite closed
H4 macro, a selected strategy signal and every existing admission check.
Historical bootstrap is not treated as a prospective fill. Market open alone
never forces an order. Source bars still require all15 observed M1 minutes.

Native28Rules are unchanged: fixed0.01, cost-inclusive10% equity cap, daily10%/
two negative completed exits, negative-net30-minute cooldown, exact BUY/SELL
SL/TP and both-side BE1R. Shared Demo-only identity, exposure, margin, broker
checks, intent-before-send, persisted UNKNOWN/no-resend and protection stay.
Revoking an entry permission does not stop an owned active/UNKNOWN manager.
Armed acceptance persists exact review bytes at startup so a closed-market
restart does not require inventing new readiness or resetting financial state.

## Fresh broker and cost evidence

Exclusive read-only probes were run with all Python senders stopped. The fresh
enabled-terminal probe confirmed exact Demo fingerprint, hedging/USD, zero
positions/orders, connected=true, terminal.trade_allowed=true,
tradeapi_disabled=false and both account trading permissions. Full41-deal
history reconciled to balance/equity$1,812.21. Actual observed trade commissions/
fees were zero. All32 saved charts were checked again before enabling terminal;
no expert sections were attached. No synthetic order was sent.

The new policy explicitly states
`CONSERVATIVE_REGULAR_SWAP_DEMO_ASSUMPTIONS`, `swap_entitlement=UNKNOWN` and
`research_economic_qualification=COST_INCONCLUSIVE`. It is not the old helper's
account-entitlement attestation. Fresh SDK POINTS rates were BUY−490.8/SELL0,
point0.001, contract100USD: regular BUY$49.08/lot/day, or$0.4908 at0.01lot;
Wednesday triple is$1.4724 at0.01lot. SELL0 is the actual SDK value, not a missing
value fallback. Published Standard commission is zero, also checked against
actual deal charges. [Standard tariff](https://www.exness.com/standard-accounts/),
[SDK swap properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants).

An8-date regular schedule uses17:00America/New_York with DST, Wednesday triple
and weekend zero. Dated broker/Personal Area exceptions remain assumptions,
not a guaranteed cost ceiling. No swap-free claim or false confirmation was
created. [Published swap schedule](https://get.exness.help/hc/en-us/articles/360014709151-About-swap).
Existing exact observed commission/swap drift guard remains: even lower actual
swap can block later entries until reviewed. Policy expires2026-11-01T13:25:18Z
(20:25Asia/Bangkok); future entries then require a genuine new review. No automatic
policy timestamp renewal exists.

## Actual deployment evidence

Immutable release:
`/home/ubuntu/c22-demo/releases/selected-0d9ff29ef41e90df`.
Archive SHA256:
`ed65988c46568d25f42a3b0ae2f801a472c490b20c52b503fc5439f0b4a84353`.
71file bindings verified; prior58 deployed runtime files unchanged. Selected
config now binds18 sources; all101 frozen research hashes remain unchanged.
Old policies, units, journals and source releases were preserved for flat rollback.

Before switching: fresh shadow execute=false/flat/no active or halt/empty outbox,
consistent journal backup and retained source manifest. The dedicated terminal
was started with both Experts Enabled=1 and AllowLiveTrading=1, then actual SDK
permissions were verified. Python execution started only afterward. The terminal
and selected manager are the only active trading surfaces on this account.
The old current pointer remains a retained old release, not the active service.

At2026-10-25T13:27:14Z (20:27Asia/Bangkok), actual source/config cohort matched
local hashes, MainPID31184,zero service restarts, exact armed review accepted,
latest cycle execute=true/flat/zero positions and quote_stale. Zero REQUEST audit
events and no broker fill observed. Startup history_unknown1 and transient
algo_permissions_required8 cycles are preserved; the initial too-early flat
verification failed during synchronization, then stable fresh flat observations
passed without restarting or clearing evidence. Market-open stability remains
part of the actual forward trial, not a claimed Sunday result.

Selected `c22-selected-backup.service` now targets the actual execution journal,
with `c22-selected-backup.timer` active/enabled every5minutes. It makes consistent
cumulative local snapshots with integrity/hash/table-count restore verification.
Actual execution and pre-activation shadow snapshots were downloaded and restored
onMac with matching SHA/counts. Source financial rows are not pruned. No cloud
upload or external Telegram/health notification was sent or qualified.

The execution service restarts on process failure; it is not enabled for automatic
boot activation, and the dedicated terminal is a transient service. A VM reboot
requires checking the actual account/positions and restoring the reviewed manager;
do not assume the old shadow boot service is execution. Never kill/restart a
manager casually while it owns active/UNKNOWN exposure. Flat rollback must return
both terminal settings to0 and verify through SDK before shadow.

## Software validation and limits

Full repository1,152tests PASS(skipped2),152.516s. Scoped Ruff and Pyright PASS.
New public tests cover conservative-policy construction and missing/unsupported
swap rejection, both-side Demo fills/BE, real-account rejection, pre-start/stale
bars, exact-policy/account/cohort bindings, stale/changed raw permission rejection,
revoked-review protection, negative swap drift and UNKNOWN no-resend. Independent
Spec and Standards/operational reviews found no unresolved material blocker.

Real archive code agreement was repeated:49,729bars,2,751recorded entry geometries
across6cost/guard paths,zero mismatches. Shared canonical helpers mean this is
not independent algorithm or broker-fill/economic parity qualification. No new
no-swap economic replay was run. No actual future fill or profit is claimed.

Machine evidence is preserved under ignored
`runs/c22-monday-armed-2026-10-25/`: source review/probe provenance, actual SDK
captures, fresh EA inventory, archived release, owner permission/policy hashes,
activation, current runtime/audit proof, backup/Mac restore and tests.

Termius follows the active sender with:

```bash
sudo journalctl -u c22-selected-execution.service -f
```
