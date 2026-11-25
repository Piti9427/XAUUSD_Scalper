# C22 causal admission proposal: virtual native control

Status: owner approved research scope2026-11-13; implementation and comparison
completed. [Research verdict](2026-11-13-c22-200-virtual-native-veto-verdict.md) records RESEARCH_PASS, with
COST_INCONCLUSIVE and adoption/forward evidence still outstanding.
No runtime change, Demo activation or economic outcome claimed.

## Evidence and decision

The earlier conditional SELL3R/BE0.5R profile at initial risk >=$25 passed all
independent net/DD gates but failed continuous acceptance. Continuous base net
attribution: retained trades +$25.418, no removed native trades, replacement
trades -$27.059. A better March2020 exit raises equity and admits an August2020
loss that native rejected; another replacement loss follows later. This is an
admission-path failure, not evidence that every new signal is valuable.

Proposed decision: test a virtual-native admission veto alongside the existing
actual-account risk cap. The virtual book follows native26b8 from $200 with the
same costs, swap, signals, limits and state carry. A candidate may enter only at
a timestamp/direction where this native virtual book would admit; its own
position, equity, margin and cost-inclusive10% checks still apply. The veto can
remove an entry; it cannot force one, increase lot/cap or supply capital.

This adds a stateful entry rule beyond static RSI/Donchian/EMA tuning. It is a
material strategy decision and received explicit owner scope approval in chat. Implementation remains
offline research only.

## Prospective experiment

- Catalog: native; native exits plus veto parity control; conditional SELL3R /
  BE0.5R at original risk >=$25/$30/$40 with and without the veto (8profiles).
  No other new parameters.
- Native recipe remains H4 EMA200, RSI7/30, Donchian48, M15 EMA50 both sides.
- Native and candidate each start $200, fixed0.01, actual cap10%, daily10%/loss2,
  cooldown2, one position. Every economic cell uses base+swap or stress+swap.
- Every independent segment gets its own $200 virtual/control book. Continuous
  mode gets exactly one $200 virtual book and one $200 candidate book, carrying
  all state across all boundaries. No resets or deposits.
- Freeze catalog, protocol, selection and hashes before economics. Same all14
  net/DD gates, strict gain, full-catalog train-only LOYO/native fallback and
  selected-fixed continuous gates. No held-out pruning or ranking changes.

## Causality and accounting requirements

An offline implementation may precompute timestamped native admission decisions,
provided prefix-invariance tests prove these decisions depend only on data at or
before each timestamp. The candidate gate may read only admission timestamp and
direction. It must not inspect future exits, realized profit, MFE/MAE or later
swap. Precomputed outcomes must never become an outcome-based trade mask.

Required tests: changed future ticks/bars leave past native decisions and gate
behavior unchanged; native-exit veto control exactly reproduces native; candidate
still obeys actual risk cap; virtual and actual books keep separate equity and
state; independent versus continuous masks stay distinct; UTC timing, swap carry
and complete ledger-to-final-balance reconciliation remain intact.

Availability reporting separates actual-account risk-cap rejects, virtual-book
risk-cap rejects and other virtual vetoes. Vetoes must not hide rejected signals
and manufacture an improved risk-lock metric. For veto profiles, continuous
acceptance uses max(actual observed rejection-span proxy, required native virtual
book's same proxy), without reordering either stream. Native compared with itself
is exactly its original proxy. Since the candidate metric is at least its raw
actual proxy and the baseline stays unchanged, this cannot relax the original
duration gate. Raw actual/virtual counts remain separately visible. This remains
an observed-span proxy, not a claim of uninterrupted entry inability.

The catalog also retains the three original ungated conditional exits as controls
(native, native-veto parity control, three ungated and three veto profiles:8total).
Review caught and RED->GREEN fixed a same-timestamp ordering bug in a discarded
merged-stream metric before any economics. That merge is not used.

Attribution must separate retained/removed/replacement trades and direct exit
changes from the veto's admission effect. All history has been seen; even a
research pass requires new forward shadow before any adoption proposal. Broker
historical swap entitlement/rates remain COST_INCONCLUSIVE. Operational support
for a virtual book is a separate decision, not authorized by a research result.
