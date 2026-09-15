# ADR-0027: Adopt S1–S4 mechanical protected-swing CHoCH for foundation structure

Status: Accepted

## Context

Issue #1 (Gold Playbook Foundation) requires M5 CHoCH before entry and forbids treating latest-fractal MSS alone as CHoCH, but left HH/HL/LH/LL construction, protected-swing selection, and weak-first-break handling unsettled. Issue #3 published proposed v1 mechanical defaults for those rules as research definitions.

## Decision

Foundation BaselinePlay structure classification adopts `docs/specs/xauusd-s1-s4-mechanical-v1.md` §3.5 (and fractal availability §3.1) as rule version `s1-s4-mechanical-v1` for protected-swing BOS/CHoCH/internal/UNKNOWN semantics.

- Confirmed user intent from issue #1: CHoCH required; internal breaks ≠ CHoCH; UNKNOWN explicit.
- Numerical defaults (5-bar strict fractal, body/range ≥ 0.45 for qualification, bars 1–8 sweep→break window when used by detectors) are adopted from mechanical proposed defaults, not claimed as individually optimized by the user.
- Legacy MSS-only detection remains available for Legacy Reference / S1 control paths and must stay separately labeled.
- Other issue #1 unsettled gates (Fibonacci anchors, account cash-flow pause, statistical protocol, data provenance) stay open and are not decided here.

## Consequences

- Implement and test a pure structure classifier before changing live Demo admission defaults.
- Detectors that require foundation CHoCH must pass an explicit `require_choch=True` (or equivalent) flag; default Legacy path stays MSS-capable until a separate Demo cutover decision.
- Changing these structure rules requires a new rule_version, not silent edits.
