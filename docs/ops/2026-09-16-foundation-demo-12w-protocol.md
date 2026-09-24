# Foundation Demo Assessment Protocol v1

Parent: [Issue #1](https://github.com/Piti9427/XAUUSD_Scalper/issues/1)  
Status: Protocol registered — **not** an executed PASS certificate

## Purpose

Define the 12-week Exness Standard Demo forward assessment without promising profit or early PASS.

## Preconditions (must be true before week 1)

1. Broker identity gate passes (`verify_broker_identity`) for Exness Demo + XAUUSD.
2. Rule version frozen: structure `s1-s4-mechanical-v1` + Gate A `foundation-gate-a-v1`.
3. risk_halt persistence path writable; halt state empty or reviewed.
4. News schedule source known; unknown schedule blocks new risk.
5. Affordability report for live balance recorded.
6. Live loop uses broker-reconciled path (legacy mutating loop remains disabled).

## Window

- Length: 12 calendar weeks from recorded start UTC date.
- No early PASS.
- Extension or restart requires a new protocol id.

## What is measured

- Bot-only closed trades (exclude manual/cash_flow from expectancy)
- Net expectancy (R and $), win/loss/flat counts, profit factor, max equity DD
- Funnel: detected → CHOCH-qualified → target-qualified → affordable → submitted → accepted → filled → closed
- Operational: UNKNOWN submits, cancel races, news blocks, risk halts

## What is not measured as edge

- Fibonacci/OTE tags
- Manual trades
- Cash flows
- Infrastructure incidents (counted separately)

## Verdict vocabulary

- PASS / FAIL / INCONCLUSIVE / DATA_INSUFFICIENT per frozen statistical ownership (profitability qualification module)
- Sample insufficiency → INCONCLUSIVE (do not loosen rules to invent trades)

## Operator checklist

- [ ] Start UTC date:
- [ ] Account login / server:
- [ ] Rule commit SHA:
- [ ] Weekly export of ledger + risk_halt state
- [ ] End-of-window report filed under `docs/reviews/`
