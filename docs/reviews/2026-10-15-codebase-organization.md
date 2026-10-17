# Codebase organization — 2026-10-15

Completed folder organization using existing module interfaces. Active Demo,
frozen research/native paths, strategy parameters/risk math and sender behavior
remain unchanged. No new pass-through modules or compatibility test duplicates.

## Changes

-130 existing Python test modules grouped into7 packages:application22,demo9,
 native2,pure_b1 12,research30,smc48,webhook7. Sharedfixtures remain centralized.
- Five historical reproducers moved `docs/reviews`→`scripts/debug/reviews`.
- Nine already-versioned JSON/text evidence files moved byte-for-byte to
 `data/research_output/review-fixtures`;SHA256all9unchanged. Explicitfilename
 allowlist preserves their versionability;newdumpfiles andallruns remainignored.
- `docs/reviews` now Markdown only. Human report links and current indexes updated;
 old broken archive links in touched reports corrected to existing archive files.
- Testreference strings updated in read-only scenario inventory andGitHubunblock
 checklist. CLI/scenarioIDs/schema/businesslogic unchanged.
- `make native-frequency-check` now imports `tests.native.test_native_frequency`.
 Existing `make bot-*` and `unittest discover -s tests` interfaces retained.
- Added folder guides in `scripts`,ops,research,config,tests,architecture and
 archivedfixtures;[module/folder map](../architecture/codebase-layout.md).

## Verification

- Final `.venv/bin/python -m unittest discover -s tests`:Ran962in78.870s,
 OK,skipped2,exit0. Same962discovered;no assertions removed or testcount reduction.
- `make native-frequency-check`:2testsPASS,including24sharednativecorecases;
 no Wine/nativeTester/brokerexecution invoked.
- Ruffchecktests/moveddebugscripts/scenarioinventoryPASS;compileallPASS.
- ASTaudit:all962existingtestmethodbodies preserved across130modules after
 normalizing imports/repositorypaths andequivalentfixtureNOWlookup. No assertions
 weakened. Mechanicalwhole-moduleASTproof initially130/130 beforefixtureisolation.
- Source/config/nativeinventory278entries verified:unchangedbytes except one
 read-onlyscenarioinventory's testpathstrings;inverse-substitution exactlyrecovers
 original. GitHubunblockscript also testpathstringonly. ActiveDemo frozenpins9/9PASS.
- Archive9/9hashesPASS;allnew/updated128localMarkdownlinksPASS;outputignorechecks
 confirm arbitrarynewruns/JSON remainignored. Dry-run botrecipes only,no botstart.

Initialfullrun exposed3errors after new discovery order:two old dynamic
`__import__('test_trial30_demo')` references,andimport-timefakeMetaTrader5 leaked
via`sys.modules.setdefault`. ScopedreproconfirmedWebhookpassesalone butfailsafter
connectorfixtureimport. Fixes only in tests:explicitNOWfixtureimport,andper-test
connectorbackendpatchwithcleanupinstead ofglobalmoduleinjection. Focused8tests
pass;final962suitepasses. Production modules not changed to accommodate fixtures.

## Historical diagnostics limitation

MasterPro7counterexamples and archivedplanchecksPASS;comparisonCLI--helpPASS,
no historicalno-swap economic rerun. Accounting/expansion reproducers remain
historicallystale:emptycurrentfixturetradeframe(IndexError),oldrevisionrejects
currentrequire_chochkeyword(TypeError). Bothsamefailures reproduced withpre-move
source andequivalentpathresolution. Markedhistorical/notcurrentacceptance in
reproducerREADME;no strategy/default changes toforceoldchecks to pass.

## Evidence and scope

Ignored `runs/codebase-organization-2026-10-15/` retains beforecopies,currentpathmap,
protectedhashes,ASTmethodproof,red/greenfixturelogs,fullsuite/native/lint/compile/link
checks andhistoricaldiagnosticbaselinefailures. This layout migration did not
change economics,rerun strategyoptimization,renewattestation,start/restart Demo,
connectbroker,sendorders/notifications,stage/commit/push or alter frozen sourcepins.
Priorowner/runtime/research edits preserved;only intendedfilelocation/import/path
changes plusnecessarytestfixtureisolation added. Historicalsource/run snapshots
keep their original paths andbytes.
