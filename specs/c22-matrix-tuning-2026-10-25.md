# C22 matrix tuning — prospectively bounded continuation

Owner authorized iterative offline tuning of the audited matrix. Objective:
maximize full-history base terminal net, stress net as tie-break, then smaller
maximum observed equity DD. Retain matched original research9e511d195c52ef3d
base/stress floors, positive net and modeled survival; DD<=40% in every reviewed
raw/cent base/stress/fee view. Streak and recovery remain disclosed trade-offs,
not additional hard gates. Report their separate Pareto alternatives.

Start from matrix row20 / aab846c7292da8b6. Use existing canonical detector and
replay, fixed0.01, original200USD continuous account, cap10%, daily10%, count2,
single position, no top-ups/recovery/lot increases. Do not change Demo, frozen
archives, canonical replay, management cadence or swap accounting.

Freeze this ordered local domain before outcomes:

- BUY target R: 1.35,1.5,2,3.
- SELL target R: 1.25,1.35,1.4,1.45,1.5,2.
- Cooldown elapsed M15 periods after a negative net exit: 0,1,2,4.
- SELL stop ATR: 1.5,2,2.5.
- BUY stop ATR: 1.5,2,2.5.
- Global BE activation R: 0.5,1,1.5. This changes both sides; SELL target below
  activation can fill before protection activates. Not BUY-only management.
- BUY protection: off,break_even.

Run at most two coordinate rounds. Each round freezes all unseen one-factor
neighbors of its incumbent before running any of that round's outcomes.
Maximum36new contracts (18neighbors per round); deduplicate by full Rules.
Round2 combinations are adaptive discovery and explicitly inherit Round1's
observed winner. If no fully qualified rank improvement, stop. If improvement
continues at round2, report budget exhaustion, not convergence/global optimum.
Raw base/stress/fee for every declared candidate. Cent in every raw-qualified
candidate, never only top2. Rank fully reviewed candidates only; keep incumbent
if none improves it. All failed cases remain saved, no forced replacement.

Same171,171,013 actual Exness Bid/Ask ticks, completed BidM15 input and price
cost scenarios through2026-10-23. Every economic view includes the named static
modeled swap policy; missing/unsupported metadata fails closed. Retain
COST_INCONCLUSIVE for unverified historical rates/calendar/commission and broker
parity. No untouched holdout exists. Repeated optimization increases selection
exposure; yearly/monthly attribution is descriptive, not fresh validation.

Freeze source/input/benchmark hashes and per-round catalogs; resumable atomic
cells with integrity proofs. Reproduce initial incumbent's six full results
exactly; repeat final selection's six full results. Audit all saved cash, swap,
initial risk, daily-count/cooldown admissions and independently reconstruct
selected full-tick DD. Recovery diagnostics must require an actual closing
balance below peak, so waiting without drawdown is not called recovery; retain
legacy measure separately for comparison. No protected net loss is relabeled.

Export research-only Rules descriptor; native Rules values outside the existing
frequency adapter's domain must never be silently exported as a runnable Demo
config. Update CORE_STRATEGY and a human report after outcome. Machine outputs
under runs/c22-matrix-tuning-2026-10-25; preserve prior matrix/artifacts.
