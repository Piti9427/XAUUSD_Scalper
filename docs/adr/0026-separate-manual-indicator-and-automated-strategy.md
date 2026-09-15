# ADR-0026: Separate manual Indicator from automated Strategy

Status: Accepted

Manual trading and automated trading use separate Pine artifacts with explicit ownership. `xauusd_master_pro_v6.pine` owns WATCH and READY Setup Signals for Trader review; `xauusd_master_pro_strategy.pine` is reserved for future bot-driven trading and does not emit duplicate Manual Signals. This supersedes only ADR-0025's single-artifact alert ownership because mixing discretionary guidance with automated execution made user intent and execution status ambiguous. Both artifacts must share a versioned detection and parameter contract, with parity evidence required before automated trading is enabled.
