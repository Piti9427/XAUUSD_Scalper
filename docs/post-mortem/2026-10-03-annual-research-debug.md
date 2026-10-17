# Annual research: coverage requirement and BE activation mismatch

Owner requested a superior BUY/SELL strategy over a real one-year archive. Prior parent-trend178 has a reproducible full/first pass but second-half fail, and only184 calendar days. That is an unmet performance/coverage requirement, not evidence that a profitable strategy necessarily exists or that replay arithmetic is defective.

## Reproduction and causal evidence

Fast artifact feedback: `PYTHONPATH=. .venv/bin/python docs/reviews/artifacts/2026-10-03-annual-feedback.py.txt coverage` fails `ONE_YEAR_COVERAGE_MISSING:184days`; `qualification` fails `SECOND_HALF_STRICT_QUALIFICATION_FAILED`. Actual qualification was inspected using Pdb before tuning. Candidate178 second-half DD41.28369/34.92871 exceeds30%, baseRR1.19769 below baseline1.20754. Both probes use hashed actual replay artifacts.

One-year coverage is a new owner requirement. Added `--require-calendar-year` at the existing public campaign CLI. Red: unknown argument; green after duration/month/actual counts checked before any output/scenario. A separate test locks ordered nonempty months, actual tick/bar counts, protocol freeze and rejection when requirement disappears on resume. Existing default behavior and comparator remain unchanged.

Data acquisition/import completed104,133,248 actual Bid/Ask ticks and23,230 complete UTCM15 across2025-10-01 through before2026-10-01. No synthetic prices, forward-filled M15, or opened Jul–Sep2025 sealed archives. Annual2026 overlap remains reused discovery, not independent validation. Dataset manifest includes monthly source ZIP/cache/tape/bars SHA256; builder and importer remain identical to recorded hashes after completion.

Independent ledger/quote arithmetic reproduces baseline/control final balances and all-tick DD in12 scenarios, plus BE/off symmetric configurations in18 scenarios. This falsifies the specific arithmetic-error explanation for those observations; it does not prove independent signal correctness, execution parity or future profitability.

## Actual config defect

Review found new annual catalog declared BE1R but omitted `protect_after_r`, inheriting0.5. Regression `test_annual_catalog_freezes_explicit_one_r_protection` failed `0.5 != 1.0`; fix explicitly passes1.0 for all36 frozen contracts. Same test passes. Initial research worker interrupted with exit130; ten completed trial results preserved as `SUPERSEDED_IMPLEMENTATION_MISMATCH`, excluded from valid results. Corrected campaign runs separate frozen output. No runtime/MT5 configuration changed.

Cause: relying on a dataclass default while documenting a different contract. Prevention: explicit safety/strategy-critical activation values in contract builders plus exact contract regression, alongside public replay behavior tests and review before accepting performance. A new architecture is unnecessary for this narrow defect.

## Undefined comparison and remaining goal

Annual trial30 full/first each executes7 SELL losses, win rate0 and realizedRR=None. Last losing entry2025-12-18; remaining591 full SELL detections fail fixed-lot risk cap. Full/first net-90.710 base/-91.817 stress; DD47.78508/48.23978. Independent second half starts$200 again and yields net507.245/452.366, DD25.98779/26.06630. These materially different capital/admission paths are preserved, never cherry-picked into a combined result.

`annual_rr` feedback isolates comparator: even a clearly labelled synthetic ideal metric probe is rejected against real baselineRR=None; changing only the baseline probe's RR to0 accepts it. Synthetic probe is a test of fail-closed semantics, never performance evidence. Owner clarification requested before any alternative baseline-RR definition; qualification code unchanged. Every valid annual candidate also exceeds30% full baseDD, so these measured candidates remain disqualified even under that hypothetical alternative.

Fixes resolve coverage/config defects; original superior-strategy goal remains unmet. No removed risk cap, forced Demo orders, date-dependent setting switching, relaxed gates, or fabricated winner. [Experiment ledger](../reviews/2026-10-03-annual-experiment-ledger.json) cross-references each probe/fix; measured report will record completed campaigns and exact-repeat proofs. Original performance feedback remains RED.

Owner subsequently approved all-lossRRreference0/candidateRR>1. Comparator now requires ledger-derivedloss count equalspositiveexecutedcount, WR0/netnegative; measuredRR staysNone. Regression reproduced missinglossmetadata thenpassedusingactualfixtureledger; empty/mixed/flat/winning/missingloss stillreject. Separate actual-ledger requalification of original192 remains0qualified. New frozen campaigns test additional hypotheses under explicitapprovedpolicy; noothergateschanged.


## Profile and async continuation

Completed14annualcatalogs648evaluations/0joint qualifiers,3,972originalfresh whole-result matches. Directional exits admit measured full/second passing candidates, but first-half trade-count/DD and second stress-profit gates remain red. Never combine partial strategies/windows or classify Python speed as profitability.

Actual annualcProfile/tracemalloc identified redundant104Mtick copies/whole-window validation plus23,230scalar searches. Publicallocationrepro peak25,045,773bytes on1Mticks fails; zero-spreadfloatingviews,100koverlappingvalidation and vectorizedUTCquoteindices preserve all quote/risk/held-position math. Initial4MiBbudget unnecessarily included unchanged held buffers (actualoptimized4,376,103bytes); final6MiBbudget remains red onoriginal25MB andgreenoptimized. Corruptedchunk-boundary timestamp/NaN/crossed quotes stillreject. Five alternatingpaired reps onthreeactualannualcases measure1.43–6.15xspeedup and complete resultmatches; tracedbasepeak2486→9–10MiB. Newoptimized24control repeats150scenarios andequals all150originalfine cases, adds0strategysettings.

Review found actualasyncstartup race: originalsupervisor onlywaitedprotocol, campaign publishesprotocol before snapshotcopies, verifierhashes snapshots immediately. Presentprotocol/absentsnapshot actualverifier reproduction exitsFileNotFoundError. Originalexecutedartifact/proofs preserved. Correctedv2 waitsallsourcehashes usingnonblockingto_thread checks/120sdeadline; missing/partialsnapshotselftest blocksuntilmatch. Timeout/errorpropagated, children terminated/waited/killedifneeded; actualoptimizedtwochildpipeline exit0/0. Prevention: readiness mustrepresentcompletefrozeninputs, notmereprotocolpresence.

Final validation776tests774pass/2skip14.667s, focusedallocation/admission/CLI tests, Ruff/mypy/whitespace pass. Standards0hard/0smells;Spec0remainingimplementationdefects afterracefix. [Final measured report](../reviews/2026-10-03-annual-tuning.md), [performance evidence](../reviews/2026-10-03-replay-performance.md), [experiment ledger](../reviews/2026-10-03-annual-experiment-ledger.json). Independent90rawquote arithmeticchecks verified, samefeed/spec limitations. Financial superiority remainsunmet; no Demo/runtime promotion or forcedorder. No retained debug instrumentation.
