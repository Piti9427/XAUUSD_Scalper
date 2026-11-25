---
id: c22-native-robustness-shadow-buy-evidence
title: Require BUY shadow evidence for BUY changes
labels: ["wayfinder:grilling"]
parent: c22-native-robustness
status: closed
assignee: null
blocked_by: []
created: 2026-11-21
---

## Question

If a candidate changes native BUY behavior, can a four-week shadow window with only SELLs support a Demo change?

## Resolution comment — 2026-11-21

The owner chose to wait for BUY shadow evidence before making a Demo proposal. A candidate that changes BUY rules stays in shadow after the four-week minimum if the affected BUY behavior has yet to be observed.

Compare candidate and native BUY decisions prospectively on the same feed and account assumptions. For an entry change, record the matched signal, the corresponding admissions or skips, and the resulting outcomes. For an exit change, record a BUY position that exercises the changed management rule and its closing outcome. Retain the original historical qualification and paired shadow requirements.

Review the closed outcomes and the reason behind each decision difference using the [paired BUY audit](../../reviews/2026-11-22-issue35-shadow-buy-evidence-audit.md). A settled outcome can follow a position or cash difference between the accounts. Check which BUY behavior the recorded decision and outcome establish before using the result in a Demo proposal.

The [synced shadow report](../../../logs/trade-journal/shadow/SHADOW_REPORT.md) showed only SELLs in the first window. It provides evidence for SELL behavior.
