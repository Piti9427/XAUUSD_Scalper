# Selected C22 research candidate to shadow and Demo

Owner selected `26b8bcd69e043653` on2026-10-25 for bot testing after the frozen
5,184-profile grid and independent audit passed. Implement the exact selected
Rules as a new adapter. Current C22 remains a retained rollback contract;
do not rewrite frozen sources/configs or their archived backtests.

## Fixed behavior and identity

Archived RSI7cross30 BUY/EMA50 and prior48 SELL/EMA50, closed H4EMA200; complete
UTC Bid M15 assembled from all15 observed M1 minutes. BUY SL2.5ATR/TP3R;
SELL SL2.5ATR/TP1.35R; both BE at1R on a newly completed bar. Fixed0.01,
cost-inclusive10% risk cap, daily10%/two negative completed positions per exit
UTC day, one position, all sessions, no baskets or lot growth. Negative net
including commission/swap/fee triggers30elapsed-minute cooldown, including
across UTC midnight/weekends. Compare the signal's first executable quote time
to cooldown expiry, not a later polling clock; reject/consume an ineligible bar.

Snapshot `RESEARCH-C22-SELECTED-20261025-26B8`; magic22261025; C22_ comments,
separate config `config/c22-selected-demo.json`, journal/cache/evidence paths.
Use existing C22 cost-policy family, broker identity, lifecycle, persistence,
daily baseline and local account writer guard. Include selected adapter code
in release/cohort hashes; code/source/config drift blocks new admissions.

## Interfaces and pre-agreed test seams

- New `scripts/c22_selected/strategy.py`: fixed contract verification, causal
  cache and canonical entry geometry. Assert all28 native Rules exactly match
  the selected research ID. Test both directions, cache divergence, missing
  warmup, UTC data, rounding and risk-cap boundaries.
- New runner uses shared DemoRunner and Admission through a focused cooldown
  adapter; no copied execution/lifecycle. Test public cycle with fake broker:
  shadow has zero sends; BUY/SELL fills and BE; loss count2; negative-swap
  cooldown boundary/UTC/restart; ambiguous sends never resubmit; journal and
  cohort/source drift cannot mix strategies. Preserve old Demo regressions.
- New CLI uses shared injectable CLI, explicit separate identity/config and
  journal. Shadow is default even with inherited send environment. Actual
  sending remains blocked until new-candidate readiness evidence is reviewed;
  the old Monday waiver/feed review is not transferred.
- Offline parity reads real archived bars, independently uses selected native
  Rules/frame and adapter decisions on identical quotes/spec/cost/account state.
  No new no-swap economic run; this is behavior agreement, not new profitability.

## Operational scope

Read actual VM/unit/journal state first. Stage a new deterministic release,
preserve the old release/current pointer and all financial evidence. Never run
two broker clients/senders on the same terminal/account. Before a shadow switch,
verify no active/UNKNOWN managed position, backup old evidence, stop only the
old shadow observer, verify stop, and make a fresh exclusive read-only broker
probe. Retain pending notifications rather than deleting or forging delivery.

New shadow uses gate0, AutoTrading disabled, new journal/cache and explicit
single-host ownership. A closed market/stale quote or unreviewed cost policy is
reported as a blocker, not bypassed. Start operational evidence on genuinely
new prospective bars; bootstrap does not count as forward observation.

Fresh cost/calendar/account review, new-candidate feed/parity, shadow review,
flat/outbox/identity/risk evidence and owner execution-time Demo decision remain
required for sending. No cost attestation, trading timer, auto-cutover,
cross-host failover, real-money deployment or new financial-risk waiver.
Forward economic review/sample endpoints remain to be agreed before that cohort
is frozen. Historical DD<=40% does not guarantee future maximum drawdown.
