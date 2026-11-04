# Selected26b8 native Demo lifecycle — final retained-evidence audit

Status: **PASS for GitHub #25's observed native lifecycle acceptance.** One genuine native SELL now has retained causal signal/admission, broker fill, initial SL/TP, eligible broker-confirmed BE, completed owned deal ledger and reconciled actual costs/net. A sanitized closure comment is prepared locally; no GitHub comment or closure was performed by this audit.

This is one observed Demo lifecycle. It does not qualify future profitability, economic parity, AP repair, real-money readiness, Swap-Free entitlement or changed-cost acceptance.

## Evidence integrity and exact scope

The retained prior journal has5,041 contiguous IDs149901–154941. The new fixed-upper capture has48,900 contiguous IDs154942–203841 across15pages. Independent recomputation verifies every gzip/CRC, compressed SHA256, ordered raw-payload SHA256, cursor boundary and cohort. Together they retain53,941 consecutive numeric audit IDs with no missing interval. Numeric continuity does not mean every market tick or unpersisted process attempt was captured.

The separately approved one-shot exporter actually completed31October03:40:46UTC with SSH exit0. It ran the reviewed host script SHA256 `935ca5728c438414ee00560b571a459fc3257c7a3074282c19d8f2519ca21910`, requested one new immutable packet from the existing sender and restored the exact prior request bytes. The execution receipt and2,302-byte filtered gzip agree on CAPTURED and PRIOR_BYTES_RESTORED. One approved invocation/request identity is retained; no second request was issued by this audit.

The script's preflight matched the current remote unit and six exporter/runtime source hashes to the actual retained deployed-source manifest. Export metadata matches the journal's account/release/config cohort and original cost-policy binding. It reports connected Demo/hedging,flat/noorders and complete epoch history from the existing sender's normal reads. No second SDK reader,order,service change or policy renewal was used. Restoration is evidenced by the executed pinned script's conditional restore and exact-byte readback; this final audit did not make another remote read.

## Acceptance mapping

| #25 acceptance | Independently checked evidence | Result |
|---|---|---|
| Causal FULL signal,recorded90s cycles,fresh quote/risk/cost checks and exact cohort | SIGNAL153033 is the unmasked native SELL for29October16:15UTC. All22 persisted CYCLEs selected by `result.captured_utc` in `[16:15:00,16:16:30)` are retained; both quote-change refusals153035/153036 remain. SENDING153037 precedes matched REQUEST153039/RESPONSE153040 and FILLED153045. Successful cycle153046 records downstream admission PASSED_THIS_CYCLE and valid execution review. Deployed source gates and retained intent bind the same signal/bar/cohort. | PASS for recorded source-bound admission; no independent replay of every original SDK numeric input is claimed. |
| Broker-confirmed fill and observed SLTP/BE | The opening broker deal matches original fill identity/time,direction,magic and0.01volume. Initial broker-observed SL4039.710/TP3982.396 remain. Protection activation169430 and pending SL169431 precede SLTP REQUEST169432/RESPONSE169433,retcode10009; BE_MOVED169435 confirms actual SL4015.254 with unchanged TP at30October06:15:08.331286UTC. | PASS; evaluated quote/request acceptance alone was not counted as BE. |
| Actual gross/commission/swap/fee/net and closed owned ledger | The new exporter retains all two rows for the original position: native SELL opening0.01 and BUY exit0.01,unique tickets,same native magic,zero signed residual. Actual profit33.84,commission0,swap0,fee0,net33.84 independently match CLOSED169977. The owned state transitions toNone. | PASS. |
| Preserve rejection/UNKNOWN paths; keep unobserved phases open | Transient UNKNOWN states153041–153044 resolve to FILLED153045. Original quote refusals remain. All13 later FULL SELL90s windows retain470 blocked cycles:312 algo-permission,154 cost-spec and4 first-quote refusals. No later market-entry request exists in the fixed range. BE and close are now observed rather than inferred from tests or service health. | PASS; no forced order or missed-profit estimate. |
| Keep AP closure separate | This audit uses lifecycle and ledger facts only. Terminal flow roles,transport causality and a matched AP repair remain separate #13/#14 requirements. | PASS; no AP closure or repair claim. |

All stated #25 acceptance items are covered within this recorded-lifecycle scope. No uncovered acceptance blocker remains. Public closure still requires the owner's separate approval of the exact sanitized comment and action.

## Broker time and actual cashflow

The broker opening timestamp is29October16:15:20.530UTC. The broker exit timestamp is30October06:47:16.472UTC. The sender records CLOSED at06:47:20.531424UTC,4.059424seconds after the actual exit. The latter is reconciliation/persistence time and must not replace the broker exit time.

The two target deals independently sum to gross33.84,commission0,swap0,fee0 and net33.84; signed volume is0.00. Both target tickets are unique and absent from the earlier retained43-deal packet. Folding those43 historical rows plus the2 target rows yields45unique tickets and the same current epoch component totals: profit1847.43,swap−1.62,commission0,fee0. The resulting cash1845.81 matches exported balance and equity.

The old43-row-plus-new2 count/cashfold is an independent aggregate reconciliation. Approval intentionally transferred only target rows,metadata and epoch totals from the new packet. Its whole45-row raw source remains private on the VM; the full-packet SHA is reported by the approved script and cannot be recomputed from the filtered local gzip. This limitation does not prevent independent verification of every target-position row and its actual cashflow. It does prevent claiming byte-for-byte equality of every unrelated historical row in the new full packet.

The exporter omits deal price,order,comment and exit reason. Prior journal evidence supplies native entry/position lineage and observed protection; this report makes no TP-reason attribution. The original BE `order_calc_profit` scalar and every original admission SDK numeric input were not separately exported; observed activation,matched request and confirmed SL establish the actual BE event without inventing those values.

## Remaining operational and financial limits

Positive lifecycle evidence does not erase adverse observations: the retained stream includes quote-stale/unknown protection observations,algo-permission refusals,exact cost-spec drift and runtime SQLite failures. The fresh exporter reports swap_long−474.7 at31October03:40:46UTC while the original policy remains bound to its reviewed terms. This observation is not cost acceptance or renewal. Actual swap0 on this SELL is a deal fact,not proof of Swap-Free entitlement; entitlement remains UNKNOWN.

No strategy,lot,risk calculation,financial journal,permission flag or policy was changed by this audit. It performed only local retained-file reads,deterministic reconciliation and report/draft writes. It did not contact the VM,SDK or broker,publish a message,commit or close an issue.

## Reproducibility and retained hashes

Machine evidence and verifier:
`runs/c22-native-lifecycle-followup-2026-10-30/capture-2026-10-31/lifecycle-final-audit/`.
Run `python3 .../lifecycle-final-audit/verify_final_lifecycle.py` from the repository root for the retained-file assertions. Actual run exits0; scoped Ruff passes. These are evidence checks,not a new economic backtest.

| Retained artifact | SHA256 |
|---|---|
| Prior5,041-row journal gzip | `cc8395582838597ebd208914f66507f3002ff6318c6e1c8681bd2b497eeaae9a` |
| Complete15-page verification manifest | `b21f3b8acde1c71b11a74ba2619f159b760afc662cab037182b5992346d33e4f` |
| Actual export execution receipt | `3bf578d5aa94f534f3c35ff100c7b657deea0051c7424b280e97103177076df4` |
| Actual filtered export gzip | `7218639839566b04a898834f6717fa94643392bead9be13cb70483930e516d69` |
| Original whole packet,reported by approved script; stays on VM | `f22371d04982085ce35c54bfcfd61d16ec7005df15a4745cc48fa5070bea6940` |
| Historical43-deal packet used for aggregate cashfold | `bfab409adbe6fdbe4aab245145b53b4f276ce72d66b163a54dd7b4edb7578711` |

Raw private account/position identifiers,host details and unrelated financial rows are excluded from this human report and the public closure draft. Machine evidence preserves the exact private bindings for local review.
