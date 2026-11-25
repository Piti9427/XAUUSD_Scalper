# Issue #35 handoff

Continue from the registered range20 prospective run on the same Mac worktree. The [research map](map.md) tracks completed rounds. The [evidence audit](../../reviews/2026-11-22-issue35-evidence-audit.md) contains the two passing historical Exness windows at $200, the 2023 and 2019–22 checks, the annual walk-forward results and the ledger risk checks. Thai updates and the remaining checklist are in [Issue #35](https://github.com/Piti9427/XAUUSD_Scalper/issues/35).

The registered observation started on 23 November 2026 at 00:00 Asia/Bangkok. The earliest four-week boundary is 21 December 2026 at 00:00 Asia/Bangkok. Before proposing implementation, confirm actual quote coverage to the boundary, terminal net above native in both swap-inclusive cost views, and resolved evidence of the affected BUY behavior. Review [the BUY evidence decision](shadow-buy-evidence.md) and the paired decisions and closed outcomes. Use the same protocol if BUY evidence arrives after the minimum.

## Resume the shadow

Run from the repo root with the existing Mac research environment. Use the registered freeze and its pinned paths.

```sh
export PYTHONPATH=.:logs/trade-journal/shadow:logs/trade-journal/research
shadow_dir=runs/issue35-range20-prospective-2026-11-22
shasum -a 256 -c "$shadow_dir/provenance.sha256" &&
  /private/tmp/issue35-venv/bin/python "$shadow_dir/prospective.py" poll --refresh
```

Read `latest-poll.json` and the current capture under `polls/` for the quote cutoff, both portfolios and BUY evidence. The public archive responded with a new ETag on 23 November 2026 at 12:16 Bangkok time. Its post-start coverage awaits the refresh and overlap checks.

The freeze, runner, raw evidence and intermediate files are gitignored under `runs/` and `logs/trade-journal/`. The review and Wayfinder documents are local worktree files. An agent on another checkout needs these inputs, including the original paths the manifest pins. The GitHub issue carries the conclusions and checklist.

Research is Mac or research box only. Keep $200, 0.01 lot, the 10% swap-inclusive risk cap, daily stop and cooldown. Keep the registered source and methodology intact. Demo release, review and execution changes require owner approval. Report actual results in Thai on Issue #35.
