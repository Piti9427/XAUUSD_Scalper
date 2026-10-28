# Selected26b8 joint BUY48 addon — retain native

**VERIFIED_COMPLETE; NO_IMPROVEMENT / DD_GATE_FAILED.** Exactly one preregistered
addon J1/d6f493f5f0dbf8b7 was evaluated jointly with native26b8, using one continuous
200USD account and one position. All12 primary paths,6fresh selected-native
repeats and12independent full-tick accounting/DD/signal/capacity/daily-MTM audits
passed. Passing an audit means the recorded result reconciles; J1 itself fails
the frozen DD<=40% gate in every view. Native26b8 remains selected. No Demo
strategy,lot,policy,service or terminal was changed by this research.

## Exact comparison and provenance

Protocol: `specs/c22-daily-addon-2026-10-28.md`. The hypothesis/catalog were sealed
before implementation/outcomes; the execution protocol froze115source hashes at
2026-10-28T15:19:00.151655+00:00, preserving110parent hashes. Protocol SHA256:
`afd70d283fda04a4ddd56bde0bebfe46617eefe8af13678dfe27c7b923f281a6`.
Independent audit SHA256:
`d3d2f48f4c8949fabe2e513a42a01488706e5646f0edf5bf74cc82d9a94fcd26`.
Artifacts: `runs/c22-daily-addon-2026-10-28/`, including FINAL, protocol, source
snapshots, every ledger/context/signal witness, daily row, integrity receipt,
checkpoint and independent verification. Raw outputs remain ignored by Git.

Input is the same exposed Exness tape:171,171,013 actual Bid/Ask quotes and49,729
complete M15 bars. Requested window2024-09-01T00:00Z through2026-10-24T00:00Z
exclusive. Effective final boundary2026-10-23T20:57:59.518Z is lastquote+1ms;
the last day is explicitly partial. Reused historical data is not fresh holdout.
Real-bar producer/independent signal equations matched every row before any new
economic replay. All6fresh native result dictionaries exactly match the frozen
parent comparator, including the fee/cent path's different trade count.

Every path includes modeled swap: historical long−567.4POINTS,short0,point.001,
contract100,UTC-midnight preceding-business-day schedule,Wednesday triple,
weekends0. Current Demo−490.0 is not substituted. Base adds0extra spread/slip/fee;
stress adds.2/.1/0;fee adds.2/.1/7USD perlot roundtrip. Raw and cent differ only
in the negative-exit flag. Broker tariffs/calendar/parity remain unverified:
**COST_INCONCLUSIVE**, not a present-account profit forecast.

## Profit, DD and recovery

| Profile | View / loss flag | Net USD | Final USD | Full-tick DD% | Trades | Min equity USD | Loss streak | Completed / ongoing recovery days |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Native | base/raw |1945.3340|2145.3340|34.2750|460|187.6636|11|125.2020 /60.7781|
| J1 joint | base/raw |1778.0572|1978.0572|48.3198|570|169.3132|18|140.8073 /50.2456|
| Native | stress/raw |1471.8700|1671.8700|37.7301|458|146.9740|11|130.2986 /60.7779|
| J1 joint | stress/raw |1447.3812|1647.3812|57.8451|571|115.6946|17|151.4241 /50.2455|
| Native | fee/raw |1464.5920|1664.5920|38.6710|458|146.4810|11|130.2986 /60.7779|
| J1 joint | fee/raw |1433.8032|1633.8032|58.9821|571|111.8756|17|140.8073 /50.2455|
| Native | base/cent |1945.3340|2145.3340|34.2750|460|187.6636|11|125.2020 /60.7781|
| J1 joint | base/cent |1778.0572|1978.0572|48.3198|570|169.3132|18|140.8073 /50.2456|
| Native | stress/cent |1471.8700|1671.8700|37.7301|458|146.9740|11|130.2986 /60.7779|
| J1 joint | stress/cent |1447.3812|1647.3812|57.8451|571|115.6946|17|151.4241 /50.2455|
| Native | fee/cent |1416.9940|1616.9940|38.6710|457|146.4810|11|130.2986 /60.7779|
| J1 joint | fee/cent |1356.3046|1556.3046|60.1861|571|111.8756|17|140.8073 /50.2455|

Base net falls167.2768USD/8.5989%. Worst6DD rises38.6710→60.1861%; base worst
consecutive-run peak-relative severity17.6910→32.7726%, worst6severity
23.9695→41.2817%. The shorter ongoing recovery is not an improvement in completed
recovery or overall risk: it starts at a different last closing-balance peak.
No new floor,stop rule,lot sizing or forced winner was chosen after the result.

## Why more entries did not improve the joint account

J1 adds a causal BUY prior48high breakout,EMA50/slope4up and the same closed
complete H4EMA200 filter. Native FULL signal always wins arbitration, including
when native admission later fails. Held trades cannot be preempted and there is
no extra slot. All downstream native costs/risk10%/daily10%/loss2/cooldown30min/
fixed.01/SLTPBE remain shared.

In base/raw,570joint trades comprise321native and249addon. Realized contributions
are1123.9758+654.0814=1778.0572USD; this is one account's ledger, not two independent
profits added. Relative to460control native admissions,157identities disappear
and18new native identities enter because the account path changes. Missing
identities have actual joint reasons:busy129,daily-loss-count13,cooldown12,
risk-cap3. Of the129busy cases,127are strictly witnessed as held addon positions;
the remaining2are held native positions. No same-ms busy boundary is ambiguous
in this path. Do not call the removed control trades' PnL additive lost profit.
Capacity/path dependence explains why positive addon contribution alone cannot
establish improvement. Stress/raw and fee/raw each miss158control native
identities,124strictly busy with addon; exact per-path identities remain saved.

## Daily MTM and honest coverage

There are782complete UTCcalendar days plus1partial final day. Flat boundaries use
reconciled realized cash; held boundaries use actual last executable Bid/Ask
strictly before midnight,entry fee and modeled signed swap through boundary−1ms.
Quotes older than60s remain explicit stale-price models. No candle,price or
midnight broker-equity proof was invented. Both boundaries must have known recent
prices or flat cash for the separate recent-price daily subset.

| Base/raw daily metric | Native | J1 joint |
|---|---:|---:|
| Modeled complete days:positive /negative /flat |206 /271 /305|224 /300 /258|
| Modeled mean /median net USD |2.5108 /0|2.2969 /0|
| Modeled worst /best day USD |−71.0124 /237.6470|−114.1690 /237.6470|
| No-entry complete days |449|423|
| Of those,held-exposure days |151|173|
| Complete days with unverified boundary prices |107|132|
| Recent-price complete subset:count |675|650|
| Subset positive /negative /flat |165 /212 /298|175 /225 /250|
| Subset mean net USD |2.1580|1.4580|

J1 has18more modeled positive days but29more negative days,larger worst daily
loss and lower total profit. Fewer no-entry days do not mean daily profit.
The two recent-price subsets have different coverage; their means are not a
matched-day superiority test. Those marks still include modeled swap and are not
observed broker midnight equity. Daily deltas telescope to each finalbalance−200;
partial-day totals are retained separately,never silently dropped. No guarantee
of profit every day,statistical significance or prospective qualification follows.

## Verification and acceptance mapping

13focused deterministic tests PASS. Fullrepository suite:1484tests,275.475s,
OK/skipped2. Source/input validation before/after campaign, independent selector
equations,all12cash/fee/swap/capacity/full-tick paths and6fresh native repeats PASS.
The independent verifier uses separate selector/entry/MTM equations and never
calls the producer selector/attribution/daily functions or replay. It shares the
frozen native adapter and archived tape-audit infrastructure; this is not broker
implementation independence. No Python coverage percentage or runtime MT5 smoke
test is claimed for these offline-only modules.

Independent agent scoped review also PASS: fresh13tests,115sourcepins,
18payload hashes,12audit cells and every daily/source-contribution reconciliation
checked without writes. No correctness blocker found. Root standards review:
new modules are research-only, no broker/network API, no dependencies or runtime
source edits; outputs remain in runs. Root spec review preserves original four
T20 criteria and all frozen gates. Managed Canvas strict TypeScript check:
0diagnostics; no screenshot/render verification is claimed.

| Requirement | Decisive evidence |
|---|---|
| Freeze before outcomes,native priority,no fallback | hypothesis/protocol hashes; `test_current_high_excluded_prefix_causal_and_disabled_control_exact`; `test_native_priority_retains_anchors_and_no_second_admission_fallback` |
| One actual joint capacity/cash stream | `test_joint_account_blocks_native_while_addon_held_and_reconciles_real_contributions`; actual source/capacity audit of every entry/context in12paths |
| Causal complete H4/no fabricated data | `test_incomplete_latest_h4_and_warmup_are_not_carried`;49,729real-bar independent signal rows match |
| Swap/fees/MTM/coverage,no-trade days | `test_signed_swap_fee_and_partial_daily_marks_telescope_actual_net`; `test_stale_actual_price_is_modelled_and_excluded_from_verified_day_stats`; `test_sell_marks_use_ask_and_signed_funding`; `test_flat_no_quote_days_are_known_cash_without_fake_price`;12independent daily vectors |
| Matched audit,no forced winner/no activation | FINAL plus6exact fresh repeats; every J1 DD fails40; retain_native=true/demo_changed=false |

Operational AP/session/boundary/collector/forward gaps remain their own issues.
Closing the bounded addon research cannot close them or establish that live
execution will reproduce the historical result.
