# Pure B1 evidence pin — 2026-09-29

**Status:** Research pin only. This file does not authorize a Demo order, a Demo probe, or real money.

Account login is omitted. The account fingerprint lives in `config/pure_b1_cost_policy.json` and in the local capture manifest.

## Contract

| Item | Value |
| --- | --- |
| Signal | Donchian 30 strict close, RSI14 EWM span 14 inside (30, 70), EMA50 EWM span 50 |
| ATR / stops | ATR14 rolling mean, SL 2.5 ATR, TP 6.25 ATR, then tick-size rounding |
| Risk | Fixed 0.01 lot. Reject above 10% of current equity. Daily loss 40% of UTC day-start equity. |
| Quote rule | `first_fresh_quote_age_60s_lateness_90s` |
| Archival quote rule | `archival_first_tick_within_900s`, labeled only |
| Bar input | Completed UTC Bid M15 from M1 intervals with all 15 minutes |
| `scripts/strategy.py` | `9f7894465fbe61e6fbd196cbef4d241227ecdf5c34db444f563a745159d31434` |
| `scripts/smc/risk.py` | `963e061b1532ca7a68e8fa3a2ed077ff315068c79014e788d67cca3dc5889935` |

Hashes are SHA-256 of the file bytes.

## Reference data

| Artifact | SHA-256 |
| --- | --- |
| `data/b1_hybrid_baseline_6mo_fixed_2026_09_28/reference_bars.csv` | `85f9f6c983231fc93e675e3e3813b80a0161c2847da58a5a50baea9b1b90bbff` |
| `data/b1_hybrid_baseline_6mo_fixed_2026_09_28/manifest.json` | `36efa8fd922260a77fdff1743aac0f8169c6fb37fb6588c7777793e64175efff` |
| `data/b1_hybrid_exness_6mo_fixed_2026_09_28/manifest.json` | `7cf23c9b675f1d1a05789b617c28559fd7fa14030aac81aefca82933eeb92619` |
| `data/b1_pure_broker_capture_v2_2026_09_29_1200_1300/manifest.json` | `74fb25f88d86e852411daca86e2f783baa7a7db5849cfe1351e27ccf4ce3be0e` |

The tick manifest under that capture is not copied here because it contains the account login.

## Cost policy

`config/pure_b1_cost_policy.json` SHA-256 `93657fcef3b084df67ab69098b83f8b39b2e0f06959695c1ae4880826a7cb488`.

- Account type: Standard Demo.
- Check date: 2026-09-29.
- Source: `docs/reviews/2026-09-29-xauusdm-broker-conditions-audit.md`, SHA-256 `2c71944754dec1d49a62768e0759b11555b703264f172c926e6cc7e0baea3892`.
- Commission: 0 USD per 1 lot, round turn, from the published Standard tariff. `symbol_info` does not provide the tariff before an order. `commission_from_symbol_info` is false.
- Slippage allowance 0.10 and spread stress 0.20 are declared assumptions, not terminal-certified values.
- `spread_buffer` is 0 because Bid/Ask entry already includes spread.
- `swap_free_scope` is `current_policy_not_historical`. Historical swap entitlement is missing.
- A policy that fails validation rejects risk admission. Shadow still requires the check to be no older than 24 hours.

## Replay evidence

Labeled output: `data/b1_pure_target_replay_labeled_2026_09_29/`.

| File | SHA-256 |
| --- | --- |
| `contract.json` | `8f99592b70b7243e4be0e689c52f73c5d4373b01be86e9bc6084820203660d7f` |
| `results.json` | `87a343d3df4f46eadb970222e620c8cc463034300a1e93a63b21604f9a6d6b4b` |

Command:

```bash
.venv/bin/python -m scripts.research.pure_b1_target_replay \
  --baseline data/b1_hybrid_baseline_6mo_fixed_2026_09_28 \
  --capture data/b1_hybrid_exness_6mo_fixed_2026_09_28 \
  --output data/b1_pure_target_replay_labeled_2026_09_29
```

| Scenario | Trades | Return | Notes |
| --- | ---: | ---: | --- |
| `standard_no_commission_swap_free_current_policy` | 4 | -33.51% | Fresh quote rule, no day quota, commission 0 with a named source, swap not applied. Not an expected Standard Demo result. |
| `non_swap_free` | 4 | -33.51% | Current-spec swap path was on. These four legs did not cross a UTC midnight, so accrued swap was 0. Historical swap entitlement is still missing. |
| `slippage_spread_stress` | 4 | -33.608% | Declared entry stress 0.30 (0.10 slippage + 0.20 spread stress) applied once. `spread_buffer` stayed 0. |

`expected_standard_demo_result` is false on every row. The hypothetical 0.10R / +150.31% result was not rerun as the Standard scenario. Prior spread-only and hypothetical numbers remain in [the earlier verdict](2026-09-29-pure-b1-target-replay-verdict.md).

82 signals were seen in each labeled run. 78 were rejected by the 10% cap. `late_quote`, `day_start_unknown`, and `daily_quota` were 0 on this tape. `order_api_called` was false.

## Still absent

Measured Demo fills, `history_deals_get` commission/swap/slippage, historical swap entitlement, and a verified per-bar equity path. Those gaps stay fail-closed.
