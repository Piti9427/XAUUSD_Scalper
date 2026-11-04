# C22 terminal-growth research — owner clarification, 2026-10-24

Objective: maximize terminal net profit on one continuous USD200 account from
2024-09-01 through the latest verified quote (2026-10-23), with no capital top-ups,
monthly resets or retrospective trade deletions. Minimum balance and DD are
descriptive, not exclusion gates. A viable result remains solvent, net-positive
after costs and inside the retained position/risk invariants.

Research execution authorized by owner. Active Demo, sender, frozen source pins,
production parameters and readiness gates remain unchanged. Preserve fixed0.01,
single position, risk cap10%, daily loss10%, no recovery. Research may compare
daily loss-count0/1/2; this is explicitly a research contract change, not adoption.

Reuse canonical prepare/replay on the already acquired and hash-bound
171,171,013 Exness Bid/Ask ticks. Use full causal indicator prefix, all recorded
ticks, no gap filling. Mandatory base+swap and price-stress+swap: extra spread
0.20USD/oz plus adverse slippage0.10USD/oz per market fill. Also run the same stress
with hypothetical commission7USD/lot/round trip. Recorded base commission0 and
snapshot point-mode swap long-567.4/short0, point0.001, preceding-business-day UTC
midnight, Wednesday triple remain COST_INCONCLUSIVE, not historical attestation.

Stage1 freezes a finite catalog before execution: incumbent, previously selected
tuned and profitable-exits research configs, one-factor investigations of entry,
exits/protection and daily admission, plus causal SELL context filters. Context
uses only completed bars: closed H4 EMA slope, breakout depth/ATR, or ATR relative
to its trailing96-bar median. No date-specific rule or future outcome feature.

Stage2 freezes one-factor neighbors of the two best Stage1 research cases after
inspecting their full results. This is adaptive discovery, not independent
validation. Cap total configs at80. No unbounded optimizer or claim of a global
optimum. Keep all losing/rejected cases and source/parameter provenance.

Primary conservative ranking maximizes minimum terminal net across base and
price stress; hypothetical fee stress breaks ties, then base net, then stable ID.
Report the maximum-base-profit leader separately if different. No DD, frequency,
monthly-positive ratio or minimum-balance ranking. Require positive net and
modeled survival in all three named cost scenarios for a research selection.
Report rather than conceal any difference between base and conservative leaders.

Accounting audits cover ledger gross/net/commission/signed swap, entry equity,
fixedlot, cost-inclusive risk<=10%, nonoverlap, exact DD witnesses and minimum
observed equity. Record conservative margin-utilization proxy using each trade's
observed adverse excursion; historical broker stop-out rules remain unverified.
Full-result repeats required for incumbent and final leaders; source/input hashes
must match. Check context-filter prefix causality. Reuse relevant deterministic
regressions; add targeted checks only for new research behavior.

Changes are static or use contemporaneously available completed-bar context.
No trade is modified after its outcome becomes known. When a trial loses money,
diagnose the completed run, freeze the next hypothesis, and rerun from the original
start. Retrospective selection is not a guarantee of future profits. All history
has research exposure; no new untouched holdout is claimed.

Artifacts: ignored `runs/c22-terminal-growth-2026-10-24/`; synthesized verdict in
`docs/reviews/`. Update CORE_STRATEGY with the research contract and outcome without
changing active section6.33. No broker connection, order, deployment or cutover.
