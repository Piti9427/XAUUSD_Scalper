# Trial30 no-order audit

Observed current blocker: quote_stale. Target Demo verified through read-only Wine probe2026-10-03T02:55:31Z; latest XAUUSDm tick2026-10-02T20:57:59.953Z, age21,451.348seconds. BrokerView requires age0..60seconds. Runner checks quote before bars/signal/risk/admission. Watcher heartbeat<1second andexecute=true observed; active=null, safety_halt=null, event journal empty. No runtime change or forced order performed. This establishes current quote admission failure; it does not establish every past cycle's reason or market session schedule.

Read-only MT5 history from2026-10-01T00:00Z: two XAUUSDm orders/two deals; zero trial30 comment-prefix and zero trial30 magic matches. These deals openedSELL Oct1 10:19:17.026Z and closed10:19:29.133Z, volume0.01, outside all four historical signal windows. They do not explain the Oct2 01:15 missed entry. Other orders are not evidence of trial30 execution. Captured closed-M1 input reconstructs174 complete M15 bars sinceOct1 and four SELL detections:

| Signal close UTC | ATR | Nominal fixed0.01 SL risk USD |
| --- | ---: | ---: |
| Oct1 00:30 |4.300643 |10.751607 |
| Oct2 01:15 |6.902643 |17.256607 |
| Oct2 15:15 |18.069643 |45.174107 |
| Oct2 16:00 |18.976786 |47.441964 |

Nominal risk here is ATR*2.5*contract100*0.01; excludes rounding/slippage/fees and uses historical bar, not an actual broker order_check. Latest two already exceed10% of observed200.07USD equity (~20.007USD) before costs. This is a risk incompatibility illustration, not proof of historical rejection at unknown equity. Latest reconstructed bar20:30UTC hasdirection0. First detection predates original watcher launch; other missed opportunities need contemporaneous cycle traces. No catch-up order after90seconds is permitted.

Journal persists latest_result/last_bar and broker lifecycle events, not every guard rejection. Current history cannot prove why Oct2 01:15 did not execute. Foreground make-session trace for that interval is missing; no fabricated diagnosis. [Sanitized audit and raw/source hashes](2026-10-03-trial30-no-order-audit.json). Raw probe JSON remains local ignoreddata; exact executed read-only probe source preserved in docs/reviews/artifacts with SHA256. No credentials published. Python runner, quote freshness, risk cap and execution-alert alignment unchanged. Research profitability and runtime order eligibility are separate measurements.

Reproduce read-only capture through existing wrapper (Demo credentials loaded from ignored.env): `.venv/bin/python -m scripts.ops.run_b1_d_wine --script docs/reviews/artifacts/2026-10-03-trial30-no-order-probe.py.txt --output data/trial30_no_order_audit_fresh.json`. Probe history startsOct1; snapshot changes with current broker clock, so fresh audit is not expected byte-identical.
