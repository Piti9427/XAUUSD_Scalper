# Reward156 paired research tuning

All cells: independent USD200 / fixed0.01 / risk10% / daily20%. No Demo change.
A: full10months and reset5month halves. B: full12months and reset6month halves.
Swap: current-spec sensitivity at quoted ticks, assumed UTC rollover; COST_INCONCLUSIVE.
Net-before-swap is attribution on swap path; no_swap is independently replayed counterfactual.

| Dataset/window | Cost/view | Contract | Net USD | Swap USD | DD % | WR % | RR | BUY/SELL | Risk blocked days |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| A/full | base/no_swap | trial30 | -145.87 | 0.00 | 73.74 | 30.91 | 1.1117 | 0/55 | 84 |
| A/full | base/swap | trial30 | -145.87 | 0.00 | 73.74 | 30.91 | 1.1117 | 0/55 | 84 |
| A/full | stress/no_swap | trial30 | -146.08 | 0.00 | 75.65 | 24.32 | 1.0283 | 0/37 | 98 |
| A/full | stress/swap | trial30 | -146.08 | 0.00 | 75.65 | 24.32 | 1.0283 | 0/37 | 98 |
| A/first_half | base/no_swap | trial30 | -140.07 | 0.00 | 73.14 | 31.48 | 1.1046 | 0/54 | 19 |
| A/first_half | base/swap | trial30 | -140.07 | 0.00 | 73.14 | 31.48 | 1.1046 | 0/54 | 19 |
| A/first_half | stress/no_swap | trial30 | -146.08 | 0.00 | 75.65 | 24.32 | 1.0283 | 0/37 | 32 |
| A/first_half | stress/swap | trial30 | -146.08 | 0.00 | 75.65 | 24.32 | 1.0283 | 0/37 | 32 |
| A/second_half | base/no_swap | trial30 | -132.90 | 0.00 | 68.07 | 15.79 | 1.0604 | 0/19 | 53 |
| A/second_half | base/swap | trial30 | -132.90 | 0.00 | 68.07 | 15.79 | 1.0604 | 0/19 | 53 |
| A/second_half | stress/no_swap | trial30 | -109.20 | 0.00 | 56.73 | 26.09 | 1.0556 | 0/23 | 50 |
| A/second_half | stress/swap | trial30 | -109.20 | 0.00 | 56.73 | 26.09 | 1.0556 | 0/23 | 50 |
| A/full | base/no_swap | reward156_original | -141.34 | 0.00 | 73.97 | 34.48 | 1.3537 | 3/84 | 21 |
| A/full | base/swap | reward156_original | -140.71 | -1.13 | 73.56 | 34.12 | 1.3588 | 3/82 | 21 |
| A/full | stress/no_swap | reward156_original | -134.88 | 0.00 | 70.95 | 34.62 | 1.3082 | 3/75 | 22 |
| A/full | stress/swap | reward156_original | -134.88 | -1.13 | 70.80 | 35.29 | 1.3224 | 3/82 | 22 |
| A/first_half | base/no_swap | reward156_original | -115.40 | 0.00 | 62.46 | 35.80 | 1.3392 | 3/78 | 2 |
| A/first_half | base/swap | reward156_original | -114.78 | -1.13 | 61.99 | 35.44 | 1.3454 | 3/76 | 2 |
| A/first_half | stress/no_swap | reward156_original | -121.02 | 0.00 | 64.76 | 35.53 | 1.2979 | 3/73 | 1 |
| A/first_half | stress/swap | reward156_original | -106.73 | -1.13 | 58.17 | 36.71 | 1.3116 | 3/76 | 2 |
| A/second_half | base/no_swap | reward156_original | -111.83 | 0.00 | 58.04 | 25.00 | 1.1845 | 0/24 | 17 |
| A/second_half | base/swap | reward156_original | -111.83 | 0.00 | 58.04 | 25.00 | 1.1845 | 0/24 | 17 |
| A/second_half | stress/no_swap | reward156_original | -130.70 | 0.00 | 66.98 | 15.79 | 1.1793 | 0/19 | 19 |
| A/second_half | stress/swap | reward156_original | -130.70 | 0.00 | 66.98 | 15.79 | 1.1793 | 0/19 | 19 |
| B/full | base/no_swap | trial30 | -90.71 | 0.00 | 47.79 | 0.00 | n/a | 0/7 | 153 |
| B/full | base/swap | trial30 | -90.71 | 0.00 | 47.79 | 0.00 | n/a | 0/7 | 153 |
| B/full | stress/no_swap | trial30 | -91.82 | 0.00 | 48.24 | 0.00 | n/a | 0/7 | 153 |
| B/full | stress/swap | trial30 | -91.82 | 0.00 | 48.24 | 0.00 | n/a | 0/7 | 153 |
| B/first_half | base/no_swap | trial30 | -90.71 | 0.00 | 47.79 | 0.00 | n/a | 0/7 | 63 |
| B/first_half | base/swap | trial30 | -90.71 | 0.00 | 47.79 | 0.00 | n/a | 0/7 | 63 |
| B/first_half | stress/no_swap | trial30 | -91.82 | 0.00 | 48.24 | 0.00 | n/a | 0/7 | 63 |
| B/first_half | stress/swap | trial30 | -91.82 | 0.00 | 48.24 | 0.00 | n/a | 0/7 | 63 |
| B/second_half | base/no_swap | trial30 | 507.25 | 0.00 | 25.99 | 53.06 | 1.1702 | 0/147 | 11 |
| B/second_half | base/swap | trial30 | 507.25 | 0.00 | 25.99 | 53.06 | 1.1702 | 0/147 | 11 |
| B/second_half | stress/no_swap | trial30 | 452.37 | 0.00 | 26.07 | 52.38 | 1.1644 | 0/147 | 11 |
| B/second_half | stress/swap | trial30 | 452.37 | 0.00 | 26.07 | 52.38 | 1.1644 | 0/147 | 11 |
| B/full | base/no_swap | reward156_original | -89.96 | 0.00 | 68.74 | 34.62 | 1.3467 | 6/20 | 56 |
| B/full | base/swap | reward156_original | -90.53 | -0.57 | 68.85 | 34.62 | 1.3433 | 6/20 | 56 |
| B/full | stress/no_swap | reward156_original | -93.27 | 0.00 | 65.60 | 31.58 | 1.2348 | 6/13 | 57 |
| B/full | stress/swap | reward156_original | -93.84 | -0.57 | 65.72 | 31.58 | 1.2291 | 6/13 | 57 |
| B/first_half | base/no_swap | reward156_original | -89.96 | 0.00 | 68.74 | 34.62 | 1.3467 | 6/20 | 21 |
| B/first_half | base/swap | reward156_original | -90.53 | -0.57 | 68.85 | 34.62 | 1.3433 | 6/20 | 21 |
| B/first_half | stress/no_swap | reward156_original | -93.27 | 0.00 | 65.60 | 31.58 | 1.2348 | 6/13 | 22 |
| B/first_half | stress/swap | reward156_original | -93.84 | -0.57 | 65.72 | 31.58 | 1.2291 | 6/13 | 22 |
| B/second_half | base/no_swap | reward156_original | 981.95 | 0.00 | 22.50 | 56.41 | 1.2310 | 21/135 | 9 |
| B/second_half | base/swap | reward156_original | 975.14 | -6.81 | 22.53 | 56.41 | 1.2270 | 21/135 | 9 |
| B/second_half | stress/no_swap | reward156_original | 933.21 | 0.00 | 22.97 | 55.84 | 1.2355 | 19/135 | 9 |
| B/second_half | stress/swap | reward156_original | 926.97 | -6.24 | 23.00 | 55.84 | 1.2317 | 19/135 | 9 |

## Frozen verdict

```json
{
  "status": "BASELINE_COMPLETE_BEFORE_TUNING"
}
```

A/B in-sample reused discovery; no prospective/live fill parity. Sealed Jul-Sep2025 not loaded.
No optimization beyond registered three candidates. Passing research does not authorize execution.
