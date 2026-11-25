# C22 optimization: implementation continuation handoff

Recorded2026-11-13, Asia/Bangkok. Owner requested a record for later implementation
and optimization. This document preserves evidence and proposed next steps; it
is not new permission to change the VM, activate a strategy, commit or deploy.
No further economic run was started for this documentation task.

## Resume here

Read this handoff, then the [final research verdict](2026-11-13-c22-200-virtual-native-veto-verdict.md)
and [Wayfinder map](../wayfinder/c22-profit-preservation/map.md). Re-read current
repository instructions and inspect Git status before modifying anything.

The original offline comparison goal has passed. The next work is an explicit
implementation/forward-validation decision, rather than another parameter search
required to manufacture a pass. Do not treat the result as production readiness.

## Verified result and selected strategy

Selected research candidate: `sell3R_risk25.0_BE05_veto`.
Native reference: `26b8bcd69e043653` / Selected26b8.

- Both start $200. Fixed0.01 lot; actual-account cost-inclusive10% cap remains.
- Keep RSI7cross30 BUY, Donchian48 SELL, both M15 EMA50 filters, closed H4 EMA200,
  both SL2.5ATR, native BUY TP3R/BE1R, daily10%/two losing exits, cooldown2.
- SELL initial admitted SL risk >=$25: TP3R and bar-close BE0.5R. Otherwise retain
  native SELL TP1.35R/BE1R. This never forces a $25 risk trade on a $200 account;
  the existing10% admission check must first permit it.
- Additional veto: candidate attempts only at the exact current quote millisecond
  and direction admitted by a separate native virtual book. Candidate still
  passes its own risk, equity, daily, exposure and fill checks.
- Virtual equity is never candidate capital. Independent windows get separate
  $200 books; continuous mode starts each book once and carries all state.
- The selected filter is H4 EMA200. EMA100/H4-off and SL1.5/2ATR were explored;
  they are not part of the selected candidate.

| Comparison, modeled swap included | Native | Selected fixed candidate |
| --- | ---: | ---: |
| 2026 base net | $699.2058 | $754.8828 |
| 2026 base MaxDD | 52.8747% | 38.0066% |
| 2026 stress net | $24.9228 | $24.9228 |
| Continuous base final / minimum equity | $17.3010 / $16.9460 | $42.7190 / $42.3640 |
| Continuous base MaxDD | 94.3453% | 85.7200% |
| Continuous stress final / minimum equity | $16.5888 / $16.5888 | $42.0808 / $42.0808 |
| Continuous stress MaxDD | 94.4537% | 85.6823% |

**Continuous accounts still lose capital from $200.** This is a relative research
comparison pass, not proof of absolute profitability or suitable live risk.

All14 fixed cells satisfy net >= native and MaxDD <= native; strict net gains:
2020base+$25.418,2020stress+$25.492,2026base+$55.677. The seven independent
segments are2020,2021,2022,2023,2024a,2024b25,2026;2026 ends2026-10-24, not year-end.

Full eight-profile catalog remained in selection, including native-veto parity
control and the three prior ungated conditional exits. Training-only LOYO passes
the held-out policy gates. The2020 fold selects ungated25USD; other six folds
select veto25USD. Continuous validation uses the fixed selected profile, not an
annual switching policy inferred from LOYO.

## Why the veto matters

The earlier ungated25USD conditional exit retained +$25.418 on continuous base
but admitted extra losing trades totalling-$27.059 after its improved exit raised
equity. The veto removes that displacement failure. Selected continuous base
retains all204 native trades with no replacements; stress retains all178 with
no replacements. In2026base,172 retained trades contribute +$39.588 exit change;
10 removed native trades had combined net-$16.089; no replacement trades.

All112 non-native attribution comparisons reconcile. All veto-profile entries
are subsets of native admissions, with identical retained entry price, initial
SL, volume and nominal riskUSD. These are diagnostics, not future outcome labels
used by the gate.

## Availability metric: preserve this correction

Actual risk-cap rejects can become zero because virtual vetoes run first. This
must never be presented as restored availability. Continuous required virtual
risk-cap rejects remain2769base/2808stress.

For veto profiles, the effective observed cap-span proxy is
`max(actual raw span, required virtual native raw span)`. Preserve ordering in
each stream. Native-self comparison must equal the original native proxy; the
candidate metric cannot fall below its raw actual proxy. A discarded merge/sort
by timestamp/direction/reason inflated a native benchmark at equal timestamps;
its RED->GREEN regression is mandatory. Do not reintroduce that merge.

Effective spans remain1193.333328base /1123.999998stress days, equal to native.
They measure consecutive observed risk-cap rejections, not uninterrupted
wall-clock entry inability. Preserve separate actual, virtual and veto counts.

## Implementation state: research exists, runtime work does not

Research modules:

- [Replay adapter](../../scripts/research/c22_profit_preservation.py): frozen-native
  source anchors, optional exits/gates and true account carry.
- [Campaign/selection](../../scripts/research/c22_profit_preservation_campaign.py):
  source/input freezing, native pins, summaries and unchanged selection protocol.
- [Virtual admission](../../scripts/research/c22_virtual_admission.py): exact-time
  decision lookup and conservative availability summary. It is not a sender or
  a maintained live virtual account.
- [Replay tests](../../tests/research/test_c22_profit_preservation.py) and
  [virtual tests](../../tests/research/test_c22_virtual_admission.py).

The offline campaign precomputes native decisions from replay. It reads only
current-time admission timestamp/direction/reason in the gate. Future exits,
net profit, MFE/MAE and later swap outcomes are excluded. Synthetic future
perturbations and16 pinned-prefix validations passed. This supports the tested
prefixes; it is not universal proof for every future path.

**Do not wire an archived historical admission mask into the live bot.** Runtime
implementation needs an online native virtual book using only information
available at each decision, with separate persistent state and restart/reconcile
semantics. That implementation has not been built or deployed.

## Next implementation decisions and proposed work

1. Confirm owner scope for an opt-in research/shadow adapter and virtual-book
   persistence design. Research approval does not activate a Demo sender.
2. Define one source/config/cost-bound online native virtual book, separate from
   actual account equity, day-start equity, daily losses, cooldown, position,
   fees/swap and journal. Never reset either book to avoid losses or improve cap
   admission. Use aware UTC and complete-bar/native timing.
3. Generate native virtual admission at the current quote before the candidate
   attempts entry. Both accounts retain their own financial checks. Define
   fail-closed handling for missing/stale/unknown virtual state; existing actual
   active/UNKNOWN position protection must continue even when entries block.
4. Reproduce the frozen candidate before optimizing further. Check signals,
   admissions, fills, SL/TP/BE timing, costs/swap, ledger and final balance, state
   carry, exact quote timing, and separate availability attribution. Retain the
   native-exit veto parity control and the equal-timestamp metric regression.
5. Collect fresh unseen forward shadow. Historical data were already viewed;
   repeated tuning and LOYO do not replace it. Review execution/cost parity and
   operational burden before any owner adoption/cutover decision.
6. If further optimization is explicitly requested, freeze a new catalog,
   selection rules, costs and hashes before economics. Keep every candidate for
   training-only LOYO, native fallback and all current non-regression gates.
   Diagnose a failure before deriving an iteration; do not cherry-pick held-out
   winners, raise capital/cap, alter lot or reset a continuous book.

Keep selected Demo service/account single-sender. No VM login, deployment,
forced order, service restart, auto-renew or real-money action is authorized by
this handoff. Re-read current active runbook before any later operations.

## Cost and VM comparison limits

All economics use base+swap/stress+swap. Archived assumptions: long-567.4POINTS,
short0, point0.001, declared UTC rollover/triple calendar; commission0. Historical
broker entitlement/rates/fills remain unverified: **COST_INCONCLUSIVE**. Missing
or unsupported swap metadata must block a new run, never become zero.

Prefix cash reconciliation was verified for the pinned zero-commission views;
nonzero commission with open exposure needs reserved-entry-fee accounting.

The latest available local contract/VM evidence identifies native26b8 as the
running strategy. The comparison above is matched $200 replay, not measured
current VM P&L or a fresh VM inspection. Approximate historical Demo balance$313
is diagnostic only. Downtime/reconnect/cost-policy blocks are not equivalent to
strategy loss and are not modeled as a current VM performance guarantee.

## Evidence and reproducibility

Campaign root: `runs/c22-profit-preservation-200-2026-11-12/`.

- `virtual-native-admission/`: economic protocol/result, full cells, native books,
  carry checkpoints, source snapshots and attribution.
- Economic protocol SHA256:
  `bf52b24042cff762e6de712b4f052c4283b461b541c79d1c6820d2b5aa2ebb90`.
- `virtual-native-prefix-validation/`:16 pinned-prefix checks and frozen inputs.
- Prefix protocol SHA256:
  `18f653d1be170729d2b94c9f5ebdc063d8cf1cfd43ab93f89c7a0673a6a1f2bf`.
- Driver: `run_virtual_native.py`; prefix driver: `verify_virtual_prefixes.py`.
  Their existing output directories are immutable. For a new run, preserve the
  originals, choose new output paths and freeze a new protocol first; do not
  invoke these fixed-output drivers expecting an overwrite/resume.
- `handoff-2026-11-13/manifest.json`: source/result/protocol hashes, original
  owner-diff hashes, branch/HEAD and canonical input paths.
- [Continued search ledger](2026-11-12-c22-200-continued-tuning.md) retains failed
  catalogs and the earlier continuous veto. [Scope proposal](2026-11-13-c22-shadow-admission-proposal.md)
  records the separate owner approval for stateful virtual-admission research.

**`runs/` is ignored by Git.** A source commit will not back up the machine
results or historical input data. Preserve them before cleaning the repository
or removing the referenced historical worktree. In particular the2023/2024a
input is under `.claude/worktrees/github-issues-review-69212b/runs/.../holdout/input`;
the economic protocol and handoff manifest contain exact paths/hashes.

## Verification already completed

- Full serial suite:1683tests OK, skipped2,285.373seconds.
- Mypy:3 research modules passed.
- Native parity14 independent; native-exit veto ledger/DD/final parity14+2.
- All112 attribution equations and veto-ledger native subsets verified.
- 16 pinned real-data prefix checks passed; both peer review axes have no remaining
  blocking finding after the metric correction.

Useful checks after later code changes (not rerun by this documentation task):

```bash
.venv/bin/python -m unittest tests.research.test_c22_profit_preservation tests.research.test_c22_virtual_admission
.venv/bin/mypy --check-untyped-defs --follow-imports=silent --ignore-missing-imports scripts/research/c22_profit_preservation.py scripts/research/c22_profit_preservation_campaign.py scripts/research/c22_virtual_admission.py
.venv/bin/python -m unittest discover -s tests
```

## Working tree and approval boundary

Repository: `/Users/nopparuj/my-agents/XAUUSD_Scalper`.
Branch: `feature/smc-v2-hardening`.
Review base/HEAD: `1ef17597ecb9d841575f43e974acfc1db1cdd8be`.

Work is uncommitted; some earlier research versions are staged while later
changes/new files are unstaged. Inspect staged and working-tree diffs separately.
Do not commit the current index blindly. Automatic approval review previously
rejected commit because explicit owner commit approval was absent.

Pre-existing owner changes must remain separate: `AGENTS.md`, selected Demo
config, `scripts/c22_selected/{__main__,strategy}.py`, demo runtime admission,
costs and journal, `tests/demo/test_c22_cost_diagnostics.py`, availability-related
untracked docs/tests and `docs/superpowers/`. CORE_STRATEGY contains an owner
availability append followed by this task's research addendum; stage only the
research changes when a commit is explicitly approved. No stash/reset/clean or
blind whole-file CORE staging. Handoff manifest retains baseline diff hashes;
ephemeral original snapshots may still exist at `/private/tmp/c22-preservation-initial-diff`
and `/private/tmp/c22-preservation-initial-status`, but do not rely on them alone.

Research scope approvals do not authorize commit/push/deploy. Wayfinder HITL
mechanism/adoption tickets remain open; test approval is not ticket resolution.
