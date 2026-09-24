# ADR-0030: Independent qualification before Demo strategy automation

Status: Accepted

BotTradeGold's reconstructed rules are new versioned Strategy Contracts, not reproductions of missing original implementations. The exposed 2010–2026 research history may select a small set of Validation Challengers but cannot qualify them; qualification for Demo strategy automation requires a frozen contract, new post-freeze Exness Bid/Ask ticks for the target Demo account and symbol, measured execution costs, account-valid sizing, and the preregistered ADR-0025 statistical and risk gates adapted to each contract's exit rules. This can leave no candidate eligible for a long time, but prevents historical selection and unmeasured costs from being presented as a proven trading edge; the separate Demo Execution Path probe does not qualify a strategy.
