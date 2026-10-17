# Shared MQL5 detector economic cases

Owner requested “ทำเทสเคสที่ได้ผลลัพที่ดีที่สุดออกมา”, then selected
“เริ่ม shared MQL5 detector + tick replay ก่อน”. Native app control is unavailable;
these are modeled economic tick replays, never native Tester results.

Freeze five cases before observing results: Trend Pullback defaults; UTC Session
Breakout windows06:00/12:00,07:00/13:00,08:00/14:00; C22 tuned comparator. Same
native `FrequencyResearchCore.mqh`, compiled as C++17; no detector-rule changes.
Native first-post-close quote geometry is precomputed causally; future ticks
cannot select signals. One consumed attempt/session, including rejections.

Each case has Base+swap (commission0 USD/lot) and COST_SURCHARGE_STRESS+swap
(commission40 USD/lot/roundtrip), zero extra spread/slippage in both. Actual quoted
Bid/Ask remain unchanged. Named commission0 is an archived Standard assumption,
not fresh measured commission. Swap points long−567.4/short0, point0.001,
Wednesday triple/UTC midnight calendar from archived input metadata. Missing or
unsupported rates/calendar blocks every run. COST_INCONCLUSIVE persists.

Use existing verified167622055 paired Exness quotes, requested2024-09-01 through
2026-10-06T17:22:04.296998UTC; actual quotes end2026-10-05T23:59:59.969UTC. Immutable
input: `runs/c22-tuning-loop-2026-10-07/campaign-01/input/`. Reused discovery,
not holdout or current-market verification. Build M1 OHLC from all ticks, then
same native complete-M1 M5/M15/H1/H4 aggregates; compare M15 bars and full historical
C22 detector to frozen Python contract before economics.

Replay uses existing canonical execution bytecode with isolated prepared-frame
and prepared-geometry globals: fixed0.01, USD200, cost-inclusive10% cap, daily10%,
one losing exit/day for new cases and unlimited count for C22 comparator. Native
execution differs: canonical fee charged fully upfront; fee-inclusive BE evaluated
on completed management bars (M5 for new strategies/M15 for C22), strict open-
position UTC-midnight baseline; native EA uses raw-price BE every tick and first-
tick daily baseline. These differences remain explicit; no native economic parity.
Initial risk does not reserve future swap/gaps. No sender, broker, chart API or
Demo contract/attestation change.

Monthly cash books upfront fee by entry month and gross+swap by exit month;
entries/winning completed positions by entry month. Only months full in requested
window and bracketed by actual first/last ticks enter statistics; observed-full
zero/warmup months included. First/last partial and unobserved months labelled.
Internal quote coverage is not proved by endpoint bracketing.

Strict improvement gate, both views: net>0 and>=C22 comparator, DD<=40%, no
bankruptcy, fixed lot/admitted cap, mean entries strictly above comparator,
median monthly net>=comparator and profitable-month ratio>=comparator. If none
pass, report NO_IMPROVEMENT; do not relax gates or call diagnostic champion a
replacement. Rank qualifiers by worst-view median monthly net, worst-view
profitable-month ratio, worst-view net, lower worst DD, higher worst frequency,
then stable case ID. Also report best measured diagnostic case among all risk-
safe positive pairs separately. All10 cells retained, no cherry-picked month.

Before selection: literal fee+swap/account fixture, missing-metadata negative
control, C22 full historical detector parity, fixed0.01/non-overlap/risk/cash/swap
audit, all10 scenarios freshly repeated with whole-result equality. Input/source/
binary/protocol/result hashes preserved; completed resume verifies every artifact and
returns without rewriting. Interrupted campaigns are retained as evidence; no
incomplete resume is accepted. Start fresh directory, rerun all cells/repeats.
Run artifacts only under ignored `runs/native-frequency-economic-2026-10-14/`.
Final synthesized report under `docs/reviews/`; no new Demo/real-money approval.
