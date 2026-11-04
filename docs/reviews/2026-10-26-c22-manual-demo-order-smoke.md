# Owner-authorized MT5 Demo BUY/close smoke

Result: **PASS**. The owner explicitly chose BUY0.01lot with SL/TP and immediate
close after broker confirmation. A real broker Demo transaction was opened and
closed on the configured account from its existing Oracle VM/MT5 terminal.
This is an execution smoke test, separate from the Selected26b8 signal cohort;
it is not evidence of strategy profitability or automatic signal readiness.

## Confirmed broker transaction

- Symbol: XAUUSDm; BUY0.01lot.
- Demo account fingerprint: `c4020d69b754dfb5`; USD hedging identity verified.
- Opening position/order: `4928000578`; opening deal: `4344127524`.
- Opening fill:3994.964 at2026-10-26T02:13:26.383Z
  (26October2026 09:13:26.383 Asia/Bangkok).
- Broker-confirmed initial SL3993.167 and TP3998.568.
- Closing order: `4928000629`; closing deal: `4344127566`.
- Closing fill:3994.724 at2026-10-26T02:13:26.664Z.
- Both send responses retcode10009; one opening and one closing send only.
- Realized signed net:−$0.24. Commission0,swap0,fee0 in this closed ledger.
- Balance:$1,812.21→$1,811.97; full history41→43deals reconciles to balance.
- Post-test broker proof: positions0,orders0,closed signed volume0.
- Manual magic22261026; comment `MANUAL_SMOKE_1173559b4e`, distinct from
  Selected26b8's magic22261025 and C22_ opening ownership filter.

## Procedure and controls actually exercised

The existing sender's journal showed flat/no active intent/no safety halt/empty
outbox. Its entry review was held atomically, and a later completed cycle
confirmed admissions were blocked while flat. Only then was the execution
service stopped; the persistent terminal stayed active. A consistent financial
journal backup was retained. No daily/equity/financial-state reset occurred.

The Windows helper acquired the same journal/account SQLite writer guards,
verified the exact configured Demo identity, full cash/position history, current
cost policy, native daily10%/loss2 checks, fresh quote, fixed0.01 volume,
margin, stop/freeze geometry and broker order_check. It used synthetic smoke
geometry with an additional risk budget min($2,1%equity), preserving the10%
upper cap. These SL/TP levels are not the native ATR-based26b8 strategy levels.

Each intent was persisted before calling order_send. Opening confirmation used
both actual position and opening deal. The immediate close specified the actual
position ticket, so the SELL close did not create a separate hedge. Complete exit
ledger, zero live exposure/orders and balance delta were checked afterward.
No ambiguous request was resent. The actual successful path exercised neither
timeout/partial-fill recovery nor broker-side SL/TP triggering.

After an independent final SDK flat/history proof, the exact original entry
review was restored. Its hash and cost-policy hash were unchanged. Selected
execution and terminal services are active; legacy senders/shadows are inactive.
The existing daily baseline, strategy identity and account identity match the
pre-test backup. No native source/config/parameters or notification channel changed.

## Scope and remaining readiness

This proves a BUY0.01 with attached SL/TP can be opened and closed through the
actual VM→MT5→Demo-broker path. It does not prove26b8 detector/admission/BE behavior,
future fills, net profitability, swap parity or live-account readiness. Before
maintenance the automatic strategy reported macro_warmup_insufficient. Early
post-restart cycles can report quote_stale; these entry blockers must remain
visible and are not waived by this manual test. No fresh research result or
economic qualification is inferred.

Final runtime check at26October2026 09:16:10 Asia/Bangkok: execution and terminal
active,execute=true,flat,no active intent,no safety halt,critical=false; the latest
cycle is again BLOCKED/macro_warmup_insufficient with macro_ema=null. All18 bound
source hashes match the pre-test selected configuration. Automatic signal entry
still requires resolving that independent data/warmup blocker.

Evidence: [transaction and broker ledger](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-manual-demo-smoke-2026-10-26/broker-test/transaction.json),
[post-test flat proof](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-manual-demo-smoke-2026-10-26/broker-test/flat-proof.json),
[controller result](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-manual-demo-smoke-2026-10-26/control-result.json),
[restoration verification](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-manual-demo-smoke-2026-10-26/restoration-verification.json),
[final runtime](/Users/nopparuj/my-agents/XAUUSD_Scalper/runs/c22-manual-demo-smoke-2026-10-26/final-runtime.json).
The request/response and position-specific close follow the official
[MT5 order_send contract](https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py).
