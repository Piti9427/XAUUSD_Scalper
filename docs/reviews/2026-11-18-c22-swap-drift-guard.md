# C22 swap-drift guard: design (2026-11-18)

Status:
- **G1 is deployed**, 2026-11-18 06:09Z, owner-approved ("Deploy G1").
  - `/usr/local/bin/c22-trade-notify` sha256 is now `bc813a24…`.
  - Backup: `/usr/local/bin/c22-trade-notify.bak-g1-20261118T060907Z` (`d87f11aa…`).
  - On the VM, `--self-test-windows` reported 0 failures.
  - After the restart: active, NRestarts 0, 0 errors over 2 minutes, and a heartbeat was posted with status 200.
  - The bot was not touched: execution active, NRestarts 0.
  - Rollback: `sudo install -o root -g root -m 755 /usr/local/bin/c22-trade-notify.bak-g1-20261118T060907Z /usr/local/bin/c22-trade-notify && sudo systemctl restart c22-trade-notify`.
- **G2 is tested on the Mac only.** It is not wired into the renewal yet.
- **G3 is not built.**
Files: `runs/c22-swap-guard-2026-11-18/`

## Problem (verified)
- Renewal v3 (2026-11-12) pinned the policy at `swap_long = -644.8`.
  - Two probes read that value, at 07:13Z and 08:14Z (one hour apart, same day).
- Broker readings on other days were all around -470 to -490:

  | Date | Reading | Source |
  |---|---|---|
  | 10-30 | -488.0 | gate |
  | 11-03 | -481.0 | gate |
  | 11-13 | -475.0 | gate |
  | 11-16 | -471.7 | gate |
  | 11-17 | -474.3 | probe |
  | 11-18 | -474.5 | probe |

  Harvested read-only into `readings-20261118.json`.
- The live gate (`costs.swap_within_band`, adverse 10 / favourable 25, cap 10%) blocked two SELL signals with `cost_spec_mismatch`:
  - 2026-11-13 13:30Z;
  - 2026-11-16 06:00Z.
- Shadow outcome of the missed signals:
  - 11-13: SL after 20 s, -14.14.
  - 11-16: outside the shadow data, so unknown.
- **No alert was sent.** Each block lasted about 80 s before turning into `entry_window_expired`. That is under `BLOCK_DEFAULT_SEC = 600` in `c22-trade-notify`.
- Base notifier replayed on the real journal: `BLOCKTEST_FIRES=0`.

## Why "probe twice" is not enough
- -644.8 looked stable for an hour. Two same-day probes both agreed with it.
- A **previous trading day** reading would have disagreed: -481.0 on 11-03.
- So the guard has to work across days.

## G1: alert at signal time (detection), highest value
**What changes:** `c22-trade-notify.g1`, sha256 `bc813a24…`, built from the deployed `d87f11aa…`.
- `IMMEDIATE_BLOCK_REASONS = {"cost_policy_invalid_or_stale"}` sets `block_delay_seconds` to 0.
- The alert detail now includes `failure.details`: code, field, expected and observed.
  - These are spec numbers only. There are no secrets in them.
- Everything else is unchanged: dedupe, the 30-min rate limit, redirect/https hardening and all other windows.

**Tests:**

| Test | Result |
|---|---|
| `--self-test-windows`: 12 cases, including the new "cost gate 80s immediate" case | PASS |
| `--self-test-blocked` on the real journal, 11-13 | base 0 fires → g1 PROBLEM with `expected=-644.8 observed=-475.0` |
| `--self-test-blocked` on the real journal, 11-16 | base 0 fires → g1 PROBLEM with `observed=-471.7` |

**Known wart:** a RECOVERED message follows about 80 s later, when the reason changes to `entry_window_expired`.
- The mismatch itself persists until a renewal.
- The PROBLEM text says so ("needs fresh cost review").

**Deploy:** install over `/usr/local/bin/c22-trade-notify` and restart. This is the same procedure as A6, with backup and rollback. It is a VM change and needs approval.

## G2: cross-day consensus at renewal (prevention)
**Files:** `swap_guard.py`, `harvest_readings.py`, `test_swap_guard.py` (6 tests pass).

**Readings:** collected read-only, with no SQLite lock.
- Probe `broker-evidence.json` files.
- `journalctl` `cost_spec_mismatch` observed values.
- Policies are not readings, because they hold approved values, not observations.

**Rule:** a candidate X is CONFIRMED only when both of these hold.
- Readings the live gate would accept under a policy of X come from ≥2 distinct UTC days.
- The newest reading from a day other than the newest day is accepted.

Otherwise the verdict is **HOLD**.

**Band function:** copied verbatim from release 6d7b `costs.py`. Diffed body-identical on 2026-11-18.

**Replays:**

| Case | Verdict |
|---|---|
| v3 at 11-12 08:14, X = -644.8 | HOLD, `previous_day_disagrees` (-481.0) |
| v4 at 11-17 11:19, X = -474.3 | CONFIRMED (supported on 11-13, 11-16 and 11-17) |
| The current policy today | CONFIRMED |

**Integration plan** for renewal v5 (derive from v4, with no change to the bot code):
1. **Pre-flight, sender still running:** harvest, then run `swap_guard.py` with X = the newest reading.
   - On HOLD, stop before the sender is touched. Probe again on another trading day.
2. **After the probe:** append the probe reading and re-run the guard.
   - On HOLD, restore through the existing `restore` path.
3. **Owner view:** show the owner the guard's history table together with the verbatim swap approval.
   - The guard never replaces the owner's approval.
   - The guard never widens the band.

**Timing:** start renewal prep ≥2 trading days before expiry.
- Next expiry is 2026-11-24 11:19Z, a Tuesday.
- Have a reading by Fri 11-20 or Mon 11-23, and renew on Mon 11-23 or Tue 11-24 before 18:19 ICT.

## G3: direction-aware spec check (root fix) — owner decision, not built
- A SELL holding pays `swap_short`, which is 0.0. Yet a `swap_long` mismatch blocks SELL entries, because the spec check covers the whole spec.
- Skipping `swap_long` drift for SELL admissions would have let both missed signals through.
- This change touches pinned runtime files (`admission.py` / `costs.py`).
  - It is a contract change.
  - It needs a new release, a review, and the owner's approval of the cost semantics.
  - Backtest impact is nil for SELL, because there is no swap on a short.
- Not recommended before G1 and G2 have run for one renewal cycle.
