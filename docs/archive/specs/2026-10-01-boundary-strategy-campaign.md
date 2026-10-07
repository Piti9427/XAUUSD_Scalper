# Boundary invalidation, sessions and loss circuits

New hypothesis after structural/trigger-RR discovery campaigns failed: crossed Donchian edge defines breakout invalidation better than full setup wick; a fixed0.5ATR buffer tolerates ordinary noise. Loss cooldown and fixed UTC liquidity sessions can interrupt loss clusters. No parameter chosen from a winning result.

384 unique configs frozen before replay: parents2 × guards2(`off/sell_only`) × entries2(`immediate/retest`) × sessions2(`london_ny/all`) × risk caps2(`5/10%`) × nominal RR3(`1.5/2/3`) × circuits4. Circuit tuples `(cooldown bars, max net losing exits per UTC day, protection)` = `(0,0,off),(4,0,off),(4,2,candle_trail),(4,2,break_even)`. Daily balance-loss admission gate5%; fixed0.01 lot, no recovery.

SL: BUY frozen crossed boundary−0.5ATR; SELL boundary+0.5ATR; round conservatively. Wrong-side, excess risk or margin rejects. TP uses entry-to-initial-rounded-SL × nominal RR. UTC sessions `[07:00,11:00)` and `[12:00,17:00)` based on actual entry quote. These are fixed research windows, not dynamically DST-adjusted exchange sessions. They block entries only; protective exits remain active. Each realized net losing exit starts cooldown from actual exit time and increments that UTC exit day's loss count. Breakeven does not count as loss.

Full-first screening and stop-on-discovery-pass. All unchanged profit/WR/DD/RR/stress and sample gates; missing half results cannot qualify. Source snapshots/hashes preserved, no live path or parent adoption.184 days remain reused discovery.

Run: `--campaign boundary --screen --stop-on-pass --output data/strategy_boundary_campaign_2026_09_30` (run initiated across local midnight).
