# ADR-0028: Freeze foundation Fib/cash-flow/quote research defaults

Status: Accepted (research defaults — not profitability-proven)

## Context

Issue #1 listed unsettled material decisions that blocked silent policy invention. ADR-0027 already froze protected-swing CHoCH. Remaining Gate A items needed explicit versioned defaults before Demo qualification code continues.

## Decision

Adopt these foundation BaselinePlay research defaults as rule package `foundation-gate-a-v1`:

1. **Fibonacci anchors:** At structural trigger, use True Swing Extremum range over Sweep→break inclusive. Retracement is logged via `compute_fibonacci_features`; OTE 62–79% is informational only (no filter/entry relocate).
2. **Cash-flow / intervention:** Deposits, withdrawals, and credits use `apply_account_pnl_event(..., source="cash_flow")`. They change equity/balance for risk gates but never enter `bot_realized_pnl`. No automatic pause/rebase unless a later ADR says so.
3. **Quote sides (research/replay):** Prefer bid for SELL fills/exits and ask for BUY fills/exits when tick sides exist. When only mid/OHLC is available, label results `quote_side=unknown` / `AMBIGUOUS` as appropriate — never invent favorable sides.
4. **Statistical protocol placeholder:** Keep PASS criteria ownership outside this ADR. Use existing profitability qualification module; do not change CI sidedness here.

## Consequences

- Code may implement these defaults without treating them as user-optimized trading edges.
- Changing any item requires a new ADR / rule version.
- Data provenance and Oracle soak remain separate open gates.
