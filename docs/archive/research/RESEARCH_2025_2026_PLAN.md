# Research 2025–2026: decisions in progress

Status: two newly requested Relick variants were implemented and backtested separately on 2025–partial 2026. Both tested contracts lost; neither replaces the prior validation challenger. No qualifying prospective validation has started. User's latest clarification supersedes the earlier 0.5% sizing premise for this experiment.

## Resolved objective

User selected option 1: **Profit-First Selection**. Rank by net profit after costs among candidates satisfying the agreed risk constraints. Report win rate, closed-trade count, and drawdown alongside profit; win rate is not the primary optimization target.

- User removed the earlier 0.5%-per-setup research cap and asked for reward:risk of at least 2:1 (profit target at least twice the entry-to-stop distance). This target does not guarantee profit, win rate, or bounded account loss.
- A maximum acceptable loss/drawdown for the intended Demo bot remains unresolved. Do not silently inherit the legacy SMC 1.5% rule or the old research qualification protocol's 0.5%/5% as if the user had selected either.
- Existing live execution protection continues to apply until a separate, explicit bot policy is decided; this document does not authorize bypassing its risk gate.

## Existing evidence boundary

Verified existing baseline covers 2025 and 2026 through 2026-08-20 23:58 UTC. These years were already exposed during selection. They are research/development data; splitting or tuning them again does not create untouched validation data.

`Donchian20_H4 / common` remains the benchmark from the preceding selection. The user's new request reopens research into techniques and new contracts; it does not certify the benchmark or authorize deployment. Existing trade results use fixed 1 oz exposure and unmeasured extra broker costs, so they do not establish the new account-level objective.

## Resolved starting capital

User specified **100 USD** as the intended Exness Demo research starting balance. No current terminal balance has been verified in this session. The earlier derived 0.50 USD setup-risk budget and 5 USD drawdown threshold are superseded by the user's later clarification.

This is a user-specified input, not a fresh terminal balance verification. Existing `data/exness-demo/export_meta.json` names `XAUUSDm` and records an older balance/equity of 1173.46; that snapshot must not override the user's new 100 USD experiment. It omits the contract size and minimum/step lot specifications needed for this sizing test. Repository code also contains example/default values (`min_lot=0.01`, `contract_size=100`, `spread_buffer=0.30`) and a small-account profile, but these are assumptions rather than an exported specification of this target account.

## Resolved target symbol

User confirmed using the previous Exness Demo information: **`XAUUSDm`**. This identifies the intended research symbol. The older export establishes its name only; current account identity, broker contract/volume/tick specifications and fees still require a fresh read before account-sized P&L claims.

User subsequently identified the intended account as Exness `Standard_Demo` on `Exness-MT5Trial7` with login matching the older export. The chat message also contained a credential-like string: never copy it to repository files, logs, or reports. Existing ignored `.env` already has broker credential keys; presence of keys does not prove valid values or current terminal connection.

Read-only MT5 `account_info`/`symbol_info` access was attempted on 2026-09-25. The sandboxed Wine call could not start `wineserver`; an escalated read-only retry reached a 45-second timeout without a metadata response. No order API was invoked and no broker specification or current balance was confirmed. Do not repeat the connection attempt without a changed terminal state.

## Next unresolved dependency

The user directed us to use repository settings. Use them for a clearly labelled exploratory scenario; do not present default broker inputs as measured current Exness specifications. Run a bounded 2025–2026 candidate experiment against the same verified cache, including sensitivity to unspecified costs. Account-level eligibility remains unverified until the target-account symbol specification and fills are captured. Resolve maximum tolerable account loss before selecting a final Demo bot strategy.

## New Relick attachment (2026-09-25)

The newly attached summary describes **two distinct research ideas**: EMA20/50 + Stochastic on M15, and RSI reversal with a doubling-lot Martingale grid plus basket TP/hard dollar stop. These are not one interchangeable strategy. The prior user choice explicitly selected RSI reversal **without** grid, whose declared 30/70 crossback implementation was already historically negative. The user then explicitly authorized testing **both** new variants separately. The grid basket has no stated per-basket 2:1 payoff contract. The attachment is a third-party summary, not complete source code or an audited trading record. Frozen assumptions, measured historical results, and rejection reasons are in [RELICK_TWO_VARIANTS_BACKTEST_2026-09-25.md](RELICK_TWO_VARIANTS_BACKTEST_2026-09-25.md). Maximum tolerable account loss for any future bot still needs a separate policy decision; neither rejected variant depends on that decision for its historical rejection.

## Repository-input feasibility check (2026-09-25)

The repository has a default small-account scenario and an Exness M5/H1 export, but no saved current `XAUUSDm` symbol-specification snapshot. Its example sizing values are `min_lot=0.01`, `contract_size=100`, and `spread_buffer=0.30`. At 100 USD and 0.5% risk, the initial budget is 0.50 USD. A 0.01-lot order therefore needs an entry-to-stop distance of at most 0.50 USD before extra fees/slippage. This threshold is conditional on the example contract values, not a verified Exness rule.

Before the risk-limit clarification, we read all 480 existing baseline trade logs (120 contracts × common/native × 2025/partial 2026). They contain 99,292 individually simulated closed trades across repeated alternatives. Under the **superseded** `risk <= 0.50` diagnostic, 52 rows fit in 2025 and zero in partial 2026; RSI crossback has zero. Repeated contracts share signals. This diagnostic is **not** a resized account backtest and must not be used to exclude candidates under the revised research brief. It remains evidence that prior fixed-1-oz profit rankings cannot be treated as a $100 account result.
