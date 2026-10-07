# Drawdown admission research — frozen before trials

Research only; no runtime strategy adoption or Demo orders.

## Hypothesis

Reject fixed 0.01-lot entries when drawdown reduces available risk budget. Use immutable all-tick equity high-water mark: flat equity DD >=15% admits at most2.5% equity risk, DD >=10% at most5%, otherwise configured10%. Recovery below thresholds restores admission budget. Cost-inclusive risk, original margin checks, daily limit and UTC semantics retained. Stops and exits continue while entries are rejected. These thresholds do not guarantee DD <=20%; actual replay gate still applies.

336 contracts: core/D48 x off/sell/buy guard x ATR/boundary stop x daily5/20% x seven protection states (off at0.5R; BE/trail/runner at0.5/1R) x reset false/true. Disabled protection does not duplicate activation values. Original parent TP retained. No indicator-period tuning.

## Data and selection

First screen the previously researched184-day2026 Bid/Ask tape, common $200 core/D48 baselines. Full and both halves, base and stressed costs, must satisfy existing gates: profit and WR exceed both baselines, DD below both and <=20%, realized RR>=1 and improves comparator where defined, minimum trades, stress passes. Freeze first qualified discovery contract. No selecting from sealed historical holdout.

Public dataset discovery Sep2024-Jun2025 may be separately screened with same gates. Jul-Sep2025 archives remain sealed. Older historical holdout is not prospective validation; a pass cannot erase failed2026 evidence. Public indicative feed and assumed historical broker specifications do not establish target Demo parity or actual swap/commission.
