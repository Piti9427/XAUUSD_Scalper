# Selected26b8 first native Demo entry

Status: NATIVE ENTRY VERIFIED; LIFECYCLE PARTIAL. At the bounded observation
ending29October2026 16:42:18UTC, a genuine native SELL had filled and initial
SL/TP were confirmed through broker position reconciliation. The owned position
remained MANAGING. No BE modification or completed net close was observed.
GitHub#25 stays open; original scope remains16closed/7open.

## Source and coverage

Read-only collection retained every journalID149901–153498:3,598 contiguous
records in one account/source/config cohort. Compressed original payload SHA256:
`4812bc13be0deb81762a50c37af493d83a07787e92638b918364aa57e322b3f8`.
The collector read the existing sender journal,unit properties and native logs;
SDKcalls0,VMwrites0,service mutations0,credential-file reads0. Original payloads
and independent recomputation are retained under
`runs/c22-postboot-native-followup-2026-10-29/`.

The90second window is16:15:00inclusive through16:16:30UTCexclusive. Selecting
CYCLE observations by `result.captured_utc` retains22cycles,IDs153035–153066.
Selecting all records by audit persistence time instead retains34rows and
includes overlapping prior-cycleID153032 while excludingID153066. Both original
records exist in the contiguous collection. The audit-time subset alone is not
the complete cycle-capture window.

## Causal entry path

| Stage | Actual evidence | Interpretation |
|---|---|---|
| Detection | SIGNAL153033,16:15:07.831815UTC; bar16:15,direction−1,raw_direction−1,macro_blocked=false | Genuine Selected26b8 SELL candidate |
| First attempts | CYCLE153035/153036:quote_changed_before_send | Refused before intent/send; bar remained available for timely retry |
| Durable intent | STATE153037 stores SENDING; STATE153038 consumes bar16:15 | Both persist before REQUEST153039 |
| Request | REQUEST153039 at16:15:20.498883UTC,fixed0.01SELL | One native request in the captured batch |
| Response | RESPONSE153040:retcode10009,matching request identity | Response retained; not the only fill proof |
| Reconciliation | LIFECYCLE153045 FILLED at16:15:20.640602UTC | Actual position/opening ledger and contract checks precede FILLED |
| Initial protection | FILLED SL4039.710/TP3982.396; CYCLE153046 protectionconfirmed | Broker position levels,not merely requested levels |
| Latest cycle | 16:42:11.123096UTC:MANAGING,one position,protectionconfirmed,critical=false | Owned management continues; no completed exit claim |

The signal and eventual send have different cycle correlation IDs. Causal
linkage uses exact bar,cohort,persisted intent/comment and matched request/
response; one correlation ID does not span all retries. Journal IDs order
persisted records; correlation IDs link their respective cycle evidence.

Recorded native thesis: prior48-bar breakout,EMA50,closed H4EMA200; SELL
SL2.5ATR,TP1.35R,BE1R. Signal close4015.373 is below prior low4015.584;
EMA50 is4029.790712 and closed-H4EMA is4176.299233. These are recorded detection
inputs,not an independent reassembly of original M1/tick history.

Requested entry4015.421; broker-confirmed fill4015.354. Broker position time is
16:15:20.530UTC. Recorded `signal_to_fill_ms=20530` measures bar close to fill,
not time from the later SIGNAL audit. Successful cycle records
downstream_admission=PASSED_THIS_CYCLE. Source tracing confirms risk,cost,margin,
timing and identity checks precede intent. Complete raw SDK inputs for a
separate numerical admission replay are not all retained; no independent
numerical replay of every admission check is claimed.

The intent records entry equity1811.97,whereas the historical research starts
at200. This actual entry is a lifecycle observation on the current Demo account,
not a matched-capital performance comparison. Fixed0.01does not remove the
equity dependence of the10%admission cap. Do not pool earlier account-wide deals,
manual activity or this already-observed entry into a newly declared unopened
profitability sample. Prospective evaluation criteria remain a separate#32gate.

## Refusal and management interpretation

Both quote refusals retain code,stage `admission.check`,source origin
`scripts/demo_runtime/admission.py:159`,correlation/evidence references and
NEXT_SENDER_CYCLE resume guidance. The recorded mechanism is the quote-change
guard; detailed underlying quote provenance is not fully present in those
failure payloads and root_cause_status remains UNKNOWN. Timely retry succeeded
without removing the guard,adding cooldown or forcing an order.

Transient UNKNOWN between response and reconciliation resolves to FILLED in
the same sequence. It is not an unresolved position at the latest checkpoint.
One pending notification event is separate from broker uncertainty and proves
neither external delivery nor receipt. External delivery remains OFF.

`be_activation_quote` stores an evaluated quote at a subsequent M15 boundary.
Source `scripts/demo_runtime/lifecycle.py` compares net modeled profit against
initial risk before enabling protection,then requires broker confirmation
before BE_MOVED. That quote field alone does not mean the BE trigger passed
or SL moved. No BE_MOVED exists in the captured journal; confirmed SL remains
4039.710 at the checkpoint.

## Remaining acceptance evidence

Keep#25 open for actual BE modification where triggered and complete owned
exit/deal-volume reconciliation with gross,commission,swap,fee and net. Missing
final costs and realized profit remain NOT_OBSERVED,not zero. No forced trade
or forced BE/exit may manufacture evidence. The earlier bounded broker export
predates this fill and cannot serve as this trade's completed cashflow ledger.

This entry does not establish AP causality or a confirmed repair(#13/#14),a
held-midnight baseline(#23),session-aware H4changes(#28),a frozen prospective
profitability protocol(#32),external delivery(#34) or future profit. Preserve
owned management while exposure exists. Source/artifact audit and independent
local recomputation passed. No runtime change,economic backtest,GitHub write,
commit or maintenance accompanied this review.
