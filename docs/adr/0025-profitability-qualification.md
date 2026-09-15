# ADR-0025: Pine Master Pro profitability qualification

Status: Accepted

Pine Master Pro uses `tradingview/xauusd_master_pro_strategy.pine` as canonical strategy and alert source. Manual order entry remains primary. `/api/v2/alerts` is notifier-only and accepts `SIMULATED_*` events; it has no broker execution adapter.

Historical candidates are SMC, TSS, GSS, and confluence of at least two engines in the same direction on the same confirmed M15 bar. Confluence geometry priority is SMC, TSS, then GSS. A candidate qualifies only with at least 100 trades, profit factor at least 1.50, positive expectancy, maximum drawdown at most 5%, positive lower 95% weekly-block bootstrap expectancy, and non-negative long, short, London, and New York slice expectancy. Twice-cost stress must retain positive expectancy and profit factor above 1.0.

Risk baseline is 0.5% of lower balance/equity. Two exits require broker-valid 0.01 + 0.01 lot. Sizing floors to the split increment; it never rounds up. Insufficient capital rejects the setup. Daily stop is two realized losing trades, cooldown is 30 minutes, and M15 positions flatten at 20:45 UTC before rollover.

Status ladder: `SOFTWARE_VERIFIED`, `HISTORICAL_QUALIFIED`, `FORWARD_VERIFIED`, `CAPITAL_VIABLE`, `REAL_MONEY_READY`. Failure states: `BLOCKED`, `INCONCLUSIVE`, `REWORK`, `NOT_VIABLE`. Real-money readiness additionally requires at least 12 weeks and 100 forward-demo trades, at least 90% execution fidelity, zero risk breach, and final Exness Standard cost calibration.

Current operational status: `INCONCLUSIVE`. Pine compilation, 24-month EXNESS:XAUUSD export, Trading Economics coverage artifact, Bar Magnifier rerun, and 12-week demo evidence remain required.
