# C22 forward shadow: setup and first interim (2026-11-17)

This is research only. Nothing on the VM, config or runtime changes, and no money is involved: real money is PROHIBITED.
Code, input and reports live in `runs/c22-forward-shadow-2026-11/` (gitignored). The README there has the refresh runbook.

## Owner decisions (2026-11-17)
- **Data:** download public Exness monthly XAUUSDm tick zips every month into a new run dir.
- **Window:** starts 2026-10-24. The candidate and the vol floor were never run after that date. Native had been seen.
- **Swap:** VM owner-approved swap_long −490.0 POINTS is primary. Archived −567.4 is run as a sensitivity. swap_short is 0 (stored zero stays zero), and the triple charge falls on Wednesday→Thursday. Costs remain COST_INCONCLUSIVE.
- **Account:** one continuous $200 book per profile. Balance moves with P&L. Lot stays fixed at 0.01 and the 10% cost-inclusive cap is unchanged.
  The owner wants size to follow equity. Equity-based lot sizing is a contract change, and earlier research found it did not help, so it is not part of this shadow.

## Design (protocol v2 `b1769109…7a35`)
| Item | Rule |
| --- | --- |
| Profiles | native 26b8; candidate `sell3R_risk25.0_BE05_veto` (native book on the same tape and view drives the veto); floor03 = candidate plus reject when 2.5·ATR/close·100 < 0.3 |
| Views | {base, stress} × {vm490, arch567} |
| Input | Aug–Oct come from the old forward zips (hash-verified). Nov onward are fresh zips. The new input matches the old input on [08-01, 11-10) for every bar and every tick |
| Maturity | window ≥ 28 days AND native ≥ 20 trades in vm490\|base. Earlier reports are INTERIM |
| Verdict per profile vs native (vm490 base and stress) | NOT_EXERCISED if the ledger is identical to native; else FORWARD_CONSISTENT iff net ≥ native AND maxDD ≤ native in both views; else FORWARD_INCONSISTENT |
| Floor vs candidate | Same rule, reported separately |
| Causality | Every run replays native, candidate and floor03 from truncated prefixes at Wednesday 12:00 and Saturday 00:00 cutoffs. Indicators are re-prepared from bars before the cutoff. Any mismatch → INVALID |
| Integrity | Every loaded engine module is pinned (transitive closure). Input artifacts are re-hashed. A previous build must be a byte prefix of the new one. Reports are never overwritten |

**v1 disclosure.** v1 (`173c07a8…`, kept in `v1/`) produced one INTERIM report. A 3-lens adversarial review with per-finding verification then confirmed six defects. All were fixed in v2 before any verdict, with profiles, account, views, maturity and thresholds unchanged:
- the vacuous-equality verdict;
- unpinned engine modules;
- no input re-hash;
- no protection against revised data;
- a hard-coded year;
- report overwrite.

The v1 `shadow.py` bytes were not kept; only their hash in `v1/protocol.json` was.

## First interim: 2026-10-24 → 2026-11-17 (24 days)
Report `reports/2026-11-17-892cce21e155.json`. Causality passed 12/12 cutoffs.

| Profile | vm490 base | vm490 stress | maxDD | Trades |
| --- | ---: | ---: | ---: | ---: |
| native | +27.68 | +27.58 | 28.6% | 8 |
| candidate | identical | identical | | |
| floor03 | identical | identical | | |

All 8 trades were SELL, and native recorded 39 risk_cap rejections. arch567 equals vm490 because no BUY was held overnight.

## Key structural finding
The candidate's rule changes only SELL trades with initial risk ≥ $25. The 10% cap admits such a trade only when balance ≥ $250, so a $200 book cannot exercise the candidate until it has grown more than 25%. Until then the candidate equals native, and the verdict would be NOT_EXERCISED.

In the same way, floor03 has not bound yet: every admitted trade had stop% ≥ 0.3.

The first meaningful candidate signal therefore needs native at $200 to compound to ≥ $250 first. The owner should expect a long wait or a NOT_EXERCISED outcome.

## v3 update (2026-11-17, owner request)
The cost renewal v4 showed that the broker swap_long is now −474.3. Protocol v3 (`15bda721…ac4d`) uses that value as the primary swap view, `br474`. vm490 and arch567 remain as non-decisive sensitivities; nothing else changed. v2 moved to `v2/`.

The 10-24→11-17 interim is unchanged: identical ledgers, 8 SELL trades, and swap_short 0. Verdict: INTERIM.
