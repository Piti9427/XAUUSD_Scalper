# Current domain glossary

Trading rules and risk math: [CORE_STRATEGY.md](CORE_STRATEGY.md).
Operational commands: [C22 Demo runbook](docs/ops/c22h4-demo.md).
Module/debug map: [architecture](docs/architecture/codebase-layout.md).

| Term | Meaning |
| --- | --- |
| C22 Demo | Selected C22 + closed H4 EMA200 strategy on the existing Exness Demo account; snapshot `RESEARCH-C22-H4EMA200-20261004`. No real-money authorization. |
| trial30 rollback | Retained SELL-only D48 strategy, snapshot `RESEARCH-D48-SELL-BE1R-20261001-T030`. Separate contract; never concurrent with C22 on one account. |
| Research | Historical replay, candidate selection and native Tester work. Results do not authorize Demo cutover or real-money use. New economic comparisons require base+swap and stress+swap. |
| Market data | Complete UTC Bid M15 bars assembled from all 15 M1 minutes. Forming bars are excluded. |
| Detection | Frozen strategy's candidate direction and levels. A signal alone is not a broker-approved order. |
| Admission | Decision whether a new entry satisfies identity, costs, exposure, risk, daily-loss, margin and broker-check gates. |
| Shadow | Admission and reconciliation without order sends. A shadow admission is not a fill. |
| Order intent | Persisted request before dispatch; an ambiguous send remains unresolved until broker evidence arrives. |
| Owned position | Position attributed to the selected strategy by its broker identity evidence. Foreign exposure blocks new entries. |
| Reconciliation | Broker evidence resolving fills, protection changes and complete exits, including restart recovery. |
| BE | Break-even protection under the selected strategy's own contract. C22 BUY has protection off; SELL uses BE1R. |
| Safety close | Containment of an unexpected owned fill; not a recovery basket. |
| Journal | Durable financial/lifecycle record and broker-confirmed event outbox. |
| Notes | Human-readable trade commentary derived from cycle results and entry thesis. Distinct from financial persistence. |
| Readiness | Separate evidence for code validation, broker parity, operational cutover and real money. Refactoring does not improve readiness by itself. |

Legacy SMC terminology and ADRs remain in the unchanged
[archived glossary](docs/archive/2026-10-18-context-smc-v2.md).
SMC sizing, scale-out, news and rollover rules are not C22/trial30 rules.
