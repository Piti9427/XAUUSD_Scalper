# B1_TP25 Matrix audit and Demo readiness — 2026-09-28

## Verdict

**NO-GO for running the claimed Hybrid Basket Recovery on Demo as a protected strategy.** Current code contains parts of the policy, but production construction, signal routing, broker ticket ownership, confirmed fill/close accounting and risk enforcement are not complete. No order was sent during this audit.

The Pure +206.9% number is reproducible at fixed 0.01 lot on $200 under the archived swap plus 0.10R extra-cost scenario. The claimed Hybrid +275.2% is not certified: the original Antigravity `compare_basket_rules.py` has now been located, inspected and executed. It clips completed Pure trade losses to -$30 without simulating recovery, early exits, daily limits or HWM. The original output exactly matches the supplied Matrix. This establishes the arithmetic source, not Hybrid trading performance.

## Fresh-price replay results

Source: 31,780,274 XAUUSDm Bid/Ask ticks freshly retrieved from the requested Exness MT5 Demo. Scoring May 14–September 25, 2026 UTC, with May 7–13 warmup. Every tape value matched the daily capture arrays and every daily file passed its manifest SHA-256. No generated price paths were used for returns.

All arms start at **$200**, use B1 completed-M15 signals, SL 2.5 ATR, TP 2.5R, fixed 0.01 lot, no compounding and no recovery. The controls deliberately test exit/risk policy differences; they are not a full Hybrid implementation or a live-ready recommendation.

| Arm | Final balance | Return | Trades | Win rate | Tick equity DD |
|---|---:|---:|---:|---:|---:|
| Pure, archived cost scenario | $613.89 | +206.94% | 164 | 35.37% | 54.92% |
| Tick-triggered $30 cap only, archived cost scenario | $316.83 | +58.42% | 170 | 32.35% | 74.24% |
| Tick cap + daily/quota/HWM guards, archived cost scenario | $164.48 | -17.76% | 2 | 0% | 20.01% |
| Pure, observed spread only | $1,023.17 | +411.59% | 164 | 35.37% | 45.21% |
| Tick-triggered $30 cap only, observed spread only | $932.47 | +366.23% | 166 | 34.34% | 44.75% |
| Tick cap + daily/quota/HWM guards, observed spread only | $166.36 | -16.82% | 2 | 0% | 20.01% |

**Costs are not all verified historical charges.** Both scenarios include actual captured spread. The archived scenario additionally uses current-spec swap with a UTC rollover approximation and 0.10R per-trade extra cost, matching the prior research assumption. Observed-spread-only results exclude unmeasured commission, swap and slippage, and must not be presented as net live profit. Broker margin approval, stop-out, execution latency and real close fills remain unverified.

The guards control uses min(15% equity, $30) frozen basket budget, 15% UTC day-start-equity loss admission limit, two entries per day, and a 20% floating-equity HWM liquidation/latch. It halts after two losing trades. HWM drawdown is measured from the running peak, so a 20% peak drawdown need not equal a 20% loss against initial capital. These guards are evaluated against every tick in this diagnostic, whereas the current BasketManager integration is bar-driven.

## Why the +275.2% figure is insufficient

Independently recomputed from `data/feedback_comparison_2026-09-28/continuous_B1_TP25_0.1.csv`:

```text
fixed_lot_net_i = archived_net_i / archived_volume_i * 0.01
sum(fixed_lot_net_i)                         = $413.8858 -> +206.9429%
sum(max(fixed_lot_net_i, -30))               = $550.3858 -> +275.1929%
```

The second formula clips 22 completed losing trades but leaves every eventual winner unchanged. It adds no 0.02-lot leg. An actual stop changes the price path, exit time, later entry availability and cost accrual:

- Signal June 11, 17:45 UTC: Pure eventually earns **+$111.8274**; tick-triggered cap exits first at **-$31.4794**.
- Signal August 21, 16:45 UTC: Pure eventually earns **+$68.3864**; tick-triggered cap exits first at **-$30.0732**.

The losses beyond $30 are observed quote overshoots under ideal immediate execution; the trigger is not a guaranteed fill price. No additional execution slippage was invented. Pure's 164 trades became 170 trades in the cap-only scenario because earlier exits free the strategy to accept later signals.

All 164 Pure entries, exits, directions and exit reasons matched the prior ledger, and every rescaled trade PnL matched within $1e-8. This verifies the reproduction, not its live feasibility.

## Matrix versus implementation

| Claim | Evidence and remaining gap |
|---|---|
| Current runtime uses B1_TP25 + BasketManager | `main.py` constructs legacy `XAUUSDSniperStrategy`. No executable `BasketManager(...)` construction exists under `scripts/` or `main.py`; the only occurrence there is a docstring. Orchestrator accepts it optionally, default `None`. |
| Single-leg TP runs to 2.5R | `basket_tp_reached` suppresses early basket TP for one leg, but the manager accepts `tp_price` from its caller and does not itself enforce 2.5R. Broker SL, HWM or basket stop may close it earlier. |
| Two-leg combined PnL > 0 closes basket | Manager emits intents, but they carry no ticket/order ID. Execution adapter rejects them outside dry-run. No verified cost-inclusive, per-ticket broker close path exists. |
| $30 basket stop always protects | Budget is min(15% equity, $30), not always $30. Orchestrator returns through single-position management before reaching basket checks when `account.open_position` is populated. Even reachable checks are bar-driven rather than continuous tick monitoring. |
| Recovery is confirmed exposure | Manager appends an open leg when emitting a PLACE_LIMIT intent, before fill confirmation. Recovery trigger is described as same-direction MSS, whereas Pure B1 uses Donchian breakout; exact intended bridge remains unresolved. |
| Broker close updates PnL | `_close_all_legs` sets `is_open=False` immediately. `on_leg_closed` only books PnL for `is_open=True`; a following confirmed -$31 close records $0 in the reproduced path. |
| Daily breaker is exactly $30 | Code uses 15% of day-start equity and blocks new baskets; this equals $30 only when day-start equity is $200. It is not a universal $30 liquidation rule. |
| HWM consistently latches at 20% | Basket SL is checked before HWM; simultaneous breaches return `CLOSE_PENDING` without setting HALTED. HWM is not checked by manager recovery admission. |
| Recovery improves safety/profit | Neither +275.2% arithmetic nor these no-recovery controls prove this. Full two-leg chronology, costs, exposure and guards need a separately frozen contract and executable replay. |

Offline lifecycle reproductions are in `readiness_probes.json`. Their hand-written prices are explicitly synthetic failure probes, never input to the historical performance calculation.

## Demo account verification

Read-only MT5 snapshot at 2026-09-28 09:15:05 UTC:

- Requested login/server match `.env`; verified Demo mode.
- USD balance/equity **$200**, free margin $200, leverage 1:1000, hedging margin mode.
- XAUUSDm minimum/step 0.01 lot, contract size 100.
- Trading/expert flags enabled; zero positions and zero pending orders.
- Password and account login omitted from report; `.env` unchanged; order API not called.

Account connectivity is confirmed. It does not resolve strategy/execution blockers.

## Validation and artifacts

- 68 existing BasketManager/orchestrator/B1/tick/comprehensive tests passed. These existing tests do not cover all demonstrated blockers.
- Offline readiness probes reproduced target rejection, lost close PnL, open-position bypass and simultaneous-stop/HWM behavior.
- All six output ledgers reconcile starting balance plus cumulative PnL, chronological entry/exit and fixed lot.
- Artifacts: `data/b1_matrix_audit_2026-09-28/contract.json`, `results.json`, six arm ledgers, `independent_checks.json`, `pure_winners_stopped_by_tick_cap.csv`, `readiness_probes.json`, `demo_identity.json`.
- Production modules/config/credentials unchanged; pre-existing basket edits preserved.

```bash
.venv/bin/python -m scripts.research.b1_fixed_matrix_audit \
  --baseline data/b1_tp25_usd200_fresh_2026-09-28_verified \
  --output data/b1_matrix_audit_NEW
.venv/bin/python -m scripts.research.basket_readiness_audit
.venv/bin/python -m unittest tests.test_basket_manager tests.test_smc_orchestrator \
  tests.test_b1_final tests.test_b1_d_ticks tests.test_b1_d_comprehensive
```

Next decision: freeze the actual recovery signal and fill contract. Then resolve ticket/confirmed-fill/close accounting and risk enforcement, replay the complete two-leg system and validate its Demo execution path. Do not treat the +275.2% Matrix as permission to bypass those blockers.

## Recheck of the complete three-column Matrix

The user subsequently supplied all three sets of balance, PnL, return and drawdown, attributing them to `compare_basket_rules.py`. Initial repository and temporary-directory searches did not locate it. After the user identified Antigravity/agy, it was found at `/Users/nopparuj/.gemini/antigravity-cli/brain/1730c142-c74c-49ae-b1bc-af441f236211/scratch/compare_basket_rules.py`. Source inspection and execution from the repository root confirm the transformations below.

Nevertheless, all supplied rounded numbers reproduce exactly from these ledger-only transformations:

| Transformation of fixed-0.01-lot PnL | Final balance | Net PnL | Return | Closed-balance DD |
|---|---:|---:|---:|---:|
| Unchanged | $613.89 | +$413.89 | +206.9% | 52.99% |
| Replace each final loss below -$30 with -$30 | $750.39 | +$550.39 | +275.2% | 46.95% |
| Same loss clipping, cap each positive final PnL at +$15 | -$1,520.75 | -$1,720.75 | -860.4% | 845.74% |

The loss clipping affects 22 rows. The last transformation caps 58 winners; all those original winners exceed $15, so this dataset produces the same result as replacing every win by $15. The actual source uses `min(n, 15.0)`, not unconditional replacement. All 12 quoted rounded metrics pass exact assertions in `scripts/research/matrix_arithmetic_recheck.py`; outputs are retained in `data/b1_matrix_audit_2026-09-28/matrix_arithmetic_recheck.json`.

This is now source-confirmed post-hoc trade arithmetic, not evidence of successful Hybrid execution. Original source lines 4–5 load and rescale completed CSV trades, line 26 applies `max(n, -30.0)`, and lines 42–45 apply `min(n, 15.0)` to winners and the loss cap to losers. The script never imports or invokes BasketManager, reads tick arrays, creates recovery legs, applies daily/HWM guards, or stops admitting trades after account depletion. Source snapshot, SHA-256 provenance and exact stdout are saved as `agy_compare_basket_rules_source.py`, `agy_compare_basket_rules_provenance.json`, and `agy_compare_basket_rules_stdout.txt` in the audit artifact directory.

Corrections to the Matrix interpretation:

1. **164 means executed research trades, not all detected signals.** The unrestricted Pure replay detected 553 eligible-window signals; 389 were skipped while a position was open.
2. **The period is about 4.5 months, not three months.** Scoring begins May 14 and ends before September 26 UTC (through September 25).
3. **52.99% and 46.95% are closed-balance drawdowns in these transformations.** They do not include floating losses. Fresh Pure replay measures 54.92% tick-equity drawdown under the archived cost scenario. MT5 explicitly distinguishes balance and equity drawdown in its [Testing Report documentation](https://www.metatrader5.com/en/terminal/help/algotrading/testing_report).
4. **22 final losses beyond $30 are not the complete set of trades touching a -$30 floating threshold.** At least two eventual Pure winners are stopped earlier by the tick cap, as shown above.
5. **A final balance of -$1,520.75 is an arithmetic stress result, not a certified feasible account path.** The transformed balance first becomes nonpositive after trade 21, but the formula continues summing all 164 rows without broker margin/stop-out or cash admission.
6. **Replacing eventual winners with $15 does not reproduce early-positive basket TP.** A chronological early-profit rule can also change eventual losers, exits and later admissions; neither the $15 amount nor those paths are established by this transformation.

Updated verdict remains **NO-GO for treating +275.2% as proven Hybrid profit or immediately promoting it to order execution**. Pure B1_TP25 can remain the research reference; full Hybrid performance and the pending recovery trigger remain unresolved.

```bash
.venv/bin/python -m scripts.research.matrix_arithmetic_recheck
```
