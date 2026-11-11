# Forward test plan — candidate B2+maxloss_1 vs native 26b8 (2026-11-11)

Status: **PLAN — awaiting owner approval to implement.** No VM change, no contract change.

Candidate under test (from `docs/reviews/2026-11-11-c22-26b8-tuning-loop.md`):
- **B2:** BUY-only break-even moved on a fresh intrabar quote at 1R (polled ≤5 s). SELL keeps the bar-close BE.
- **maxloss_1:** stop new entries for the rest of the UTC day after the first losing exit (native allows 2).

In-sample backtest (7 yearly $313 accounts, base):

| Metric | native | B2+maxloss_1 |
| --- | --- | --- |
| Mean per month | $13.89 | $17.45 |
| Profitable months | 46.8% | 53.2% |

Every historical year is already used, so only data after **2026-10-24** is clean.

## Track 1 — model forward replay (no VM change; start now)

Same tick engine, unseen months, both profiles side by side.
- **Data:** Exness public tick archive monthly zips. The October 2026 zip is complete and November 2026
  is growing; HEAD returned 200 on 2026-11-11.
  - Forward window: 2026-10-24 00:00 UTC onward.
  - October 1–23 is used only as indicator warm-up, already seen, so it is excluded from stats.
- **Build:** reuse `public_exness_archive.import_month` with sha-pinned zips (same builder as the 2020-22
  holdout). Each update appends a new month or extends the current one. Earlier months stay frozen and hashed.
- **Profiles:** native vs B2(5 s)+maxloss_1, run by the parity-checked `loopeng.py`.
  - One continuous $313 account started at 2026-10-24 (live-like).
  - A monthly $313 reset view for comparing month to month.
- **Views:** base+swap and stress+swap. Current broker swap applies (COST_INCONCLUSIVE).
- **Cadence:**
  - A partial-month snapshot every week, informational only.
  - The official record at each month close, once the archive month is complete.
- **Protocol:** freeze `runs/c22-forward-2026-11/protocol.json` before the first forward month is
  evaluated. It holds the profiles, gates and window, and its hash goes into every report.

### Gates (predeclared, both views)
Evaluate after **≥3 complete forward months AND ≥60 native trades**, whichever comes later.

| Gate | Rule |
| --- | --- |
| Mean monthly net | candidate ≥ native + $1.00 |
| Profitable months | candidate ≥ native |
| Worst month | candidate ≥ native − $5.00 |
| Max DD (continuous) | candidate ≤ native + 2 pp |

- **Pass:** all gates pass in both views. Track 1 PASS → eligible for Phase 2 review.
- **Early kill** (checked at each month close): candidate behind native by > $60 cumulative in both views
  after ≥2 complete months → stop. Native stays; no more tuning on that data.
- **Inconclusive:** the gates neither pass nor kill at 3 months → extend by up to 3 more months, then decide
  with the owner.
- Each month close runs the standing root-cause attribution (side × outcome, slot, cap) whatever the result.
  It is diagnostic only and does not retune the candidate.

## Track 2 — live runtime observation on the Demo sender (needs owner approval to deploy)

The live Demo keeps trading **native 26b8**. The sender only records what the candidate would have done.
1. **B2 observe** (already implemented locally, CORE_STRATEGY 6.66): journal `BE_TRIGGER_INTRABAR_OBSERVED`
   when an open BUY first reaches 1R on a fresh quote.
2. **maxloss_1 observe** (new, small): when native admits an entry on a UTC day that already has one
   owned losing exit, journal `MAXLOSS1_WOULD_BLOCK` with the bar, side and the outcome once the trade closes.
   No admission change.
3. **Runtime health gate:** before deploy, measure the cycle interval read-only from the VM journal. After deploy:
   - cycle p99 and lock/busy errors no worse than the 7-day baseline;
   - `be_trigger_lag_ms` p95 ≤ 5 s.
4. **Deploy steps** (owner-attended): local tests → new release/fingerprint → maintenance revoke at flat →
   deploy → verify → resume. Rollback = previous release.

Track 2 checks that the live runtime can execute the candidate faithfully:
- trigger latency;
- modify feasibility, i.e. that the stops/freeze level allows BE at the trigger moment;
- that would-block days match Track 1's model on the same days.

Gate: ≥10 BUY intrabar observations and ≥5 would-block events, each reconciled against the Track 1 replay
of the same trades. Any mismatch is root-caused before Phase 2.

## Phase 2 — switch the Demo to the candidate (after Track 1 PASS + Track 2 healthy, owner approval)
- `max_daily_losses=1` is part of the research `Rules`, so this is a **new research RulesID** as well as
  the new runtime contract (B2 acting).
  - New snapshot, CORE_STRATEGY section, config, pins, release fingerprint.
  - Owner-attended cost-generation review, because the installed generation is bound to 26b8.
- Native stays the rollback contract. Same magic/prefix, so loss/cooldown history stays continuous.
- Post-switch watch for ≥8 weeks. Revert to native if:
  - realized net trails the Track 1 native shadow by > $60 over any 4-week span; or
  - any runtime safety incident (UNKNOWN / blind-resend risk) cannot be resolved.
- Real money remains PROHIBITED throughout.

## Timeline (approximate)

| When | Step |
| --- | --- |
| Now | Approve plan → build Track 1 tooling, freeze protocol, first partial snapshot (Oct 24 – Nov 11) |
| Now + approval | Implement maxloss_1 observe, tests, VM latency read, deploy Track 2 (attended) |
| Early Dec 2026 | November complete → first official month |
| Early Feb 2027 | ≥3 months (Nov, Dec, Jan) → Track 1 gate decision |
| After pass + ≥10 BUY triggers | Phase 2 review with owner |

## Limits
- Three forward months is a small sample. Gold regime may stay trend-like, the regime where native already
  does well and maxloss_1 gives back profit.
- Exness archive ticks are not identical to MT5 terminal fills; Track 2 covers part of that gap.
- Swap entitlement and historical swap remain UNKNOWN (COST_INCONCLUSIVE).
