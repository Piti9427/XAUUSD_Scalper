# C22 diversified continuation loop

Research-only continuation of the owner-approved C22 frequency campaign. Keep
its domains, adapter, accounting, qualification and winner ranking unchanged.
USD200 once, fixed0.01, single position, admission cap<=10%, no recovery.
Both base+swap and stress+swap remain mandatory. Net must exceed zero and match
or beat baseline, equity DD<=40%, mean>=15 entries/full UTC month, survival and
conservative terminal risk-cap gate must pass. COST_INCONCLUSIVE remains.

Diagnosis: original gate-count search ranked correctly but never expanded its
highest-frequency parent. Diversify exploration; do not claim an accounting bug.
Select one distinct, unexpanded parent per lane, in frequency/balanced/quality
order. Survival and risk-invariant passes take precedence in every lane.
Frequency maximizes minimum scenario monthly frequency, then minimizes worst DD,
maximizes worst net and breaks ties by ID. Balanced minimizes summed normalized
frequency/DD/net shortfalls against unchanged gates, then frequency/DD/net/ID.
Quality retains original search rank. Lane selection changes exploration only.

Seed each campaign from three distinct lane champions of completed prior results.
Replay seeds and baseline on that campaign's fresh input before ranking neighbors.
Freeze catalog before results, expand one-parameter neighbors in existing domain
order, deduplicate against all prior campaigns, search 300 new configs per campaign
or exhaust available neighbors. Complete whole campaign before selecting winner.
Run at most three campaigns, stop between campaigns if a qualifier exists.

Check latest archive and download current month separately for each campaign;
record requested end and actual last quote, never fill missing quotes. Clone
immutable historical tape with APFS copy-on-write when available; portable copy
fallback checks free space. Rebuild fresh partial-month tail, preserving source.
Freeze source/config/runtime/input/provenance and verify prior completion hashes.
Lock/checkpoint/resume and mismatch BLOCKED behavior remain mandatory.

Fresh replay baseline, top5 qualifiers and frequency/balanced diagnostic champions
in both views; require complete-result equality. Diagnostic champions are not
winners unless every original gate passes. Independently audit cash/risk/trades.
Machine artifacts under runs/, synthesized Markdown report under docs/reviews/.
Preserve Demo section6.33 and frozen evidence; no push/deploy/cutover.
