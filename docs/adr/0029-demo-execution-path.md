# ADR-0029: Demo Execution Path uses the existing Python adapter

Status: Accepted

Automated Trading Strategy’s first milestone is a Demo Execution Path, not strategy qualification and not real-money. Live execution reuses `evaluate_smc_setup` as the detection module and `execute_intent` as the only Execution Adapter. The adapter runs against an Exness-logged terminal on this Mac Wine host first; a Windows VPS gets the same adapter only if IPC still returns authorization failure. MQL5 strategy rewrite, a second MQL5 adapter, Python↔EA bridges, and Computer Use are rejected for this path.

The first broker proof is an Execution Path Probe: a geometrically valid pending limit admitted through Orchestrator / risk / geometry, placed far enough not to fill, then cancelled after broker confirmation. Target account is the env Exness Demo; hedging is required; Foreign Positions (`comment` not `SMC_*`) block new risk; the bot never closes a Foreign Position and never substitutes another gold symbol. Both order-sending scripts require explicit `MT5_ENABLE_DEMO_ORDER_SEND=1` and fail closed when broker position/order state is unavailable. ADR-0025 / ADR-0026 qualification gates stay closed.
