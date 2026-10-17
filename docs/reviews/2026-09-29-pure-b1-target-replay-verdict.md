# Pure B1 target signal replay — 2026-09-29

**Decision: research only; NO-GO for live execution.** Owner selected Donchian 30 + strict RSI 30–70 + EMA50 as the target signal, then chose to keep it in research after the replay. `main.py` and the webhook bridge were not connected to this signal. No broker order or alert was sent.

## Source and reproduction

- Pure detection: `scripts/strategy.py:pure_b1_bars`, using completed UTC M15 Bid bars, prior 30 highs/lows, RSI14 EWM span14, EMA50 EWM span50, ATR14 simple rolling true range.
- Replay: `scripts/research/pure_b1_target_replay.py`, using the archived `Replay` tick execution engine on the same saved Bid/Ask capture and UTC window as the +341.99% result. Fixed 0.01 lot; no recovery; 2.5 ATR stop; 6.25 ATR target; 40% day-start equity gate. Added a cost-inclusive 10% current-equity admission gate before each entry. Historical execution uses first tick after signal bar close.
- Input baseline: `data/b1_hybrid_baseline_6mo_fixed_2026_09_28`; capture: `data/b1_hybrid_exness_6mo_fixed_2026_09_28`; output: `data/b1_pure_target_replay_cost_gated_2026_09_29`. Output `contract.json` records input and source SHA-256 values; all three source hashes rechecked against current files.

```bash
.venv/bin/python -m scripts.research.pure_b1_target_replay \
  --baseline data/b1_hybrid_baseline_6mo_fixed_2026_09_28 \
  --capture data/b1_hybrid_exness_6mo_fixed_2026_09_28 \
  --output data/b1_pure_target_replay_cost_gated_2026_09_29
```

Output directory must not already exist. For a rerun, choose a new directory; preserve the recorded output.

## Results

| Policy on same 2026-03-28 to 2026-09-28 ticks | Signals in window | Trades | Final equity | Return | Max tick equity DD | Win rate | Rejections |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Archived B1, RSI BUY <=75 / SELL >=25, no EMA50, hypothetical 0.10R fee | 737 | 190 | $883.99 | +341.99% | 34.38% | 37.37% | 99 engine `margin_proxy` |
| Target RSI (30,70) + EMA50, spread only | 82 | 4 | $132.98 | -33.51% | 36.12% | 0% | 78 cost-inclusive cap |
| Target RSI (30,70) + EMA50, hypothetical 0.10R fee/current-spec swap | 82 | 49 | $500.62 | +150.31% | 40.32% | 40.82% | 19 cost-inclusive cap |

The two target cost scenarios take different trades. The fee scenario rejects early entries whose price loss plus fee would breach 10%; rejected losses change future equity and which later orders qualify. The spread-only run takes four early losing orders, then lower equity blocks later entries. The fee scenario has 20 winning and 29 losing positions; one closes at end of sample. **Neither target result preserves the archived +341.99% return or 34.38% DD.** The 40.32% maximum is peak-to-trough tick equity DD, not evidence that the 40% UTC day-start gate fired; replay recorded zero daily-loss rejections.

An independent calculation using the original `run_b1_breakdown.py` RSI/EMA/ATR functions produced exactly the same 83 target signals across all 12,100 saved bars (82 in the replay window), with zero direction mismatches and zero maximum indicator difference. Output ledger checks: all legs 0.01 lot, one leg per basket, no recovery, every entry's initial stop loss plus modeled fee <=10% of pre-entry equity, all leg net sums reconcile to final equity. Source and input hashes matched. This verifies the local reconstruction, not broker fill parity.

## Limits and next gate

- Saved tick replay is retrospective. Historical commission, slippage, margin approval, and stop-out behavior remain unmeasured; the extra 0.10R fee and current swap spec are scenarios.
- `run_b1_breakdown.py` OHLC result uses different bar inputs and fill assumptions; it cannot establish target tick profitability.
- The previous preliminary target replay result of -36.81% omitted fee from the pre-entry 10% gate. It is superseded by the cost-inclusive replay above.
- `main.py` still runs the legacy wick-rejection alert path. Existing SMC/webhook modules remain separate historical code and are not Pure B1 evidence.

Keep target strategy in research. Before any Demo order adapter: freeze indicator and cost contract, obtain representative broker costs, test risk and daily guards end to end, and review a new performance/readiness verdict. Real-money execution requires separate owner approval.
