# C22 Oracle market-open preparation — 2026-10-24

Owner request: “ตรวจสอบให้พร้อมใช้งานอันไนที่ไม่พร้อมก็เตรียมไว้เพื่อตอนที่ตลาดเปิดจะได้ลองใช้งานจริงเลยในการเข้า order ได้”. Preparation and read-only broker verification completed within the existing Oracle VM. Sending remains disabled; market opening is not a sending approval. Frozen C22 parameters and research pins are unchanged. Telegram remains deferred.

## Actual broker checks

An exclusive probe stopped only the C22 shadow service, connected to the dedicated Demo terminal/account, collected evidence, shut down that exact Wine prefix, then restored shadow. No order_send call exists in the probe. Both BUY/SELL diagnostic order_check requests used0.01lot with synthetic stop geometry, not invented C22 signals. Both returned retcode0; calculated margin wasUSD4 and diagnostic stop loss wasUSD10. These results verify API calculations/checking only: stale weekend quotes, AutoTrading off and an unqualified strategy admission still prevent sending.

At06:16:02UTC (13:16:02Asia/Bangkok), account balance/equity/free margin wereUSD1812.21, leverage1000, positions0 and orders0. Demo identity, fingerprint and hedging mode matched. Terminal was connected with trade_allowed=false; account trade_allowed/trade_expert were true. The intentionally disabled terminal permission is an explicit cutover step, not a reason to enable trading during preparation.

Broker XAUUSDm spec: contract100, tick/point0.001, tick valueUSD0.1, minimum/step0.01, maximum200, filling_mode3, stop/freeze levels0. Swap mode1 means points; long=-490.8points and short=0points, triple dayWednesday. At this spec, conversion is0.1USD per point per lot: ordinary BUY rollover=-49.08USD/lot or-0.4908USD at0.01lot. SELL zero is an observed broker field, not a missing-data fallback. Rates can change; these are not historical tariff values.

Read-only history returned41 deals, including38 trade deals. None of those38 recorded commission or fee;3 completed BUY positions recorded swap-0.54USD each betweenOct2 andOct5. This disproves a blanket swap-free assumption and does not establish tomorrow's rate or every account charge.

Raw evidence, diagnostic requests/results and historical swap summaries are under ignored `runs/c22-market-open-readiness-2026-10-24/`. Financial/account credentials were not copied into the preparation release.

## Cost preparation

A v2 draft is staged privately at `/home/ubuntu/c22-demo/preparation/cost-policy-v2.draft.json`. It includes hashed tariff/spec/calendar documents and dated rollover estimates throughNovember1, including the US DST transition. `reviewed_utc` is deliberately null and status is DRAFT_NOT_ATTESTED. Actual runtime validation rejects it. A separate in-memory schema check with the observed capture time passed; no attested file was created and the runtime's COST_INCONCLUSIVE file was not replaced.

Official sources checked2026-10-24:

- [Standard tariff](https://www.exness.com/standard-accounts/): published Standard commission is zero; account applicability still requires review.
- [Exness swap rules](https://get.exness.help/hc/en-us/articles/360014709151-About-swap): rollover21:00UTC in summer/22:00UTC in winter, metals Wednesday triple and weekend schedule. Dated holiday exceptions may change it.
- [Exness trading schedule](https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours): US DST applies to gold; broker notices and actual new quotes govern availability. The weekend maintenance window overlaps this investigation, so weekend connectivity cannot independently qualify weekday execution.
- [MT5 symbol properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants#enum_symbol_swap_mode): points conversion and per-day swap multipliers. This Python SDK did not expose the per-day multiplier fields; no null-to-zero substitution was made.

Before cutover, refresh identity/spec/deals, confirm Standard tariff and account-specific swap applicability, verify dated calendar/holiday notices, and attest supported documents within24hours. Do not refresh only the timestamp. Runtime C22 v2 lifetime remains168hours; the stricter cutover freshness remains24hours.

## Feed parity diagnosis, without retuning

The original feed comparison remains failed:40 signal bars,3direction/admission divergences,8geometry and40indicator differences. Broker history beginsJuly15; archive beginsSeptember2024. Both frozen causal prefixes were retained for the original verdict.

Controlled diagnostics changed only the archive start date, then used identical-feed controls:

| Control | Direction/admission differences | Geometry differences | Maximum H4 EMA difference |
| --- | --- | --- | --- |
| Original causal prefixes | 3 | 8 | 27.2933303 |
| Common July15 start | 1 | 8 | 0.0277327 |
| Identical broker input | 0 | 0 | 0 |
| Identical archive input | 0 | 0 | 0 |

Two direction differences depend on EMA initialization/history depth. Trimming the diagnostic reference explains sensitivity; it does not authorize trimming production history or changing the selected detector. The remaining September11 03:45UTC difference is a real feed boundary: both closes4304.146, but prior96 low is4304.044 on broker and4304.149 on archive. The close breaks the archive low but not the broker low. Both prior lows occur03:15UTC. Identical-feed controls show no implementation mismatch on those inputs; they do not make different feeds equivalent.

These are signal/feed comparisons only, not economic backtests, PnL rankings or profitability qualification. No new no-swap economic scenario was run. Owner review of these explanations and the permitted history basis remains required; parity_gate was not rewritten to true.

## Prepared operational path

- [c22h4_readiness.py](../../scripts/ops/c22h4_readiness.py): native read-only report over a consistent journal snapshot plus fresh broker/parity/cost evidence. It never initializes MT5, sends orders, rewrites financial state or grants execution permission.
- [prepare_market_open.py](../../deploy/c22-demo/prepare_market_open.py): manual Oracle-only workflow with a nonblocking local lock. Requires fresh flat shadow/no halt/empty outbox, verifies source manifest, stops only shadow, runs the exclusive read-only probe, restores shadow even on failure, waits for a fresh post-start cycle, verifies cumulative backup checksum and runs the report. No policy renewal or automatic sending.
- [oracle_broker_probe.py](../../deploy/c22-demo/oracle_broker_probe.py): reusable Demo identity/spec/deal/order_check evidence. Account credentials stay in the existing private config; output contains no password/login/server.
- [c22-oracle-execution.service](../../deploy/c22-demo/c22-oracle-execution.service): reviewed template staged under preparation only. No Install section; not installed/enabled/started. It conflicts with the shadow unit, retains the same durable journal/account guard, checks release hashes and requires an explicit approved cost-policy file. Its existence and successful unit parsing are not readiness approval.

Manual preparation command on the VM:

```bash
python3 /home/ubuntu/c22-demo/preparation/prepare_market_open.py \
  --since "$C22_SHADOW_SINCE_UTC"
```

Set `C22_SHADOW_SINCE_UTC` to the reviewer-selected aware UTC start, including `+00:00`; an empty/future/naive value is rejected. After a supported cost attestation exists, pass `--cost-policy /home/ubuntu/c22-demo/state/cost-policy-approved.json` explicitly. This command interrupts shadow and therefore must not be run during the qualification window merely to inspect status. It refuses to stop when exposure is unknown or active; it is not a recovery tool for an existing trade. Every run keeps a dated evidence directory and never reuses an old probe result after a failed refresh. Readiness exit2 is an expected measured blocker, not permission to change a guard.

Prospective bars count once, only after the selected start, with an aligned closed-bar timestamp and finite macro EMA. Historical bootstrap bars do not count. Mixed release/config/account evidence, execution in the shadow window, stale heartbeat, coverage gaps, protection uncertainty and blocked cycles remain visible. The report is deliberately conservative about scheduled closed sessions: retain them for explicit session-calendar review, never silently discard them. Even a report with no measured blocker returns AWAITING_OPERATOR_REVIEW and execution_authorized=false; exact-cache replay, parity explanations, calendar/deal costs, external monitoring/cloud restore, single-sender/cutover-day and owner approval remain explicit reviews.

## What still requires market-open or owner evidence

1. Fresh broker quotes and actual closed M1/M15 bars;48hours/96prospective completed M15 spanningUTCmidnight. Weekend elapsed time alone cannot provide96 new bars. Deliberate diagnostic interruptions are not continuous soak.
2. Sustained connection/cache behavior under fresh market data, including real entry-window/bootstrap latency. Short stable periods and weekend order_check do not prove fills/close/BE behavior on this emulator.
3. Human acceptance/resolution of feed/history differences without frozen-strategy edits.
4. Fresh supported v2 costs and account-specific calendar evidence; no invented zero swap or automatic timestamp renewal.
5. External monitoring/critical delivery and private off-host recovery remain unconfigured. Local cumulative snapshots/restore are proven; they do not prove remote/cloud survival. Telegram's deferral does not waive this sending requirement.
6. Actual execution-time owner approval, flat account/empty outbox/stopped old sender, cutover UTC-day checks and intentional AutoTrading enablement. Then install/start only the approved execution unit; do not enable automatic boot sending. Do not stop a sender with active exposure as a casual rollback.

Market opening alone cannot satisfy these conditions or guarantee an immediate C22 signal. A trial Demo order must come from the frozen detector and pass current admission; no forced signal or real-money trade was prepared.

## Executed verification and recovery

The complete preparation path ran twice on the actual VM, at06:31:19 and06:34:09UTC. Both probes returned0, restored the shadow service and produced readiness exit2/BLOCKED for the measured open gates. This is the expected conservative result during market closure, not a failed broker connection or a bypassed test. The latest cumulative snapshot contained5294 audit rows,0events and8kv rows. Its SHA256 was
`a1cb40525324011ad195716d11e3407455cd523cd4995986471045dcd2401fc7`.

A30-file preparation evidence bundle was downloaded and all manifest checksums verified. Bundle SHA256:
`124cfdec71625c51ed25ba6f283348a79c24eaf6c3cd9211cd3f44b56ecfafb2`.
Both snapshots restored on the Mac with integrity_check=ok. The earlier5212 audit rows matched the prefix of the later5294 rows exactly byid/payload. Prepared VM scripts/template matched the repository files byte-for-byte. No credential file was included. Raw files and `local-verification.json` remain under ignored `runs/c22-market-open-readiness-2026-10-24/`.

An additional offline replay used the actual pinned Windows venv/QEMU/Wine while shadow remained active. On6588 actual broker M15 bars, BarCache bootstrap took4.281s and final-bar append2.520s. All cached directions matched the unchanged frozen research reference, macro EMA was finite (4207.171342970332), and duplicate polling reused the existing row. Input SHA256 was
`5255ec6461e12d34d521f4e246419ea0a1fe3fb715f1b3df8c7dc6acaec783d3`.
No SDK method or order API was called. These are archived-input calculations on the deployment runtime, not prospective shadow bars or full live-entry latency/fill proof.

Readiness regression was written before the new reporter existed and first failed with ModuleNotFoundError. An initial test's mutation-count assertion incorrectly counted unrelated fixture inserts; it was replaced by a stronger query_only SQLite connection plus exact before/after database comparison. Financial assertions were not relaxed. The final10 tests cover historical/duplicate bars, UTC/finite/closed-bar evidence, changing cohort/disconnects, stale costs/parity/outbox, quote age at probe versus fresh restored shadow, missing dated swap coverage, output protection and mandatory owner review even when all measured prerequisites pass.

Full unittest discovery passed1022 tests in117.929s,2skipped. Final `make test-demo` passed140 tests in72.742s. Repository compile/dependency/lint checks passed; all4 new Python files passed Ruff format checks. Earlier full-run1021/Demo139 results predate the final added swap-calendar case; the focused10 and final complete runs cover it. No frozen source/config hash changed, and the deployed shadow runtime release remains `d091bc6b810e792c`.

The final collected status at06:36:24UTC (13:36:24Asia/Bangkok) showed shadow enabled/active, NRestarts=0, backup timer active, fresh execute=false/positions0/protection=flat and quote_stale. The execution unit was absent from `/etc/systemd/system`. The later offline replay also confirmed shadow active. Preparation introduced no scheduled cutover or automatic activation.

Final template review added explicit systemd ordering after the shadow service,
in addition to Conflicts, so the approved transition waits for shadow stop.
The updated template was staged and systemd-analyze verified again with exit0;
SHA256 `c843db21aa2f09c9d373e4d97638b7167c4fcdda7f35c8cb9589f24ad2ef33eb`.
The earlier30-file bundle retains the preceding template as historical evidence;
`final-ordered-template-status.json` records this final revision separately.
At06:40:26UTC (13:40:26Asia/Bangkok), shadow was still active with NRestarts=0,
source manifest check0, backup timer active,5556 audit rows and fresh flat
execute=false state. The execution template remained uninstalled.
