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
| A/full | base/no_swap | reward156_no_pause | 222.10 | 0.00 | 69.73 | 44.68 | 1.3607 | 212/164 | 7 |
| A/full | base/swap | reward156_no_pause | 103.66 | -60.14 | 72.85 | 44.70 | 1.3025 | 197/152 | 20 |
| A/full | stress/no_swap | reward156_no_pause | -164.05 | 0.00 | 85.41 | 36.19 | 1.2182 | 69/36 | 140 |
| A/full | stress/swap | reward156_no_pause | -164.91 | -24.97 | 85.49 | 36.79 | 1.1807 | 72/34 | 139 |
| A/first_half | base/no_swap | reward156_no_pause | 55.79 | 0.00 | 69.73 | 44.27 | 1.3352 | 112/80 | 0 |
| A/first_half | base/swap | reward156_no_pause | 34.74 | -39.15 | 72.85 | 44.74 | 1.2824 | 111/79 | 0 |
| A/first_half | stress/no_swap | reward156_no_pause | -164.05 | 0.00 | 85.41 | 36.19 | 1.2182 | 69/36 | 36 |
| A/first_half | stress/swap | reward156_no_pause | -164.91 | -24.97 | 85.49 | 36.79 | 1.1807 | 72/34 | 35 |
| A/second_half | base/no_swap | reward156_no_pause | -88.64 | 0.00 | 69.41 | 40.45 | 1.2181 | 60/29 | 48 |
| A/second_half | base/swap | reward156_no_pause | -102.61 | -11.92 | 73.33 | 38.10 | 1.1604 | 44/19 | 62 |
| A/second_half | stress/no_swap | reward156_no_pause | -99.21 | 0.00 | 73.54 | 37.88 | 1.2068 | 47/19 | 60 |
| A/second_half | stress/swap | reward156_no_pause | -92.53 | -14.75 | 69.18 | 40.26 | 1.1683 | 56/21 | 52 |
| A/full | base/no_swap | reward156_h4_ema100 | 273.85 | 0.00 | 37.87 | 47.42 | 1.3412 | 147/66 | 1 |
| A/full | base/swap | reward156_h4_ema100 | 223.35 | -50.50 | 39.22 | 47.42 | 1.2955 | 147/66 | 1 |
| A/full | stress/no_swap | reward156_h4_ema100 | 198.15 | 0.00 | 38.61 | 46.19 | 1.3404 | 149/61 | 1 |
| A/full | stress/swap | reward156_h4_ema100 | 139.10 | -48.80 | 40.98 | 46.15 | 1.2907 | 148/60 | 1 |
| A/first_half | base/no_swap | reward156_h4_ema100 | 75.00 | 0.00 | 37.87 | 45.92 | 1.3637 | 62/36 | 0 |
| A/first_half | base/swap | reward156_h4_ema100 | 52.30 | -22.70 | 39.22 | 45.92 | 1.3044 | 62/36 | 0 |
| A/first_half | stress/no_swap | reward156_h4_ema100 | 10.37 | 0.00 | 38.61 | 43.16 | 1.3460 | 63/32 | 0 |
| A/first_half | stress/swap | reward156_h4_ema100 | -12.33 | -22.70 | 40.98 | 43.16 | 1.2835 | 63/32 | 0 |
| A/second_half | base/no_swap | reward156_h4_ema100 | 198.85 | 0.00 | 33.83 | 48.70 | 1.3054 | 85/30 | 1 |
| A/second_half | base/swap | reward156_h4_ema100 | 166.85 | -26.10 | 35.75 | 48.67 | 1.2709 | 84/29 | 1 |
| A/second_half | stress/no_swap | reward156_h4_ema100 | 187.78 | 0.00 | 34.65 | 48.70 | 1.2883 | 86/29 | 1 |
| A/second_half | stress/swap | reward156_h4_ema100 | 160.54 | -27.24 | 36.33 | 48.70 | 1.2521 | 86/29 | 1 |
| A/full | base/no_swap | reward156_h4_ema200 | 298.30 | 0.00 | 35.27 | 48.04 | 1.3893 | 138/41 | 0 |
| A/full | base/swap | reward156_h4_ema200 | 287.61 | -47.09 | 37.16 | 48.31 | 1.3687 | 138/40 | 1 |
| A/full | stress/no_swap | reward156_h4_ema200 | 260.66 | 0.00 | 39.31 | 46.70 | 1.4181 | 142/40 | 1 |
| A/full | stress/swap | reward156_h4_ema200 | 214.14 | -46.53 | 41.44 | 46.70 | 1.3649 | 142/40 | 1 |
| A/first_half | base/no_swap | reward156_h4_ema200 | 61.63 | 0.00 | 35.27 | 45.33 | 1.4142 | 43/32 | 0 |
| A/first_half | base/swap | reward156_h4_ema200 | 44.61 | -17.02 | 37.16 | 45.33 | 1.3529 | 43/32 | 0 |
| A/first_half | stress/no_swap | reward156_h4_ema200 | 26.87 | 0.00 | 39.31 | 42.86 | 1.4275 | 45/32 | 0 |
| A/first_half | stress/swap | reward156_h4_ema200 | 9.85 | -17.02 | 41.44 | 42.86 | 1.3671 | 45/32 | 0 |
| A/second_half | base/no_swap | reward156_h4_ema200 | 273.07 | 0.00 | 23.15 | 50.49 | 1.3900 | 95/8 | 1 |
| A/second_half | base/swap | reward156_h4_ema200 | 243.00 | -30.07 | 24.20 | 50.49 | 1.3399 | 95/8 | 1 |
| A/second_half | stress/no_swap | reward156_h4_ema200 | 233.79 | 0.00 | 25.53 | 49.52 | 1.3628 | 97/8 | 1 |
| A/second_half | stress/swap | reward156_h4_ema200 | 204.29 | -29.50 | 28.39 | 49.52 | 1.3156 | 97/8 | 1 |
| B/full | base/no_swap | reward156_no_pause | -87.82 | 0.00 | 76.90 | 41.35 | 1.3099 | 73/31 | 181 |
| B/full | base/swap | reward156_no_pause | -85.52 | -7.94 | 74.57 | 41.54 | 1.2376 | 53/12 | 210 |
| B/full | stress/no_swap | reward156_no_pause | -78.28 | 0.00 | 75.50 | 42.31 | 1.2331 | 63/15 | 197 |
| B/full | stress/swap | reward156_no_pause | -109.79 | -9.65 | 76.13 | 39.44 | 1.3330 | 49/22 | 211 |
| B/first_half | base/no_swap | reward156_no_pause | -79.73 | 0.00 | 76.90 | 40.23 | 1.3679 | 60/27 | 70 |
| B/first_half | base/swap | reward156_no_pause | -88.67 | -7.94 | 74.57 | 40.98 | 1.2539 | 49/12 | 82 |
| B/first_half | stress/no_swap | reward156_no_pause | -71.22 | 0.00 | 75.50 | 41.94 | 1.2410 | 50/12 | 81 |
| B/first_half | stress/swap | reward156_no_pause | -109.79 | -9.65 | 76.13 | 39.44 | 1.3330 | 49/22 | 79 |
| B/second_half | base/no_swap | reward156_no_pause | -78.85 | 0.00 | 52.68 | 35.71 | 1.2644 | 23/5 | 103 |
| B/second_half | base/swap | reward156_no_pause | -87.67 | -6.24 | 49.69 | 36.00 | 1.1222 | 22/3 | 106 |
| B/second_half | stress/no_swap | reward156_no_pause | -88.34 | 0.00 | 49.92 | 37.04 | 1.1321 | 21/6 | 103 |
| B/second_half | stress/swap | reward156_no_pause | 149.58 | -19.86 | 68.77 | 47.16 | 1.2081 | 96/80 | 29 |
| B/full | base/no_swap | reward156_h4_ema100 | -43.61 | 0.00 | 70.78 | 43.59 | 1.2243 | 67/11 | 117 |
| B/full | base/swap | reward156_h4_ema100 | 383.22 | -20.43 | 64.96 | 49.41 | 1.2302 | 99/71 | 61 |
| B/full | stress/no_swap | reward156_h4_ema100 | -65.76 | 0.00 | 62.72 | 42.25 | 1.2402 | 62/9 | 121 |
| B/full | stress/swap | reward156_h4_ema100 | 362.78 | -19.29 | 54.73 | 49.06 | 1.2585 | 86/73 | 69 |
| B/first_half | base/no_swap | reward156_h4_ema100 | -26.35 | 0.00 | 55.53 | 44.26 | 1.2085 | 58/3 | 39 |
| B/first_half | base/swap | reward156_h4_ema100 | -17.37 | -10.21 | 57.90 | 44.78 | 1.2050 | 64/3 | 35 |
| B/first_half | stress/no_swap | reward156_h4_ema100 | -27.19 | 0.00 | 53.16 | 43.64 | 1.2281 | 52/3 | 43 |
| B/first_half | stress/swap | reward156_h4_ema100 | -27.96 | -9.08 | 54.73 | 43.64 | 1.2259 | 52/3 | 43 |
| B/second_half | base/no_swap | reward156_h4_ema100 | 729.05 | 0.00 | 27.02 | 53.96 | 1.2527 | 38/101 | 12 |
| B/second_half | base/swap | reward156_h4_ema100 | 717.13 | -11.92 | 27.19 | 53.96 | 1.2447 | 38/101 | 12 |
| B/second_half | stress/no_swap | reward156_h4_ema100 | 600.27 | 0.00 | 27.15 | 52.52 | 1.2440 | 38/101 | 12 |
| B/second_half | stress/swap | reward156_h4_ema100 | 544.69 | -10.21 | 24.44 | 52.94 | 1.2540 | 35/84 | 19 |
| B/full | base/no_swap | reward156_h4_ema200 | 593.84 | 0.00 | 52.24 | 51.81 | 1.2296 | 72/94 | 43 |
| B/full | base/swap | reward156_h4_ema200 | -73.37 | -9.65 | 58.00 | 42.86 | 1.1352 | 48/1 | 113 |
| B/full | stress/no_swap | reward156_h4_ema200 | -19.03 | 0.00 | 57.43 | 45.45 | 1.1567 | 51/4 | 108 |
| B/full | stress/swap | reward156_h4_ema200 | 449.43 | -18.72 | 49.96 | 50.90 | 1.1909 | 71/96 | 44 |
| B/first_half | base/no_swap | reward156_h4_ema200 | -29.50 | 0.00 | 47.98 | 43.90 | 1.1840 | 41/0 | 34 |
| B/first_half | base/swap | reward156_h4_ema200 | -34.04 | -4.54 | 49.29 | 43.90 | 1.1705 | 41/0 | 34 |
| B/first_half | stress/no_swap | reward156_h4_ema200 | -31.99 | 0.00 | 48.65 | 43.90 | 1.1767 | 41/0 | 34 |
| B/first_half | stress/swap | reward156_h4_ema200 | -17.81 | -5.11 | 49.96 | 45.00 | 1.1662 | 40/0 | 35 |
| B/second_half | base/no_swap | reward156_h4_ema200 | 608.43 | 0.00 | 29.12 | 53.91 | 1.2024 | 32/96 | 8 |
| B/second_half | base/swap | reward156_h4_ema200 | 594.81 | -13.62 | 29.17 | 53.91 | 1.1928 | 32/96 | 8 |
| B/second_half | stress/no_swap | reward156_h4_ema200 | 463.35 | 0.00 | 29.18 | 52.34 | 1.1847 | 32/96 | 8 |
| B/second_half | stress/swap | reward156_h4_ema200 | 449.73 | -13.62 | 29.23 | 52.34 | 1.1753 | 32/96 | 8 |

## Frozen verdict

```json
{
  "candidates": {
    "reward156_no_pause": {
      "improves_reward156": false,
      "qualifies_vs_trial30": false,
      "worst_continuous_dd": 85.49204204662361,
      "minimum_continuous_net": -164.90759999997044,
      "cells": [
        {
          "dataset": "A",
          "window": "full",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "full",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "first_half",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "first_half",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "second_half",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "second_half",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "full",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "full",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "first_half",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "first_half",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "second_half",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "second_half",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        }
      ]
    },
    "reward156_h4_ema100": {
      "improves_reward156": false,
      "qualifies_vs_trial30": false,
      "worst_continuous_dd": 64.96134795324829,
      "minimum_continuous_net": 139.10460000005838,
      "cells": [
        {
          "dataset": "A",
          "window": "full",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "full",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "first_half",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "first_half",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "second_half",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "second_half",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "full",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "full",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "first_half",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "first_half",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "second_half",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": true
        },
        {
          "dataset": "B",
          "window": "second_half",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": true
        }
      ]
    },
    "reward156_h4_ema200": {
      "improves_reward156": false,
      "qualifies_vs_trial30": false,
      "worst_continuous_dd": 58.00030380438687,
      "minimum_continuous_net": -73.36680000000035,
      "cells": [
        {
          "dataset": "A",
          "window": "full",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "full",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "first_half",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "first_half",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "A",
          "window": "second_half",
          "cost": "base",
          "improves_original": true,
          "qualifies_trial30": true
        },
        {
          "dataset": "A",
          "window": "second_half",
          "cost": "stress",
          "improves_original": true,
          "qualifies_trial30": true
        },
        {
          "dataset": "B",
          "window": "full",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "full",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "first_half",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "first_half",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        },
        {
          "dataset": "B",
          "window": "second_half",
          "cost": "base",
          "improves_original": false,
          "qualifies_trial30": true
        },
        {
          "dataset": "B",
          "window": "second_half",
          "cost": "stress",
          "improves_original": false,
          "qualifies_trial30": false
        }
      ]
    }
  },
  "selected": null,
  "holdout": "NOT_OPENED_NO_QUALIFIER",
  "demo": "UNCHANGED_TRIAL30",
  "real_money": "NO_GO",
  "costs": "COST_INCONCLUSIVE"
}
```

A/B in-sample reused discovery; no prospective/live fill parity. Sealed Jul-Sep2025 not loaded.
No optimization beyond registered three candidates. Passing research does not authorize execution.
