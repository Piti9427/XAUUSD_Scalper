# B1/D risk and RR experiment — 2026-09-26

Verdict: **NO ACCEPTABLE ACCOUNT PROFILE FOUND IN THIS BOUNDED TEST**. User authorized adjusting risk/RR for more executable opportunities; these are versioned historical experiments, not deployment approval or a claim of reasonable personal financial risk. No runtime risk setting changed.

Version `b1-d-risk-rr-experiment-v1.1.0`. Same authenticated Demo snapshot, 1,173.46 USD, 5,708,205 ticks from 1–25 September 2026. Entry/ATR-stop rules frozen; B1 SL remains 2.5 ATR, D 2 ATR. Risk fractions 0.5%, 1%, 1.5%, 2%. Compare proposed TP 2R against native B1 2.5R / D 3R. One independent simulated account per candidate/config, compounding realized balance and floored broker lot steps. All configurations recorded, including failures.

## Observed B1 results

| Risk cap | RR reward | Extra cost R/trade | Trades | Net USD | PF | Win rate | Max tick equity DD |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5% | 2R | 0 | 0 | +0.00 | n/a | n/a | 0.00% |
| 0.5% | 2R | 0.1 | 0 | +0.00 | n/a | n/a | 0.00% |
| 1% | 2R | 0 | 0 | +0.00 | n/a | n/a | 0.00% |
| 1% | 2R | 0.1 | 0 | +0.00 | n/a | n/a | 0.00% |
| 1.5% | 2R | 0 | 9 | -51.79 | 0.540 | 22.2% | 6.34% |
| 1.5% | 2R | 0.1 | 4 | -23.09 | 0.540 | 25.0% | 4.73% |
| 2% | 2R | 0 | 38 | +29.50 | 1.059 | 34.2% | 11.69% |
| 2% | 2R | 0.1 | 33 | -42.14 | 0.907 | 33.3% | 16.47% |
| 0.5% | 2.5R | 0 | 0 | +0.00 | n/a | n/a | 0.00% |
| 0.5% | 2.5R | 0.1 | 0 | +0.00 | n/a | n/a | 0.00% |
| 1% | 2.5R | 0 | 0 | +0.00 | n/a | n/a | 0.00% |
| 1% | 2.5R | 0.1 | 0 | +0.00 | n/a | n/a | 0.00% |
| 1.5% | 2.5R | 0 | 10 | +6.93 | 1.062 | 30.0% | 3.35% |
| 1.5% | 2.5R | 0.1 | 4 | -15.95 | 0.682 | 25.0% | 4.73% |
| 2% | 2.5R | 0 | 32 | +114.47 | 1.263 | 34.4% | 13.19% |
| 2% | 2.5R | 0.1 | 30 | +108.12 | 1.257 | 36.7% | 12.65% |

D produces zero September signals and zero trades in every row. Increasing risk/TP cannot create signals.

## Interpretation

0.5% and 1% admit no B1 trades: initial budgets 5.87/11.73 USD remain below cheapest minimum-lot stop risk 14.24 USD. Changing TP alone cannot solve minimum-lot affordability because position risk depends on entry-to-SL distance.

1.5% / 2R loses before added costs. 1.5% / native 2.5R yields only +6.93 USD across ten trades and turns negative under 0.10R additional-cost sensitivity. 2% / 2R is nearly flat before unmeasured costs and negative after sensitivity. 2% / native 2.5R is positive here, but 13.19% drawdown greatly exceeds previous 5% account acceptance threshold. Neither increased trade frequency nor an attractive nominal RR is sufficient for selection.

A 2R target means planned gross winner twice nominal stop loss. If every trade realizes exactly +2R/-1R, break-even win rate is 1/3 before costs. Slippage, gaps, fees, swap and sample-end exits change realized outcomes. Actual stop loss can exceed nominal sizing risk during a price gap; see [FINRA stop-order explanation](https://www.finra.org/investors/insights/stop-orders-factors-consider-during-volatile-markets) (general order-mechanics guidance, not broker-specific XAUUSD advice).

Extra 0.10R is an explicit sensitivity and admission-cost reserve, not measured historical commission/slippage or twice-measured-cost validation. Trade identity/count can change when added costs prevent minimum lots. Spread is actual Bid/Ask. Current-spec swap and historical margin limitations remain as in [real-tick report](B1_D_EXNESS_REAL_TICKS_2026-09-26.md).

This exposed 25-day window cannot establish a stable edge or safe risk level. No configuration passes qualification; no claim of out-of-sample confirmation. User permission supersedes older 0.5% cap for these experiments only; qualification and runtime defaults are unchanged.

## Reproduce

```bash
.venv/bin/python -m scripts.research.b1_d_ticks \
  --capture data/b1_d_exness_ticks_2026-09-26 \
  --output data/b1_d_risk_rr2_2026-09-26 \
  --risk-pcts .005 .01 .015 .02 --rr 2
```

Repeat without `--rr 2` and with new output path for native exits. Output directories refuse overwrite. Each includes manifest/metrics with exact specs and hashes, sixteen trade ledgers and COMPLETE.

Verification: six focused tick tests, including explicit risk override and invalid-risk rejection; combined tick/research/shadow suite **38 passed**. Explicit-risk RED failed on missing risk_pct parameter before implementation; then GREEN passed. Each nonempty trade ledger checked against risk budget, lot grid and target/stop ratio. No Demo orders submitted.

Decision: retain B1/D as unqualified research candidates; do not promote 2% merely because it generates trades. Freeze any next contract before a longer/new independent test; any tighter stop is a new trading hypothesis requiring fresh evidence.
