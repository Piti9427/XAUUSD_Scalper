# Shared MQL5 detector economic verdict — 2026-10-15

**Best measured diagnostic case: C22 tuned. Verdict: NO_IMPROVEMENT.** No new
case meets all preregistered profitability/frequency/risk gates in both views.
This is shared native detector + modeled canonical tick execution, **not a native
MT5 Strategy Tester economic run**. Current Demo remains frozen variant
`1af968e9ac6a26ea`; tested `c22_tuned` corresponds to research comparator
`b823f4aefe10fc72`, not an approved Demo replacement.

From USD200, C22 tuned finishes **USD941.13 base+swap / USD803.60 cost-stress+swap**.
Net **USD741.13 / USD603.60**, maximum quoted-tick equity DD **29.63% / 36.96%**.
404/402 trades over entire requested window; 16.79/16.71 entries and
5.75/5.83 profitable completed entries per full month. Median monthly cash net
USD16.37/21.95; profitable full months17/24 and16/24. Swap−USD55.6052 each.
Stress median exceeding base follows changed fee/risk admissions and equity
path; it does not imply fees improve strategy quality.

Session07:00/13:00 UTC raises profitable entries to6.21/6.54 per full month;
netUSD214.97/74.85, but stressDD57.99% exceeds40% gate, monthly median/positive
ratio and net are lower than comparator. Pullback increases base frequency but
stress losesUSD180.47 with90.69%DD. More orders did not produce a safer improvement.

## All preregistered results

Cash and median units USD; monthly denominators24 full requested AND observed-
bracketed months (Oct2024–Sep2026). Winners are net-positive completed positions
attributed to entry month, not guaranteed signals or calendar-month exit counts.

| Case | View | Net | Max DD | Entries/month | Winners/month | Median month net | Positive months |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| pullback | base-swap | 79.40 | 49.85% | 27.54 | 7.92 | -1.17 | 12/24 |
| pullback | cost-stress-swap | -180.47 | 90.69% | 12.79 | 3.62 | -1.82 | 2/24 |
| session_0600_1200 | base-swap | -167.87 | 88.36% | 18.83 | 4.79 | -9.88 | 9/24 |
| session_0600_1200 | cost-stress-swap | -183.74 | 92.72% | 10.12 | 2.58 | -0.96 | 6/24 |
| session_0700_1300 | base-swap | 214.97 | 33.46% | 19.38 | 6.21 | 5.02 | 12/24 |
| session_0700_1300 | cost-stress-swap | 74.85 | 57.99% | 19.50 | 6.54 | 4.30 | 13/24 |
| session_0800_1400 | base-swap | -73.41 | 56.94% | 18.42 | 5.58 | -5.10 | 11/24 |
| session_0800_1400 | cost-stress-swap | -178.48 | 91.32% | 13.17 | 4.00 | -5.46 | 7/24 |
| c22_tuned | base-swap | 741.13 | 29.63% | 16.79 | 5.75 | 16.37 | 17/24 |
| c22_tuned | cost-stress-swap | 603.60 | 36.96% | 16.71 | 5.83 | 21.95 | 16/24 |

## Evidence and execution scope

- [Frozen economic protocol](../../docs/specs/2026-10-14-native-frequency-economic-cases.md).
- All10 cells independently audited for cash, fixed0.01, nonoverlap, admitted
  cost-inclusive10% cap, swap attribution and recomputed monthly metrics.
- All10 freshly repeated complete results identical; all artifact hashes verified
  after completion. Incomplete runs cannot resume; use fresh directory.
- 167622055 immutable paired Exness quotes;739312 physical M1 aggregated by actual
  shared `FrequencyResearchCore.mqh`;48465 M15 bars/full historical C22 direction
  parity PASS (327BUY/329SELL). Detector parity is not native execution parity.
- Requested2024-09-01T00:00:00UTC→2026-10-06T17:22:04.296998UTC; actual first
  2024-09-01T22:05:06.129UTC, last2026-10-05T23:59:59.969UTC. Sep2024 andOct2026
  partial, explicitly labelled/excluded; warmup/zero full months included.
  Endpoint bracketing does not verify internal quote coverage.
- Base actual Bid/Ask, modeled commission0USD/lot/roundtrip; stress same Bid/Ask
  plus40USD/lot/roundtrip (=USD0.40 at0.01). Cash-cost stress only, not changing
  spread/slippage. Both views mandatory swap pointslong−567.4/short0,point0.001,
  Wednesday triple,UTC-midnight assumed rollover. Archived cost metadata remains
  **COST_INCONCLUSIVE**; no current broker-history attestation.
- Canonical fee fully upfront, fee-inclusive BE on completed M5/M15 management
  bars, strict open-position midnight baseline. Native EA uses raw-price BE every
  tick and first-tick baseline. No native execution/performance equivalence claim.
- Reused discovery window, no unopened holdout/current-market qualification.
  Initial cap does not reserve future swap/gap exposure. No sender/account/
  cost-attestation/approved Demo baseline change; no Demo or real-money promotion.

## Validation and requirement mapping

| Requirement | Evidence |
| --- | --- |
| “ทำเทสเคสที่ได้ผลลัพที่ดีที่สุดออกมา” | Five paired cases,10 cells+10 identical whole-result repeats; selection retains NO_IMPROVEMENT and diagnostic C22. `test_one_profitable_view_cannot_be_selected`, `test_every_repeat_must_match_before_selection`. |
| “เริ่ม shared MQL5 detector + tick replay ก่อน” | Actual shared core compiled C++17;48465-bar detector parity. `test_native_geometry_fee_stress_and_swap_flow_through_complete_replay` checks exact entry risk2.6,fee0.4,Wednesday swap−1.7022,net2.2978 plus actual replay→monthly reporting. |
| “ให้ test แบบรวม swap ทุกครั้ง” | `test_missing_swap_metadata_blocks_economic_replay`; both10 economic scenarios require archived swap metadata and all10 independent rollover audits. |
| Validation | `.venv/bin/python -m unittest tests.test_native_frequency_replay`:7 passed. `.venv/bin/python -m unittest discover -s tests`:Ran962,OK,skipped2,77.846s. Scoped Ruff PASS. Standards/Spec final review0/0. |

Integrated report bug `bankrupt` missing from canonical result caught by campaign02;
adapter now derives liquidation/equity evidence, frozen replay unchanged. Attempt01
caught only timestamp dtype comparison mismatch before economics. Attempts retained,
never treated as completed evidence. Campaign03 executed clean exit0, audited and
hash-verification command exit0. Whole suite skips are existing environment cases. Task-scoped diff check PASS;
repository-wide diff check fails preexisting generated Demo journal CRLF trailing
whitespace. Journal preserved; no unrelated cleanup. Git task commit pending
earlier authorization; no stage/commit/push performed.

## Artifacts and native follow-up

Machine artifacts are ignored `runs/native-frequency-economic-2026-10-14/campaign-03/`:
`protocol.json`, `detector-parity.json`, `prepared-verified.json`, `cells/`, `repeats/`,
`source_snapshot/`, `results.json`, `COMPLETE.json`. Additional independent audit
`../audit-final.json`; clean stdout `../campaign-03.log`.

Handoff `../handoff/` includes C22 tuned base/stress `.set` with archived modeled
rates and all attestations **false**. `FrequencyResearch-best-case-review.zip`
contains already-compiled EA/core/test harness, two review presets and this report.
Native build sources4/4 unchanged from previous isolated MetaEditor build
0errors/0warnings; native harness execution/economic Tester run NOT_RUN.
Native Tester must separately validate real ticks, USD200, fixed0.01, swap/calendar,
server UTC offset and actual commission0/40USD/lot/roundtrip before attestation.
Do not enable attestations from replay evidence alone. Current Demo unchanged.
