# C22 forward shadow: F2+F3 live vs variants (offline, research only)

Protocol `c22-forward-shadow-f2-v1`, sha256 `b911ca7a50102a826cfc281834e555446d1c876f5fe9b4b4759efe4c5d474965` (frozen 2026-11-24).
Owner request 2026-11-24: "Set up shadow". No VM, no orders, no real money.

| profile | rules | role |
|---|---|---|
| `native` | 26b8 (`26b8bcd69e043653`), max 2 losses/day | rollback watch only |
| `live` | 26b8 + F2 (≥10 ATR from closed H4 EMA200, trade side) + F3 (max 1 loss/UTC day) | mirrors `selected-ff17a3a8c0890cb0` |
| `f2ml2` | 26b8 + F2, max 2 losses/day | arm |
| `tp20` | `live` + SELL TP 2.0R (BE stays 1R) | arm |

- Window starts **2026-11-25 00:00 UTC**. Books: $400 (primary) and $300, fixed 0.01, swap br474, base + stress.
- Verdict (per arm vs `live`) only when ≥90 days AND `live` ≥60 trades AND ≥40 SELL in b400|base. Earliest **2027-02-23**. Before that: INTERIM, descriptive only.
- CONSISTENT = arm net ≥ live AND maxDD ≤ live in both base and stress. It only gives the owner evidence for a new release. It never changes the bot.
- Each report also carries `rollback_watch` (live vs native: net, maxDD, worst month).

## Refresh (monthly)
1. Refresh the input of `../c22-forward-shadow-2026-11` per its README (move partial zip aside, `acquire`, `shadow.py build`). This shadow reads that input and re-hashes it.
2. `cd runs/c22-forward-shadow-f2-2026-11 && PYTHONPATH=/Users/nopparuj/my-agents/XAUUSD_Scalper ../../.venv/bin/python shadow_f2.py run`
   Writes `reports/<end>-<input sha12>.json`. Never overwrites.

Never edit `shadow_f2.py`, `protocol.json`, or the pinned engine and old-shadow files: `run()` asserts their hashes.

## Freeze-time checks (2026-11-24)
- F2 distance on this input vs 9 live trades (`docs/research/2026-11-24/data/04-f2f3-validate/live-crosscheck.csv`): within 0.04–0.19 ATR. Skip decisions are equal on all 9. Signals within about 0.2 ATR of 10 may differ from live.
- Causality dry-test on the seen window: 6 cutoffs, all profiles match.
- SEEN run `reports/seen-*` (2026-10-24..11-17, informational, not evidence): native +99.65 / live +155.27 / f2ml2 +141.12 / tp20 +31.70 (b400 base).
- The `run` at freeze returned NO_DATA, because the input ends 2026-11-16. That run confirmed the hash path works end to end.
- Gaps: the live balance was not read from the VM ($400 assumed). F2 is reimplemented from its spec, not the release source. The no-regression tolerance is still open.
