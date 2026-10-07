# YouTube transcript versus B1 research — 2026-09-28

## Current capital decision

User set Demo starting capital to **$200**. New comparison runners default to $200; all future primary strategy comparisons use this amount. Historical $100/$10,000 artifacts remain historical evidence. Broker balance is not asserted or changed. The old continuous/TTL scripts are archived reproduction scripts, not current-capital defaults. No $200 rerun has been performed by this configuration change.

## Finding

These are different strategies and different exposure regimes. B1_TP25 is the strongest observed 0.10R-cost candidate in the previous bounded tick comparison, not a reproduction of the clip's RSI/recovery system and not proof that our extracted recovery strategy returns only 7.19%.

## Evidence from supplied transcript

Source: `/Users/nopparuj/Downloads/Nopparuj - บันทึกจาก Youtube-transcript.txt` (839 lines), read in full this turn. Claims below are narrator statements, not an independently verified broker statement.

- 01:59–02:19: EMA20/50 plus **Stochastic**, bounce/touch entry, reported M15 win rate 63%. Exact line identity, Stochastic settings, sample and exits are not supplied. This is not EMA crossover plus RSI.
- 02:34–03:59: narrator changes strategy to RSI/other entries with recovery, larger hedging position and basket close when combined profit covers losses.
- 03:28 and 07:55–08:38: initial $200; reported final $279.81, profit $79.81, arithmetically +39.905%. Stated dates September 8–17; do not infer an exact year from file timestamp or contradictory weekday narration.
- 05:50–06:25: basket stop initially $80, changed to $55 after a losing event.
- 07:19–07:35: legs reach 0.01→0.02→0.04→0.08. Transcript does not specify complete hedge direction/grid/re-entry/basket TP logic. Four simultaneous open legs would sum to 0.15 gross lots, but transcript alone does not prove all remain open simultaneously.
- $55 is 27.5% of initial $200, and $80 is 40%. These are initial-capital reference ratios, not measured per-basket risk on then-current equity or maximum drawdown.
- Win rate 63% belongs to the earlier EMA/Stochastic experiment, not proven for the final profitable recovery run.

## Verified B1_TP25 ledger

Source: `data/feedback_comparison_2026-09-28/continuous_B1_TP25_0.1.csv`.

- May 14–September 25, 2026, hypothetical $10,000; 164 independent trades, 58 wins / 106 losses; win rate 35.3659%.
- Donchian30 breakout + RSI guard; SL2.5ATR, TP2.5R; one position; no recovery.
- Drawdown risk policy caps nominal budget from 1% down to 0.25%. Actual sampled nominal tiers: 73 trades at 1%, 88 at 0.75%, 3 at 0.5%.
- Average admitted stop risk / entry equity: 0.6712%, excluding extra cost reserve; lot flooring and reserves reduce deployed stop risk below nominal budget.
- Gross price PnL +$1,997.69; swap scenario -$98.1602; extra 0.10R cost scenario -$1,180.3796; net +$719.1502 = +7.1915%.
- Mean net trade +0.12212R; mean winner +2.39110R; mean loser -1.11940R. Cash PF1.081898 and tick-equity DD6.928706%.
- Separate full replay at 0R reserve returned +25.9043%; at 0.20R returned -6.3211%. Those are separate equity/sizing paths, not simple fee subtraction from an unchanged ledger. Actual extra commission/slippage remains unmeasured; the reserve is a stress assumption.

Trade count is not profit count. Most of these 164 trades lost, winners offset losers, and net edge after cost was small. The result reflects both limited exposure and weak cost robustness; it should not be defended as merely conservative sizing.

## Scope and implementation mismatch

The previous runner never constructs/injects `BasketManager`. Its SMC orchestrator is single-position. The current extracted code/config also differs from the clip:

| Element | Supplied clip | Current extracted code/config | Prior tested B1 |
|---|---|---|---|
| Entry | RSI/unspecified techniques | MSS-based, recovery requires new same-direction signal | Donchian breakout + RSI guard |
| Recovery | Larger hedge, ladder reaches 0.08 | Same-direction entry/recovery, two legs 0.01/0.02 | None |
| Basket loss | $55 after changing from $80 | min(15% equity, $30), plus daily/HWM gates | Individual stop with tiered risk |
| Profit closure | Combined recovery profit covers losses | Basket net close condition | Fixed TP2.5R |
| Evidence here | Narrator report | Source inspection only; not backtested in previous round | Captured-tick Python replay |

Sources inspected: `config/settings.yaml` money_management; `scripts/smc/basket_manager.py`; `scripts/smc/backtester.py`; `scripts/research/feedback_round.py`; central strategy registry sections 5.1–5.2. Central registry already labels exact clip rules incomplete. No current-run performance claim is made from older handoff summaries of separate martingale experiments.

## Next comparison that answers the intended question

Use three separate controls: B1_TP25, extracted two-leg recovery, and an explicitly documented clip-inspired RSI hedge reconstruction. Compare $200 simulation and $100 target sensitivity on identical ticks/cost assumptions, with equal-risk results separate from native-exposure results. Report baskets and individual legs separately; include floating-equity drawdown, gross/net exposure, worst basket, margin/stop-out assumptions and every rolling short-window result. Short profitable clip period is not a substitute for complete multi-month results.

Freeze missing grid distances, hedge side, RSI trigger, basket TP and leg cap before implementing the reconstruction; assumptions must not be presented as exact clip rules. No live configuration or risk cap changed during this comparison.
