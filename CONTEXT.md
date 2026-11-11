# Current domain glossary

Trading rules and risk math: [CORE_STRATEGY.md](CORE_STRATEGY.md).
Operational commands: [Selected26b8 Demo runbook](docs/ops/c22-selected-demo.md).
Module/debug map: [architecture](docs/architecture/codebase-layout.md).

| Term | Meaning |
| --- | --- |
| C22 Demo | Current Selected26b8 adapter in scripts/c22_selected on the existing Exness Demo account; snapshot `RESEARCH-C22-SELECTED-20261025-26B8`, RulesID26b8bcd69e043653. Actual armed Demo execution requires exact-cohort owner review. No real-money authorization. |
| Legacy C22H4 | Retained frozen rollback adapter in scripts/c22h4, snapshot RESEARCH-C22-H4EMA200-20261004. Never run alongside selected execution on the same account. |
| trial30 rollback | Retained SELL-only D48 strategy, snapshot `RESEARCH-D48-SELL-BE1R-20261001-T030`. Separate contract; never concurrent with C22 on one account. |
| Research | Historical replay, candidate selection and native Tester work. Results do not authorize Demo cutover or real-money use. New economic comparisons require base+swap and stress+swap. |
| Research engineering closure | A verdict limited to reproducibility, accounting integrity and agreement with the declared strategy contract. It does not establish market-data coverage, historical broker economics, forward profitability or Demo authorization. |
| Terminal net profit | Ending equity minus initial capital on one continuous account after all modeled costs, with no capital top-ups or account resets. Intermediate drawdown is descriptive; survival and the declared risk protections remain required. |
| Risk efficiency | The trade-off between terminal net profit and the capital exposure, equity drawdown, recovery time and tail losses borne to obtain it. Higher profit alone does not establish better risk efficiency. |
| Retained profits | Trading profits left in the same account and included in its subsequent capital. Retaining profits does not by itself increase position size under a fixed-lot contract. |
| Equity-based sizing | Position sizing that depends on current account equity and the declared risk rule. It is distinct from retaining profits and is not part of the current fixed-lot C22 contract. |
| Loss streak | Consecutive closed trades with negative net results after costs and swap. The count describes sequence length; loss magnitude and protection state describe severity separately. |
| Closing-balance recovery | An interval from a recorded closing-balance peak until a subsequent close reaches or exceeds that peak. Completed intervals and a still-unrecovered interval are separate evidence; this is not continuous equity underwater time. |
| Research DD ceiling | The maximum observed peak-to-trough equity decline permitted for qualification of a research scenario. Passing this ceiling does not guarantee a future or broker-enforced maximum loss. |
| Matrix tuning | A prospectively bounded sequence of one-factor neighborhoods around the fully reviewed research incumbent. Each round freezes its candidates before outcomes, retains failed cases, and promotes only according to the declared profit/DD rank. It does not imply global optimization, new validation data or Demo adoption. |
| Actual closing drawdown recovery | A closing-peak recovery interval that contains at least one below-peak closing balance. It excludes idle or monotone peak-to-peak intervals; the legacy peak-interval metric remains separately available. Still not continuous tick-equity recovery. |
| Conditional block closure | Complete enumeration of each declared parameter block at the final incumbent's fixed opposite block yields no strict eligible objective improvement. It does not establish the global optimum across jointly changed blocks. |
| Downside repair lane | An exploratory search alternative preserving latest matched base/stress profit and each matched scenario's risk metrics while prioritizing lower worst-case DD, recovery age, loss-run severity and streak. Separate from the owner's primary profit ranking and from Demo adoption. |
| Censored recovery age | The observed age of an actual closing drawdown still unrecovered at the final source quote. It is a lower bound on eventual recovery duration, not a recovery forecast. |
| Market data | Complete UTC Bid M15 bars assembled from all 15 M1 minutes. Forming bars are excluded. |
| Detection | Frozen strategy's candidate direction and levels. A signal alone is not a broker-approved order. |
| Admission | Decision whether a new entry satisfies identity, costs, exposure, risk, daily-loss, margin and broker-check gates. |
| Signal capture rate | Live owned fills divided by the model-admissible signals of the same strategy over the same window. Misses caused by the strategy's own rules (risk cap, daily loss, cooldown, open position) are excused. Misses caused by operations (cost policy, AutoTrading, review, sender outage, foreign exposure) count against it. |
| Bot-only account | A Demo account used only by the strategy's sender during a measurement window: no manual trades and no deposits or withdrawals, so live results stay comparable with replay. |
| Shadow | Admission and reconciliation without order sends. A shadow admission is not a fill. |
| Order intent | Persisted request before dispatch; an ambiguous send remains unresolved until broker evidence arrives. |
| Owned position | Position attributed to the selected strategy by its broker identity evidence. Foreign exposure blocks new entries. |
| Reconciliation | Broker evidence resolving fills, protection changes and complete exits, including restart recovery. |
| Attended maintenance | Owner-attended operational work within an explicitly approved scope and a bounded pause of new Admission. Exposure ownership and the financial Journal remain authoritative during recovery; uncertain actions do not become permission to repeat them. |
| Maintenance plan | A reviewable description of one attended operation, its permitted changes, required evidence and recovery scope. A plan is not permission to execute. |
| Operation handle | Stable identity of one maintenance attempt used to inspect or continue that same approved attempt. It does not grant permission for another dispatch. |
| BE | Current Selected26b8 uses BE1R for both BUY and SELL, evaluated at a new completed M15. Its native price calculation includes declared commission/slippage, not accrued or future holding swap; it does not guarantee nonnegative final net. Legacy C22H4 BUY protection remains off. |
| Safety close | Containment of an unexpected owned fill; not a recovery basket. |
| Journal | Durable financial/lifecycle record and broker-confirmed event outbox. |
| Notes | Human-readable trade commentary derived from cycle results and entry thesis. Distinct from financial persistence. |
| Readiness | Separate evidence for code validation, broker parity, operational cutover and real money. Refactoring does not improve readiness by itself. |

Legacy SMC terminology and ADRs remain in the unchanged
[archived glossary](docs/archive/2026-10-18-context-smc-v2.md).
SMC sizing, scale-out, news and rollover rules are not C22/trial30 rules.
