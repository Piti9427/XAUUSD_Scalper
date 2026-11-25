# C22 26b8: closing the losing years with an equity-curve pause (design, 2026-11-12)

Status: design approved in chat (sections 1 and 2). This is a research spec only: no runtime, config or VM change. Real money is PROHIBITED.

## Intent (owner, 2026-11-12)
- **Goal:** stop the known losing periods from damaging the account.
- **Success (owner choice):** "survive and lose little":
  - range years lose at most 5% per year;
  - the account never cap-locks;
  - trend-year profit falls by at most 15%.
- **Capital target (owner choice):** **$200**, the strictest case.
- **Approach (owner choice):** A is the core (equity-curve pause). B is secondary (a weekly side-direction gate).

## Why this approach
Evidence: `docs/reviews/2026-11-12-c22-losing-years-diagnosis.md` and `docs/reviews/2026-11-12-c22-regime-fix-loyo.md`.
- In 2020–2024a, follow-through on 26b8 signals is no better than random entry:
  - SELL breakdowns run against the up-drift;
  - BUY pullbacks do not follow through.
- Costs are 7–14% of R at low ATR.
- A continuous $200 account started before Sep 2024 falls to $17–37 and cap-locks.
- Bar-level entry filters failed LOYO, so the regime cannot be predicted from indicators.
- The pause uses the strategy's *own* closed results instead of a market prediction.

## Mechanisms

**Base:** B2+maxloss_1, i.e. native 26b8 entry/exit, tick BE on BUY at 1R polled every 5 s, and at most 1 losing exit per UTC day. Also unchanged:
- 10% cost-inclusive cap;
- 0.01 lot;
- daily 10% limit;
- 30-min cooldown;
- costs and swap.

**A. Equity-curve pause**
- **Shadow stream:** the trades the base would take with no pause, from the same tick replay. Only shadow trades whose exit is strictly before the decision time count, so there is no look-ahead.
- **Pause:** if the R sum of the last N closed shadow trades is below −k, reject new real entries (rejection reason `equity_pause`). An open real position is managed normally.
- **Resume:** once the R sum of the last N closed shadow trades is at least r.
- **Grid (12 specs):** N ∈ {10, 20, 30}, k ∈ {2, 4}, r ∈ {0, +2}.
- **R of a shadow trade:** net / risk_usd.
- **Warm-up:** the shadow history is continuous within a tape (w2022, w2324, disc). Pausing is impossible until N shadow trades have closed.

**B. Weekly side gate**
- Use closed W1 bars only (weeks end Friday 21:00 UTC; resample by `W-FRI` on closes known at the decision time).
- BUY is allowed only if the last closed W1 close is above SMA(L) of W1 closes. SELL is allowed only if it is below.
- Grid: L ∈ {10, 20}. Each L runs alone (2 specs) and combined with A (12 × 2 = 24 specs).

Catalog total: base + 12 A + 2 B + 24 A+B = 39 specs.

## Evaluation
- **Data:** real ticks for the 7 segments 2020, 2021, 2022, 2023, 2024a, 2024b25, 2026 (to 2026-10-23). Base+swap and stress+swap views.
- **Selection (LOYO):**
  - Each segment is an independent **$200** account.
  - For each held-out segment, pick the best spec on the other 6 by the min-over-views mean-monthly edge vs base, among specs that pass the gate in both views:
    - mean monthly ≥ base + $1;
    - % profitable months ≥ base;
    - worst month ≥ base − $5;
    - year wins vs base ≥ 3 of 6.
  - If no spec passes, the fold keeps the base.
- **Pass (all must hold, scored on held-out segments):**
  1. The sum of held-out nets beats B2+maxloss_1 in both base and stress.
  2. Each range year (2020, 2021, 2022, 2023, 2024a) is ≥ −$10 in base. Stress is reported.
  3. Each trend segment (2024b25, 2026) is ≥ 85% of B2+maxloss_1's net in base.
  4. **Survival.** The spec picked on all 7 segments runs one continuous $200 account from 2020-01 to 2026-10, with the balance carried across tapes. In both views:
     - it never cap-locks. Cap-lock means a span of more than 30 consecutive calendar days that contains at least one signal, where every signal not paused by A or B is rejected by `risk_cap` and no trade is admitted;
     - it ends above $200.
- **Forward:** 2026-10-24..11-11, at $200 and $313, base+stress. Reported only.
- **On failure:** do per-trade root-cause attribution vs the base, then run **one** derived iteration with a newly frozen protocol (owner standing rule), then stop.

## Implementation notes (research)
- Engine: the composed `runs/c22-26b8-tuning-loop-2026-11-11/loopeng.py`, through its `gate` hook (`X['gate']`).
  - The shadow stream is a pre-run of the base spec on the same tape.
  - Its `(exit_ms, R)` list is binary-searched inside the gate.
  - W1 closes are precomputed per tape.
- Parity: a spec with k = ∞ and no B gate must equal the base exactly in all 14 cells.
- Protocol `runs/c22-pause-2026-11-12/protocol.json`, with its sha256 recorded, is frozen before any run. Use Pool(2) and a low-disk guard.
- Output: `result.json` and the verdict doc `docs/reviews/2026-11-1x-c22-losing-years-pause-verdict.md`.

## Out of scope
- Live runtime of the shadow stream. A new RulesID, cost review and owner approval would be needed after a pass plus forward observation.
- Sizing changes.
- H1 timeframe (approach C was declined).

## Limits
- All history has already been seen. LOYO guards the selection, not the design of the families.
- Any winner is a forward-observation candidate only.
