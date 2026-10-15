# Active C22H4 Demo vs C22 tuned — paired replay

Owner: “เอาไปลอง backtest ว่าได้ผลลัพดีกว่าเดิมมั้ย”; explicitly selected
“เทียบ Demo ปัจจุบันกับ C22 tuned (แนะนำ)”. Native UI retry failed
`Sky Computer Use native pipe startup failed`; economic execution remains offline
canonical tick replay, not native MT5 Tester. No Python chart acquisition.

Freeze exactly two cases before new results:
- Active Demo `config/c22h4-demo.json`, contract1af968e9ac6a26ea. Existing
  `baseline_config()` adds explicit buy_ema50; all other behavior must equal
  active contract exactly. This changes normalized hash to b86cfc2df8bf297d,
  not behavior. Same frozen public `prepare` + `execute_cell` used for both.
- Tuned research `config/research-c22-qualified-b823f4aefe10fc72.json`.
  Changes only RSI14→7, BUY protectionoff→BE1R, SELL TP3ATR→2R,
  max_daily_losses1→0 (no count stop). Daily10% and initial cost-inclusive
 10% risk cap remain; fixed0.01,USD200,one position,no recovery.

Same immutable167622055 paired quote tape and48465 complete M15 bars in
`runs/c22-tuning-loop-2026-10-07/campaign-01/input/` for every cell.
Requested2024-09-01UTC→2026-10-06T17:22:04.296998UTC; actual first
2024-09-01T22:05:06.129UTC,last2026-10-05T23:59:59.969UTC. No new data download,
no opened holdout, reused discovery. Research source/input/config hashes frozen.

Exactly4 economic cells: both cases × Base+swap / COST_SURCHARGE_STRESS+swap.
Base commission0,stress commission40USD/lot/roundtrip (USD0.40 at0.01), quoted
Bid/Ask unchanged,zero extra spread/slippage. Override old price-stress cost
metadata privately; do not compare mixed stress definitions. Mandatory modeled
points swaplong−567.4/short0,point0.001,Wednesday triple,UTC-midnight assumed
rollover. Validate complete supported metadata first; missing blocks. Archived
cost assumptions not broker-history verified: COST_INCONCLUSIVE.

Reuse canonical `execute_cell` unchanged. Canonical tick stop/TP and bar-based
fee-inclusive BE, commission fully upfront, strict open-position midnight
baseline; no native economic or live process-baseline parity. Old shared-native
geometry results may differ slightly due price-grid rounding; do not compare them
as identical execution. Both current cells share exactly same engine/geometry.

Monthly upfrontfee books entry month,gross+swap exit month; completed net-positive
positions counted by entry month.24 full requested+observed-bracketed months,
Oct2024–Sep2026. Partial/unobserved labels retained; warmup/zero full months kept.
Report monthly entries AND winners,median cash,positive months,net,DD,swap.
Endpoint bracketing does not prove internal data coverage.

Preregister MODELED_IMPROVEMENT only if both views net improves and remains
positive,mean winning entries AND entries/month improve,median monthly cash and
positive-month ratio not lower,DD<=40%,no bankruptcy,cost-inclusive admittedcap
<=10%. Report DD delta even if gate passes: more profit does not mean lower risk.
No automatic live/readiness qualification. Explicitly disclose one-loss-per-day
count removal; never change active Demo policy or sender.

All4 cells audited cash/lot/risk/nonoverlap/swap; all4 freshly repeated with whole-
result equality. Verify final persisted repeats and source/artifact hashes.
Fresh output only; preserve failures,never resume unverified partial checkpoint.
Raw run outputs in ignored `runs/c22-demo-vs-tuned-2026-10-15/`; synthesized
report under `docs/reviews/`. Runtime/broker/attestation untouched.
