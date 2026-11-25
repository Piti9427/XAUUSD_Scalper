# C22 cost renewal v5: preparation and runbook (2026-11-18)

Status: **uploaded to the VM on 2026-11-18 at 06:26Z (owner: "Upload เลย"). Nothing has been run yet.**
- **VM location:** `state/staging-renew-v5-20261118/`, containing `v5/`, `MANIFEST.sha256` and `expected-cohort.json`.
- **Contents check:** MANIFEST OK on the VM. The macOS `._*` files and the `__pycache__` were removed.
- **Script check:** `bash -n` passes, and `cohort.py` on the live 6d7b release equals the expected cohort.
- **G2 harvest on the VM:** CONFIRMED for −474.3.
- **Still missing:** `sources.json`, which needs a fresh source review on the renewal day.

Run it as: `cd ~/c22-demo/state/staging-renew-v5-20261118 && v5/go-renew-v5.sh renew 6d7b9c468a0947e2 expected-cohort.json <X> <owner-verbatim.txt>`

- Toolkit: `runs/c22-renewal-v5-2026-11-18/v5/`. Its manifest is `runs/c22-renewal-v5-2026-11-18/MANIFEST.sha256`.
- Dry-run inputs: `vm/` and `dry/`, both read-only copies.
- Current policy (v4): swap_long −474.3. It expires on **2026-11-24 at 11:19:13Z (18:19 ICT, a Tuesday)**.
- Live review: the 18 Nov code-only review on release 6d7b (`preparation/selected-code-release-20261118T012804Z`). It binds the v4 policy; the canonical hash was verified.

## What changed vs v4
| Item | v4 | v5 |
|---|---|---|
| `PREVIOUS_CUTOFF` | 2026-11-12T08:14:35.278872Z | 2026-11-17T11:19:13.915187Z |
| `PREVIOUS_SWAP_LONG` | −644.8 | −474.3 |
| `PREVIOUSLY_AUDITED_NATIVE_IDS` | 6 ids | the 9 ids in the v4 provenance |
| kind | `…RENEWAL_V4_SAME_RELEASE` | `…RENEWAL_V5_SAME_RELEASE` |
| Toolkit path | hard-coded (caused attempt-1 failure) | derived from the script location; the Windows `Z:` path is derived too |
| Time guards | 23:50–00:10Z only | also 21:45–23:10Z (backup and daily break), and starts only 1–4 min after an M15 close |
| Swap guard | none | **G2** pre-flight (sender untouched) and post-probe (via restore) |
| Modes | renew | `renew` and `record-only` (stop, probe, restart on the unchanged review; this only records the day's swap) |

All other logic is byte-identical to v4. `diff` shows only the constants, the docstring and the kind text.

## Mac verification (2026-11-18)
- **Release copy:** 6d7b scripts and config match `release.sha256`.
- **Cohort:** `cohort.py` gives exactly `expected-cohort.json` (6d7b… / df6a71…).
- **Positive dry-run:** the 18 Nov probe (swap_long −474.5), now = probe + 60 s.
  - BUILT, audit `PASS_NATIVE_POSITIONS_AUDITED_UNDER_PREVIOUS_POLICY`, 10 native ids including 5067895413 (17 Nov).
  - `dryrun_check`, using the live `ExecutionReview`: **VALID review_valid CURRENT**, `EXECUTION_REVIEW_ACCEPTED`.
- **Negatives, all failing closed with no output written:**

  | Case | Fails with |
  |---|---|
  | Owner-approved value ≠ broker value | assert |
  | Broker evidence older than 5 min | `transition_fresh_broker_evidence_required` |
  | Previous review bytes wrong | `previous_review_bytes` |
  | A native position not acknowledged | `transition_native_positions_not_owner_acknowledged` |
  | Sources older than 24 h | `trial_cost_fresh_official_source_required` |

- **G2 gate**, on the real readings:

  | Candidate | Result |
  |---|---|
  | −474.3 / −474.5 | CONFIRMED (exit 0) |
  | −644.8 | HOLD `previous_day_disagrees` (exit 3) |

  Missing arguments exit 2. `test_swap_guard`: 6 tests OK.
- **Time-window table** tested at 2144 / 2145 / 2310 / 2311 / 0005 / 0011, and at minute%15 = 0 / 1 / 4 / 5.
- `bash -n go-renew-v5.sh`: OK.

**Not verified:** the script has not run on the VM, so the Wine/probe path and the systemd steps are exercised only by v4 history.

## Runbook (needs the owner at each step marked [OWNER])
1. **[OWNER] Approve the upload.** Copy `v5/` and `MANIFEST.sha256` to VM `state/staging-renew-<date>/`, plus `expected-cohort.json` (copied from `staging-deploy-20261118b`). This is a VM file write; nothing runs yet.
2. **Pick the day.** Monday 2026-11-23, a weekday that is flat with margin before the expiry.
   - The 23 Nov 09:00 ICT reminder already exists.
   - Avoid 21:45–23:10Z and 23:50–00:10Z.
   - Start 1–4 minutes after an M15 close.
3. **[OWNER] Source review.** Sign in to Exness in the browser pane. I review the 3 pages and write `state/staging-renew-<date>/sources.json`, which is valid for 24 h.
4. **Read today's swap.** Either:
   - run `MODE=record-only` ([OWNER] approve: about 2–3 min of sender downtime while flat), or
   - run `renew` with X = −474.3. If the broker differs, the script restores by itself and prints the new value.
5. **[OWNER] Approve the exact broker value verbatim.** I then run `renew` with that X.
   - G2 must be CONFIRMED. The 18 Nov reading (−474.5) is the previous-day support for any X within the band.
   - If G2 says HOLD, the policy is not renewed that day. Re-probe on the next trading day, still before expiry (Tue 24 Nov, before 11:19Z).
6. **Post-check.** The same checks as v4: active, NRestarts 0, kv review sha, VALID, release hash. The G1 notifier stays as installed.

**If G2 holds until expiry:** the bot blocks entries with `review_expired` (fail-closed, as D2 designed). That is a deliberate safety stop, not a crash. Ask the owner how to proceed. Never widen the band or bypass the guard.

## Not done
- Upload to the VM.
- `sources.json` for the renewal day.
- The owner's swap approval.
- Committing to the repo.

## Next after v5: G3 deploy (owner, 2026-11-21: "หลัง renewal v5")
- After v5 succeeds, deploy G3 (`docs/reviews/2026-11-18-c22-g3-side-aware-swap.md`, patch `runs/c22-g3-2026-11-18/g3.patch`) as a code-only release review through `go-deploy.sh`.
  - Base it on the live 6d7b tree, while flat and outside the windows.
  - It needs a separate owner approval at that step.
- The new release_hash should be `e09853cb…`. Recompute it on the VM build; do not trust the Mac value.
- v5 runs on the current 6d7b cohort, so its `expected-cohort.json` stays as uploaded.
